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
    "gpu_entry_8gb_vram": {
        "min_ram_gb": 16, "min_vram_gb": 6,
        "max_model_size_gb": 10, "recommended_context": 8192, "max_simultaneous_models": 2
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
    """Detects system hardware and returns a HardwareProfile instance."""
    os_name = platform.system()
    os_version = platform.release()
    cpu_name = platform.processor() or "Unknown"
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

    # a. Try nvidia-smi
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

    # b. Try WMI via powershell
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

    # c. Try torch.cuda
    if not gpu_present:
        try:
            import torch
            if torch.cuda.is_available():
                gpu_present = True
                gpu_vendor = "nvidia"
                gpu_name = torch.cuda.get_device_name(0)
                gpu_vram_gb = torch.cuda.get_device_properties(0).total_memory / (1024 ** 3)
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
