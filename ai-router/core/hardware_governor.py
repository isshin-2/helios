import logging
import json
from dataclasses import dataclass, asdict
from typing import Dict, Any, List, Optional
import sys
import os

script_dir = os.path.abspath(os.path.dirname(__file__))
if script_dir in sys.path:
    sys.path.remove(script_dir)
ai_router_dir = os.path.abspath(os.path.join(script_dir, ".."))
if ai_router_dir not in sys.path:
    sys.path.insert(0, ai_router_dir)

from core.hardware_profiler import detect_hardware, HardwareProfile

logger = logging.getLogger("helios.governor")

@dataclass
class HardwareTierDecision:
    tier: int  # 1: High-Performance, 2: Balanced, 3: Budget / iGPU
    tier_name: str
    is_budget: bool
    warnings: List[str]
    downgrade_advisories: Dict[str, str]
    recommended_models: Dict[str, str]
    max_concurrent_agents: int
    vla_max_resolution: str
    target_fps_3d: int
    recommended_tts_engine: str

class HardwareGovernor:
    """Evaluates hardware capabilities, assigns system tier, and enforces budget capability downgrades."""

    def __init__(self, profile: Optional[HardwareProfile] = None):
        self.profile = profile or detect_hardware()
        self.decision = self._evaluate_tier()

    def _evaluate_tier(self) -> HardwareTierDecision:
        vram = self.profile.gpu_vram_gb
        ram = self.profile.ram_total_gb
        gpu_name = self.profile.gpu_name.lower()
        gpu_vendor = self.profile.gpu_vendor.lower()

        is_integrated = (
            "iris" in gpu_name or
            "intel" in gpu_name or
            "radeon(tm) graphics" in gpu_name or
            "uhd" in gpu_name or
            vram < 3.0
        )

        warnings: List[str] = []
        downgrades: Dict[str, str] = {}

        if not is_integrated and vram >= 7.5 and ram >= 16.0:
            # Tier 1: High Performance
            tier = 1
            tier_name = "Tier 1: High Performance (Dedicated GPU >= 8GB)"
            is_budget = False
            rec_models = {
                "general": "qwen2.5:7b",
                "coder": "qwen2.5-coder:7b",
                "vision": "qwen3-vl:8b",
                "embed": "nomic-embed-text:latest"
            }
            max_agents = 8
            vla_res = "1080p (Native)"
            target_fps = 60
            tts_engine = "GPT-SoVITS Neural / Kokoro"

        elif not is_integrated and (vram >= 3.8 or ram >= 30.0):
            # Tier 2: Balanced
            tier = 2
            tier_name = "Tier 2: Balanced Performance (Dedicated GPU 4-6GB / 32GB RAM)"
            is_budget = False
            rec_models = {
                "general": "qwen2.5:3b",
                "coder": "qwen2.5-coder:3b",
                "vision": "qwen2.5vl:3b",
                "embed": "nomic-embed-text:latest"
            }
            max_agents = 4
            vla_res = "720p Lanczos"
            target_fps = 60
            tts_engine = "Kokoro-ONNX / Edge-TTS"
        else:
            # Tier 3: Budget / Integrated GPU or Low RAM
            tier = 3
            tier_name = "Tier 3: Budget / Integrated Graphics (iGPU or <= 16GB RAM)"
            is_budget = True
            
            warnings.append(
                "SYSTEM MEMORY / VRAM CONSTRAINT: Host is operating on integrated graphics or limited VRAM (~{:.1f}GB VRAM, {:.1f}GB RAM).".format(
                    vram, ram
                )
            )
            warnings.append(
                "VLA VISION OVERLOAD: 8B+ vision models (e.g. qwen3-vl:8b, gemma4:12b) will cause high latency and memory swapping."
            )
            warnings.append(
                "SWARM CONCURRENCY HAZARD: Running 8 parallel coding agents simultaneously may exhaust RAM and trigger OS thrashing."
            )
            warnings.append(
                "3D GRAPHICS LOAD: Dual PBR 3D VRM rendering with shadows and physics will reduce frame rates on integrated GPUs."
            )

            downgrades["vision"] = "Downgraded to moondream:latest (1B) or qwen2.5vl:3b with 540p downscaled capture."
            downgrades["coding_swarm"] = "Throttled to sequential single-agent execution using qwen2.5-coder:1.5b / 3b."
            downgrades["3d_viewer"] = "Capped to 30 FPS, shadow maps disabled, MSAA reduced."
            downgrades["tts"] = "Defaulting to low-overhead Kokoro-ONNX / Edge-TTS fallback."

            rec_models = {
                "general": "qwen2.5:1.5b",
                "coder": "qwen2.5-coder:1.5b",
                "vision": "moondream:latest",
                "embed": "nomic-embed-text:latest"
            }
            max_agents = 2
            vla_res = "540p Fast"
            target_fps = 30
            tts_engine = "Kokoro-ONNX"

        return HardwareTierDecision(
            tier=tier,
            tier_name=tier_name,
            is_budget=is_budget,
            warnings=warnings,
            downgrade_advisories=downgrades,
            recommended_models=rec_models,
            max_concurrent_agents=max_agents,
            vla_max_resolution=vla_res,
            target_fps_3d=target_fps,
            recommended_tts_engine=tts_engine
        )

    def get_advisory_banner(self) -> str:
        """Returns a formatted CLI banner for console output."""
        d = self.decision
        if not d.is_budget:
            return f"[Hardware Governor] Running on {d.tier_name}. All systems nominal at full capability."

        lines = [
            "=" * 78,
            "  [WARNING - BUDGET HARDWARE DETECTED] ",
            f"  Current Tier: {d.tier_name}",
            f"  Detected GPU: {self.profile.gpu_name} ({self.profile.gpu_vram_gb:.1f} GB VRAM) | RAM: {self.profile.ram_total_gb:.1f} GB",
            "-" * 78,
            "  ADVISED CAPABILITY DOWNGRADES FOR SYSTEM STABILITY:"
        ]
        for w in d.warnings:
            lines.append(f"  * {w}")
        lines.append("-" * 78)
        lines.append("  RECOMMENDED ADJUSTMENTS:")
        for feature, desc in d.downgrade_advisories.items():
            lines.append(f"  * {feature.upper():14}: {desc}")
        lines.append("=" * 78)
        return "\n".join(lines)

    def to_dict(self) -> Dict[str, Any]:
        return {
            "profile": asdict(self.profile),
            "decision": asdict(self.decision)
        }

if __name__ == "__main__":
    governor = HardwareGovernor()
    print(governor.get_advisory_banner())
