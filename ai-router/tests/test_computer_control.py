import asyncio
import pytest
import pyautogui
from PIL import Image
from tools.desktop_utils import ensure_desktop_access
from tools.computer import ComputerControlTool, ComputerInput
from tools.screen_vision import ScreenVisionTool

@pytest.mark.asyncio
async def test_ensure_desktop_access():
    success = ensure_desktop_access()
    assert success is True, "ensure_desktop_access should succeed on interactive Windows session"

def test_pyautogui_screen_dimensions():
    ensure_desktop_access()
    size = pyautogui.size()
    assert size.width > 0 and size.height > 0
    print(f"Verified screen size: {size.width}x{size.height}")

@pytest.mark.asyncio
async def test_computer_control_move():
    import json
    ensure_desktop_access()
    tool = ComputerControlTool()
    res, tool_name = await tool.execute(user_id=1, action="move", x=500, y=400)
    assert tool_name == "computer_control"
    data = json.loads(res) if isinstance(res, str) else res
    assert data["success"] is True
    assert data["action"] == "move"
    assert data["target"] == {"x": 500, "y": 400}
    pos = pyautogui.position()
    assert (pos.x, pos.y) == (500, 400), f"Expected (500, 400) but got {pos}"

def test_computer_input_validation():
    # Test action validation
    inp = ComputerInput(action="click", x=100, y=200)
    assert inp.action == "click"
    assert inp.x == 100
    assert inp.y == 200

    # Test alias mapping from click_type
    inp2 = ComputerInput(click_type="double_click")
    assert inp2.action == "double_click"

    inp3 = ComputerInput(click_type="right_click")
    assert inp3.action == "right_click"

@pytest.mark.asyncio
async def test_screen_vision_capture():
    ensure_desktop_access()
    import mss
    from PIL import ImageGrab
    
    # Verify screenshot capability
    try:
        with mss.MSS() as sct:
            sct_img = sct.grab(sct.monitors[1])
            shot = Image.frombytes("RGB", sct_img.size, sct_img.bgra, "raw", "BGRX")
    except Exception:
        shot = ImageGrab.grab()
        
    assert shot is not None
    assert shot.size[0] > 0 and shot.size[1] > 0
    print(f"Captured screen frame: {shot.size}")

@pytest.mark.asyncio
async def test_screen_vision_tool_execution():
    class DummyProvider:
        async def _post(self, endpoint, payload):
            return {"response": "I see the active Windows desktop with various open windows."}
            
    class DummyMonitor:
        pass
        
    tool = ScreenVisionTool(provider=DummyProvider(), monitor=DummyMonitor())
    res, tool_name = await tool.execute(user_id=1, query="What is on screen?")
    assert tool_name == "screen_vision"
    assert "I see the active Windows desktop" in res
    print(f"Screen vision tool execution verified: {res[:60]}...")

if __name__ == "__main__":
    asyncio.run(test_ensure_desktop_access())
    test_pyautogui_screen_dimensions()
    asyncio.run(test_computer_control_move())
    test_computer_input_validation()
    asyncio.run(test_screen_vision_capture())
    asyncio.run(test_screen_vision_tool_execution())
    print("\nALL COMPUTER CONTROL TESTS PASSED SUCCESSFULLY!")
