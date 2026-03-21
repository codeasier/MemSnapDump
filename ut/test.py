import sys
import unittest
from pathlib import Path

ut_dir = Path(__file__).parent.resolve()
project_dir = Path(__file__).parent.parent.resolve()
# 由于ut目录下有与根目录下同名的各模块，需要将项目根目录放置到ut目录之前
if project_dir not in sys.path:
    idx = sys.path.index(str(ut_dir)) if str(ut_dir) in sys.path else -1
    sys.path.insert(idx, str(project_dir))



def run_tests():
    loader = unittest.defaultTestLoader
    suite = unittest.TestSuite()
    
    for module_name in ['base', 'simulate', 'tools', 'util']:
        module_dir = ut_dir / module_name
        for test_file in module_dir.glob('test_*.py'):
            module_import_name = f'ut.{module_name}.{test_file.stem}'
            try:
                module_suite = loader.loadTestsFromName(module_import_name)
                suite.addTests(module_suite)
            except Exception as e:
                print(f"Failed to load {module_import_name}: {e}")
    
    runner = unittest.TextTestRunner(verbosity=2)
    result = runner.run(suite)
    return 0 if result.wasSuccessful() else 1


if __name__ == "__main__":
    sys.exit(run_tests())
