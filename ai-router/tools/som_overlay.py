import logging
from dataclasses import dataclass
from typing import List, Tuple, Dict, Optional
import PIL.Image
import PIL.ImageDraw
import PIL.ImageFont

try:
    import pywinauto
except ImportError:
    pywinauto = None

from config import SOM_ENABLED, SOM_MIN_ELEMENT_THRESHOLD

logger = logging.getLogger(__name__)

@dataclass
class UIElement:
    id: int
    name: str
    control_type: str
    rect: Tuple[int, int, int, int]  # (left, top, right, bottom)
    centroid: Tuple[int, int]  # (cx, cy)
    is_enabled: bool
    is_visible: bool

def get_ui_elements() -> List[UIElement]:
    if pywinauto is None:
        logger.warning("pywinauto not installed. Cannot get UI elements for SoM overlay.")
        return []

    elements = []
    try:
        desktop = pywinauto.Desktop(backend='uia')
        windows = desktop.windows()
        
        if not windows:
            return []
            
        fg_window = windows[0] # assuming first is foreground/active
        
        valid_control_types = {'Button', 'Edit', 'CheckBox', 'ComboBox', 'MenuItem', 'ListItem', 'Link', 'TabItem', 'TreeItem'}
        
        # Traverse elements
        # Using a simple recursive approach up to depth 4
        def traverse(element, current_depth, max_depth):
            if current_depth > max_depth:
                return
            
            try:
                ctrl_type = element.element_info.control_type
                
                # Check if actionable
                if ctrl_type in valid_control_types:
                    rect = element.rectangle()
                    width = rect.width()
                    height = rect.height()
                    
                    # Screen bounds check and size check (>= 10x10)
                    if width >= 10 and height >= 10 and width < 4000 and height < 4000:
                        is_visible = element.is_visible()
                        is_enabled = element.is_enabled()
                        
                        if is_visible and is_enabled:
                            cx = rect.left + (width // 2)
                            cy = rect.top + (height // 2)
                            
                            name = element.element_info.name or ""
                            
                            ui_el = UIElement(
                                id=len(elements) + 1,
                                name=name,
                                control_type=ctrl_type,
                                rect=(rect.left, rect.top, rect.right, rect.bottom),
                                centroid=(cx, cy),
                                is_enabled=is_enabled,
                                is_visible=is_visible
                            )
                            elements.append(ui_el)
                            
                for child in element.children():
                    traverse(child, current_depth + 1, max_depth)
            except Exception as e:
                logger.debug(f"Error traversing element: {e}")

        traverse(fg_window, 1, 4)
        
    except Exception as e:
        logger.error(f"Failed to get UI elements: {e}")
        
    return elements


def draw_grid_overlay(screenshot: PIL.Image.Image) -> Tuple[PIL.Image.Image, Dict[str, Tuple[int, int]]]:
    width, height = screenshot.size
    cell_w = width // 4
    cell_h = height // 4
    
    # Create a copy so we don't modify the original directly
    img = screenshot.copy()
    draw = PIL.ImageDraw.Draw(img)
    
    try:
        font = PIL.ImageFont.truetype("arial.ttf", 20)
    except IOError:
        font = PIL.ImageFont.load_default()
        
    grid_map = {}
    cols = ['A', 'B', 'C', 'D']
    rows = ['1', '2', '3', '4']
    
    for i in range(4):
        for j in range(4):
            x = i * cell_w
            y = j * cell_h
            
            # Draw cell bounds (thin red lines)
            draw.rectangle([x, y, x + cell_w, y + cell_h], outline="red", width=1)
            
            # Label
            label = f"{cols[i]}{rows[j]}"
            
            # Calculate centroid
            cx = x + cell_w // 2
            cy = y + cell_h // 2
            grid_map[label] = (cx, cy)
            
            # Draw label box
            text_bbox = draw.textbbox((0, 0), label, font=font)
            text_w = text_bbox[2] - text_bbox[0]
            text_h = text_bbox[3] - text_bbox[1]
            
            draw.rectangle([x, y, x + text_w + 4, y + text_h + 4], fill="white", outline="red", width=1)
            draw.text((x + 2, y + 2), label, fill="red", font=font)
            
    return img, grid_map


def draw_marks(screenshot: PIL.Image.Image, elements: List[UIElement]) -> Tuple[PIL.Image.Image, Dict[int, UIElement]]:
    img = screenshot.copy()
    draw = PIL.ImageDraw.Draw(img)
    
    try:
        font = PIL.ImageFont.truetype("arial.ttf", 14)
    except IOError:
        font = PIL.ImageFont.load_default()
        
    element_map = {}
    
    for el in elements:
        element_map[el.id] = el
        left, top, right, bottom = el.rect
        
        # Draw bounding box
        draw.rectangle([left, top, right, bottom], outline="red", width=2)
        
        # Draw ID label background and text
        label = str(el.id)
        text_bbox = draw.textbbox((0, 0), label, font=font)
        text_w = text_bbox[2] - text_bbox[0]
        text_h = text_bbox[3] - text_bbox[1]
        
        draw.rectangle([left, top, left + text_w + 4, top + text_h + 4], fill="white", outline="red", width=1)
        draw.text((left + 2, top + 2), label, fill="red", font=font)
        
    return img, element_map


def get_element_coordinates(mark_id: int, element_map: Dict[int, UIElement]) -> Tuple[int, int]:
    if mark_id not in element_map:
        raise ValueError(f"Element ID {mark_id} not found in map")
    return element_map[mark_id].centroid
