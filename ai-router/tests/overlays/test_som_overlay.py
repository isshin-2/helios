import unittest
import os
import PIL.Image
import PIL.ImageDraw
from tools.som_overlay import draw_grid_overlay, draw_marks, UIElement

class TestSOMOverlay(unittest.TestCase):
    def setUp(self):
        # Create a dummy image for testing
        self.img_size = (800, 600)
        self.img = PIL.Image.new("RGB", self.img_size, color="black")

    def test_draw_grid_overlay(self):
        # Test grid drawing logic
        img_with_grid, grid_map = draw_grid_overlay(self.img)
        
        # Verify grid map output
        self.assertIsNotNone(grid_map)
        self.assertEqual(len(grid_map), 16) # 4x4 grid = 16 cells
        
        # Verify specific cells exist
        self.assertIn("A1", grid_map)
        self.assertIn("D4", grid_map)
        
        # Verify centroid coordinates for A1
        # cell_w = 200, cell_h = 150 -> centroid should be (100, 75)
        self.assertEqual(grid_map["A1"], (100, 75))

    def test_draw_marks(self):
        # Create dummy UI elements
        elements = [
            UIElement(
                id=1,
                name="Test Button",
                control_type="Button",
                rect=(10, 10, 110, 60),
                centroid=(60, 35),
                is_enabled=True,
                is_visible=True
            ),
            UIElement(
                id=2,
                name="Test Input",
                control_type="Edit",
                rect=(200, 200, 300, 250),
                centroid=(250, 225),
                is_enabled=True,
                is_visible=True
            )
        ]
        
        img_with_marks, element_map = draw_marks(self.img, elements)
        
        self.assertEqual(len(element_map), 2)
        self.assertIn(1, element_map)
        self.assertIn(2, element_map)
        self.assertEqual(element_map[1].name, "Test Button")

if __name__ == "__main__":
    unittest.main()
