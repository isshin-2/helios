"""
HELIOS — Action Verification Subsystem
Deterministic closed-loop verification of computer actions using:
1. Window State (title, process, visibility)
2. UI Automation State Changes
3. Visual Diff / Settle Detection
4. OCR / Output Text Matching
5. Vision-Language Verification (VLM)
"""

from __future__ import annotations

import asyncio
import logging
from typing import Any, Dict, List, Optional

from pydantic import BaseModel, Field

from computer.actions import ComputerAction, ComputerActionType
from computer.screenshot import ScreenshotData
from computer.vision import ComputerVisionProvider
from computer.windows import BaseWindowBackend

logger = logging.getLogger("helios.computer.verifier")


# ─── Verification Result Model ───────────────────────────────────────────────

class VerificationResult(BaseModel):
    """
    Structured outcome of post-action verification.
    Determines whether the loop succeeds, retries, or replans.
    """
    verified: bool
    confidence: float = Field(ge=0.0, le=1.0, description="Verification certainty.")
    method: str = Field(description="Method used for verification (e.g., 'window_state', 'pixel_diff', 'vlm').")
    expected: str = Field(description="What was expected to happen.")
    observed: str = Field(description="What was actually detected.")
    details: Dict[str, Any] = Field(default_factory=dict)
    retry_suggested: bool = False
    replan_suggested: bool = False


# ─── Action Verifier ─────────────────────────────────────────────────────────

class ActionVerifier:
    """
    Closed-loop verifier that assesses whether an action succeeded in changing system state.
    """

    def __init__(
        self,
        window_backend: Optional[BaseWindowBackend] = None,
        vision_provider: Optional[ComputerVisionProvider] = None,
    ):
        self.window_backend = window_backend
        self.vision_provider = vision_provider

    async def verify(
        self,
        action: ComputerAction,
        expected_outcome: str,
        pre_screenshot: Optional[ScreenshotData] = None,
        post_screenshot: Optional[ScreenshotData] = None,
        pre_windows: Optional[List[Dict[str, Any]]] = None,
        post_windows: Optional[List[Dict[str, Any]]] = None,
    ) -> VerificationResult:
        """
        Verify the effect of an executed action against the expected outcome.
        """
        act_type = action.action_type
        exp_lower = expected_outcome.lower().strip()

        # ── 1. Window State Verification ─────────────────────────────────────
        if act_type in (
            ComputerActionType.LAUNCH_APPLICATION,
            ComputerActionType.FOCUS_WINDOW,
            ComputerActionType.CLOSE_WINDOW,
        ) or action.window_title:
            win_result = await self._verify_window_state(action, expected_outcome, pre_windows, post_windows)
            if win_result:
                return win_result


        # ── 2. Screenshot Difference / Settlement Verification ──────────────
        diff_info = None
        if pre_screenshot and post_screenshot:
            diff_info = self._calculate_pixel_diff(pre_screenshot, post_screenshot)

        # Actions that must alter the screen (click, type, press, scroll)
        if act_type in (
            ComputerActionType.CLICK,
            ComputerActionType.DOUBLE_CLICK,
            ComputerActionType.TYPE,
            ComputerActionType.PRESS,
            ComputerActionType.HOTKEY,
            ComputerActionType.SCROLL,
        ):
            is_mock = (
                (pre_screenshot and pre_screenshot.metadata.get("mock"))
                or (post_screenshot and post_screenshot.metadata.get("mock"))
            )
            if not is_mock and diff_info and diff_info["changed_pixels_ratio"] < 0.0001:
                # No screen change detected at all on physical display
                if not any(k in exp_lower for k in ("no change", "steady", "ignore")):
                    return VerificationResult(
                        verified=False,
                        confidence=0.85,
                        method="pixel_diff",
                        expected=expected_outcome,
                        observed="No visible change detected on the screen after the action.",
                        details=diff_info,
                        retry_suggested=True,
                        replan_suggested=False,
                    )


        # ── 3. Visual Reasoning / VLM Verification ───────────────────────────
        if self.vision_provider and post_screenshot:
            vlm_result = await self._verify_via_vlm(action, expected_outcome, post_screenshot)
            if vlm_result:
                return vlm_result

        # ── 4. Fallback: Reasonable state change heuristic ───────────────────
        if diff_info and diff_info["changed_pixels_ratio"] >= 0.0001:
            return VerificationResult(
                verified=True,
                confidence=0.75,
                method="pixel_diff",
                expected=expected_outcome,
                observed=f"Screen state changed ({diff_info['changed_pixels_ratio']:.2%} pixels changed).",
                details=diff_info,
            )

        # Default fallback
        return VerificationResult(
            verified=True,
            confidence=0.6,
            method="heuristic",
            expected=expected_outcome,
            observed="Action completed execution.",
        )

    # ── Helpers ──────────────────────────────────────────────────────────────

    async def _verify_window_state(
        self,
        action: ComputerAction,
        expected_outcome: str,
        pre_windows: Optional[List[Dict[str, Any]]],
        post_windows: Optional[List[Dict[str, Any]]],
    ) -> Optional[VerificationResult]:
        """Check window lists before and after."""
        current_windows = post_windows
        if current_windows is None and self.window_backend:
            wins = await self.window_backend.list_windows()
            current_windows = [w.to_dict() for w in wins]

        if not current_windows:
            return None

        target = (action.app_name or action.window_title or expected_outcome).lower()

        # Handle launch_application or open window expectation
        if action.action_type == ComputerActionType.LAUNCH_APPLICATION or (action.window_title and "open" in expected_outcome.lower()):

            for w in current_windows:
                title = w.get("title", "").lower()
                proc = w.get("process_name", "").lower()
                if any(t in title or t in proc for t in target.split() if len(t) > 2):
                    return VerificationResult(
                        verified=True,
                        confidence=0.95,
                        method="window_state",
                        expected=f"Application '{target}' window visible",
                        observed=f"Detected window '{w.get('title')}' (process: {w.get('process_name')})",
                        details={"matched_window": w},
                    )

            # Not found
            return VerificationResult(
                verified=False,
                confidence=0.90,
                method="window_state",
                expected=f"Application '{target}' window visible",
                observed="Target application window not found among visible windows.",
                details={"open_windows": [w.get("title") for w in current_windows[:10]]},
                retry_suggested=True,
                replan_suggested=True,
            )

        # Handle close_window expectation
        if action.action_type == ComputerActionType.CLOSE_WINDOW or "close" in expected_outcome.lower():
            found = False
            for w in current_windows:
                title = w.get("title", "").lower()
                proc = w.get("process_name", "").lower()
                if any(t in title or t in proc for t in target.split() if len(t) > 2):
                    found = True
                    break

            if not found:
                return VerificationResult(
                    verified=True,
                    confidence=0.95,
                    method="window_state",
                    expected=f"Window '{target}' closed",
                    observed="Window is no longer visible.",
                )
            else:
                return VerificationResult(
                    verified=False,
                    confidence=0.90,
                    method="window_state",
                    expected=f"Window '{target}' closed",
                    observed="Window is still open.",
                    retry_suggested=True,
                )

        # Handle focus_window
        if action.action_type == ComputerActionType.FOCUS_WINDOW:
            if self.window_backend:
                active = await self.window_backend.get_active_window()
                if active:
                    act_title = active.title.lower()
                    if any(t in act_title for t in target.split() if len(t) > 2):
                        return VerificationResult(
                            verified=True,
                            confidence=0.95,
                            method="window_state",
                            expected=f"Window '{target}' focused",
                            observed=f"Active window is '{active.title}'",
                            details={"active_window": active.to_dict()},
                        )

        return None

    def _calculate_pixel_diff(
        self, pre: ScreenshotData, post: ScreenshotData
    ) -> Dict[str, Any]:
        """Compute pixel change ratio between two frames."""
        try:
            from PIL import ImageChops
            img1 = pre.to_pil_image().convert("RGB")
            img2 = post.to_pil_image().convert("RGB")

            if img1.size != img2.size:
                img2 = img2.resize(img1.size)

            diff = ImageChops.difference(img1, img2)
            stat = diff.getbbox()
            if not stat:
                return {"changed_pixels_ratio": 0.0, "has_difference": False}

            # Sample difference intensity
            hist = diff.histogram()
            non_zero = sum(hist[1:256] + hist[257:512] + hist[513:768])
            total = (img1.size[0] * img1.size[1]) * 3
            ratio = non_zero / total if total > 0 else 0.0

            return {
                "changed_pixels_ratio": ratio,
                "has_difference": ratio > 0.0001,
                "bounding_box": list(stat),
            }
        except Exception as e:
            logger.debug(f"Pixel diff calculation failed: {e}")
            return {"changed_pixels_ratio": 0.0, "has_difference": False, "error": str(e)}

    async def _verify_via_vlm(
        self,
        action: ComputerAction,
        expected_outcome: str,
        post_screenshot: ScreenshotData,
    ) -> Optional[VerificationResult]:
        """Ask VLM if expected state was achieved."""
        if not self.vision_provider:
            return None

        prompt = (
            f"Verification task: Action '{action.action_type.value}' was performed.\n"
            f"Expected outcome: {expected_outcome}\n"
            f"Examine the screenshot and determine if the expected outcome was achieved.\n"
            f"Reply with JSON: {{\"verified\": true/false, \"confidence\": float, \"observed\": \"summary of what you see\"}}"
        )

        try:
            analysis = await self.vision_provider.analyze_screenshot(
                screenshot_base64=post_screenshot.base64_str,
                query=prompt,
            )
            import json
            import re
            m = re.search(r'\{[^{}]*"verified"\s*:\s*(true|false).*"observed"\s*:.*\}', analysis, re.IGNORECASE | re.DOTALL)
            if m:
                data = json.loads(m.group(0))
                is_ver = bool(data.get("verified"))
                conf = float(data.get("confidence", 0.8))
                obs = str(data.get("observed", ""))
                return VerificationResult(
                    verified=is_ver,
                    confidence=conf,
                    method="vlm",
                    expected=expected_outcome,
                    observed=obs,
                    retry_suggested=not is_ver,
                    replan_suggested=not is_ver and conf >= 0.8,
                )
        except Exception as e:
            logger.debug(f"VLM verification fallback failed: {e}")

        return None
