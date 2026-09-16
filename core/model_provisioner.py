"""
HELIOS First-Start Model Provisioner

Implements the full provisioning state machine:
    PROVISION_INIT -> HARDWARE_SCAN -> CATALOG_LOAD -> ANALYZER_READY ->
    MODEL_SELECTION -> RECOMMENDATION_VALIDATION -> MODEL_PULL ->
    MODEL_VERIFY -> CLEANUP -> COMMIT

Uses a 1B-3B mini-model to analyze hardware and recommend models from
a constrained catalog. Falls back to deterministic tier-based selection
if the analyzer produces invalid output.
"""

import asyncio
import json
import logging
import os
import time
from typing import Any, Dict, List, Optional, Callable

from core.hardware_profiler import (
    HardwareProfile, detect_hardware, classify_tier, TIER_THRESHOLDS
)

logger = logging.getLogger(__name__)

# --- Constants ---------------------------------------------------------------
INITIALIZED_FILE = ".helios_initialized.json"
CHECKPOINT_FILE = ".helios_provisioning_checkpoint.json"
CATALOG_PATH = os.path.join(os.path.dirname(os.path.dirname(__file__)), "config", "model_catalog.json")

# Preferred analyzer models in priority order (smallest first)
ANALYZER_CANDIDATES = ["qwen2.5:1.5b", "llama3.2:1b", "llama3.2:3b", "qwen2.5:3b", "qwen3.5:4b"]

MAX_ANALYZER_RETRIES = 2
MAX_PULL_RETRIES = 2
REQUIRED_ROLES = ["general"]


# --- Provisioning States -----------------------------------------------------
class ProvisionState:
    PROVISION_INIT = "PROVISION_INIT"
    HARDWARE_SCAN = "HARDWARE_SCAN"
    CATALOG_LOAD = "CATALOG_LOAD"
    ANALYZER_READY = "ANALYZER_READY"
    MODEL_SELECTION = "MODEL_SELECTION"
    RECOMMENDATION_VALIDATION = "RECOMMENDATION_VALIDATION"
    MODEL_PULL = "MODEL_PULL"
    MODEL_VERIFY = "MODEL_VERIFY"
    CLEANUP = "CLEANUP"
    COMMIT = "COMMIT"
    COMPLETED = "COMPLETED"
    FAILED = "FAILED"


# --- Model Catalog -----------------------------------------------------------
def load_model_catalog() -> List[Dict[str, Any]]:
    """Load the model catalog from config/model_catalog.json."""
    try:
        with open(CATALOG_PATH, "r", encoding="utf-8") as f:
            data = json.load(f)
        return data.get("models", [])
    except Exception as e:
        logger.error(f"Failed to load model catalog from {CATALOG_PATH}: {e}")
        return []


def filter_catalog_for_tier(catalog: List[Dict], tier_name: str, tier_limits: Dict) -> List[Dict]:
    """Filter catalog entries compatible with the given hardware tier."""
    compatible = []
    for model in catalog:
        if tier_name in model.get("tiers", []):
            if model.get("estimated_size_gb", 999) <= tier_limits.get("max_model_size_gb", 0):
                compatible.append(model)
    return compatible


def deterministic_fallback_selection(
    compatible_models: List[Dict],
    disk_free_gb: float
) -> List[Dict]:
    """
    Select models deterministically by picking the highest-priority model
    per required role, respecting disk constraints.
    """
    selected = []
    roles_filled = set()
    total_disk_needed = 0.0

    # Group by role, sort by priority descending
    by_role: Dict[str, List[Dict]] = {}
    for m in compatible_models:
        role = m.get("role", "general")
        by_role.setdefault(role, []).append(m)
    for role in by_role:
        by_role[role].sort(key=lambda x: x.get("priority", 0), reverse=True)

    # Always fill required roles first
    for role in REQUIRED_ROLES:
        if role in by_role:
            for candidate in by_role[role]:
                size = candidate.get("estimated_size_gb", 0)
                if total_disk_needed + size + 2.0 <= disk_free_gb:
                    selected.append(candidate)
                    total_disk_needed += size
                    roles_filled.add(role)
                    break

    # Fill optional roles
    for role, candidates in by_role.items():
        if role in roles_filled:
            continue
        for candidate in candidates:
            if any(s["name"] == candidate["name"] for s in selected):
                continue
            size = candidate.get("estimated_size_gb", 0)
            if total_disk_needed + size + 2.0 <= disk_free_gb:
                selected.append(candidate)
                total_disk_needed += size
                roles_filled.add(role)
                break

    # Always include embedding if available
    if "embedding" not in roles_filled:
        for m in compatible_models:
            if m.get("role") == "embedding":
                size = m.get("estimated_size_gb", 0)
                if total_disk_needed + size + 1.0 <= disk_free_gb:
                    selected.append(m)
                    break

    return selected


# --- Analyzer Prompt ----------------------------------------------------------
def build_analyzer_prompt(
    profile: HardwareProfile,
    tier_name: str,
    tier_limits: Dict,
    compatible_models: List[Dict]
) -> str:
    """Build the constrained prompt for the mini-model analyzer."""
    model_list = "\n".join(
        f"  - {m['name']} (role: {m['role']}, size: {m['estimated_size_gb']}GB, priority: {m.get('priority', 0)})"
        for m in compatible_models
    )

    return f"""You are a hardware-aware model selection assistant. Analyze the system specs below and select the optimal set of AI models from the ALLOWED LIST ONLY.

SYSTEM SPECS:
- OS: {profile.os_name} {profile.os_version}
- CPU: {profile.cpu_name} ({profile.cpu_cores_physical} cores, {profile.cpu_cores_logical} threads)
- RAM: {profile.ram_total_gb:.1f} GB total, {profile.ram_available_gb:.1f} GB available
- GPU: {"Yes" if profile.gpu_present else "No"} ({profile.gpu_vendor}, {profile.gpu_name}, {profile.gpu_vram_gb:.1f} GB VRAM)
- Disk Free: {profile.disk_free_gb:.1f} GB
- Hardware Tier: {tier_name}

CONSTRAINTS:
- Max model size: {tier_limits['max_model_size_gb']} GB
- Recommended context: {tier_limits['recommended_context']}
- Max simultaneous models: {tier_limits['max_simultaneous_models']}
- MUST include at least one "general" role model
- Total disk usage of all selected models must be under {profile.disk_free_gb:.0f} GB

ALLOWED MODELS (you MUST only select from this list):
{model_list}

Select the best combination of models. Pick ONE model per role where possible.
Prefer higher priority models when hardware allows.

Respond with ONLY valid JSON, no explanation, no markdown:
{{"models": [{{"name": "model_name", "role": "role_name"}}, ...]}}"""


def parse_analyzer_response(raw: str, compatible_models: List[Dict]) -> Optional[List[Dict]]:
    """
    Parse and validate the analyzer's JSON response.
    Returns list of validated model entries or None if invalid.
    """
    cleaned = raw.strip()
    if cleaned.startswith("```"):
        lines = cleaned.split("\n")
        lines = [l for l in lines if not l.strip().startswith("```")]
        cleaned = "\n".join(lines).strip()

    try:
        start = cleaned.index("{")
        end = cleaned.rindex("}") + 1
        cleaned = cleaned[start:end]
        data = json.loads(cleaned)
    except (ValueError, json.JSONDecodeError) as e:
        logger.warning(f"Analyzer response is not valid JSON: {e}")
        return None

    if not isinstance(data, dict) or "models" not in data:
        logger.warning("Analyzer response missing 'models' key")
        return None

    models = data["models"]
    if not isinstance(models, list) or len(models) == 0:
        logger.warning("Analyzer returned empty or invalid models list")
        return None

    allowed_names = {m["name"] for m in compatible_models}

    validated = []
    seen_names = set()
    for entry in models:
        if not isinstance(entry, dict):
            continue
        name = entry.get("name", "")
        role = entry.get("role", "")

        if name not in allowed_names:
            logger.warning(f"Analyzer suggested model '{name}' not in catalog -- rejected")
            continue

        if name in seen_names:
            continue
        seen_names.add(name)

        for key in entry:
            if key not in ("name", "role"):
                logger.warning(f"Analyzer included unexpected field '{key}' -- ignoring field")

        validated.append({"name": name, "role": role})

    if len(validated) == 0:
        return None

    return validated


def validate_recommendation(
    recommendation: List[Dict],
    compatible_models: List[Dict],
    tier_limits: Dict,
    disk_free_gb: float
) -> List[Dict]:
    """
    Validate every recommended model against catalog, tier, RAM, VRAM, disk.
    Returns only the models that pass all checks.
    """
    catalog_lookup = {m["name"]: m for m in compatible_models}
    validated = []
    total_size = 0.0

    for rec in recommendation:
        name = rec.get("name", "")
        catalog_entry = catalog_lookup.get(name)

        if not catalog_entry:
            logger.warning(f"Validation: '{name}' not in compatible catalog -- skipped")
            continue

        size = catalog_entry.get("estimated_size_gb", 0)
        if size > tier_limits.get("max_model_size_gb", 0):
            logger.warning(f"Validation: '{name}' exceeds max model size -- skipped")
            continue

        if total_size + size + 2.0 > disk_free_gb:
            logger.warning(f"Validation: '{name}' would exceed disk budget -- skipped")
            continue

        total_size += size
        validated.append(catalog_entry)

    # Ensure at least one general model
    has_general = any(m.get("role") == "general" for m in validated)
    if not has_general:
        for m in compatible_models:
            if m.get("role") == "general" and m["name"] not in {v["name"] for v in validated}:
                validated.insert(0, m)
                break

    return validated


# --- Checkpoint Persistence ---------------------------------------------------
def save_checkpoint(state: str, data: Dict, base_dir: str = "."):
    """Save provisioning checkpoint for crash recovery."""
    path = os.path.join(base_dir, CHECKPOINT_FILE)
    checkpoint = {
        "state": state,
        "timestamp": time.time(),
        "data": data
    }
    try:
        tmp_path = path + ".tmp"
        with open(tmp_path, "w", encoding="utf-8") as f:
            json.dump(checkpoint, f, indent=2)
        if os.path.exists(path):
            os.remove(path)
        os.rename(tmp_path, path)
    except Exception as e:
        logger.error(f"Failed to save checkpoint: {e}")


def load_checkpoint(base_dir: str = ".") -> Optional[Dict]:
    """Load existing checkpoint if present."""
    path = os.path.join(base_dir, CHECKPOINT_FILE)
    if not os.path.exists(path):
        return None
    try:
        with open(path, "r", encoding="utf-8") as f:
            return json.load(f)
    except Exception as e:
        logger.warning(f"Corrupt checkpoint, starting fresh: {e}")
        return None


def clear_checkpoint(base_dir: str = "."):
    """Remove checkpoint file."""
    path = os.path.join(base_dir, CHECKPOINT_FILE)
    try:
        if os.path.exists(path):
            os.remove(path)
    except Exception:
        pass


# --- Initialization Manifest -------------------------------------------------
def write_initialized_manifest(
    tier_name: str,
    analyzer_model: str,
    analyzer_was_preexisting: bool,
    provisioned_models: List[str],
    base_dir: str = "."
):
    """Atomically write the .helios_initialized.json manifest."""
    manifest = {
        "version": 1,
        "status": "complete",
        "initialized_at": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
        "hardware_tier": tier_name,
        "analyzer_model": analyzer_model,
        "analyzer_was_preexisting": analyzer_was_preexisting,
        "models": provisioned_models
    }
    path = os.path.join(base_dir, INITIALIZED_FILE)
    tmp_path = path + ".tmp"
    try:
        with open(tmp_path, "w", encoding="utf-8") as f:
            json.dump(manifest, f, indent=2)
        if os.path.exists(path):
            os.remove(path)
        os.rename(tmp_path, path)
        logger.info(f"Initialization manifest written: {path}")
    except Exception as e:
        logger.error(f"Failed to write initialization manifest: {e}")
        raise


def is_initialized(base_dir: str = ".") -> bool:
    """Check if HELIOS has already been initialized."""
    path = os.path.join(base_dir, INITIALIZED_FILE)
    if not os.path.exists(path):
        return False
    try:
        with open(path, "r", encoding="utf-8") as f:
            data = json.load(f)
        return data.get("status") == "complete"
    except Exception:
        return False


def read_initialized_manifest(base_dir: str = ".") -> Optional[Dict]:
    """Read the initialization manifest if it exists."""
    path = os.path.join(base_dir, INITIALIZED_FILE)
    if not os.path.exists(path):
        return None
    try:
        with open(path, "r", encoding="utf-8") as f:
            return json.load(f)
    except Exception:
        return None


# --- Main Provisioner ---------------------------------------------------------
class ModelProvisioner:
    """
    HELIOS First-Start Model Provisioner.

    Implements a resumable state machine that:
    1. Detects hardware
    2. Loads constrained model catalog
    3. Uses a lightweight 1B-3B analyzer (or deterministic fallback)
    4. Pulls and verifies recommended models
    5. Cleans up temporary resources
    6. Atomically commits initialization manifest
    """

    def __init__(self, ollama_provider, event_callback: Optional[Callable] = None, base_dir: str = "."):
        self.provider = ollama_provider
        self.event_callback = event_callback
        self.base_dir = base_dir

        self.profile: Optional[HardwareProfile] = None
        self.tier_name: str = ""
        self.tier_limits: Dict = {}
        self.catalog: List[Dict] = []
        self.compatible_models: List[Dict] = []
        self.selected_models: List[Dict] = []
        self.provisioned_models: List[str] = []
        self.failed_models: List[str] = []
        self.analyzer_model: str = ""
        self.analyzer_was_preexisting: bool = True
        self.current_state: str = ProvisionState.PROVISION_INIT

    async def _emit(self, event_type: str, data: Any = None):
        """Emit a provisioning event."""
        # Sanitize data to avoid leaking secrets
        safe_data = data
        if isinstance(data, dict):
            safe_data = {k: v for k, v in data.items() if k.lower() not in ("api_key", "token", "secret", "password")}
        logger.info(f"[PROVISION] {event_type}: {safe_data}")
        if self.event_callback:
            try:
                if asyncio.iscoroutinefunction(self.event_callback):
                    await self.event_callback(event_type, safe_data)
                else:
                    self.event_callback(event_type, safe_data)
            except Exception:
                pass

    async def run(self, dry_run: bool = False, force: bool = False) -> Dict[str, Any]:
        """
        Execute the full provisioning pipeline.

        Args:
            dry_run: If True, analyze and report but do not pull/delete anything.
            force: If True, re-run even if already initialized.

        Returns:
            Dict with provisioning result summary.
        """
        if not force and is_initialized(self.base_dir):
            manifest = read_initialized_manifest(self.base_dir)
            logger.info("HELIOS already initialized, skipping provisioning.")
            await self._emit("provisioning_skipped", manifest)
            return {"status": "already_initialized", "manifest": manifest}

        await self._emit("provisioning_started")

        # Check for resume checkpoint
        checkpoint = load_checkpoint(self.base_dir)
        resume_from = None
        if checkpoint:
            resume_from = checkpoint.get("state")
            checkpoint_data = checkpoint.get("data", {})
            logger.info(f"Resuming provisioning from state: {resume_from}")
            self.provisioned_models = checkpoint_data.get("provisioned_models", [])
            self.analyzer_model = checkpoint_data.get("analyzer_model", "")
            self.analyzer_was_preexisting = checkpoint_data.get("analyzer_was_preexisting", True)

        try:
            # --- HARDWARE_SCAN ---
            self.current_state = ProvisionState.HARDWARE_SCAN
            self.profile = detect_hardware()
            self.tier_name, self.tier_limits = classify_tier(self.profile)
            await self._emit("hardware_detected", {
                "tier": self.tier_name,
                "ram_gb": round(self.profile.ram_total_gb, 1),
                "gpu": self.profile.gpu_name if self.profile.gpu_present else "None",
                "disk_free_gb": round(self.profile.disk_free_gb, 1)
            })

            # --- CATALOG_LOAD ---
            self.current_state = ProvisionState.CATALOG_LOAD
            self.catalog = load_model_catalog()
            if not self.catalog:
                raise RuntimeError("Model catalog is empty or missing")
            self.compatible_models = filter_catalog_for_tier(
                self.catalog, self.tier_name, self.tier_limits
            )
            await self._emit("catalog_loaded", {
                "total_models": len(self.catalog),
                "compatible_models": len(self.compatible_models)
            })

            if not self.compatible_models:
                raise RuntimeError(f"No compatible models found for tier '{self.tier_name}'")

            # --- ANALYZER_READY ---
            early_states = (
                ProvisionState.PROVISION_INIT, ProvisionState.HARDWARE_SCAN,
                ProvisionState.CATALOG_LOAD, ProvisionState.ANALYZER_READY
            )
            if not resume_from or resume_from in early_states:
                self.current_state = ProvisionState.ANALYZER_READY
                analyzer_info = await self._find_or_pull_analyzer()
                if analyzer_info:
                    self.analyzer_model, self.analyzer_was_preexisting = analyzer_info
                    await self._emit("analyzer_selected", {
                        "model": self.analyzer_model,
                        "preexisting": self.analyzer_was_preexisting
                    })
                else:
                    logger.warning("No analyzer available, using deterministic fallback")
                    self.analyzer_model = "deterministic"
                    self.analyzer_was_preexisting = True

            # --- MODEL_SELECTION ---
            selection_states = early_states + (ProvisionState.MODEL_SELECTION,)
            if not resume_from or resume_from in selection_states:
                self.current_state = ProvisionState.MODEL_SELECTION
                if self.analyzer_model and self.analyzer_model != "deterministic":
                    self.selected_models = await self._run_analyzer()
                else:
                    self.selected_models = []

                # --- RECOMMENDATION_VALIDATION ---
                self.current_state = ProvisionState.RECOMMENDATION_VALIDATION
                if self.selected_models:
                    self.selected_models = validate_recommendation(
                        self.selected_models,
                        self.compatible_models,
                        self.tier_limits,
                        self.profile.disk_free_gb
                    )

                if not self.selected_models:
                    logger.info("Using deterministic fallback for model selection")
                    self.selected_models = deterministic_fallback_selection(
                        self.compatible_models, self.profile.disk_free_gb
                    )
                    await self._emit("deterministic_fallback", {
                        "models": [m["name"] for m in self.selected_models]
                    })

            if dry_run:
                await self._emit("dry_run_complete", {
                    "tier": self.tier_name,
                    "selected_models": [m["name"] for m in self.selected_models],
                    "analyzer": self.analyzer_model
                })
                return {
                    "status": "dry_run",
                    "tier": self.tier_name,
                    "selected_models": [m["name"] for m in self.selected_models],
                    "analyzer": self.analyzer_model,
                    "hardware": {
                        "ram_gb": round(self.profile.ram_total_gb, 1),
                        "gpu": self.profile.gpu_name if self.profile.gpu_present else "None",
                        "disk_free_gb": round(self.profile.disk_free_gb, 1),
                    }
                }

            # --- MODEL_PULL ---
            self.current_state = ProvisionState.MODEL_PULL
            for model_entry in self.selected_models:
                model_name = model_entry["name"]

                if model_name in self.provisioned_models:
                    logger.info(f"Model '{model_name}' already provisioned, skipping")
                    continue

                if await self.provider.model_exists(model_name):
                    logger.info(f"Model '{model_name}' already exists in Ollama")
                    self.provisioned_models.append(model_name)
                    self._save_pull_checkpoint()
                    continue

                await self._emit("model_pull_started", {"model": model_name})

                pull_success = False
                for attempt in range(MAX_PULL_RETRIES):
                    success = await self.provider.pull_model(model_name, progress_callback=None)
                    if success:
                        pull_success = True
                        break
                    else:
                        logger.warning(f"Pull attempt {attempt + 1}/{MAX_PULL_RETRIES} failed for '{model_name}'")
                        await asyncio.sleep(2)

                if not pull_success:
                    logger.error(f"Failed to pull '{model_name}' after {MAX_PULL_RETRIES} attempts")
                    await self._emit("model_pull_failed", {"model": model_name})
                    self.failed_models.append(model_name)
                    continue

                await self._emit("model_pull_completed", {"model": model_name})

                # --- MODEL_VERIFY ---
                self.current_state = ProvisionState.MODEL_VERIFY
                await self._emit("model_verification_started", {"model": model_name})

                verified = await self._verify_model(model_name)
                if verified:
                    self.provisioned_models.append(model_name)
                    await self._emit("model_verification_completed", {"model": model_name})
                else:
                    logger.error(f"Model '{model_name}' failed verification")
                    self.failed_models.append(model_name)
                    await self._emit("model_pull_failed", {"model": model_name, "reason": "verification_failed"})

                self._save_pull_checkpoint()

            # Verify we have at least one usable model
            if not self.provisioned_models:
                raise RuntimeError("Provisioning failed: no models were successfully provisioned")

            # --- CLEANUP ---
            self.current_state = ProvisionState.CLEANUP
            await self._cleanup_analyzer()
            await self._emit("analyzer_cleanup", {
                "model": self.analyzer_model,
                "deleted": not self.analyzer_was_preexisting and self.analyzer_model not in self.provisioned_models
            })

            # --- COMMIT ---
            self.current_state = ProvisionState.COMMIT
            write_initialized_manifest(
                tier_name=self.tier_name,
                analyzer_model=self.analyzer_model,
                analyzer_was_preexisting=self.analyzer_was_preexisting,
                provisioned_models=self.provisioned_models,
                base_dir=self.base_dir
            )
            clear_checkpoint(self.base_dir)

            self.current_state = ProvisionState.COMPLETED
            result = {
                "status": "complete",
                "tier": self.tier_name,
                "provisioned_models": self.provisioned_models,
                "failed_models": self.failed_models,
                "analyzer": self.analyzer_model
            }
            await self._emit("provisioning_completed", result)
            return result

        except Exception as e:
            self.current_state = ProvisionState.FAILED
            logger.error(f"Provisioning failed: {e}")
            await self._emit("provisioning_failed", {"error": str(e), "state": self.current_state})
            return {"status": "failed", "error": str(e), "state": self.current_state}

    def _save_pull_checkpoint(self):
        """Save checkpoint after each model pull/verify cycle."""
        save_checkpoint(ProvisionState.MODEL_PULL, {
            "provisioned_models": self.provisioned_models,
            "analyzer_model": self.analyzer_model,
            "analyzer_was_preexisting": self.analyzer_was_preexisting
        }, self.base_dir)

    async def _find_or_pull_analyzer(self) -> Optional[tuple]:
        """
        Find an existing lightweight model or pull a temporary one.
        Returns (model_name, was_preexisting) or None.
        """
        try:
            tags = await self.provider.list_models()
            existing_models = tags.get("models", [])
            existing_names = {m.get("name", "") for m in existing_models}
        except Exception:
            existing_names = set()
            existing_models = []

        # First: check if any existing model is in our analyzer candidates
        for candidate in ANALYZER_CANDIDATES:
            if candidate in existing_names:
                logger.info(f"Reusing existing model '{candidate}' as analyzer")
                return (candidate, True)

        # Second: check if any existing small model (<=3B) can serve
        for m_info in existing_models:
            name = m_info.get("name", "")
            param_size = m_info.get("details", {}).get("parameter_size", "")
            try:
                if param_size.endswith("B"):
                    size_val = float(param_size[:-1])
                    if size_val <= 3.5 and "embed" not in name.lower():
                        logger.info(f"Reusing existing lightweight model '{name}' ({param_size}) as analyzer")
                        return (name, True)
                elif param_size.endswith("M"):
                    size_val = float(param_size[:-1])
                    if size_val >= 500:
                        logger.info(f"Reusing existing model '{name}' ({param_size}) as analyzer")
                        return (name, True)
            except (ValueError, TypeError):
                continue

        # Third: pull a temporary analyzer (only try the two smallest)
        for candidate in ANALYZER_CANDIDATES[:2]:
            logger.info(f"Pulling temporary analyzer model '{candidate}'...")
            success = await self.provider.pull_model(candidate)
            if success:
                logger.info(f"Successfully pulled temporary analyzer '{candidate}'")
                return (candidate, False)
            else:
                logger.warning(f"Failed to pull analyzer '{candidate}'")

        return None

    async def _run_analyzer(self) -> List[Dict]:
        """
        Run the mini-model analyzer and parse its recommendation.
        Returns validated model list or empty list on failure.
        """
        prompt = build_analyzer_prompt(
            self.profile, self.tier_name, self.tier_limits, self.compatible_models
        )

        for attempt in range(MAX_ANALYZER_RETRIES):
            try:
                logger.info(f"Running analyzer (attempt {attempt + 1}/{MAX_ANALYZER_RETRIES})...")

                response = await self.provider.generate(
                    model=self.analyzer_model,
                    prompt=prompt,
                    options={"num_ctx": 2048, "temperature": 0.1},
                    stream=False,
                    keep_alive="2m"
                )

                raw_text = response.get("response", "")
                logger.debug(f"Analyzer raw response: {raw_text[:500]}")

                parsed = parse_analyzer_response(raw_text, self.compatible_models)
                if parsed:
                    logger.info(f"Analyzer recommended: {[m['name'] for m in parsed]}")
                    return parsed
                else:
                    logger.warning(f"Analyzer attempt {attempt + 1} produced invalid output")

            except Exception as e:
                logger.error(f"Analyzer attempt {attempt + 1} failed: {e}")

        logger.warning("All analyzer attempts failed, returning empty for deterministic fallback")
        return []

    async def _verify_model(self, model_name: str) -> bool:
        """
        Verify a model works by checking existence and running minimal inference.
        """
        try:
            if not await self.provider.model_exists(model_name):
                logger.error(f"Verification: '{model_name}' not found after pull")
                return False

            try:
                response = await self.provider.generate(
                    model=model_name,
                    prompt="Reply with only the word 'OK'.",
                    options={"num_ctx": 256, "num_predict": 10},
                    stream=False,
                    keep_alive=0
                )
                output = response.get("response", "").strip()
                if len(output) > 0:
                    logger.info(f"Verification passed for '{model_name}': got '{output[:50]}'")
                    return True
                else:
                    logger.warning(f"Verification: '{model_name}' returned empty response")
                    return False
            except Exception as e:
                logger.error(f"Verification inference failed for '{model_name}': {e}")
                return False

        except Exception as e:
            logger.error(f"Verification error for '{model_name}': {e}")
            return False

    async def _cleanup_analyzer(self):
        """Delete the temporary analyzer model if HELIOS downloaded it."""
        if self.analyzer_was_preexisting or self.analyzer_model == "deterministic":
            logger.info(f"Analyzer '{self.analyzer_model}' was pre-existing or deterministic -- keeping it")
            return

        if self.analyzer_model in self.provisioned_models:
            logger.info(f"Analyzer '{self.analyzer_model}' is also a provisioned model -- keeping it")
            return

        logger.info(f"Deleting temporary analyzer model '{self.analyzer_model}'...")
        try:
            await self.provider.unload_model(self.analyzer_model)
            await asyncio.sleep(1)
        except Exception:
            pass

        success = await self.provider.delete_model(self.analyzer_model)
        if success:
            logger.info(f"Successfully deleted temporary analyzer '{self.analyzer_model}'")
        else:
            logger.warning(f"Failed to delete temporary analyzer '{self.analyzer_model}' -- manual cleanup may be needed")

    def get_status(self) -> Dict[str, Any]:
        """Get current provisioning status."""
        return {
            "state": self.current_state,
            "tier": self.tier_name,
            "provisioned": self.provisioned_models,
            "failed": self.failed_models,
            "analyzer": self.analyzer_model,
            "analyzer_preexisting": self.analyzer_was_preexisting,
        }


# --- Entry Point for Server Integration --------------------------------------
async def run_first_start_provisioning(event_bus=None, base_dir: str = ".") -> Dict[str, Any]:
    """
    Entry point called from main.py lifespan.
    Sets up the Ollama provider and runs the provisioner.
    """
    from providers.ollama import OllamaProvider
    from config import OLLAMA_HOST

    provider = OllamaProvider(host=OLLAMA_HOST)

    async def event_bridge(event_type: str, data: Any = None):
        """Bridge provisioner events to the global EventBus."""
        if event_bus:
            try:
                await event_bus.publish("provisioning_event", {
                    "event": event_type,
                    "data": data
                })
            except Exception:
                pass

    provisioner = ModelProvisioner(
        ollama_provider=provider,
        event_callback=event_bridge,
        base_dir=base_dir
    )

    result = await provisioner.run()

    try:
        await provider.close()
    except Exception:
        pass

    return result
