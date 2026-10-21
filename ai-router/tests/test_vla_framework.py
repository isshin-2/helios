"""
Unit and Integration Tests for HELIOS VLA Computer Control Framework & System Audit Engine.
Tests:
1. System Audit inspection and Markdown generation.
2. Composite State Hashing, drift detection, and changelog history appending.
3. High-speed in-memory frame capture and Lanczos downsampling to 1080p.
4. Coordinate normalization math (bounding box centroiding, native conversion, DPI division).
5. Deadlock detection rolling window (+-5px radius trigger).
6. 500ms visual settlement buffer.
"""

import asyncio
import io
import math
import tempfile
import time
from pathlib import Path
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from PIL import Image

from system_audit import (
    AuditReport,
    AuditSyncManager,
    ComputeMemoryBudget,
    DisplayMetrics,
    HostEnvironmentInspector,
    InstalledModel,
    LocalInferenceRuntime,
    MarkdownAuditFormatter,
    MonitorBounds,
)
from vla_engine import (
    ActionType,
    CapturedFrame,
    CoordinateNormalizer,
    DeadlockDetector,
    DeadlockDetectedError,
    HighSpeedFrameCapturer,
    InputDispatcher,
    LoopStatus,
    StatefulVLAExecutionLoop,
    VLAAction,
)


# ─── 1. System Audit & Inspector Tests ────────────────────────────────────────

def test_host_environment_inspector_display():
    inspector = HostEnvironmentInspector()
    disp = inspector.inspect_display()

    assert disp.physical_resolution[0] > 0
    assert disp.physical_resolution[1] > 0
    assert disp.logical_resolution[0] > 0
    assert disp.logical_resolution[1] > 0
    assert disp.dpi >= 72
    assert disp.dpi_scaling_factor > 0.0
    assert disp.primary_monitor.width > 0
    assert disp.primary_monitor.height > 0


def test_host_environment_inspector_compute():
    inspector = HostEnvironmentInspector()
    comp = inspector.inspect_compute_budget()

    assert comp.total_physical_ram_gb > 0
    assert comp.available_physical_ram_gb > 0
    assert comp.cpu_physical_cores >= 1
    assert comp.cpu_logical_cores >= 1
    assert len(comp.gpu_model) > 0


def test_host_environment_inspector_runtime():
    inspector = HostEnvironmentInspector()
    rt = inspector.inspect_local_runtime()

    assert rt.ollama_status in ("RUNNING", "OFFLINE")
    assert "mss" in rt.package_versions
    assert "pyautogui" in rt.package_versions
    assert "pillow" in rt.package_versions
    assert "psutil" in rt.package_versions
    assert rt.package_versions["mss"] != "not installed"


def test_composite_state_hash_determinism():
    inspector = HostEnvironmentInspector()
    disp = DisplayMetrics(
        physical_resolution=(1920, 1080),
        logical_resolution=(1920, 1080),
        dpi=96,
        dpi_scaling_factor=1.0,
        primary_monitor=MonitorBounds(0, 0, 1920, 1080),
        all_monitors=[MonitorBounds(0, 0, 1920, 1080)],
        multi_monitor=False,
    )
    comp = ComputeMemoryBudget(
        gpu_model="Test GPU",
        gpu_driver_version="1.0.0",
        gpu_total_vram_mb=4096.0,
        gpu_free_vram_mb=2048.0,
        total_physical_ram_gb=16.0,
        available_physical_ram_gb=8.0,
        cpu_architecture="x86_64",
        cpu_processor="Intel",
        cpu_physical_cores=8,
        cpu_logical_cores=16,
    )
    rt = LocalInferenceRuntime(
        ollama_status="RUNNING",
        ollama_endpoint="http://localhost:11434",
        installed_models=[
            InstalledModel("qwen3-vl:8b", 5000.0, "8B", "Q4", "qwen", ["vision"], True, False)
        ],
        active_vision_models=["qwen3-vl:8b"],
        package_versions={"mss": "10.0.0"},
    )

    h1 = inspector.compute_state_hash(disp, comp, rt)
    h2 = inspector.compute_state_hash(disp, comp, rt)
    assert h1 == h2
    assert len(h1) == 64  # SHA-256


# ─── 2. Auto-Update & Drift Hook Tests ────────────────────────────────────────

def test_audit_sync_manager_drift_detection(tmp_path: Path):
    audit_file = tmp_path / "SYSTEM_AUDIT.md"
    manager = AuditSyncManager(audit_file_path=audit_file)

    # Initial run: should generate baseline
    drift1, rep1 = manager.check_and_sync()
    assert drift1 is True
    assert audit_file.exists()
    content1 = audit_file.read_text(encoding="utf-8")
    assert "## 5. Audit History / Changelog" in content1
    assert "Baseline initialization" in content1

    # Second run without changes: no drift
    drift2, rep2 = manager.check_and_sync()
    assert drift2 is False
    assert rep2.state_hash == rep1.state_hash

    # Simulate drift by modifying cached hash in markdown file
    modified_content = content1.replace(rep1.state_hash, "f" * 64)
    audit_file.write_text(modified_content, encoding="utf-8")

    # Third run: should detect drift and append changelog entry with ISO timestamp
    drift3, rep3 = manager.check_and_sync()
    assert drift3 is True
    content3 = audit_file.read_text(encoding="utf-8")
    assert "Environment drift detected" in content3
    # Both initial baseline and drift entries must exist
    assert "Baseline initialization" in content3


# ─── 3. Frame Capture & Lanczos Downsampling Tests ────────────────────────────

def test_frame_capturer_downsampling_and_encoding():
    disp = DisplayMetrics(
        physical_resolution=(2560, 1440),  # > 1080p height
        logical_resolution=(2560, 1440),
        dpi=96,
        dpi_scaling_factor=1.0,
        primary_monitor=MonitorBounds(0, 0, 2560, 1440),
    )
    capturer = HighSpeedFrameCapturer(display_metrics=disp)

    # Mock grab to return a 2560x1440 synthetic image
    mock_img = Image.new("RGB", (2560, 1440), color=(100, 150, 200))
    bgra_data = bytearray(2560 * 1440 * 4)

    mock_sct = MagicMock()
    mock_sct.grab.return_value = MagicMock(size=(2560, 1440), bgra=bytes(bgra_data))

    with patch.object(capturer, "_get_sct", return_value=MagicMock(__enter__=MagicMock(return_value=mock_sct))):
        frame = capturer.capture_frame()

        assert frame.original_width == 2560
        assert frame.original_height == 1440
        # Must be downsampled to max height 1080p
        assert frame.downsampled_height == 1080
        assert frame.downsampled_width == int(round(2560 * (1080 / 1440)))  # 1920
        assert frame.scale_x == 2560 / 1920
        assert frame.scale_y == 1440 / 1080
        assert len(frame.base64_jpeg) > 0


# ─── 4. Coordinate Normalization Tests ────────────────────────────────────────

def test_coordinate_normalizer_bounding_box():
    # Frame downsampled from 3840x2160 (4K) to 1920x1080 (downsampled) with 1.5x DPI scaling
    normalizer = CoordinateNormalizer(dpi_scaling_factor=1.5, primary_offset=(0, 0))

    frame = CapturedFrame(
        original_width=3840,
        original_height=2160,
        downsampled_width=1920,
        downsampled_height=1080,
        scale_x=2.0,
        scale_y=2.0,
        base64_jpeg="test",
        raw_pil_image=MagicMock(),
        capture_time_ms=10.0,
        monitor_left=0,
        monitor_top=0,
    )

    # Bounding box in downsampled space: [100, 200, 300, 400]
    # Center point in downsampled space: (200, 300)
    # Native display pixels: (200 * 2.0, 300 * 2.0) = (400, 600)
    # OS DPI divided: round(400 / 1.5) = 267, round(600 / 1.5) = 400
    norm = normalizer.normalize([100, 200, 300, 400], frame)

    assert norm.center_downsampled == (200.0, 300.0)
    assert norm.native_pixel == (400.0, 600.0)
    assert norm.os_dpi_divided == (round(400.0 / 1.5), round(600.0 / 1.5))


def test_coordinate_normalizer_thousand_scale():
    # Model returns UI-TARS/Qwen-VL style 1000-scale box: [100, 200, 300, 400]
    normalizer = CoordinateNormalizer(dpi_scaling_factor=1.0, primary_offset=(0, 0))
    frame = CapturedFrame(
        original_width=1920,
        original_height=1080,
        downsampled_width=1920,
        downsampled_height=1080,
        scale_x=1.0,
        scale_y=1.0,
        base64_jpeg="test",
        raw_pil_image=MagicMock(),
        capture_time_ms=10.0,
        monitor_left=0,
        monitor_top=0,
    )

    norm = normalizer.normalize([100, 200, 300, 400], frame, is_thousand_scale=True)
    # 1000-scale: x_center = 200 / 1000 * 1920 = 384.0, y_center = 300 / 1000 * 1080 = 324.0
    assert norm.center_downsampled == (384.0, 324.0)
    assert norm.native_pixel == (384.0, 324.0)
    assert norm.os_dpi_divided == (384, 324)


# ─── 5. Deadlock & Infinite Loop Detector Tests ───────────────────────────────

def test_deadlock_detector_triggers_on_three_actions_within_five_pixels():
    detector = DeadlockDetector(radius_px=5.0)

    # 1st action at (500, 300)
    assert detector.record_and_check(500.0, 300.0, "click") is False
    # 2nd action at (502, 301) - within 5px
    assert detector.record_and_check(502.0, 301.0, "click") is False
    # 3rd action at (498, 299) - within 5px of all previous actions!
    assert detector.record_and_check(498.0, 299.0, "click") is True


def test_deadlock_detector_does_not_trigger_on_distinct_actions():
    detector = DeadlockDetector(radius_px=5.0)

    assert detector.record_and_check(100.0, 100.0, "click") is False
    assert detector.record_and_check(150.0, 100.0, "click") is False
    assert detector.record_and_check(200.0, 100.0, "click") is False


# ─── 6. Stateful VLA Execution Loop & Visual Settlement Buffer Tests ───────────

@pytest.mark.asyncio
async def test_stateful_vla_loop_deadlock_break(tmp_path: Path):
    audit_file = tmp_path / "SYSTEM_AUDIT.md"

    # Setup loop in dry-run mode
    loop = StatefulVLAExecutionLoop(
        audit_file_path=audit_file,
        dry_run=True,
    )

    # Mock the model client to repeatedly return identical coordinates [500, 500]
    mock_action = VLAAction(
        action_type=ActionType.CLICK,
        target_coord=[500, 500],
        thought="Loop test clicking button"
    )

    with patch.object(loop.model_client, "predict_action", new=AsyncMock(return_value=mock_action)):
        # Execute 3 steps
        action1, status1 = await loop.execute_single_step("Test goal")
        assert status1 == LoopStatus.RUNNING

        action2, status2 = await loop.execute_single_step("Test goal")
        assert status2 == LoopStatus.RUNNING

        # 3rd step must trigger DEADLOCK_DETECTED and break
        action3, status3 = await loop.execute_single_step("Test goal")
        assert status3 == LoopStatus.DEADLOCK_DETECTED


@pytest.mark.asyncio
async def test_visual_settlement_buffer_delay(tmp_path: Path):
    audit_file = tmp_path / "SYSTEM_AUDIT.md"
    loop = StatefulVLAExecutionLoop(
        audit_file_path=audit_file,
        dry_run=True,
    )

    mock_action = VLAAction(
        action_type=ActionType.CLICK,
        target_coord=[100, 200],
        thought="Testing settlement buffer"
    )

    with patch.object(loop.model_client, "predict_action", new=AsyncMock(return_value=mock_action)):
        t_start = time.perf_counter()
        await loop.execute_single_step("Test buffer delay")
        t_elapsed = time.perf_counter() - t_start

        # Visual settlement buffer is 500ms, so execution time must be >= 0.50s
        assert t_elapsed >= 0.48
