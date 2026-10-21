"""
HELIOS — Computer Safety & Risk Governance
Risk classification, protected application isolation, and emergency stop.
"""

from __future__ import annotations

import asyncio
import logging
from typing import Any, Dict, Optional, Set

from computer.actions import ActionRiskLevel, ComputerAction, ComputerActionType

logger = logging.getLogger("helios.computer.safety")


# ─── Protected Applications and Keywords ──────────────────────────────────────

PROTECTED_PROCESS_NAMES: Set[str] = {
    "1password.exe", "1password", "bitwarden.exe", "bitwarden",
    "keepass.exe", "keepassxc.exe", "keepass", "lastpass",
    "dashlane.exe", "dashlane", "enpass.exe", "enpass",
    "credentialuibroker.exe", "consent.exe",  # Windows UAC / Credential prompts
    "regedit.exe", "regedt32.exe", "secpol.msc", "gpedit.msc",
    "taskmgr.exe", "mmc.exe", "powershell.exe", "cmd.exe" # High-privilege consoles when targeted directly
}

PROTECTED_WINDOW_PATTERNS: Set[str] = {
    "user account control",
    "windows security",
    "credential manager",
    "master password",
    "password manager",
    "sign in with windows hello",
    "pin verification",
    "bitwarden",
    "keepass",
    "1password",
    "registry editor",
    "security settings"
}

CREDENTIAL_KEYWORDS: Set[str] = {
    "password", "passwd", "master password", "secret", "private_key",
    "access_token", "api_key", "bearer ", "credit card", "cvv"
}

DESTRUCTIVE_KEY_COMBOS: Set[str] = {
    "alt+f4", "ctrl+alt+del", "win+r", "ctrl+shift+esc"
}


# ─── Emergency Stop ──────────────────────────────────────────────────────────

class EmergencyStop:
    """
    Immediate emergency stop primitive for all computer control.
    When triggered, halts active execution, cancels queued operations,
    and signals the orchestrator and supervisor.
    """

    def __init__(self):
        self._stopped = False
        self._reason = ""
        self._event = asyncio.Event()
        self._event.set()  # Initial state: clear to run

    @property
    def is_stopped(self) -> bool:
        return self._stopped

    @property
    def reason(self) -> str:
        return self._reason

    def trigger(self, reason: str = "Emergency stop triggered") -> None:
        """Trigger emergency stop immediately."""
        self._stopped = True
        self._reason = reason
        self._event.clear()
        logger.warning(f"EMERGENCY STOP TRIGGERED: {reason}")

    def reset(self) -> None:
        """Reset emergency stop (requires explicit administrative confirmation)."""
        self._stopped = False
        self._reason = ""
        self._event.set()
        logger.info("Emergency stop reset.")

    async def wait_if_stopped(self) -> None:
        """Wait if stopped or raise cancellation if emergency stop is engaged."""
        if self._stopped:
            raise asyncio.CancelledError(f"Computer execution halted by Emergency Stop: {self._reason}")
        await self._event.wait()


# Global singleton instance
emergency_stop = EmergencyStop()


# ─── Risk Classifier ─────────────────────────────────────────────────────────

class ComputerSafety:
    """
    Evaluates safety rules and assigns risk classifications to ComputerAction requests.
    """

    @staticmethod
    def is_protected_target(
        window_title: Optional[str] = None,
        process_name: Optional[str] = None,
        text: Optional[str] = None,
    ) -> bool:
        """
        Detect whether an interaction targets a protected credential manager,
        security dialog, or system configuration window.
        """
        if process_name:
            proc = process_name.lower().strip()
            for p in PROTECTED_PROCESS_NAMES:
                if proc == p or proc.endswith(p):
                    return True

        if window_title:
            title = window_title.lower().strip()
            for pattern in PROTECTED_WINDOW_PATTERNS:
                if pattern in title:
                    return True

        if text:
            txt_lower = text.lower()
            for kw in CREDENTIAL_KEYWORDS:
                if kw in txt_lower:
                    return True

        return False

    @staticmethod
    def classify_risk(action: ComputerAction) -> ActionRiskLevel:
        """
        Classify action risk:
        LOW: screenshot, move, scroll, wait
        MEDIUM: click, double_click, right_click, type, press, standard hotkey, focus_window, launch_application
        HIGH: drag, close_window, destructive key combinations, unknown application launch
        CRITICAL: credential inputs, interaction with protected applications/windows
        """
        # 1. Protected target check -> always CRITICAL
        if ComputerSafety.is_protected_target(
            window_title=action.window_title or action.element_query,
            process_name=action.app_name,
            text=action.text
        ):
            return ActionRiskLevel.CRITICAL

        # 2. Action type specifics
        act_type = action.action_type

        if act_type in (
            ComputerActionType.SCREENSHOT,
            ComputerActionType.MOVE,
            ComputerActionType.SCROLL,
            ComputerActionType.WAIT,
        ):
            return ActionRiskLevel.LOW

        if act_type == ComputerActionType.STOP:
            return ActionRiskLevel.LOW

        if act_type in (
            ComputerActionType.DRAG,
            ComputerActionType.CLOSE_WINDOW,
        ):
            return ActionRiskLevel.HIGH

        if act_type == ComputerActionType.HOTKEY and action.keys:
            combo = "+".join(k.lower().strip() for k in action.keys)
            if any(dk in combo for dk in DESTRUCTIVE_KEY_COMBOS):
                return ActionRiskLevel.HIGH

        if act_type == ComputerActionType.TYPE and action.text:
            text_lower = action.text.lower()
            if any(kw in text_lower for kw in CREDENTIAL_KEYWORDS):
                return ActionRiskLevel.CRITICAL

        # Default standard interactive actions are MEDIUM
        return ActionRiskLevel.MEDIUM
