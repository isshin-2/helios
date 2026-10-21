"""
HELIOS — Model Router & VRAM Lifecycle Manager
Manages per-agent model profiles, fallbacks, and intelligent VRAM model swapping
tailored for hardware constraints and dynamic GPU VRAM thresholds.
"""

from __future__ import annotations

import logging
import os
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

import yaml
from pydantic import BaseModel, Field

from providers.base import BaseProvider

logger = logging.getLogger("helios.model_router")

CONFIG_PATH = Path(__file__).resolve().parent.parent / "config" / "agent_profiles.yaml"


class AgentModelProfile(BaseModel):
    """Configuration profile for an individual agent's model requirements."""
    model: str
    temperature: float = 0.1
    fallback_models: List[str] = Field(default_factory=list)
    options: Dict[str, Any] = Field(default_factory=dict)


class HardwareLimits(BaseModel):
    """Hardware constraints for model execution."""
    target_device: str = "auto"
    max_vram_gb: float = 16.0
    system_ram_gb: float = 64.0
    cpu: str = "auto"
    max_concurrent_large_models: int = 3
    large_model_threshold_gb: float = 6.0
    default_context_tokens: int = 16384
    ram_offload_enabled: bool = True



DEFAULT_PROFILES: Dict[str, Dict[str, Any]] = {
    "planner": {
        "model": "qwen2.5-coder:14b",
        "temperature": 0.2,
        "fallback_models": ["qwen2.5-coder:7b", "hermes3:8b", "qwen2.5-coder:3b", "llama3.2:3b", "qwen2.5:3b"],
    },
    "architect": {
        "model": "qwen2.5-coder:32b",
        "temperature": 0.1,
        "fallback_models": ["qwen2.5-coder:14b", "qwen2.5-coder:7b", "hermes3:8b", "qwen3.5:9b", "qwen2.5-coder:3b", "llama3.2:3b"],
    },
    "repo_mapper": {
        "model": "qwen2.5-coder:7b",
        "temperature": 0.1,
        "fallback_models": ["qwen2.5-coder:3b", "llama3.2:3b", "qwen2.5:3b"],
    },
    "coder": {
        "model": "qwen2.5-coder:32b",
        "temperature": 0.1,
        "fallback_models": ["qwen2.5-coder:14b", "qwen2.5-coder:7b", "qwen2.5-coder:3b", "llama3.2:3b", "qwen2.5:3b"],
    },
    "tester": {
        "model": "qwen2.5-coder:14b",
        "temperature": 0.0,
        "fallback_models": ["qwen2.5-coder:7b", "qwen2.5-coder:3b", "llama3.2:3b", "qwen2.5:3b"],
    },
    "repair": {
        "model": "qwen2.5-coder:32b",
        "temperature": 0.1,
        "fallback_models": ["qwen2.5-coder:14b", "qwen2.5-coder:7b", "qwen2.5-coder:3b", "llama3.2:3b", "qwen2.5:3b"],
    },
    "reviewer": {
        "model": "qwen2.5-coder:14b",
        "temperature": 0.0,
        "fallback_models": ["qwen2.5-coder:7b", "hermes3:8b", "qwen2.5-coder:3b", "llama3.2:3b", "qwen2.5:3b"],
    },
    "security_reviewer": {
        "model": "qwen2.5-coder:14b",
        "temperature": 0.0,
        "fallback_models": ["qwen2.5-coder:7b", "hermes3:8b", "qwen2.5-coder:3b", "llama3.2:3b", "qwen2.5:3b"],
    },
}


class ModelRouter:
    """
    Intelligent Model Router that handles:
    1. Per-agent model profile configuration.
    2. Model swapping and eviction under GPU VRAM limits.
    3. Multi-tier model fallback when primary models are unavailable or OOM.
    4. Lifecycle event logging.
    """

    def __init__(self, config_file: Optional[Path] = None):
        self.config_file = config_file or CONFIG_PATH
        self.profiles: Dict[str, AgentModelProfile] = {}
        self.hardware = HardwareLimits()
        self.active_large_models: List[str] = []
        self.load_configuration()

    @property
    def active_large_model(self) -> Optional[str]:
        return self.active_large_models[-1] if self.active_large_models else None

    @active_large_model.setter
    def active_large_model(self, model: Optional[str]) -> None:
        if model is None:
            self.active_large_models.clear()
        elif model not in self.active_large_models:
            self.active_large_models.append(model)

    def load_configuration(self) -> None:
        """Loads profiles from YAML or falls back to defaults."""
        data = {}
        if self.config_file and self.config_file.exists():
            try:
                with open(self.config_file, "r", encoding="utf-8") as f:
                    data = yaml.safe_load(f) or {}
            except Exception as e:
                logger.warning(f"Failed to read {self.config_file}: {e}, using default profiles.")

        profile_data = data.get("agent_profiles", DEFAULT_PROFILES)
        for agent_type, conf in profile_data.items():
            self.profiles[agent_type] = AgentModelProfile(**conf)

        if "hardware_limits" in data:
            self.hardware = HardwareLimits(**data["hardware_limits"])

    def get_profile(self, agent_type: str) -> AgentModelProfile:
        """Retrieve model profile for given agent type."""
        if agent_type in self.profiles:
            return self.profiles[agent_type]
        # Return generic fallback profile
        return AgentModelProfile(
            model=os.getenv("HELIOS_DEFAULT_MODEL", "qwen2.5-coder:7b"),
            temperature=0.1,
            fallback_models=["llama3.2:3b"],
        )

    def set_profile(self, agent_type: str, profile: AgentModelProfile) -> None:
        """Programmatically override an agent's model profile."""
        self.profiles[agent_type] = profile

    def _is_large_model(self, model_name: str) -> bool:
        """Heuristic to detect if model exceeds safe multi-tenancy in active GPU VRAM."""
        lower = model_name.lower()
        return any(tag in lower for tag in ["14b", "24b", "32b", "70b", "devstral", "mixtral", "gemma4:12b"])

    async def prepare_model_for_agent(
        self,
        agent_type: str,
        provider: BaseProvider,
    ) -> Tuple[str, Dict[str, Any]]:
        """
        Manages the GPU lifecycle before executing an agent:
        1. Identifies the desired model from the agent profile.
        2. Swaps/unloads any active large model if needed to preserve VRAM.
        3. Validates model availability, falling back to smaller models if needed.
        4. Returns the chosen model and generation options.
        """
        profile = self.get_profile(agent_type)
        target_model = profile.model

        # 1. Check model availability and determine candidate
        candidate_models = [target_model] + profile.fallback_models
        chosen_model = target_model

        if hasattr(provider, "model_exists"):
            found = False
            for candidate in candidate_models:
                try:
                    exists = await provider.model_exists(candidate)
                    if exists:
                        chosen_model = candidate
                        found = True
                        break
                except Exception as ex:
                    logger.debug(f"Error checking model existence for {candidate}: {ex}")

            # If none of candidate_models exist, query installed models on provider
            if not found and hasattr(provider, "list_models"):
                try:
                    res = await provider.list_models()
                    installed = [m.get("name", "") for m in res.get("models", []) if m.get("name")]
                    if installed:
                        best_match = None
                        # Priority 1: coding models
                        for m in installed:
                            m_lower = m.lower()
                            if "coder" in m_lower or "code" in m_lower:
                                best_match = m
                                break
                        # Priority 2: general reasoning models
                        if not best_match:
                            for m in installed:
                                m_lower = m.lower()
                                if any(k in m_lower for k in ["qwen", "llama", "deepseek", "mistral", "gemma", "phi"]):
                                    best_match = m
                                    break
                        # Priority 3: first available model
                        if not best_match and installed:
                            best_match = installed[0]

                        if best_match:
                            chosen_model = best_match
                            found = True
                            logger.info(
                                f"[MODEL_LIFECYCLE] Preferred models for '{agent_type}' not found in provider. "
                                f"Auto-adapting to installed model '{chosen_model}'."
                            )
                except Exception as e:
                    logger.debug(f"Could not query installed models: {e}")

            if chosen_model != target_model:
                logger.info(
                    f"[MODEL_LIFECYCLE] Primary model '{target_model}' for agent '{agent_type}' "
                    f"unavailable; resolved to '{chosen_model}'."
                )

        # 2. VRAM/RAM Lifecycle: Manage multi-model retention with 64 GB host RAM + 16 GB VRAM
        is_large = self._is_large_model(chosen_model)
        if is_large:
            if chosen_model in self.active_large_models:
                # Move to end (most recently used)
                self.active_large_models.remove(chosen_model)
                self.active_large_models.append(chosen_model)
            else:
                # If pool is at limit, evict the least recently used model
                max_models = max(1, self.hardware.max_concurrent_large_models)
                while len(self.active_large_models) >= max_models:
                    evict_model = self.active_large_models.pop(0)
                    logger.info(
                        f"[MODEL_LIFECYCLE] RAM/VRAM threshold reached ({max_models} models): "
                        f"Evicting '{evict_model}' to make room for '{chosen_model}'."
                    )
                    try:
                        if hasattr(provider, "unload_model"):
                            await provider.unload_model(evict_model)
                            logger.info(f"[MODEL_LIFECYCLE] Successfully unloaded '{evict_model}'.")
                    except Exception as e:
                        logger.warning(f"[MODEL_LIFECYCLE] Error unloading '{evict_model}': {e}")

                self.active_large_models.append(chosen_model)

        options = dict(profile.options)
        options["temperature"] = profile.temperature
        if "num_ctx" not in options and self.hardware.default_context_tokens:
            options["num_ctx"] = self.hardware.default_context_tokens

        return chosen_model, options

    async def unload_all_large_models(self, provider: BaseProvider) -> None:
        """Evicts all active large models from RAM/VRAM."""
        for model in list(self.active_large_models):
            if hasattr(provider, "unload_model"):
                try:
                    logger.info(f"[MODEL_LIFECYCLE] Evicting active model '{model}' from memory.")
                    await provider.unload_model(model)
                except Exception as e:
                    logger.warning(f"Error evicting model '{model}': {e}")
        self.active_large_models.clear()


# Global instance
model_router = ModelRouter()
