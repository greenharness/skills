"""sweep.py loads as a module without running its command line.

The skill's directory name has a hyphen, so it is not an importable package:
tests load the file by path.
"""
import importlib.util
import sys
import unittest
from pathlib import Path

SWEEP = Path(__file__).resolve().parent.parent / "parts/workflow/skills/worktree-sweep/sweep.py"


def load_sweep():
    spec = importlib.util.spec_from_file_location("sweep", SWEEP)
    module = importlib.util.module_from_spec(spec)
    # Registered first: @dataclass looks its module up in sys.modules.
    sys.modules["sweep"] = module
    spec.loader.exec_module(module)
    return module


class Loads(unittest.TestCase):
    def test_loads_without_running_main(self):
        self.assertTrue(callable(load_sweep().main))


if __name__ == "__main__":
    unittest.main()
