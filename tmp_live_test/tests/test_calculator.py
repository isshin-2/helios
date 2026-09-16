import sys
import os
sys.path.insert(0, os.path.abspath('tmp_live_test/src'))
from calculator import add

def test_add():
    assert add(2, 3) == 5
