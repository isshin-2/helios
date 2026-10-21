"""
TDD Suite: Comprehensive End-to-End Verification of All 34 HELIOS Tools
Validates that HELIOS ToolRouter can route and execute every single tool provided to it.
"""

import pytest
import os
import sys
from pathlib import Path
from unittest.mock import AsyncMock, patch, MagicMock

# Setup paths
AI_ROUTER_DIR = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(AI_ROUTER_DIR))

from core.tool_router import ToolRouter
from security.permissions import PermissionManager, HELIOS_REPO_ROOT, HELIOS_DIR
from health.monitor import SystemMonitor

@pytest.fixture
def mock_env():
    mock_provider = AsyncMock()
    mock_provider.generate.return_value = {
        "response": '{"summary": "Test response"}'
    }
    mock_provider.chat.return_value = {
        "message": {"content": "Test content", "role": "assistant"}
    }
    
    pm = PermissionManager()
    mon = SystemMonitor(mock_provider)
    router = ToolRouter(mock_provider, mon, pm)
    return router, pm, mock_provider

ALL_TOOLS = [
    "archival_memory_search",
    "ask_user",
    "bambu_printer_status",
    "bambu_printer_stop",
    "browser_tool",
    "computer_control",
    "core_memory_append",
    "directory_lister",
    "env_secrets",
    "file_patch",
    "file_patcher",
    "file_reader",
    "file_writer",
    "git_ops",
    "github_create_issue",
    "github_list_issues",
    "google_drive_list_files",
    "google_drive_read_file",
    "http_client",
    "llmfit",
    "octoprint_control",
    "octoprint_status",
    "process_monitor",
    "repo_map",
    "reverse_engineer",
    "screen_vision",
    "self_modification",
    "sidecar_control",
    "stateful_repl",
    "stateful_shell",
    "subagent",
    "system_management",
    "terminal",
    "web_search"
]

def test_all_34_tools_registered_in_router(mock_env):
    router, _, _ = mock_env
    schemas = router.get_tool_schemas()
    registered_names = {s["function"]["name"] for s in schemas}
    
    missing = [t for t in ALL_TOOLS if t not in registered_names]
    assert not missing, f"Missing tools in router schemas: {missing}"
    assert len(registered_names) == 34

@pytest.mark.parametrize("tool_name", ALL_TOOLS)
@pytest.mark.asyncio
async def test_every_tool_executable_via_router(mock_env, tool_name, tmp_path):
    router, pm, provider = mock_env
    user_id = 1
    
    # Tool-specific minimal valid arguments to test execution path
    sample_args = {
        "archival_memory_search": {"query": "helios architecture"},
        "ask_user": {"question": "Ready?", "options": ["yes", "no"]},
        "bambu_printer_status": {"ip_address": "127.0.0.1", "access_code": "00000000", "serial_number": "01P00A000000000"},
        "bambu_printer_stop": {"ip_address": "127.0.0.1", "access_code": "00000000", "serial_number": "01P00A000000000"},
        "browser_tool": {"url": "https://example.com", "action": "extract_text"},
        "computer_control": {"action": "cursor_position"},
        "core_memory_append": {"section": "test_section", "content": "test_content"},
        "directory_lister": {"directory_path": str(HELIOS_DIR)},
        "env_secrets": {"show_keys_only": True},
        "file_patch": {"file_path": "README.md", "search_block": "test", "replace_block": "test"},
        "file_patcher": {"file_path": "README.md", "search_block": "test", "replace_block": "test"},
        "file_reader": {"file_path": "README.md"},
        "file_writer": {"file_path": "test_dummy.txt", "content": "dummy"},
        "git_ops": {"action": "status"},
        "github_create_issue": {"repo": "owner/repo", "title": "Test Issue", "body": "Body"},
        "github_list_issues": {"repo": "owner/repo"},
        "google_drive_list_files": {"query": "test"},
        "google_drive_read_file": {"file_id": "dummy_id"},
        "http_client": {"url": "http://127.0.0.1:8000/health", "method": "GET"},
        "llmfit": {"action": "system"},
        "octoprint_control": {"action": "pause"},
        "octoprint_status": {},
        "process_monitor": {"action": "system_stats"},
        "repo_map": {"root_path": str(HELIOS_DIR)},
        "reverse_engineer": {"action": "rea_knowledge", "topic": "ghidra"},
        "screen_vision": {"query": "Find buttons"},
        "self_modification": {"action": "list_experiments"},
        "sidecar_control": {"action": "status"},
        "stateful_repl": {"code": "x = 42\nprint(x)"},
        "stateful_shell": {"command": "echo helios_test"},
        "subagent": {"task": "verify tool system", "budget": 1},
        "system_management": {"action": "list_models"},
        "terminal": {"command": "dir"},
        "web_search": {"query": "helios autonomous agent"}
    }
    
    args = sample_args.get(tool_name, {})
    
    # Patches for tools that touch network / external systems to ensure unit isolation
    with patch.dict(os.environ, {"DOCKER_ENV": "1"}), \
         patch("httpx.AsyncClient.request") as mock_req, \
         patch("asyncio.create_subprocess_exec") as mock_subproc, \
         patch("tools.screen_vision.ScreenVisionTool.execute", new_callable=AsyncMock) as mock_vision, \
         patch("tools.computer.ComputerControlTool.execute", new_callable=AsyncMock) as mock_comp, \
         patch("tools.browser_tool.async_playwright") as mock_playwright, \
         patch("tools.web_search.DDGS") as mock_ddgs:
         
        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.headers = {"content-type": "application/json"}
        mock_response.text = '{"status": "ok"}'
        mock_req.return_value = mock_response
        
        mock_proc = AsyncMock()
        mock_proc.communicate.return_value = (b"yes", b"")
        mock_subproc.return_value = mock_proc

        mock_vision.return_value = ("Screen analysis complete.", "screen_vision")
        mock_comp.return_value = ("(100, 100)", "computer_control")

        # Mock browser page
        mock_page = AsyncMock()
        mock_page.evaluate.return_value = "Sample page extracted content"
        mock_page.goto.return_value = None
        mock_browser = AsyncMock()
        mock_browser.new_page.return_value = mock_page
        mock_p_ctx = AsyncMock()
        mock_p_ctx.chromium.launch.return_value = mock_browser
        mock_playwright.return_value.__aenter__.return_value = mock_p_ctx

        # Mock DDGS
        mock_ddgs_instance = MagicMock()
        mock_ddgs_instance.text.return_value = [{"title": "HELIOS AI", "body": "Autonomous agent framework", "href": "https://example.com"}]
        mock_ddgs.return_value.__enter__.return_value = mock_ddgs_instance

        result, returned_name = await router.execute(tool_name, user_id=user_id, **args)
        
        # Verify execution succeeded: returned_name must match the tool or an alias
        target_tool = router.tools[tool_name]
        valid_names = [target_tool.name] + getattr(target_tool, "aliases", [])
        assert returned_name in valid_names, f"Tool {tool_name} returned unexpected name {returned_name}"
        assert isinstance(result, str), f"Tool {tool_name} output must be a string, got {type(result)}"
        assert len(result) > 0, f"Tool {tool_name} returned empty result"
        assert not result.startswith("Error: Tool '"), f"Tool {tool_name} was not found: {result}"
