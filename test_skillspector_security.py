import os
import unittest
import sys

# Ensure we're in the right directory and marker is clean
ROOT_DIR = os.path.dirname(os.path.abspath(__file__))
MARKER_PATH = os.path.join(ROOT_DIR, "malicious_marker.txt")

if os.path.exists(MARKER_PATH):
    os.remove(MARKER_PATH)

import config
config.SKILLS_VALIDATION_TIMEOUT = 120
from skills.manifest import manifest_manager

class TestSkillspectorSecurity(unittest.TestCase):
    def test_malicious_skill_quarantined_not_imported(self):
        # The malicious skill should NOT be in the loaded skills
        self.assertNotIn("malicious_skill", manifest_manager.skills)
        
        # The marker file should NOT exist because the module was never imported
        self.assertFalse(os.path.exists(MARKER_PATH), "CRITICAL: Malicious skill was imported!")
        
        # Verify quarantine metadata was generated
        quarantine_file = os.path.join(ROOT_DIR, "quarantine", "malicious_skill_test.py.quarantine.json")
        self.assertTrue(os.path.exists(quarantine_file), "Quarantine metadata was not created")

    def test_safe_skill_loaded(self):
        # InternetSkill is safe and should be loaded
        self.assertIn("InternetSkill", manifest_manager.skills)
        
if __name__ == "__main__":
    unittest.main()
