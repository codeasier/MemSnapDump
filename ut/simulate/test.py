import sys
import unittest
from pathlib import Path

project_dir = Path(__file__).parent.parent.parent.resolve()
if project_dir not in sys.path:
    sys.path.append(str(project_dir))

module_dir = Path(__file__).parent.resolve()


def run_tests():
    loader = unittest.defaultTestLoader
    suite = loader.discover(module_dir, pattern='test_*.py')
    runner = unittest.TextTestRunner(verbosity=2)
    result = runner.run(suite)
    return 0 if result.wasSuccessful() else 1


if __name__ == "__main__":
    sys.exit(run_tests())
