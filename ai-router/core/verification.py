import logging
from typing import Dict, Any, Tuple

logger = logging.getLogger(__name__)

class RecoveryManager:
    """
    Phase 6 & 7: Verification and Bounded Recovery.
    Tracks failure streaks per task to enforce Unbounded execution -> STOP.
    """
    def __init__(self, max_retries: int = 3):
        self.max_retries = max_retries
        self.task_failures: Dict[str, int] = {}

    def record_failure(self, task_id: str) -> bool:
        """
        Records a failure. 
        Returns True if recovery is allowed, False if limit exceeded.
        """
        failures = self.task_failures.get(task_id, 0) + 1
        self.task_failures[task_id] = failures
        
        if failures > self.max_retries:
            logger.warning(f"Task {task_id} exceeded max recovery attempts ({self.max_retries}).")
            return False
        return True

    def record_success(self, task_id: str):
        """Resets the failure streak upon a verified success."""
        if task_id in self.task_failures:
            self.task_failures[task_id] = 0

    def verify_tool_result(self, tool_name: str, result_dict: Dict[str, Any]) -> Tuple[bool, str]:
        """
        Phase 6: Heuristic verification of tool outputs.
        Returns (is_verified, reason).
        """
        status = result_dict.get("status")
        result_text = str(result_dict.get("result", ""))
        
        if status in ["error", "validation_error", "permission_denied", "unavailable"]:
            return False, f"Tool reported formal failure status: {status}"
            
        # Heuristic checks for silent failures
        if "traceback (most recent call last)" in result_text.lower():
            return False, "Detected unhandled Python traceback in output."
            
        if tool_name == "TerminalTool":
            if "command not found" in result_text.lower() or "not recognized as an internal or external command" in result_text.lower():
                return False, "Terminal command failed to execute (command not found)."
            
        return True, "Result heuristically verified."

verification_manager = RecoveryManager()
