"""
Automated Test Suite for HELIOS Site, Sol Engine Cognitive Thinking Pipeline,
and Broken Authentication Defenses using Playwright Browser Automation.
"""

import os
import sys
import time
import json
import socket
import threading
import pytest
from http.server import SimpleHTTPRequestHandler, HTTPServer
from playwright.sync_api import sync_playwright

AI_ROUTER_DIR = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
if AI_ROUTER_DIR not in sys.path:
    sys.path.insert(0, AI_ROUTER_DIR)

SOLSTICE_DIR = os.path.abspath(os.path.join(AI_ROUTER_DIR, "..", "..", "solstice-addon"))
if os.path.exists(SOLSTICE_DIR) and SOLSTICE_DIR not in sys.path:
    sys.path.insert(0, SOLSTICE_DIR)

SITE_DIST_DIR = os.path.abspath(os.path.join(AI_ROUTER_DIR, "..", "..", "helios-site", "dist"))
if not os.path.exists(SITE_DIST_DIR):
    SITE_DIST_DIR = os.path.abspath(os.path.join(AI_ROUTER_DIR, "..", "..", "helios-site"))


def get_free_port():
    s = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    s.bind(('', 0))
    port = s.getsockname()[1]
    s.close()
    return port


class QuietHandler(SimpleHTTPRequestHandler):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, directory=SITE_DIST_DIR, **kwargs)

    def log_message(self, format, *args):
        pass


@pytest.fixture(scope="module")
def site_server():
    port = get_free_port()
    server = HTTPServer(('127.0.0.1', port), QuietHandler)
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()
    time.sleep(0.3)
    yield f"http://127.0.0.1:{port}"
    server.shutdown()


def test_thinking_extraction_unit():
    """Verify cognitive thinking (<think>...</think>) tag parser in character_manager."""
    from core.character_manager import extract_thinking_and_content

    # Scenario 1: Standard reasoning model block
    raw = "<think>Evaluating memory bounds and kernel ring-0 safety.</think>All bounds validated. Safe."
    thinking, clean = extract_thinking_and_content(raw)
    assert thinking == "Evaluating memory bounds and kernel ring-0 safety."
    assert clean == "All bounds validated. Safe."

    # Scenario 2: No think tags
    raw_plain = "Direct system response without explicit thought block."
    thinking2, clean2 = extract_thinking_and_content(raw_plain)
    assert thinking2 == ""
    assert clean2 == raw_plain

    # Scenario 3: Broken/unclosed think tag
    raw_unclosed = "<think>Initial thought formulation without closure"
    thinking3, clean3 = extract_thinking_and_content(raw_unclosed)
    assert "Initial thought formulation" in thinking3


def test_solstice_cognitive_chat_unit():
    """Verify Solstice engine cognitive chat pipeline and persona-differentiated reasoning."""
    import ai_server as solstice_server
    from ai_server import SolChatRequest

    # Test Airi Persona
    req_airi = SolChatRequest(message="Test exploit scan", avatar="airi")
    res_airi = solstice_server.sol_chat(req_airi)
    assert isinstance(res_airi, dict)
    assert res_airi["avatar"] == "airi"
    assert len(res_airi["thinking"]) > 0
    assert "Airi" in res_airi["thinking"] or "Cognitive Engine" in res_airi["thinking"]
    assert res_airi["emissive_color"] == "#00E5FF"
    assert len(res_airi["reply"]) > 0

    # Test Ren Tactical Persona
    req_ren = SolChatRequest(message="Audit memory safety", avatar="ren")
    res_ren = solstice_server.sol_chat(req_ren)
    assert isinstance(res_ren, dict)
    assert res_ren["avatar"] == "ren"
    assert "Ren" in res_ren["thinking"] or "Tactical" in res_ren["thinking"]
    assert res_ren["emissive_color"] == "#FF9900"
    assert res_ren["emotion"] == "tactical"

    # Test Dual Synergy Mode
    req_dual = SolChatRequest(message="Synchronize twins", avatar="dual")
    res_dual = solstice_server.sol_chat(req_dual)
    assert isinstance(res_dual, dict)
    assert res_dual["avatar"] == "dual"
    assert "Airi" in res_dual["thinking"] and "Ren" in res_dual["thinking"]
    assert res_dual["emotion"] == "excited"


def test_bridgeguard_security_and_broken_auth_defense():
    """Verify BridgeGuard Zero-Trust HMAC defense against forged tokens and tampering."""
    from core.security.bridge_guard import BridgeGuard, IsolationViolationError

    guard = BridgeGuard()

    # Valid token generation
    token, ts = guard.generate_token("solstice", "helios", "cognitive_query")
    assert isinstance(token, str)
    assert "." in token

    # Broken Auth Test 1: Forged signature attempt
    forged_token = f"{int(ts)}.000000000000000000000000000000000000000000000000000000000000dead"
    with pytest.raises(IsolationViolationError):
        # Even if enabled or disabled, forged token should fail validation
        guard.validate_request("solstice", "helios", "cognitive_query", forged_token)

    # Broken Auth Test 2: Expired timestamp (>5s)
    old_ts = time.time() - 100
    expired_token, _ = guard.generate_token("solstice", "helios", "cognitive_query", timestamp=old_ts)
    with pytest.raises(IsolationViolationError):
        guard.validate_request("solstice", "helios", "cognitive_query", expired_token)

    # Broken Auth Test 3: Unauthorized source engine route
    unauthorized_token, _ = guard.generate_token("attacker_rogue", "solstice", "avatar_telemetry")
    with pytest.raises(IsolationViolationError):
        guard.validate_request("attacker_rogue", "solstice", "avatar_telemetry", unauthorized_token)


def test_helios_site_playwright_e2e(site_server):
    """Playwright E2E browser automation verifying site navigation, 3D HoloDeck, Cognitive Lab, and Security Suite."""
    with sync_playwright() as p:
        browser = p.chromium.launch(headless=True)
        context = browser.new_context(viewport={"width": 1440, "height": 900})
        page = context.new_page()

        page.goto(site_server, wait_until="networkidle")

        # 1. Navigation & Tabs
        assert "HELIOS" in page.title()
        assert page.locator("#tab-sol").is_visible()
        assert page.locator("#tab-code").is_visible()
        assert page.locator("#tab-desk").is_visible()
        assert page.locator("#tab-downloads").is_visible()

        # 2. HoloDeck 3D WebGL Canvas & Persona Switching
        assert page.locator("#holodeck-section").is_visible()
        assert page.locator("#holodeck-btn-airi").is_visible()
        assert page.locator("#holodeck-btn-twin").is_visible()

        page.click("#holodeck-btn-twin")
        page.wait_for_timeout(300)
        page.click("#holodeck-btn-airi")
        page.wait_for_timeout(300)

        # 3. Sol Cognitive Pipeline & Reasoning Lab
        assert page.locator("#sol-cognitive-lab").is_visible()
        assert page.locator("#cog-btn-airi").is_visible()
        assert page.locator("#cog-btn-ren").is_visible()
        assert page.locator("#cog-btn-dual").is_visible()

        # Switch to Dual Synergy Mode and run cognitive thinking simulation
        page.click("#cog-btn-dual")
        page.wait_for_timeout(200)

        page.click("#btn-run-thinking")
        page.wait_for_selector("#cognitive-terminal-content:has-text('<think>')", timeout=5000)

        # Wait for thinking trace to finish streaming and transition to speaking
        page.wait_for_selector("#cognitive-terminal-content:has-text('Dual Twins')", timeout=8000)
        assert "COMPLETE" in page.locator("#cog-token-speed").inner_text()

        brain_dir = os.path.join(
            os.path.expanduser("~"), ".gemini", "antigravity", "brain",
            "1183a31c-ae38-49df-8581-9ef6bc483d70"
        )
        os.makedirs(brain_dir, exist_ok=True)

        cog_shot = os.path.join(brain_dir, "helios_cognitive_lab_verified.png")
        page.locator("#sol-cognitive-lab").screenshot(path=cog_shot)

        # 4. Downloads & Real Files
        page.click("#tab-downloads")
        page.wait_for_selector("#view-downloads", state="visible")

        # Click setup.bat download button
        download_btn = page.locator("button:has-text('Download setup.bat')")
        assert download_btn.is_visible()
        download_btn.click()

        # Toast notification appears
        page.wait_for_selector("#dl-toast", state="visible", timeout=3000)
        assert "setup.bat" in page.locator("#dl-toast-title").inner_text()

        # 5. Zero-Trust Security Lab & Broken Auth Test Suite
        assert page.locator("#auth-security-lab").is_visible()

        # Scenario 1: Test Genuine Pro License
        page.click("#btn-test-valid-license")
        page.wait_for_selector("#security-audit-status:has-text('PASSED (SECURE)')", timeout=3000)
        assert "Ed25519 Asymmetric Signature MATCH" in page.locator("#security-audit-output").inner_text()

        # Scenario 2: Simulate Tampered Entitlement (Attack)
        page.click("#btn-test-tampered-license")
        page.wait_for_selector("#security-audit-status:has-text('ATTACK TRAPPED (REJECTED)')", timeout=3000)
        assert "Broken Authentication Bypass Prevented" in page.locator("#security-audit-output").inner_text()

        # Scenario 3: Simulate Cross-Engine IPC Spoofing
        page.click("#btn-test-forged-bridge")
        page.wait_for_selector("#security-audit-status:has-text('BLOCKED (403 ISOLATION)')", timeout=3000)
        assert "403 Forbidden" in page.locator("#security-audit-output").inner_text()

        sec_shot = os.path.join(brain_dir, "helios_security_lab_verified.png")
        page.locator("#auth-security-lab").screenshot(path=sec_shot)

        screenshot_path = os.path.join(brain_dir, "helios_site_cognitive_and_security_verified.png")
        page.screenshot(path=screenshot_path, full_page=True)

        browser.close()
