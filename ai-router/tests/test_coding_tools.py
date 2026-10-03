import asyncio
import logging
import os
import sys

sys.stdout.reconfigure(encoding='utf-8')

from tools.stateful_shell import StatefulShellTool
from security.permissions import PermissionManager, PermissionResult

import pytest

logging.basicConfig(level=logging.INFO)

@pytest.mark.asyncio
async def test_coding_tools():
    print("Initializing Permission Manager...", flush=True)
    pm = PermissionManager()
    
    # Mock approval manager and permission manager
    pm.approval_manager.has_session_approval = lambda user_id, action, target: True
    pm.can_execute = lambda user_id, cmd, args, cwd: PermissionResult(True, "Allowed for test")
    
    print("\nInitializing Tools...", flush=True)
    shell_tool = StatefulShellTool(permission_manager=pm)
    
    test_script_path = "test_fib.py"
    code = """def fib(n):
    if n <= 1:
        return n
    return fib(n-1) + fib(n-2)

print('Fibonacci of 10 is:', fib(10))
"""
    print(f"\n[1] Writing {test_script_path}...", flush=True)
    with open(test_script_path, "w") as f:
        f.write(code)
    print("Done.", flush=True)
        
    print(f"\n[2] Testing StatefulShellTool (Running 'python {test_script_path}')...", flush=True)
    try:
        result, name = await shell_tool.execute(
            user_id=1,
            command=f"python {test_script_path}"
        )
        print(f"Result:\n{result}", flush=True)
    except Exception as e:
        print(f"StatefulShellTool failed: {e}", flush=True)
        
    print(f"\n[3] Cleanup...", flush=True)
    try:
        if os.path.exists(test_script_path):
            os.remove(test_script_path)
            print("Cleanup successful.", flush=True)
    except Exception as e:
        print(f"Cleanup failed: {e}", flush=True)

if __name__ == "__main__":
    asyncio.run(test_coding_tools())
