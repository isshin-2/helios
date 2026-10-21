"""
HELIOS — Comprehensive Computer-Use System Test Suite
Covers:
- Action validation & coordinate bounds
- Screenshot subsystem & multi-monitor support
- Window management & process safety
- UI grounding (UIA, tree, OCR, vision, fallback)
- Risk classification & protected target isolation
- PermissionManager integration & agent-mode boundary fix
- Emergency stop & cancellation safety
- Verification (window state, pixel diff, VLM)
- Closed-loop ComputerAgent (happy path, retry on failure, approval required, protected block, timeout)
- Acceptance test scenario (VS Code + HELIOS + tests)
"""

import asyncio
import json
import pytest
from unittest.mock import AsyncMock, MagicMock

from computer.actions import (
    ActionRiskLevel,
    ActionResult,
    ComputerAction,
    ComputerActionType,
)
from computer.controller import (
    ComputerController,
    MockComputerBackend,
)
from computer.grounding import UIElement, UIGroundingEngine
from computer.safety import (
    ComputerSafety,
    EmergencyStop,
    emergency_stop,
)
from computer.screenshot import (
    MockScreenshotBackend,
    MonitorInfo,
    ScreenshotData,
    ScreenshotManager,
)
from computer.verifier import ActionVerifier, VerificationResult
from computer.vision import MockVisionProvider
from computer.windows import MockWindowBackend, WindowInfo
from agents.base import AgentStatus
from agents.computer_agent import ComputerAgent
from core.events import EventBus
from core.task_contract import (
    ComputerConstraints,
    RiskLevel,
    TaskCapability,
    TaskContract,
)
from security.permissions import PermissionManager, PermissionResult
from tools.computer import ComputerControlTool, ComputerToolInput


# ─── 1. Action Validation & Coordinate Bounds ─────────────────────────────────

class TestComputerActions:
    def test_action_normalization_and_aliases(self):
        # Alias: open_app -> launch_application
        a1 = ComputerAction(action="open_app", app_name="calc")
        assert a1.action_type == ComputerActionType.LAUNCH_APPLICATION
        assert a1.app_name == "calc"

        # Alias: key -> keys
        a2 = ComputerAction(action="press", key="enter")
        assert a2.action_type == ComputerActionType.PRESS
        assert a2.keys == ["enter"]

        # Alias: hotkey string "ctrl+c" -> ["ctrl", "c"]
        a3 = ComputerAction(action="hotkey", keys="ctrl+c")
        assert a3.action_type == ComputerActionType.HOTKEY
        assert a3.keys == ["ctrl", "c"]

    def test_coordinate_bounds_validation(self):
        screen_w, screen_h = 1920, 1080

        # In bounds
        valid_act = ComputerAction(action_type=ComputerActionType.CLICK, x=960, y=540)
        assert valid_act.validate_bounds(screen_w, screen_h) is None

        # Negative X
        neg_act = ComputerAction(action_type=ComputerActionType.CLICK, x=-10, y=100)
        assert "out of screen bounds" in neg_act.validate_bounds(screen_w, screen_h)

        # Exceeds width
        overflow_x = ComputerAction(action_type=ComputerActionType.CLICK, x=1920, y=100)
        assert "out of screen bounds" in overflow_x.validate_bounds(screen_w, screen_h)

        # Drag bounds
        drag_act = ComputerAction(
            action_type=ComputerActionType.DRAG,
            start_x=100, start_y=100, end_x=2000, end_y=500
        )
        assert "Drag end_x" in drag_act.validate_bounds(screen_w, screen_h)

    def test_action_result_serialization(self):
        res = ActionResult(
            success=True,
            action="click",
            target={"x": 500, "y": 300},
            backend="mock",
            details={"clicked": True}
        )
        d = res.to_dict()
        assert d["success"] is True
        assert d["action"] == "click"
        assert d["target"]["x"] == 500
        assert "timestamp" in d


# ─── 2. Screenshot Subsystem & Multi-Monitor Support ──────────────────────────

class TestScreenshotSubsystem:
    @pytest.mark.asyncio
    async def test_monitor_listing_and_selection(self):
        backend = MockScreenshotBackend(width=2560, height=1440)
        monitors = await backend.list_monitors()
        assert len(monitors) == 2
        assert monitors[0].is_primary is True
        assert monitors[0].width == 2560
        assert monitors[1].is_primary is False

    @pytest.mark.asyncio
    async def test_screenshot_capture_and_data_url(self):
        backend = MockScreenshotBackend(width=1920, height=1080)
        shot = await backend.capture(monitor_id=1, image_format="jpeg")
        assert shot.width == 1920
        assert shot.height == 1080
        assert shot.format == "jpeg"
        assert shot.base64_str is not None
        assert shot.data_url.startswith("data:image/jpeg;base64,")

    @pytest.mark.asyncio
    async def test_screenshot_manager_caching(self):
        backend = MockScreenshotBackend(width=1920, height=1080)
        manager = ScreenshotManager(backend=backend, cache_ttl_seconds=0.5)

        shot1 = await manager.capture_screen(force_fresh=False)
        shot2 = await manager.capture_screen(force_fresh=False)
        assert shot1 is shot2  # Cached instance returned

        shot3 = await manager.capture_screen(force_fresh=True)
        assert shot3 is not shot1  # Fresh capture requested


# ─── 3. Window Management Subsystem ──────────────────────────────────────────

class TestWindowSubsystem:
    @pytest.mark.asyncio
    async def test_window_operations(self):
        backend = MockWindowBackend()
        windows = await backend.list_windows()
        assert len(windows) >= 2

        # Focus window
        ok_focus = await backend.focus_window("PowerShell")
        assert ok_focus is True
        active = await backend.get_active_window()
        assert "PowerShell" in active.title

        # Launch application
        ok_launch = await backend.launch_application("notepad")
        assert ok_launch is True
        active = await backend.get_active_window()
        assert "Notepad" in active.title

        # Close window
        ok_close = await backend.close_window("notepad")
        assert ok_close is True


# ─── 4. UI Grounding Engine ──────────────────────────────────────────────────

class TestUIGrounding:
    @pytest.mark.asyncio
    async def test_grounding_priority_and_centroids(self):
        vision = MockVisionProvider()
        grounding = UIGroundingEngine(vision_provider=vision, use_uia=False)

        # Set mock elements (highest priority in tests)
        mock_el = UIElement(
            role="Button",
            name="Run Tests",
            bounds=(400, 200, 500, 240),
            confidence=0.98,
            source="uia"
        )
        grounding.set_mock_elements([mock_el])

        backend = MockScreenshotBackend()
        shot = await backend.capture()

        # Resolve "Run Tests"
        target = await grounding.ground_query("Run Tests", shot)
        assert target is not None
        assert target.name == "Run Tests"
        assert target.centroid == (450, 220)
        assert target.confidence == 0.98

    @pytest.mark.asyncio
    async def test_vision_fallback_grounding(self):
        vision = MockVisionProvider()
        vision.set_location("settings", {"x": 800, "y": 400, "bounds": (780, 390, 820, 410), "confidence": 0.88})

        grounding = UIGroundingEngine(vision_provider=vision, use_uia=False)
        backend = MockScreenshotBackend()
        shot = await backend.capture()

        target = await grounding.ground_query("settings button", shot)
        assert target is not None
        assert target.centroid == (800, 400)
        assert target.source == "vision"


# ─── 5. Safety, Risk Classification & Permissions ────────────────────────────

class TestSafetyAndPermissions:
    def test_risk_classification(self):
        # LOW risk
        low_action = ComputerAction(action_type=ComputerActionType.SCREENSHOT)
        assert ComputerSafety.classify_risk(low_action) == ActionRiskLevel.LOW

        # MEDIUM risk
        med_action = ComputerAction(action_type=ComputerActionType.CLICK, x=100, y=100)
        assert ComputerSafety.classify_risk(med_action) == ActionRiskLevel.MEDIUM

        # HIGH risk (drag or destructive hotkey)
        high_action = ComputerAction(action_type=ComputerActionType.HOTKEY, keys=["alt", "f4"])
        assert ComputerSafety.classify_risk(high_action) == ActionRiskLevel.HIGH

        # CRITICAL risk (credential entry)
        crit_action = ComputerAction(action_type=ComputerActionType.TYPE, text="my_secret_password_123")
        assert ComputerSafety.classify_risk(crit_action) == ActionRiskLevel.CRITICAL

    def test_protected_target_detection(self):
        # Password managers
        assert ComputerSafety.is_protected_target(process_name="bitwarden.exe") is True
        assert ComputerSafety.is_protected_target(window_title="1Password - Enter Master Password") is True
        assert ComputerSafety.is_protected_target(window_title="Windows Security Prompt") is True
        assert ComputerSafety.is_protected_target(process_name="regedit.exe") is True

        # Benign applications
        assert ComputerSafety.is_protected_target(process_name="Code.exe") is False
        assert ComputerSafety.is_protected_target(window_title="Visual Studio Code - HELIOS") is False

    def test_emergency_stop_lifecycle(self):
        es = EmergencyStop()
        assert es.is_stopped is False

        es.trigger("User pressed Stop button")
        assert es.is_stopped is True
        assert es.reason == "User pressed Stop button"

        es.reset()
        assert es.is_stopped is False

    def test_permission_manager_agent_mode_boundary(self):
        pm = PermissionManager()

        # Read-only / LOW risk allowed in agent mode
        assert pm.is_safe_for_agent_mode("file_read", "some_file.py") is True
        assert pm.is_safe_for_agent_mode("computer.screenshot", "display") is True
        assert pm.is_safe_for_agent_mode("computer.move", "coords") is True

        # MEDIUM / HIGH / CRITICAL actions NOT safe for agent_mode bypass
        assert pm.is_safe_for_agent_mode("computer.click", "submit_button") is False
        assert pm.is_safe_for_agent_mode("computer.type", "code") is False
        assert pm.is_safe_for_agent_mode("computer.hotkey", "alt+f4") is False

        # Protected targets NEVER safe
        assert pm.is_safe_for_agent_mode("computer.click", "Bitwarden") is False
        assert pm.is_safe_for_agent_mode("computer.screenshot", "Windows Security") is False


# ─── 6. Action Verification Subsystem ────────────────────────────────────────

class TestActionVerifier:
    @pytest.mark.asyncio
    async def test_window_state_verification_success(self):
        win_backend = MockWindowBackend()
        verifier = ActionVerifier(window_backend=win_backend)

        # Expected VS Code open -> already in MockWindowBackend
        action = ComputerAction(action_type=ComputerActionType.LAUNCH_APPLICATION, app_name="code")
        res = await verifier.verify(action=action, expected_outcome="Visual Studio Code window detected")
        assert res.verified is True
        assert res.method == "window_state"

    @pytest.mark.asyncio
    async def test_window_state_verification_failure_triggers_retry(self):
        win_backend = MockWindowBackend()
        verifier = ActionVerifier(window_backend=win_backend)

        # Expected App not in MockWindowBackend
        action = ComputerAction(action_type=ComputerActionType.LAUNCH_APPLICATION, app_name="nonexistent_app")
        res = await verifier.verify(action=action, expected_outcome="Application 'nonexistent_app' window visible")
        assert res.verified is False
        assert res.retry_suggested is True


# ─── 7. High-Level ComputerController ────────────────────────────────────────

class TestComputerController:
    @pytest.mark.asyncio
    async def test_execute_action_flow(self):
        backend = MockComputerBackend()
        win_backend = MockWindowBackend()
        ctrl = ComputerController(backend=backend, window_backend=win_backend)

        # Click
        res = await ctrl.click(500, 300)
        assert res.success is True
        assert backend.cursor_pos == (500, 300)

        # Type text
        res = await ctrl.type_text("Hello HELIOS")
        assert res.success is True
        assert "Hello HELIOS" in backend.typed_text

        # Emergency stop enforcement
        ctrl.stop("Testing emergency stop")
        res_blocked = await ctrl.click(100, 100)
        assert res_blocked.success is False
        assert "Emergency stop engaged" in res_blocked.error
        ctrl.reset_stop()


# ─── 8. ComputerControlTool Integration ──────────────────────────────────────

class TestComputerControlTool:
    @pytest.mark.asyncio
    async def test_tool_execution_structured_json(self):
        backend = MockComputerBackend()
        ctrl = ComputerController(backend=backend)
        tool = ComputerControlTool(controller=ctrl)

        json_out, tool_name = await tool.execute(user_id=1, action="click", x=640, y=480)
        data = json.loads(json_out)
        assert data["success"] is True
        assert data["action"] == "click"
        assert data["target"]["x"] == 640
        assert data["target"]["y"] == 480
        assert tool_name == "computer_control"

    @pytest.mark.asyncio
    async def test_tool_bounds_error(self):
        backend = MockComputerBackend(width=1920, height=1080)
        ctrl = ComputerController(backend=backend)
        tool = ComputerControlTool(controller=ctrl)

        json_out, _ = await tool.execute(user_id=1, action="click", x=5000, y=5000)
        data = json.loads(json_out)
        assert data["success"] is False
        assert "out of screen bounds" in data["error"]


# ─── 9. ComputerAgent Closed-Loop Execution ──────────────────────────────────

class TestComputerAgentLoop:
    @pytest.mark.asyncio
    async def test_agent_happy_path(self):
        backend = MockComputerBackend()
        win_backend = MockWindowBackend()
        ctrl = ComputerController(backend=backend, window_backend=win_backend)
        agent = ComputerAgent(controller=ctrl)

        # Launch Calculator workflow
        result = await agent.execute("Launch calculator application", context={"maximum_actions": 5})
        assert result.status == AgentStatus.SUCCESS
        assert "calculator" in result.summary.lower()

    @pytest.mark.asyncio
    async def test_agent_protected_target_blocks_and_requests_approval(self):
        backend = MockComputerBackend()
        win_backend = MockWindowBackend()
        # Simulate active window is Bitwarden password manager
        win_backend.windows[999] = WindowInfo(
            handle=999,
            title="Bitwarden - Master Password",
            process_name="bitwarden.exe",
            pid=9999,
            bounds=(100, 100, 600, 500),
            is_active=True,
            is_visible=True,
        )
        win_backend.active_handle = 999

        ctrl = ComputerController(backend=backend, window_backend=win_backend)
        agent = ComputerAgent(controller=ctrl)

        result = await agent.execute("Click the submit button", context={"maximum_actions": 3})
        assert result.status == AgentStatus.NEEDS_APPROVAL
        assert "protected application detected" in result.summary.lower()

    @pytest.mark.asyncio
    async def test_agent_emergency_stop_halts_execution(self):
        backend = MockComputerBackend()
        win_backend = MockWindowBackend()
        ctrl = ComputerController(backend=backend, window_backend=win_backend)
        agent = ComputerAgent(controller=ctrl)

        ctrl.stop("Manual halt")
        try:
            result = await agent.execute("Open notepad", context={"maximum_actions": 5})
            assert result.status == AgentStatus.FAILURE
            assert "emergency stop" in result.summary.lower()
        finally:
            ctrl.reset_stop()


# ─── 10. Acceptance Test Scenario ────────────────────────────────────────────

class TestAcceptanceScenario:
    """
    Acceptance Test Scenario from Section 22:
    "Open VS Code, open the HELIOS project, run the tests, and tell me whether they passed."
    """
    @pytest.mark.asyncio
    async def test_vscode_project_test_workflow(self):
        backend = MockComputerBackend()
        win_backend = MockWindowBackend()
        # Set up initial desktop state where VS Code is not open
        win_backend.windows.clear()
        win_backend.windows[10] = WindowInfo(
            handle=10,
            title="Desktop",
            process_name="explorer.exe",
            pid=500,
            bounds=(0, 0, 1920, 1080),
            is_active=True,
            is_visible=True,
        )
        win_backend.active_handle = 10

        ctrl = ComputerController(backend=backend, window_backend=win_backend)
        agent = ComputerAgent(controller=ctrl)

        objective = "Open VS Code, open the HELIOS project, run the tests, and tell me whether they passed."
        result = await agent.execute(objective, context={"maximum_actions": 10})

        assert result.status == AgentStatus.SUCCESS
        assert "VS Code" in result.summary
        assert "HELIOS" in result.summary
        assert "test" in result.summary.lower()
        assert len(result.evidence.get("steps", [])) >= 4
