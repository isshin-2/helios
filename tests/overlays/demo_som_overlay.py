import os
import sys
import PIL.ImageGrab

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))
from tools.som_overlay import draw_grid_overlay

def demo_som():
    print("Taking screenshot...")
    # Grab full screen
    screenshot = PIL.ImageGrab.grab()
    
    print("Drawing Set-of-Mark Grid Overlay...")
    img_with_grid, grid_map = draw_grid_overlay(screenshot)
    
    print("Opening annotated image in default viewer...")
    img_with_grid.show()

if __name__ == "__main__":
    demo_som()
