import logging
import platform
import subprocess
import json
import os
import shutil
from dataclasses import dataclass, asdict
import psutil

logger = logging.getLogger(__name__)

@dataclass
class HardwareProfile:
    """Dataclass representing the hardware profile of the system."""
    os_name: str
    os_version: str
    cpu_name: str
    cpu_cores_physical: int
    cpu_cores_logical: int
    ram_total_gb: float
    ram_available_gb: float
    gpu_present: bool
    gpu_vendor: str
    gpu_name: str
    gpu_vram_gb: float
    disk_free_gb: float

TIER_THRESHOLDS = {
    "gpu_workstation_16gb_plus": {
        "min_ram_gb": 16, "min_vram_gb": 16,
        "max_model_size_gb": 20, "recommended_context": 16384, "max_simultaneous_models": 3
    },
    "apple_silicon_unified_16gb_plus": {
        "min_ram_gb": 16, "min_vram_gb": 10,
        "max_model_size_gb": 14, "recommended_context": 8192, "max_simultaneous_models": 2
    },
    "gpu_entry_8gb_vram": {
        "min_ram_gb": 16, "min_vram_gb": 6,
        "max_model_size_gb": 10, "recommended_context": 8192, "max_simultaneous_models": 2
    },
    "workstation_cpu_32gb_plus": {
        "min_ram_gb": 28, "min_vram_gb": 0,
        "max_model_size_gb": 8, "recommended_context": 8192, "max_simultaneous_models": 2
    },
    "balanced_cpu_16gb": {
        "min_ram_gb": 12, "min_vram_gb": 0,
        "max_model_size_gb": 5, "recommended_context": 4096, "max_simultaneous_models": 1
    },
    "budget_cpu_8gb": {
        "min_ram_gb": 0, "min_vram_gb": 0,
        "max_model_size_gb": 2.5, "recommended_context": 2048, "max_simultaneous_models": 1
    },
}

def detect_hardware() -> HardwareProfile:
    """Detects system hardware across Windows, macOS, and Linux."""
    os_name = platform.system()
    os_version = platform.release()
    cpu_name = platform.processor() or "Unknown"

    # Refine CPU name on macOS or Linux if generic
    if os_name == "Darwin":
        try:
            res = subprocess.run(['sysctl', '-n', 'machdep.cpu.brand_string'], capture_output=True, text=True, timeout=2)
            if res.returncode == 0 and res.stdout.strip():
                cpu_name = res.stdout.strip()
        except Exception:
            pass
    elif os_name == "Linux" and (cpu_name in ("Unknown", "", "x86_64", "aarch64")):
        try:
            with open("/proc/cpuinfo", "r", encoding="utf-8") as f:
                for line in f:
                    if line.startswith("model name"):
                        cpu_name = line.split(":", 1)[1].strip()
                        break
        except Exception:
            pass

    cpu_cores_physical = psutil.cpu_count(logical=False) or 0
    cpu_cores_logical = psutil.cpu_count(logical=True) or 0
    
    vm = psutil.virtual_memory()
    ram_total_gb = vm.total / (1024 ** 3)
    ram_available_gb = vm.available / (1024 ** 3)
    
    # Disk free space on the drive where this file resides
    current_drive = os.path.splitdrive(os.path.abspath(__file__))[0] or "/"
    try:
        disk_usage = shutil.disk_usage(current_drive)
        disk_free_gb = disk_usage.free / (1024 ** 3)
    except Exception as e:
        logger.warning(f"Could not get disk usage for {current_drive}: {e}")
        disk_free_gb = 0.0

    gpu_present = False
    gpu_vendor = "none"
    gpu_name = "Unknown"
    gpu_vram_gb = 0.0

    # a. Try nvidia-smi (cross-platform: Linux & Windows)
    try:
        result = subprocess.run(
            ['nvidia-smi', '--query-gpu=name,memory.total', '--format=csv,noheader,nounits'],
            capture_output=True, text=True, timeout=5
        )
        if result.returncode == 0 and result.stdout.strip():
            parts = result.stdout.strip().split(',', 1)
            if len(parts) == 2:
                gpu_name = parts[0].strip()
                gpu_vram_gb = float(parts[1].strip()) / 1024.0
                gpu_vendor = "nvidia"
                gpu_present = True
    except Exception as e:
        logger.debug(f"nvidia-smi check failed: {e}")

    # b. Try Apple Silicon unified memory GPU (macOS M1/M2/M3/M4)
    if not gpu_present and os_name == "Darwin":
        machine = platform.machine().lower()
        if "arm" in machine or "aarch64" in machine or "apple" in cpu_name.lower():
            gpu_present = True
            gpu_vendor = "apple"
            gpu_name = cpu_name if "apple" in cpu_name.lower() else f"Apple Silicon ({machine})"
            # Apple unified memory: up to ~75% can be allocated for Metal/GPU inference
            gpu_vram_gb = round(ram_total_gb * 0.75, 1)

    # c. Try WMI via powershell on Windows
    if not gpu_present and os_name == "Windows":
        try:
            result = subprocess.run(
                ['powershell', '-Command', 'Get-CimInstance Win32_VideoController | Select-Object Name,AdapterRAM | ConvertTo-Json'],
                capture_output=True, text=True, timeout=5
            )
            if result.returncode == 0 and result.stdout.strip():
                data = json.loads(result.stdout.strip())
                if isinstance(data, list):
                    data = data[0]
                
                if isinstance(data, dict):
                    name = data.get("Name", "Unknown")
                    ram = data.get("AdapterRAM")
                    if ram is not None:
                        gpu_name = name
                        gpu_vram_gb = float(ram) / (1024 ** 3)
                        gpu_present = True
                        
                        lower_name = name.lower()
                        if "nvidia" in lower_name:
                            gpu_vendor = "nvidia"
                        elif "amd" in lower_name or "radeon" in lower_name:
                            gpu_vendor = "amd"
                        elif "intel" in lower_name:
                            gpu_vendor = "intel"
                        else:
                            gpu_vendor = "unknown"
        except Exception as e:
            logger.debug(f"WMI GPU check failed: {e}")

    # d. Try Linux AMD ROCm (rocm-smi) or lspci
    if not gpu_present and os_name == "Linux":
        try:
            result = subprocess.run(['rocm-smi', '--showmeminfo', 'vram'], capture_output=True, text=True, timeout=3)
            if result.returncode == 0:
                gpu_present = True
                gpu_vendor = "amd"
                gpu_name = "AMD Radeon GPU (ROCm)"
                gpu_vram_gb = 8.0  # safe default fallback
        except Exception:
            pass

    # e. Try torch CUDA / MPS
    if not gpu_present:
        try:
            import torch
            if torch.cuda.is_available():
                gpu_present = True
                gpu_vendor = "nvidia"
                gpu_name = torch.cuda.get_device_name(0)
                gpu_vram_gb = torch.cuda.get_device_properties(0).total_memory / (1024 ** 3)
            elif hasattr(torch.backends, "mps") and torch.backends.mps.is_available():
                gpu_present = True
                gpu_vendor = "apple"
                gpu_name = "Apple Metal (MPS)"
                gpu_vram_gb = round(ram_total_gb * 0.75, 1)
        except Exception as e:
            logger.debug(f"torch GPU check failed: {e}")

    return HardwareProfile(
        os_name=os_name,
        os_version=os_version,
        cpu_name=cpu_name,
        cpu_cores_physical=cpu_cores_physical,
        cpu_cores_logical=cpu_cores_logical,
        ram_total_gb=ram_total_gb,
        ram_available_gb=ram_available_gb,
        gpu_present=gpu_present,
        gpu_vendor=gpu_vendor,
        gpu_name=gpu_name,
        gpu_vram_gb=gpu_vram_gb,
        disk_free_gb=disk_free_gb
    )

def classify_tier(profile: HardwareProfile) -> tuple[str, dict]:
    """
    Classifies the hardware profile into a tier based on TIER_THRESHOLDS.
    Checks tiers in order from highest to lowest.
    Returns:
        tuple[str, dict]: (tier_name, tier_limits_dict)
    """
    for tier_name, limits in TIER_THRESHOLDS.items():
        if profile.ram_total_gb >= limits["min_ram_gb"] and profile.gpu_vram_gb >= limits["min_vram_gb"]:
            return tier_name, limits
            
    # Default to lowest if nothing matches
    lowest_tier = list(TIER_THRESHOLDS.keys())[-1]
    return lowest_tier, TIER_THRESHOLDS[lowest_tier]

def get_hardware_summary() -> dict:
    """Returns a summarized dictionary of the hardware profile and its tier classification."""
    profile = detect_hardware()
    tier_name, tier_limits = classify_tier(profile)
    
    summary = asdict(profile)
    summary["tier"] = tier_name
    summary["tier_limits"] = tier_limits
    return summary


def get_tts_resource_profile() -> dict:
    """
    Evaluates hardware specifically for TTS inference:
    CUDA availability, VRAM capability, recommended TTS backend, and RAM staging budget.
    """
    profile = detect_hardware()
    cuda_available = False
    cuda_device = "cpu"
    try:
        import torch
        cuda_available = torch.cuda.is_available()
        if cuda_available:
            cuda_device = "cuda"
    except ImportError:
        pass

    # High-VRAM workstation
    if profile.gpu_vram_gb >= 12.0 and profile.ram_total_gb >= 32.0:
        recommended_tts = "gpt_sovits"
        ram_staging_gb = 32.0
    elif profile.gpu_vram_gb >= 6.0 and profile.ram_total_gb >= 16.0:
        recommended_tts = "gpt_sovits"
        ram_staging_gb = 16.0
    else:
        # Integrated graphics or low VRAM/RAM: Kokoro ONNX is ideal
        recommended_tts = "kokoro"
        ram_staging_gb = 4.0

    return {
        "recommended_backend": recommended_tts,
        "cuda_available": cuda_available,
        "device": cuda_device,
        "gpu_name": profile.gpu_name,
        "gpu_vendor": profile.gpu_vendor,
        "vram_gb": round(profile.gpu_vram_gb, 2),
        "ram_total_gb": round(profile.ram_total_gb, 2),
        "ram_available_gb": round(profile.ram_available_gb, 2),
        "ram_staging_budget_gb": ram_staging_gb,
    }


def get_cluster_hardware_summary() -> dict:
    """
    Returns unified cluster telemetry covering:
    1. Local controller machine specs & utilization
    2. Remote NVIDIA PAIR GPU node specs & live status
    3. Aggregated cluster computing capacity
    """
    local = get_hardware_summary()
    
    ai_pc_status = {}
    try:
        from core.ai_pc_manager import get_ai_pc_node_status
        ai_pc_status = get_ai_pc_node_status(timeout=1.0)
    except Exception as e:
        ai_pc_status = {"reachable": False, "error": str(e)}

    ai_pc_online = ai_pc_status.get("reachable", False)
    ai_pc_vram = 16.0 if ai_pc_online else 0.0
    ai_pc_ram = 64.0 if ai_pc_online else 0.0

    return {
        "cluster_online": True,
        "nodes": {
            "local_controller": local,
            "ai_pc_gpu_node": ai_pc_status,
        },
        "aggregate_capacity": {
            "total_ram_gb": round(local.get("ram_total_gb", 0) + ai_pc_ram, 1),
            "total_vram_gb": round(local.get("gpu_vram_gb", 0) + ai_pc_vram, 1),
            "total_logical_cores": local.get("cpu_cores_logical", 0) + (12 if ai_pc_online else 0),
            "ai_pc_available": ai_pc_online,
        }
    }

