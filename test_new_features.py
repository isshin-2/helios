import asyncio
from core.verification import verification_manager
from core.agent_manager import agent_manager
from core.task_manager import TaskManager, TaskState

async def run_tests():
    print("--- TESTING HELIOS NEW FEATURES ---")
    
    # 1. Test Verification Manager (Heuristics)
    print("\n[1] Testing Verification Manager...")
    success, reason = verification_manager.verify_tool_result("AnyTool", {"status": "success", "result": "Traceback (most recent call last): ValueError"})
    print(f"Expected Reject (Traceback): {not success} - Reason: {reason}")
    
    success, reason = verification_manager.verify_tool_result("TerminalTool", {"status": "success", "result": "command not found: ls"})
    print(f"Expected Reject (Command not found): {not success} - Reason: {reason}")
    
    success, reason = verification_manager.verify_tool_result("AnyTool", {"status": "success", "result": "All good"})
    print(f"Expected Accept: {success} - Reason: {reason}")

    # 2. Test Bounded Recovery
    print("\n[2] Testing Bounded Recovery...")
    verification_manager.record_failure("test_task")
    verification_manager.record_failure("test_task")
    verification_manager.record_failure("test_task")
    can_recover = verification_manager.record_failure("test_task") # 4th time should fail (max 3)
    print(f"Expected Recovery Denied (Max Retries): {not can_recover}")
    
    # 3. Test Agent Manager
    print("\n[3] Testing Agent Manager...")
    agent = agent_manager.get_agent("browsing")
    print(f"Resolved 'browsing' to Agent: {agent.__class__.__name__}")
    
    # 4. Test Task Manager & Telemetry
    print("\n[4] Testing Task Manager & Telemetry...")
    tm = TaskManager()
    task = tm.create_task("session_123", "Test objective", 1)
    print(f"Task Initial State: {task.state.name}")
    task.transition(TaskState.RUNNING, "Starting execution")
    print(f"Task Transitioned to: {task.state.name}")
    task.transition(TaskState.COMPLETED, "Done")
    print(f"Task Final State: {task.state.name}")

    print("\nAll new subsystems successfully tested!")

asyncio.run(run_tests())
