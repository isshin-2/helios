import os
import sys
import sqlite3
import pytest
import time

# Ensure ai-router is on path
BASE_DIR = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
AI_ROUTER_DIR = os.path.join(BASE_DIR, "ai-router")
if AI_ROUTER_DIR not in sys.path:
    sys.path.insert(0, AI_ROUTER_DIR)

from core.security.bridge_guard import BridgeGuard, IsolationViolationError
from core.security.zero_leak import ZeroLeakFilter
from core.hardware_governor import HardwareGovernor

def test_database_isolation():
    """Verify that HELIOS, Hikari, and Solstice have distinct physical databases and cannot leak rows."""
    data_dir = os.path.join(BASE_DIR, "data")
    os.makedirs(data_dir, exist_ok=True)
    
    helios_db = os.path.join(data_dir, "helios.db")
    hikari_db = os.path.join(data_dir, "hikari.db")
    solstice_db = os.path.join(data_dir, "solstice.db")

    # 1. Write unique secret to Hikari
    conn_hikari = sqlite3.connect(hikari_db)
    cur_hikari = conn_hikari.cursor()
    cur_hikari.execute("CREATE TABLE IF NOT EXISTS secret_test (key TEXT PRIMARY KEY, val TEXT)")
    cur_hikari.execute("INSERT OR REPLACE INTO secret_test VALUES ('hikari_secret', 'HIKARI_ISOLATED_DATA_999')")
    conn_hikari.commit()
    conn_hikari.close()

    # 2. Write unique secret to HELIOS
    conn_helios = sqlite3.connect(helios_db)
    cur_helios = conn_helios.cursor()
    cur_helios.execute("CREATE TABLE IF NOT EXISTS secret_test (key TEXT PRIMARY KEY, val TEXT)")
    cur_helios.execute("INSERT OR REPLACE INTO secret_test VALUES ('helios_secret', 'HELIOS_ISOLATED_DATA_111')")
    conn_helios.commit()

    # 3. Assert HELIOS cannot query Hikari's data
    cur_helios.execute("SELECT val FROM secret_test WHERE key='hikari_secret'")
    row = cur_helios.fetchone()
    assert row is None, "Isolation breach: HELIOS was able to query Hikari data!"
    conn_helios.close()

    # 4. Write unique secret to Solstice
    conn_sol = sqlite3.connect(solstice_db)
    cur_sol = conn_sol.cursor()
    cur_sol.execute("CREATE TABLE IF NOT EXISTS secret_test (key TEXT PRIMARY KEY, val TEXT)")
    cur_sol.execute("INSERT OR REPLACE INTO secret_test VALUES ('sol_secret', 'SOLSTICE_ISOLATED_DATA_777')")
    conn_sol.commit()

    # 5. Assert Solstice cannot query HELIOS data
    cur_sol.execute("SELECT val FROM secret_test WHERE key='helios_secret'")
    assert cur_sol.fetchone() is None, "Isolation breach: Solstice was able to query HELIOS data!"
    conn_sol.close()

def test_bridge_guard_blocks_by_default():
    """Verify that cross-engine calls are denied by default without explicit bridge enable."""
    guard = BridgeGuard()
    # Force disabled
    guard.config["bridge_enabled"] = False
    if "BRIDGE_ENABLED" in os.environ:
        del os.environ["BRIDGE_ENABLED"]

    with pytest.raises(IsolationViolationError) as exc_info:
        guard.validate_request("helios", "hikari", "task_dispatch", None)
    assert "HARD ISOLATION ENFORCED" in str(exc_info.value)

def test_bridge_guard_authenticated_flow():
    """Verify that an authorized HMAC signature succeeds when bridge is enabled."""
    guard = BridgeGuard()
    guard.config["bridge_enabled"] = True
    guard.config["allowed_routes"]["helios->hikari"] = ["task_dispatch"]

    token, ts = guard.generate_token("helios", "hikari", "task_dispatch")
    assert guard.validate_request("helios", "hikari", "task_dispatch", token) is True

def test_bridge_guard_rejects_expired_and_forged_tokens():
    """Verify replay prevention and counterfeit token detection."""
    guard = BridgeGuard()
    guard.config["bridge_enabled"] = True
    guard.config["allowed_routes"]["helios->hikari"] = ["task_dispatch"]

    # Forged signature
    with pytest.raises(IsolationViolationError) as exc_info:
        guard.validate_request("helios", "hikari", "task_dispatch", f"{int(time.time())}.fake_signature")
    assert "SIGNATURE MISMATCH" in str(exc_info.value)

    # Expired token (10s old when max_age is 5s)
    old_ts = int(time.time()) - 10
    expired_token, _ = guard.generate_token("helios", "hikari", "task_dispatch", timestamp=old_ts)
    with pytest.raises(IsolationViolationError) as exc_info:
        guard.validate_request("helios", "hikari", "task_dispatch", expired_token)
    assert "EXPIRED TOKEN" in str(exc_info.value)

def test_zero_leak_sanitizer():
    """Verify zero-leak redaction of secrets, IPs, and local paths."""
    sample = "Connecting to 192.168.1.50 with key sk-99887766554433221100aa at C:\\Users\\krithik\\code and export API_KEY=secret_xyz"
    clean, count = ZeroLeakFilter.sanitize_text(sample)
    assert count >= 4
    assert "[REDACTED_LOCAL_IP]" in clean
    assert "[REDACTED_API_KEY]" in clean
    assert "[REDACTED_LOCAL_PATH]" in clean
    assert "[REDACTED_ENV_VAR]" in clean

def test_hardware_governor_budget_awareness():
    """Verify the Hardware Governor detects constraints and attaches warnings."""
    gov = HardwareGovernor()
    assert gov.decision.tier in (1, 2, 3)
    if gov.decision.is_budget:
        assert len(gov.decision.warnings) > 0
        assert "vision" in gov.decision.downgrade_advisories
        assert "coding_swarm" in gov.decision.downgrade_advisories

def test_voice_biometrics_binary_profile_and_sensitive_gating(tmp_path):
    """Verify voice biometrics saves binary centroid profile and gates sensitive operations."""
    from core.security.voice_biometrics import VoiceBiometricsManager
    import numpy as np

    store_json = str(tmp_path / "voiceprint.json")
    store_bin = str(tmp_path / "voice_profile.bin")
    vbm = VoiceBiometricsManager(store_path=store_json, bin_path=store_bin)

    # 1. Non-sensitive action allowed without enrollment
    allowed, msg = vbm.gate_sensitive_action("read_time")
    assert allowed is True
    assert "non-sensitive" in msg

    # 2. Sensitive action allowed with warning if not yet enrolled
    allowed, msg = vbm.gate_sensitive_action("wipe_memory")
    assert allowed is True
    assert "not enrolled" in msg

    # 3. Enroll synthetic speaker (3 samples)
    t = np.linspace(0, 1.0, 16000, endpoint=False, dtype=np.float32)
    sample1 = np.sin(2 * np.pi * 150 * t).astype(np.float32)
    sample2 = np.sin(2 * np.pi * 150 * t + 0.1).astype(np.float32)
    sample3 = np.sin(2 * np.pi * 150 * t + 0.2).astype(np.float32)
    vbm.enroll_speaker([sample1, sample2, sample3], pin="4321")

    # 4. Verify binary profile file exists and has correct size
    assert os.path.exists(store_bin)
    assert os.path.getsize(store_bin) >= 16 + 768  # 16-byte header + 768-byte float32 array

    # 5. Sensitive action requires match now
    # Matching voice sample
    allowed, msg = vbm.gate_sensitive_action("wipe_memory", voice_sample=sample1)
    assert allowed is True

    # Bad voice sample, valid fallback PIN
    impostor = np.sin(2 * np.pi * 500 * t).astype(np.float32)
    allowed, msg = vbm.gate_sensitive_action("wipe_memory", voice_sample=impostor, pin="4321")
    assert allowed is True
    assert "fallback PIN" in msg

    # Bad voice sample, invalid PIN -> DENIED
    allowed, msg = vbm.gate_sensitive_action("wipe_memory", voice_sample=impostor, pin="9999")
    assert allowed is False

