import os
import shutil
import unittest
from pathlib import Path
from memsnapdump.util.file_util import load_pickle_to_dict
from memsnapdump.util.logger import suppress_logs, restore_logs
from memsnapdump.simulate import SimulateDeviceSnapshot
from memsnapdump.tools.slice_dump.hooker import SliceDumpHooker
from tests.simulate.test_simulate import ReplayEventHooker

test_data_dir = Path(__file__).parent.parent.resolve() / "test_data"


class SliceDumpTest(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        suppress_logs()

    @classmethod
    def tearDownClass(cls):
        restore_logs()

    def setUp(self):
        self.tmp_out_dir = test_data_dir / "slices"
        if os.path.exists(self.tmp_out_dir):
            shutil.rmtree(self.tmp_out_dir)
        os.makedirs(self.tmp_out_dir)

    def tearDown(self):
        shutil.rmtree(self.tmp_out_dir)

    def testSplitSnapshotWithDefaultArgs(self):
        snapshot_path = test_data_dir / "snapshot_with_empty_cache.pkl"
        snapshot = SimulateDeviceSnapshot(load_pickle_to_dict(snapshot_path), 0)
        total_entries = len(snapshot.device_snapshot.trace_entries)
        expect_slices = max(total_entries // 15000, 4)
        hooker = SliceDumpHooker(dump_dir=self.tmp_out_dir)
        snapshot.register_hooker(hooker)
        self.assertTrue(snapshot.replay())
        pkl_files = [
            f for f in self.tmp_out_dir.iterdir() if f.is_file() and f.suffix == ".pkl"
        ]
        self.assertEqual(len(pkl_files), expect_slices)
        for pkl_file in pkl_files:
            snapshot_slice = SimulateDeviceSnapshot(load_pickle_to_dict(pkl_file), 0)
            snapshot_slice.register_hooker(ReplayEventHooker(self))
            self.assertTrue(snapshot_slice.replay())

    def testSplitExpandableSnapshot(self):
        snapshot_path = test_data_dir / "snapshot_with_empty_cache_expandable.pkl"
        snapshot = SimulateDeviceSnapshot(load_pickle_to_dict(snapshot_path), 0)
        total_entries = len(snapshot.device_snapshot.trace_entries)
        expect_slices = max(total_entries // 15000, 4)
        hooker = SliceDumpHooker(dump_dir=self.tmp_out_dir)
        snapshot.register_hooker(hooker)
        self.assertTrue(snapshot.replay())
        pkl_files = [
            f for f in self.tmp_out_dir.iterdir() if f.is_file() and f.suffix == ".pkl"
        ]
        self.assertEqual(len(pkl_files), expect_slices)
        for pkl_file in pkl_files:
            snapshot_slice = SimulateDeviceSnapshot(load_pickle_to_dict(pkl_file), 0)
            snapshot_slice.register_hooker(ReplayEventHooker(self))
            self.assertTrue(snapshot_slice.replay())


if __name__ == "__main__":
    import unittest

    unittest.main(verbosity=2, module="test_slice_dump")
