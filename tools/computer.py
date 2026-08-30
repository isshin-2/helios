import logging
from typing import Tuple, List, Optional
from pydantic import BaseModel, Field

try:
    import pyautogui
    pyautogui.FAILSAFE = False
except ImportError:
    pyautogui = None

from tools.base import BaseTool

logger = logging.getLogger(__name__)

class ComputerInput(BaseModel):
    action: str = Field(..., description="Action to perform: 'move', 'click', 'double_click', 'right_click', 'type', 'press', 'hotkey', 'scroll'")
    x: Optional[int] = Field(None, description="X coordinate for move/click")
    y: Optional[int] = Field(None, description="Y coordinate for move/click")
    text: Optional[str] = Field(None, description="Text to type")
    keys: Optional[List[str]] = Field(None, description="Keys to press or hotkey combo (e.g. ['ctrl', 'c'])")
    amount: Optional[int] = Field(None, description="Amount to scroll")

class ComputerControlTool(BaseTool):
    """
    Agentic computer control. Allows the AI to interact with the PC by moving the mouse, clicking, and typing.
    """
    
    def __init__(self, **kwargs):
        pass
        
    @property
    def name(self) -> str:
        return "computer_control"
        
    @property
    def description(self) -> str:
        return "Interact with the user's computer (mouse, keyboard). Pair this with screen_vision to see the UI. ALWAYS request the user's screen before clicking."
        
    @property
    def input_schema(self) -> type[BaseModel]:
        return ComputerInput
        
    @property
    def requires_permission(self) -> bool:
        return False # Set to false to avoid interrupting the agent flow unnecessarily, assuming they want autonomous agents.
        
    async def execute(self, user_id: int, **kwargs) -> Tuple[str, str]:
        if pyautogui is None:
            return ("Error: pyautogui is not installed.", self.name)
            
        action = kwargs.get("action")
        
        try:
            if action == "move":
                x = kwargs.get("x")
                y = kwargs.get("y")
                pyautogui.moveTo(x, y, duration=0.5)
                return (f"Moved mouse to ({x}, {y})", self.name)
                
            elif action == "click":
                x = kwargs.get("x")
                y = kwargs.get("y")
                if x is not None and y is not None:
                    pyautogui.click(x=x, y=y)
                    return (f"Clicked at ({x}, {y})", self.name)
                else:
                    pyautogui.click()
                    return ("Clicked at current mouse position", self.name)
                    
            elif action == "double_click":
                pyautogui.doubleClick()
                return ("Double clicked", self.name)
                
            elif action == "right_click":
                pyautogui.rightClick()
                return ("Right clicked", self.name)
                
            elif action == "type":
                text = kwargs.get("text", "")
                pyautogui.write(text, interval=0.01)
                return (f"Typed text: '{text}'", self.name)
                
            elif action == "press":
                keys = kwargs.get("keys", [])
                for key in keys:
                    pyautogui.press(key)
                return (f"Pressed keys: {keys}", self.name)
                
            elif action == "hotkey":
                keys = kwargs.get("keys", [])
                pyautogui.hotkey(*keys)
                return (f"Executed hotkey: {keys}", self.name)
                
            elif action == "scroll":
                amount = kwargs.get("amount", 0)
                pyautogui.scroll(amount)
                return (f"Scrolled {amount}", self.name)
                
            else:
                return (f"Unknown action: {action}", self.name)
                
        except Exception as e:
            logger.error(f"Computer control failed: {e}")
            return (f"Error executing {action}: {str(e)}", self.name)
