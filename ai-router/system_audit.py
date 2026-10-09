"""
HELIOS — Automated System Audit Module (system_audit.py)
Inspects host environment metrics (Display/DPI, Compute/VRAM/RAM/CPU, Ollama/VLA Models)
Generates and maintains a self-updating SYSTEM_AUDIT.md with drift detection and changelog history.
"""

from __future__ import annotations

import ctypes
import dataclasses
from datetime import datetime, timezone
import hashlib
import json
import logging
import os
import platform
import subprocess
import sys
import urllib.error
import urllib.request
from dataclasses import asdict, dataclass, field
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

import psutil

logger = logging.getLogger("helios.vla.system_audit")
logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(name)s: %(message)s")


# ─── Data Contracts ───────────────────────────────────────────────────────────

@dataclass
class MonitorBounds:
    left: int
    top: int
    width: int
    height: int
    is_primary: bool = True
    name: str = "Primary Monitor"


@dataclass
class DisplayMetrics:
    physical_resolution: Tuple[int, int]  # (width, height)
    logical_resolution: Tuple[int, int]   # (width, height)
    dpi: int
    dpi_scaling_factor: float            # e.g., 1.0, 1.25, 1.5, 2.0
    primary_monitor: MonitorBounds
    all_monitors: List[MonitorBounds] = field(default_factory=list)
    multi_monitor: bool = False


@dataclass
class ComputeMemoryBudget:
    gpu_model: str
    gpu_driver_version: str
    gpu_total_vram_mb: float
    gpu_free_vram_mb: float
    total_physical_ram_gb: float
    available_physical_ram_gb: float
    cpu_architecture: str
    cpu_processor: str
    cpu_physical_cores: int
    cpu_logical_cores: int


@dataclass
class InstalledModel:
    name: str
    size_mb: float
    parameter_size: str
    quantization_level: str
    family: str
    capabilities: List[str]
    is_vision: bool
    is_coder: bool


@dataclass
class LocalInferenceRuntime:
    ollama_status: str                   # "RUNNING" or "OFFLINE"
    ollama_endpoint: str
    installed_models: List[InstalledModel] = field(default_factory=list)
    active_vision_models: List[str] = field(default_factory=list)
    active_coder_models: List[str] = field(default_factory=list)
    recommended_vla_model: Optional[str] = None
    python_version: str = field(default_factory=lambda: sys.version.split()[0])
    python_executable: str = field(default_factory=lambda: sys.executable)
    package_versions: Dict[str, str] = field(default_factory=dict)


@dataclass
class AuditReport:
    timestamp_iso: str
    state_hash: str
    display: DisplayMetrics
    compute: ComputeMemoryBudget
    runtime: LocalInferenceRuntime
    changelog: List[str] = field(default_factory=list)


# ─── Host Environment Inspector ───────────────────────────────────────────────

class HostEnvironmentInspector:
    """
    Dynamically interrogates OS, Display Subsystems, Compute/Hardware,
    and Local Inference daemons.
    """

    KEY_PACKAGES = [
        "mss",
        "pyautogui",
        "pillow",
        "psutil",
        "torch",
        "requests",
        "httpx",
        "pynvml",
        "pywin32",
    ]

    def __init__(self, ollama_url: str = "http://localhost:11434"):
        self.ollama_url = ollama_url.rstrip("/")

    # 1. Display & Scaling Metrics ─────────────────────────────────────────────

    def inspect_display(self) -> DisplayMetrics:
        """Query physical and logical display bounds plus OS DPI UI scaling."""
        system_os = platform.system()

        if system_os == "Windows":
            return self._inspect_windows_display()
        elif system_os == "Darwin":
            return self._inspect_macos_display()
        else:
            return self._inspect_linux_display()

    def _inspect_windows_display(self) -> DisplayMetrics:
        # Set DPI awareness for current process to get true physical metrics
        try:
            ctypes.windll.shcore.SetProcessDpiAwareness(2)  # Per-Monitor DPI Aware
        except Exception:
            try:
                ctypes.windll.user32.SetProcessDPIAware()
            except Exception:
                pass

        user32 = ctypes.windll.user32
        gdi32 = ctypes.windll.gdi32

        # Physical resolution via SystemMetrics
        phys_w = int(user32.GetSystemMetrics(0))  # SM_CXSCREEN
        phys_h = int(user32.GetSystemMetrics(1))  # SM_CYSCREEN

        # DPI via GetDpiForSystem or GDI LOGPIXELSX
        dpi = 96
        try:
            dpi = int(user32.GetDpiForSystem())
        except Exception:
            hdc = user32.GetDC(0)
            if hdc:
                dpi = int(gdi32.GetDeviceCaps(hdc, 88))  # LOGPIXELSX
                user32.ReleaseDC(0, hdc)

        scaling_factor = round(dpi / 96.0, 3)

        # Logical resolution
        log_w = int(round(phys_w / scaling_factor)) if scaling_factor > 0 else phys_w
        log_h = int(round(phys_h / scaling_factor)) if scaling_factor > 0 else phys_h

        # Multi-monitor enumeration via mss if available
        monitors: List[MonitorBounds] = []
        try:
            import mss
            sct_cls = getattr(mss, "MSS", getattr(mss, "mss", None))
            with sct_cls() as sct:
                raw_monitors = sct.monitors
                # raw_monitors[0] is the bounding box of ALL monitors combined
                # raw_monitors[1:] are individual physical monitors
                for idx, m in enumerate(raw_monitors[1:], start=1):
                    is_prim = (m.get("left", 0) == 0 and m.get("top", 0) == 0) or m.get("is_primary", False)
                    monitors.append(MonitorBounds(
                        left=m.get("left", 0),
                        top=m.get("top", 0),
                        width=m.get("width", phys_w),
                        height=m.get("height", phys_h),
                        is_primary=bool(is_prim),
                        name=m.get("name", f"Display-{idx}")
                    ))
        except Exception as e:
            logger.debug("mss monitor enumeration fallback: %s", e)

        if not monitors:
            monitors.append(MonitorBounds(
                left=0,
                top=0,
                width=phys_w,
                height=phys_h,
                is_primary=True,
                name="Primary Monitor"
            ))

        primary = next((m for m in monitors if m.is_primary), monitors[0])

        return DisplayMetrics(
            physical_resolution=(phys_w, phys_h),
            logical_resolution=(log_w, log_h),
            dpi=dpi,
            dpi_scaling_factor=scaling_factor,
            primary_monitor=primary,
            all_monitors=monitors,
            multi_monitor=len(monitors) > 1
        )

    def _inspect_macos_display(self) -> DisplayMetrics:
        # Fallback for macOS via system_profiler or default
        scale = 1.0
        width, height = 1920, 1080
        try:
            from AppKit import NSScreen
            main_screen = NSScreen.mainScreen()
            if main_screen:
                scale = float(main_screen.backingScaleFactor())
                frame = main_screen.frame()
                width = int(frame.size.width * scale)
                height = int(frame.size.height * scale)
        except Exception:
            pass

        primary = MonitorBounds(left=0, top=0, width=width, height=height, is_primary=True, name="Main Screen")
        return DisplayMetrics(
            physical_resolution=(width, height),
            logical_resolution=(int(width / scale), int(height / scale)),
            dpi=int(96 * scale),
            dpi_scaling_factor=scale,
            primary_monitor=primary,
            all_monitors=[primary],
            multi_monitor=False
        )

    def _inspect_linux_display(self) -> DisplayMetrics:
        # Fallback for Linux
        width, height = 1920, 1080
        scale = 1.0
        try:
            out = subprocess.check_output(["xrandr", "--current"], text=True)
            for line in out.splitlines():
                if " connected primary " in line or (" connected " in line and "x" in line):
                    parts = line.split()
                    for p in parts:
                        if "+" in p and "x" in p:
                            res = p.split("+")[0].split("x")
                            width, height = int(res[0]), int(res[1])
                            break
        except Exception:
            pass

        primary = MonitorBounds(left=0, top=0, width=width, height=height, is_primary=True, name="Default")
        return DisplayMetrics(
            physical_resolution=(width, height),
            logical_resolution=(width, height),
            dpi=96,
            dpi_scaling_factor=scale,
            primary_monitor=primary,
            all_monitors=[primary],
            multi_monitor=False
        )

    # 2. Compute & Memory Budget ───────────────────────────────────────────────

    def inspect_compute_budget(self) -> ComputeMemoryBudget:
        """Inspect GPU VRAM, System RAM, and CPU Cores."""
        gpu_model = "Unknown GPU"
        gpu_driver = "Unknown"
        gpu_total_vram = 0.0
        gpu_free_vram = 0.0

        # Try pynvml first (NVIDIA)
        nvml_success = False
        try:
            import pynvml
            pynvml.nvmlInit()
            device_count = pynvml.nvmlDeviceGetCount()
            if device_count > 0:
                handle = pynvml.nvmlDeviceGetHandleByIndex(0)
                gpu_model = pynvml.nvmlDeviceGetName(handle)
                if isinstance(gpu_model, bytes):
                    gpu_model = gpu_model.decode("utf-8")
                gpu_driver = pynvml.nvmlSystemGetDriverVersion()
                if isinstance(gpu_driver, bytes):
                    gpu_driver = gpu_driver.decode("utf-8")
                mem_info = pynvml.nvmlDeviceGetMemoryInfo(handle)
                gpu_total_vram = round(mem_info.total / (1024 * 1024), 2)
                gpu_free_vram = round(mem_info.free / (1024 * 1024), 2)
                nvml_success = True
        except Exception:
            pass

        # Try torch.cuda next
        if not nvml_success:
            try:
                import torch
                if torch.cuda.is_available():
                    gpu_model = torch.cuda.get_device_name(0)
                    free_b, total_b = torch.cuda.mem_get_info(0)
                    gpu_total_vram = round(total_b / (1024 * 1024), 2)
                    gpu_free_vram = round(free_b / (1024 * 1024), 2)
                    nvml_success = True
            except Exception:
                pass

        # Windows WMI / VideoController fallback for Intel/AMD/DirectX
        if not nvml_success and platform.system() == "Windows":
            try:
                cmd = [
                    "powershell",
                    "-NoProfile",
                    "-Command",
                    "Get-CimInstance Win32_VideoController | Select-Object Name, AdapterRAM, DriverVersion | ConvertTo-Json"
                ]
                res = subprocess.run(cmd, capture_output=True, text=True, timeout=5)
                if res.returncode == 0 and res.stdout.strip():
                    data = json.loads(res.stdout)
                    item = data[0] if isinstance(data, list) else data
                    gpu_model = item.get("Name", gpu_model)
                    gpu_driver = str(item.get("DriverVersion", gpu_driver))
                    adapter_ram = float(item.get("AdapterRAM", 0) or 0)
                    gpu_total_vram = round(adapter_ram / (1024 * 1024), 2)
                    # For shared system memory, estimate free VRAM proportional to available RAM
                    vm = psutil.virtual_memory()
                    gpu_free_vram = round((vm.available / vm.total) * gpu_total_vram, 2) if gpu_total_vram > 0 else 0.0
            except Exception as e:
                logger.debug("Windows VideoController query exception: %s", e)

        # System RAM
        vm = psutil.virtual_memory()
        total_ram = round(vm.total / (1024 ** 3), 2)
        avail_ram = round(vm.available / (1024 ** 3), 2)

        # CPU Cores
        phys_cores = psutil.cpu_count(logical=False) or 1
        log_cores = psutil.cpu_count(logical=True) or 1
        cpu_arch = platform.machine()
        cpu_proc = platform.processor() or platform.machine()

        return ComputeMemoryBudget(
            gpu_model=gpu_model,
            gpu_driver_version=gpu_driver,
            gpu_total_vram_mb=gpu_total_vram,
            gpu_free_vram_mb=gpu_free_vram,
            total_physical_ram_gb=total_ram,
            available_physical_ram_gb=avail_ram,
            cpu_architecture=cpu_arch,
            cpu_processor=cpu_proc,
            cpu_physical_cores=phys_cores,
            cpu_logical_cores=log_cores,
        )

    # 3. Local Inference Runtime ───────────────────────────────────────────────

    def inspect_local_runtime(self) -> LocalInferenceRuntime:
        """Query Ollama daemon and local installed packages."""
        models: List[InstalledModel] = []
        ollama_status = "OFFLINE"
        active_vision: List[str] = []
        active_coder: List[str] = []
        rec_model: Optional[str] = None

        try:
            req = urllib.request.Request(f"{self.ollama_url}/api/tags", headers={"User-Agent": "HELIOS-VLA"})
            with urllib.request.urlopen(req, timeout=2.5) as resp:
                if resp.status == 200:
                    ollama_status = "RUNNING"
                    payload = json.loads(resp.read().decode("utf-8"))
                    raw_models = payload.get("models", [])

                    for m in raw_models:
                        name = m.get("name", "")
                        size_mb = round(m.get("size", 0) / (1024 * 1024), 2)
                        details = m.get("details", {})
                        param_size = details.get("parameter_size", "unknown")
                        quant = details.get("quantization_level", "unknown")
                        family = details.get("family", "")
                        caps = m.get("capabilities", [])

                        # Classify Vision and Coder models
                        name_lower = name.lower()
                        is_vision = (
                            "vision" in caps
                            or any(token in name_lower for token in ["vl", "vision", "uitars", "ui-tars", "moondream", "gemma4"])
                            or any(token in family.lower() for token in ["vl", "clip"])
                        )
                        is_coder = (
                            "coder" in name_lower
                            or "code" in name_lower
                            or any(token in family.lower() for token in ["code", "coder"])
                        )

                        model_obj = InstalledModel(
                            name=name,
                            size_mb=size_mb,
                            parameter_size=param_size,
                            quantization_level=quant,
                            family=family,
                            capabilities=caps,
                            is_vision=is_vision,
                            is_coder=is_coder,
                        )
                        models.append(model_obj)

                        if is_vision:
                            active_vision.append(name)
                        if is_coder:
                            active_coder.append(name)

                    # Determine best recommended model
                    # Prioritize UI-TARS or Qwen-VL or Qwen3.5-VL
                    for candidate in ["ui-tars", "qwen3-vl", "qwen2.5vl", "qwen3.5", "gemma4", "moondream"]:
                        for v in active_vision:
                            if candidate in v.lower():
                                rec_model = v
                                break
                        if rec_model:
                            break
                    if not rec_model and active_vision:
                        rec_model = active_vision[0]
        except Exception as e:
            logger.debug("Ollama daemon query failed: %s", e)
            ollama_status = "OFFLINE"

        # Check installed packages
        packages: Dict[str, str] = {}
        for pkg in self.KEY_PACKAGES:
            try:
                import importlib.metadata
                packages[pkg] = importlib.metadata.version(pkg)
            except Exception:
                try:
                    mod = __import__(pkg)
                    packages[pkg] = getattr(mod, "__version__", "installed")
                except Exception:
                    packages[pkg] = "not installed"

        return LocalInferenceRuntime(
            ollama_status=ollama_status,
            ollama_endpoint=self.ollama_url,
            installed_models=models,
            active_vision_models=active_vision,
            active_coder_models=active_coder,
            recommended_vla_model=rec_model,
            python_version=sys.version.split()[0],
            python_executable=sys.executable,
            package_versions=packages,
        )

    # 4. Composite State Hash ──────────────────────────────────────────────────

    def compute_state_hash(
        self,
        display: DisplayMetrics,
        compute: ComputeMemoryBudget,
        runtime: LocalInferenceRuntime,
    ) -> str:
        """
        Computes a composite hash of display settings (resolution, scaling),
        connected hardware, virtual environment packages, and local Ollama models.
        """
        canonical_state = {
            "display": {
                "physical_resolution": list(display.physical_resolution),
                "logical_resolution": list(display.logical_resolution),
                "dpi": display.dpi,
                "dpi_scaling_factor": display.dpi_scaling_factor,
                "primary_monitor": asdict(display.primary_monitor),
                "monitor_count": len(display.all_monitors),
            },
            "hardware": {
                "cpu_architecture": compute.cpu_architecture,
                "cpu_physical_cores": compute.cpu_physical_cores,
                "cpu_logical_cores": compute.cpu_logical_cores,
                "total_ram_gb": round(compute.total_physical_ram_gb, 1),
                "gpu_model": compute.gpu_model,
                "gpu_driver": compute.gpu_driver_version,
            },
            "packages": sorted(runtime.package_versions.items()),
            "models": sorted([
                (m.name, m.parameter_size, m.quantization_level)
                for m in runtime.installed_models
            ]),
            "ollama_status": runtime.ollama_status,
        }

        raw_json = json.dumps(canonical_state, sort_keys=True)
        return hashlib.sha256(raw_json.encode("utf-8")).hexdigest()

    def generate_full_report(self, existing_changelog: Optional[List[str]] = None) -> AuditReport:
        """Inspects all domains and compiles a full AuditReport."""
        disp = self.inspect_display()
        comp = self.inspect_compute_budget()
        rt = self.inspect_local_runtime()
        h = self.compute_state_hash(disp, comp, rt)
        iso_time = datetime.now(timezone.utc).astimezone().isoformat()

        return AuditReport(
            timestamp_iso=iso_time,
            state_hash=h,
            display=disp,
            compute=comp,
            runtime=rt,
            changelog=existing_changelog or [],
        )


# ─── Markdown Document Formatter ──────────────────────────────────────────────

class MarkdownAuditFormatter:
    """Renders structured, human-readable, and machine-traceable SYSTEM_AUDIT.md."""

    HASH_TAG_PREFIX = "<!-- CACHED_STATE_HASH:"

    @classmethod
    def render(cls, report: AuditReport) -> str:
        d = report.display
        c = report.compute
        r = report.runtime

        lines: List[str] = [
            "# HELIOS System & VLA Environment Audit",
            "",
            f"{cls.HASH_TAG_PREFIX} {report.state_hash} -->",
            f"> **Last Synchronized:** `{report.timestamp_iso}`  ",
            f"> **Composite State Hash:** `{report.state_hash}`  ",
            f"> **VLA Readiness:** `{'READY (Local Vision Models Detected)' if r.active_vision_models else 'DEGRADED (No Vision Models Active)'}`",
            "",
            "---",
            "",
            "## 1. Display & Scaling Metrics",
            "",
            "| Parameter | Verified Value | Description / Coordinates |",
            "| :--- | :--- | :--- |",
            f"| **Physical Resolution** | `{d.physical_resolution[0]} x {d.physical_resolution[1]}` | True native panel framebuffer resolution |",
            f"| **Logical / Virtual Resolution** | `{d.logical_resolution[0]} x {d.logical_resolution[1]}` | OS viewport coordinates passed to standard window APIs |",
            f"| **OS DPI UI Scaling Factor** | **`{d.dpi_scaling_factor}x`** (`{d.dpi} DPI`) | Active scaling queried via `ctypes` / Win32 API |",
            f"| **Primary Monitor Bounds** | `left={d.primary_monitor.left}, top={d.primary_monitor.top}, w={d.primary_monitor.width}, h={d.primary_monitor.height}` | Primary display viewport boundaries |",
            f"| **Multi-Monitor Setup** | `{'Yes (' + str(len(d.all_monitors)) + ' Displays)' if d.multi_monitor else 'Single Display'}` | Multi-display active arrangement |",
            "",
            "### Detailed Monitor Map",
        ]

        for i, mon in enumerate(d.all_monitors, start=1):
            lines.append(f"- **Display {i}** (`{mon.name}`): `left={mon.left}, top={mon.top}, width={mon.width}, height={mon.height}`, Primary: `{mon.is_primary}`")

        lines.extend([
            "",
            "---",
            "",
            "## 2. Compute & Memory Budget",
            "",
            "| Component | Specification | Allocation / Status |",
            "| :--- | :--- | :--- |",
            f"| **GPU Model** | `{c.gpu_model}` | Video graphics accelerator |",
            f"| **GPU Driver Version** | `{c.gpu_driver_version}` | Driver revision queried via hardware provider |",
            f"| **GPU Total VRAM** | `{c.gpu_total_vram_mb:.1f} MB` | Dedicated/Shared memory budget |",
            f"| **GPU Free VRAM** | `{c.gpu_free_vram_mb:.1f} MB` | Immediately accessible for model offload |",
            f"| **Physical System RAM** | `{c.total_physical_ram_gb:.2f} GB Total` | Available: `{c.available_physical_ram_gb:.2f} GB` |",
            f"| **CPU Architecture** | `{c.cpu_architecture}` | Processor: `{c.cpu_processor}` |",
            f"| **CPU Core Topology** | `{c.cpu_physical_cores} Physical / {c.cpu_logical_cores} Logical` | Core count for preprocessing & Lanczos scaling |",
            "",
            "---",
            "",
            "## 3. Local Inference Runtime",
            "",
            f"- **Ollama Daemon Status:** `{'ONLINE (' + r.ollama_endpoint + ')' if r.ollama_status == 'RUNNING' else 'OFFLINE'}`",
            f"- **Active Vision / VLA Models:** `{', '.join(r.active_vision_models) if r.active_vision_models else 'None found'}`",
            f"- **Active Coder Models:** `{', '.join(r.active_coder_models) if r.active_coder_models else 'None found'}`",
            f"- **Recommended Model for VLA:** **`{r.recommended_vla_model or 'None'}`**",
            f"- **Python Runtime:** `{r.python_version}` (`{r.python_executable}`)",
            "",
            "### Critical Package Dependencies",
            "",
            "| Package | Installed Version | Status |",
            "| :--- | :--- | :--- |",
        ])

        for pkg, ver in sorted(r.package_versions.items()):
            status = "Installed" if ver != "not installed" else "Missing"
            lines.append(f"| `{pkg}` | `{ver}` | {status} |")

        lines.extend([
            "",
            "### Local Models Inventory",
            "",
            "| Model Tag | Size (MB) | Params | Quant | Capabilities | Role |",
            "| :--- | :--- | :--- | :--- | :--- | :--- |",
        ])

        if r.installed_models:
            for m in r.installed_models:
                role = "Vision (VLA)" if m.is_vision else ("Coder" if m.is_coder else "General")
                caps = ", ".join(m.capabilities) if m.capabilities else "completion"
                lines.append(f"| `{m.name}` | `{m.size_mb:.1f}` | `{m.parameter_size}` | `{m.quantization_level}` | `{caps}` | **{role}** |")
        else:
            lines.append("| *No models found in Ollama daemon* | - | - | - | - | - |")

        lines.extend([
            "",
            "---",
            "",
            "## 4. Active VLA Normalization Constants",
            "",
            "The following runtime constants are used by the coordinate normalization engine:",
            "```python",
            f"OS_DPI_SCALE = {d.dpi_scaling_factor}",
            f"NATIVE_RESOLUTION = ({d.physical_resolution[0]}, {d.physical_resolution[1]})",
            f"PRIMARY_OFFSET = ({d.primary_monitor.left}, {d.primary_monitor.top})",
            "MAX_INFERENCE_HEIGHT = 1080",
            "POST_ACTION_SETTLEMENT_DELAY_MS = 500",
            "DEADLOCK_RADIUS_PX = 5",
            "```",
            "",
            "---",
            "",
            "## 5. Audit History / Changelog",
            "",
        ])

        if report.changelog:
            for entry in report.changelog:
                lines.append(f"- {entry}")
        else:
            lines.append(f"- `[{report.timestamp_iso}]` Baseline system audit generated with hash `{report.state_hash[:12]}`.")

        lines.append("")
        return "\n".join(lines)


# ─── Audit Synchronization Manager (Auto-Update & Drift Hook) ─────────────────

class AuditSyncManager:
    """
    Guarantees SYSTEM_AUDIT.md never becomes stale.
    Performs composite state hashing, detects drift, regenerates markdown,
    appends timestamped changelog entries, and updates in-memory parameters.
    """

    def __init__(
        self,
        audit_file_path: Optional[Path] = None,
        ollama_url: str = "http://localhost:11434"
    ):
        if audit_file_path is None:
            # Check current working dir first, then parent directory, then ai-router
            cwd_cand = Path("SYSTEM_AUDIT.md").resolve()
            parent_cand = (Path(__file__).resolve().parent.parent / "SYSTEM_AUDIT.md").resolve()
            local_cand = (Path(__file__).resolve().parent / "SYSTEM_AUDIT.md").resolve()
            if cwd_cand.exists():
                audit_file_path = cwd_cand
            elif parent_cand.exists():
                audit_file_path = parent_cand
            elif local_cand.exists():
                audit_file_path = local_cand
            else:
                audit_file_path = cwd_cand

        self.audit_file_path = Path(audit_file_path).resolve()
        self.inspector = HostEnvironmentInspector(ollama_url=ollama_url)
        self.current_report: Optional[AuditReport] = None
        self._cached_scaling_factor: float = 1.0

    @property
    def active_scaling_factor(self) -> float:
        return self._cached_scaling_factor

    def read_cached_state(self) -> Tuple[Optional[str], List[str]]:
        """Reads cached state hash and existing changelog from SYSTEM_AUDIT.md."""
        if not self.audit_file_path.exists():
            return None, []

        try:
            content = self.audit_file_path.read_text(encoding="utf-8")
        except Exception as e:
            logger.warning("Could not read existing audit file: %s", e)
            return None, []

        cached_hash = None
        for line in content.splitlines():
            if line.startswith(MarkdownAuditFormatter.HASH_TAG_PREFIX):
                parts = line.replace(MarkdownAuditFormatter.HASH_TAG_PREFIX, "").replace("-->", "").strip()
                cached_hash = parts
                break

        changelog: List[str] = []
        in_changelog = False
        for line in content.splitlines():
            if line.startswith("## 5. Audit History / Changelog"):
                in_changelog = True
                continue
            if in_changelog:
                if line.startswith("## "):
                    break
                if line.strip().startswith("- "):
                    changelog.append(line.strip()[2:])

        return cached_hash, changelog

    def check_and_sync(self, force: bool = False) -> Tuple[bool, AuditReport]:
        """
        Executes non-blocking environment drift check.
        Returns:
            (has_drifted: bool, report: AuditReport)
        """
        cached_hash, changelog = self.read_cached_state()
        new_report = self.inspector.generate_full_report(existing_changelog=changelog)

        drift_detected = force or (cached_hash is None) or (cached_hash != new_report.state_hash)

        if drift_detected:
            # Formulate changelog message
            iso_now = new_report.timestamp_iso
            if cached_hash is None:
                change_desc = f"`[{iso_now}]` Baseline initialization. Recorded `{new_report.display.physical_resolution[0]}x{new_report.display.physical_resolution[1]}` @ `{new_report.display.dpi_scaling_factor}x` DPI scale. Found {len(new_report.runtime.installed_models)} models."
            else:
                change_desc = f"`[{iso_now}]` Environment drift detected (`{cached_hash[:8]}` → `{new_report.state_hash[:8]}`). Refreshed display ({new_report.display.physical_resolution[0]}x{new_report.display.physical_resolution[1]} @ {new_report.display.dpi_scaling_factor}x) & model catalog."

            new_report.changelog.append(change_desc)

            # Render and write
            rendered_md = MarkdownAuditFormatter.render(new_report)
            self.audit_file_path.parent.mkdir(parents=True, exist_ok=True)
            self.audit_file_path.write_text(rendered_md, encoding="utf-8")
            logger.info("SYSTEM_AUDIT.md updated at %s (Hash: %s)", self.audit_file_path, new_report.state_hash[:8])
        else:
            logger.debug("SYSTEM_AUDIT.md is up-to-date (Hash: %s)", new_report.state_hash[:8])

        self.current_report = new_report
        self._cached_scaling_factor = new_report.display.dpi_scaling_factor
        return drift_detected, new_report


# ─── Singleton & Convenience Entry Points ──────────────────────────────────────

_global_sync_manager: Optional[AuditSyncManager] = None


def get_audit_manager(audit_file_path: Optional[Path] = None) -> AuditSyncManager:
    global _global_sync_manager
    if _global_sync_manager is None:
        _global_sync_manager = AuditSyncManager(audit_file_path=audit_file_path)
    return _global_sync_manager


def run_audit(audit_file_path: Optional[Path] = None, force: bool = False) -> AuditReport:
    """Runs a system audit and syncs the audit file."""
    mgr = get_audit_manager(audit_file_path=audit_file_path)
    _, report = mgr.check_and_sync(force=force)
    return report


if __name__ == "__main__":
    import argparse
    parser = argparse.ArgumentParser(description="HELIOS VLA System Audit Engine")
    parser.add_argument("--output", "-o", default="SYSTEM_AUDIT.md", help="Path to SYSTEM_AUDIT.md")
    parser.add_argument("--force", "-f", action="store_true", help="Force regeneration of audit file")
    args = parser.parse_args()

    out_path = Path(args.output).resolve()
    print(f"[*] Running Host Environment Inspection (Target: {out_path})...")
    manager = AuditSyncManager(audit_file_path=out_path)
    drift, rep = manager.check_and_sync(force=args.force)
    print(f"[+] Audit Complete!")
    print(f"    - State Hash: {rep.state_hash}")
    print(f"    - Display: {rep.display.physical_resolution[0]}x{rep.display.physical_resolution[1]} @ {rep.display.dpi_scaling_factor}x DPI scale")
    print(f"    - GPU: {rep.compute.gpu_model} (VRAM: {rep.compute.gpu_total_vram_mb} MB)")
    print(f"    - Ollama Status: {rep.runtime.ollama_status} ({len(rep.runtime.installed_models)} models installed)")
    print(f"    - Recommended VLA Model: {rep.runtime.recommended_vla_model}")
    print(f"    - Audit Written To: {out_path}")
