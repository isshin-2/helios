"""
HELIOS Character Model Manifest Manager (Phase 11 & Section 15)
Renderer-independent model manifest loader and validator supporting VRM and Live2D.
"""
import json
from pathlib import Path
from typing import Any, Dict, List, Optional


DEFAULT_HELIOS_V1_MANIFEST: Dict[str, Any] = {
    "id": "helios-v1",
    "name": "HELIOS",
    "format": "vrm",
    "version": "1.0",
    "model_path": "models/Yu1_1.vrm",
    "aesthetic": {
        "hair": "silver/gray wolf-cut",
        "eyes": "cyan/blue expressive",
        "details": "subtle piercings",
        "outfit": "dark technical clothing with cyan technological accents",
        "style": "anime-style, cool exterior, friendly/playful behavior",
    },
    "expressions": [
        "neutral",
        "happy",
        "amused",
        "surprised",
        "concerned",
        "serious",
        "smirk",
    ],
    "animations": [
        "idle",
        "thinking",
        "wave",
        "nod",
        "talking",
    ],
}


class CharacterModelRegistry:
    """Loads and validates renderer-independent character model manifests."""

    REQUIRED_KEYS = {"id", "name", "format", "version", "expressions", "animations"}

    def __init__(self, search_dirs: Optional[List[Path]] = None):
        repo_root = Path(__file__).resolve().parent.parent.parent
        self.search_dirs = search_dirs or [
            repo_root / "helios-character" / "viewer" / "models",
            repo_root / "helios-character" / "models",
        ]
        self._manifests: Dict[str, Dict[str, Any]] = {
            "helios-v1": dict(DEFAULT_HELIOS_V1_MANIFEST)
        }
        self.discover_manifests()

    def discover_manifests(self) -> None:
        for d in self.search_dirs:
            if not d.exists():
                continue
            for manifest_file in d.rglob("*manifest*.json"):
                try:
                    data = json.loads(manifest_file.read_text(encoding="utf-8"))
                    if self.validate_manifest(data):
                        self._manifests[data["id"]] = data
                except Exception:
                    pass

    @classmethod
    def validate_manifest(cls, data: Any) -> bool:
        if not isinstance(data, dict):
            return False
        if not cls.REQUIRED_KEYS.issubset(data.keys()):
            return False
        if data.get("format") not in {"vrm", "live2d"}:
            return False
        if not isinstance(data.get("expressions"), list) or not isinstance(
            data.get("animations"), list
        ):
            return False
        return True

    def get_manifest(self, model_id: str = "helios-v1") -> Dict[str, Any]:
        return dict(self._manifests.get(model_id, DEFAULT_HELIOS_V1_MANIFEST))

    def list_manifests(self) -> List[Dict[str, Any]]:
        return list(self._manifests.values())
