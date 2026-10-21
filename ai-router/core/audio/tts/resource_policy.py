"""
HELIOS Central Resource Manager
Intelligent Unified RAM/VRAM resource tiering, arbitration, and model residency management.
Optimized for high-VRAM GPU workstations (e.g. RTX 5060 Ti 16 GB + 64 GB RAM) and dynamically
scalable down to integrated GPUs and CPU-only systems.
"""
import os
import time
import logging
import psutil
from enum import Enum
from typing import Dict, Any, Optional, List, Tuple
from dataclasses import dataclass, field
import yaml

from core.hardware_profiler import detect_hardware, classify_tier, HardwareProfile
from core.audio.tts.base import ModelResidencyState

logger = logging.getLogger(__name__)


class MemoryPressure(str, Enum):
    """System memory pressure levels."""
    NORMAL = "NORMAL"
    ELEVATED = "ELEVATED"
    HIGH = "HIGH"
    CRITICAL = "CRITICAL"


@dataclass
class ModelResourceEntry:
    """Metadata for a model managed across RAM/VRAM tiers."""
    model_id: str
    subsystem: str               # 'tts', 'llm', 'vision', 'embeddings'
    residency_state: ModelResidencyState
    ram_size_mb: float = 0.0
    vram_size_mb: float = 0.0
    last_active_time: float = field(default_factory=time.time)
    demote_handler: Optional[Any] = None
    promote_handler: Optional[Any] = None
    unload_handler: Optional[Any] = None


class ResourceManager:
    """
    Central resource manager arbitrating VRAM and RAM allocation across HELIOS AI services.
    Enforces non-destructive tiering:
      SSD -> System RAM (cache/staging) -> GPU VRAM (active tensors)
    Never evicts an active generation and preserves an OS/application memory safety buffer.
    """

    _instance = None

    def __new__(cls, *args, **kwargs):
        if cls._instance is None:
            cls._instance = super(ResourceManager, cls).__new__(cls)
            cls._instance._initialized = False
        return cls._instance

    def __init__(self, config_path: Optional[str] = None):
        if self._initialized:
            return
        self._initialized = True
        self.config_path = config_path or os.environ.get("RESOURCES_CONFIG_PATH", "config/resources.yaml")
        self.config = self._load_config()

        # Hardware profiling
        self.hw_profile: HardwareProfile = detect_hardware()
        self.tier_name, self.tier_limits = classify_tier(self.hw_profile)

        # PyTorch / CUDA detection
        self._torch_cuda_available = False
        try:
            import torch
            self._torch_cuda_available = torch.cuda.is_available()
        except ImportError:
            pass

        # Registered models and LRU cache
        self._models: Dict[str, ModelResourceEntry] = {}
        self._allocated_vram_mb: float = 0.0
        self._allocated_ram_cache_mb: float = 0.0
        self._is_llm_active: bool = False

        # Configured thresholds
        self.gpu_reserve_mb = float(self.config.get("gpu", {}).get("reserve_mb", 2048.0))
        self.ram_reserve_gb = float(self.config.get("ram", {}).get("reserve_gb", 8.0))
        self.ram_cache_limit_gb = float(self.config.get("ram", {}).get("cache_limit_gb", 32.0))
        self.vram_high_watermark_gb = float(self.config.get("gpu", {}).get("vram_high_watermark_gb", 8.0))
        self.vram_constrained_watermark_gb = float(self.config.get("gpu", {}).get("vram_constrained_watermark_gb", 4.0))
        self.idle_unload_seconds = float(self.config.get("policy", {}).get("idle_unload_seconds", 300.0))

        logger.info(
            f"[ResourceManager] Initialized on {self.hw_profile.gpu_name} ({self.hw_profile.gpu_vram_gb:.1f} GB VRAM) "
            f"| RAM: {self.hw_profile.ram_total_gb:.1f} GB (Avail: {self.hw_profile.ram_available_gb:.1f} GB) | Tier: {self.tier_name}"
        )

    def _load_config(self) -> Dict[str, Any]:
        """Loads resource configuration with safe defaults."""
        defaults = {
            "gpu": {
                "enabled": True,
                "reserve_mb": 2048.0,
                "max_utilization_percent": 90,
                "vram_high_watermark_gb": 8.0,
                "vram_constrained_watermark_gb": 4.0,
            },
            "ram": {
                "reserve_gb": 8.0,
                "cache_limit_gb": 32.0,
                "ram_emergency_release_gb": 8.0,
            },
            "policy": {
                "prefer_gpu": True,
                "allow_cpu_fallback": True,
                "keep_tts_loaded": True,
                "idle_unload_seconds": 300.0,
                "max_cached_models": 8,
            },
        }
        if os.path.exists(self.config_path):
            try:
                with open(self.config_path, "r", encoding="utf-8") as f:
                    data = yaml.safe_load(f)
                    if isinstance(data, dict) and "resources" in data:
                        return data["resources"]
            except Exception as e:
                logger.warning(f"[ResourceManager] Could not parse {self.config_path}: {e}")
        return defaults

    def set_llm_active(self, is_active: bool):
        """Notifies the manager whether the LLM is actively streaming/generating tokens."""
        self._is_llm_active = is_active

    @property
    def is_llm_active(self) -> bool:
        return self._is_llm_active

    # ── Memory Queries ──────────────────────────────────────────

    def get_system_memory(self) -> Dict[str, float]:
        """Returns physical system RAM metrics in GB."""
        vm = psutil.virtual_memory()
        return {
            "total_gb": round(vm.total / (1024 ** 3), 2),
            "available_gb": round(vm.available / (1024 ** 3), 2),
            "used_gb": round(vm.used / (1024 ** 3), 2),
            "percent": vm.percent,
            "cache_limit_gb": self.ram_cache_limit_gb,
            "reserve_gb": self.ram_reserve_gb,
        }

    def get_gpu_memory(self) -> Dict[str, float]:
        """Returns GPU VRAM metrics in MB/GB using NVML or PyTorch where available."""
        total_mb = self.hw_profile.gpu_vram_gb * 1024.0
        free_mb = total_mb

        if self._torch_cuda_available:
            try:
                import torch
                free_b, total_b = torch.cuda.mem_get_info()
                free_mb = free_b / (1024 * 1024)
                total_mb = total_b / (1024 * 1024)
            except Exception:
                pass
        else:
            # Platform fallback via nvidia-smi if available
            try:
                import subprocess
                res = subprocess.run(
                    ['nvidia-smi', '--query-gpu=memory.free,memory.total', '--format=csv,noheader,nounits'],
                    capture_output=True, text=True, timeout=2
                )
                if res.returncode == 0 and res.stdout.strip():
                    parts = res.stdout.strip().split(',')
                    if len(parts) == 2:
                        free_mb = float(parts[0].strip())
                        total_mb = float(parts[1].strip())
            except Exception:
                pass

        return {
            "total_mb": round(total_mb, 1),
            "free_mb": round(free_mb, 1),
            "available_for_models_mb": round(max(0.0, free_mb - self.gpu_reserve_mb), 1),
            "total_gb": round(total_mb / 1024.0, 2),
            "available_gb": round(max(0.0, free_mb - self.gpu_reserve_mb) / 1024.0, 2),
            "allocated_by_helios_mb": round(self._allocated_vram_mb, 1),
        }

    def get_memory_pressure(self) -> MemoryPressure:
        """Evaluates overall system memory pressure state."""
        mem = self.get_system_memory()
        gpu = self.get_gpu_memory()

        avail_ram_gb = mem["available_gb"]
        avail_vram_gb = gpu["available_gb"]

        if avail_ram_gb < (self.ram_reserve_gb * 0.5) or (self.hw_profile.gpu_present and avail_vram_gb < 1.0):
            return MemoryPressure.CRITICAL
        elif avail_ram_gb < self.ram_reserve_gb or (self.hw_profile.gpu_present and avail_vram_gb < 2.0):
            return MemoryPressure.HIGH
        elif avail_ram_gb < (self.ram_reserve_gb * 1.5) or (self.hw_profile.gpu_present and avail_vram_gb < self.vram_constrained_watermark_gb):
            return MemoryPressure.ELEVATED
        return MemoryPressure.NORMAL

    # ── Model Registration & Lifecycle ──────────────────────────

    def register_model(
        self,
        model_id: str,
        subsystem: str,
        residency_state: ModelResidencyState = ModelResidencyState.UNLOADED,
        ram_size_mb: float = 0.0,
        vram_size_mb: float = 0.0,
        demote_handler: Optional[Any] = None,
        promote_handler: Optional[Any] = None,
        unload_handler: Optional[Any] = None,
    ):
        """Registers a model with its handlers and footprint for memory management."""
        self._models[model_id] = ModelResourceEntry(
            model_id=model_id,
            subsystem=subsystem,
            residency_state=residency_state,
            ram_size_mb=ram_size_mb,
            vram_size_mb=vram_size_mb,
            last_active_time=time.time(),
            demote_handler=demote_handler,
            promote_handler=promote_handler,
            unload_handler=unload_handler,
        )

    def request_model_execution(
        self,
        model_id: str,
        required_vram_mb: float = 2048.0,
        required_ram_mb: float = 1024.0,
        prefer_gpu: bool = True,
    ) -> Tuple[str, bool]:
        """
        Arbitrates resources for a model execution request.
        Returns (placement_device, success) where placement_device is 'cuda', 'cpu', or None.
        If VRAM is insufficient, performs LRU demotion of inactive models to RAM first.
        """
        entry = self._models.get(model_id)
        if entry:
            entry.last_active_time = time.time()

        pressure = self.get_memory_pressure()
        if pressure == MemoryPressure.CRITICAL:
            self._handle_critical_pressure()

        gpu_info = self.get_gpu_memory()
        avail_vram_mb = gpu_info["available_for_models_mb"]

        # Check if GPU execution is requested and system has GPU
        if prefer_gpu and self.hw_profile.gpu_present and (self._torch_cuda_available or self.hw_profile.gpu_vendor == "nvidia"):
            if avail_vram_mb >= required_vram_mb:
                # Direct GPU placement
                if entry:
                    entry.residency_state = ModelResidencyState.ACTIVE
                return "cuda", True

            # If not enough VRAM, attempt to demote inactive models to RAM
            logger.info(
                f"[ResourceManager] VRAM constrained ({avail_vram_mb:.1f} MB < {required_vram_mb:.1f} MB required). "
                f"Attempting to demote inactive models to RAM..."
            )
            reclaimed_mb = self.demote_inactive_gpu_models(exclude_ids=[model_id])
            new_gpu_info = self.get_gpu_memory()

            if new_gpu_info["available_for_models_mb"] >= required_vram_mb:
                if entry:
                    entry.residency_state = ModelResidencyState.ACTIVE
                return "cuda", True

        # Fallback to CPU / System RAM execution
        ram_info = self.get_system_memory()
        avail_ram_mb = ram_info["available_gb"] * 1024.0

        if avail_ram_mb >= (self.ram_reserve_gb * 1024.0 + required_ram_mb):
            if entry:
                entry.residency_state = ModelResidencyState.ACTIVE
            return "cpu", True

        # System under severe constraint
        logger.warning(
            f"[ResourceManager] Unable to grant memory reservation for '{model_id}' "
            f"(VRAM free: {avail_vram_mb:.1f} MB, RAM free: {avail_ram_mb:.1f} MB)"
        )
        return "cpu", False

    def release_model_execution(self, model_id: str):
        """Marks model as no longer actively executing; updates LRU timestamp."""
        entry = self._models.get(model_id)
        if entry:
            entry.last_active_time = time.time()
            if entry.residency_state == ModelResidencyState.ACTIVE:
                # Remain GPU resident if VRAM budget allows, else mark RAM_RESIDENT
                gpu_info = self.get_gpu_memory()
                if gpu_info["available_for_models_mb"] >= 1024.0 and (self._torch_cuda_available or self.hw_profile.gpu_vendor == "nvidia"):
                    entry.residency_state = ModelResidencyState.GPU_RESIDENT
                else:
                    entry.residency_state = ModelResidencyState.RAM_RESIDENT

    def demote_inactive_gpu_models(self, exclude_ids: Optional[List[str]] = None) -> float:
        """
        Demotes inactive GPU-resident models to System RAM (LRU order).
        Returns total MB of VRAM reclaimed.
        """
        excludes = set(exclude_ids or [])
        reclaimed_mb = 0.0

        # Sort inactive GPU candidates by last_active_time ascending
        candidates = [
            m for m in self._models.values()
            if m.model_id not in excludes
            and m.residency_state == ModelResidencyState.GPU_RESIDENT
        ]
        candidates.sort(key=lambda m: m.last_active_time)

        for m in candidates:
            if m.demote_handler:
                try:
                    logger.info(f"[ResourceManager] Demoting '{m.model_id}' from VRAM to RAM...")
                    success = m.demote_handler()
                    if success:
                        m.residency_state = ModelResidencyState.RAM_RESIDENT
                        reclaimed_mb += m.vram_size_mb
                except Exception as e:
                    logger.error(f"[ResourceManager] Error demoting '{m.model_id}': {e}")

        return reclaimed_mb

    def _handle_critical_pressure(self):
        """Aggressive relief when memory enters CRITICAL state."""
        logger.warning("[ResourceManager] Handling CRITICAL memory pressure...")
        # 1. Demote all inactive GPU models
        self.demote_inactive_gpu_models()
        # 2. Release inactive models from RAM
        now = time.time()
        for m in list(self._models.values()):
            if m.residency_state == ModelResidencyState.RAM_RESIDENT:
                if (now - m.last_active_time) > 60.0 and m.unload_handler:
                    try:
                        logger.info(f"[ResourceManager] Unloading inactive RAM model '{m.model_id}'...")
                        m.unload_handler()
                        m.residency_state = ModelResidencyState.UNLOADED
                    except Exception as e:
                        logger.error(f"[ResourceManager] Error unloading '{m.model_id}': {e}")

    def sweep_idle_models(self):
        """Periodic background sweep for models exceeding idle timeout."""
        now = time.time()
        for m in self._models.values():
            idle_s = now - m.last_active_time
            if idle_s > self.idle_unload_seconds:
                if m.residency_state == ModelResidencyState.GPU_RESIDENT and m.demote_handler:
                    logger.info(f"[ResourceManager] Idle sweep: Demoting '{m.model_id}' (idle {idle_s:.0f}s) to RAM.")
                    m.demote_handler()
                    m.residency_state = ModelResidencyState.RAM_RESIDENT

    def get_diagnostics(self) -> Dict[str, Any]:
        """Provides complete memory telemetry, active states, and model placement."""
        sys_mem = self.get_system_memory()
        gpu_mem = self.get_gpu_memory()
        pressure = self.get_memory_pressure()

        models_status = {}
        for mid, entry in self._models.items():
            models_status[mid] = {
                "subsystem": entry.subsystem,
                "residency": entry.residency_state.value,
                "last_active_seconds_ago": round(time.time() - entry.last_active_time, 1),
            }

        cluster_info = {}
        try:
            from core.hardware_profiler import get_cluster_hardware_summary
            cluster_info = get_cluster_hardware_summary()
        except Exception as e:
            cluster_info = {"error": str(e)}

        return {
            "tier": self.tier_name,
            "pressure": pressure.value,
            "llm_active": self._is_llm_active,
            "memory": {
                "ram_total_gb": sys_mem["total_gb"],
                "ram_available_gb": sys_mem["available_gb"],
                "ram_used_gb": sys_mem["used_gb"],
                "ram_reserve_gb": self.ram_reserve_gb,
                "vram_total_gb": gpu_mem["total_gb"],
                "vram_available_gb": gpu_mem["available_gb"],
                "vram_allocated_by_helios_mb": gpu_mem["allocated_by_helios_mb"],
                "gpu_present": self.hw_profile.gpu_present,
                "gpu_name": self.hw_profile.gpu_name,
                "gpu_vendor": self.hw_profile.gpu_vendor,
            },
            "models": models_status,
            "cluster": cluster_info,
        }


# Global singleton instance
resource_manager = ResourceManager()
