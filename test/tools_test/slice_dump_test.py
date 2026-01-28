import os
import shutil
import unittest
import pandas as pd
from pathlib import Path
from simulate import SimulateDeviceSnapshot
from tools.slice_dump.hooker import SliceDumpHooker
from ..simulate_test import TestReplayEventHooker

current_dir = Path(__file__).parent.resolve()


class SliceDumpTest(unittest.TestCase):
    def setUp(self):
        self.tmp_out_dir = current_dir / '../test-data/slices'
        if os.path.exists(self.tmp_out_dir):
            shutil.rmtree(self.tmp_out_dir)
        os.makedirs(self.tmp_out_dir)

    def tearDown(self):
        shutil.rmtree(self.tmp_out_dir)

    def testSplitSnapshotWithDefaultArgs(self):
        snapshot_path = current_dir / '../test-data/' / 'snapshot_1768383987920985470.pkl'
        snapshot = SimulateDeviceSnapshot(pd.read_pickle(snapshot_path), 0)
        total_entries = len(snapshot.device_snapshot.trace_entries)
        expect_slices = max(total_entries // 15000, 4)
        hooker = SliceDumpHooker(
            dump_dir=self.tmp_out_dir
        )
        snapshot.register_hooker(hooker)
        snapshot.replay()
        pkl_files = [f for f in self.tmp_out_dir.iterdir() if f.is_file() and f.suffix == '.pkl']
        self.assertEqual(len(pkl_files), expect_slices)
        for pkl_file in pkl_files:
            snapshot_slice = SimulateDeviceSnapshot(pd.read_pickle(pkl_file), 0)
            snapshot_slice.register_hooker(TestReplayEventHooker(self))
            snapshot_slice.replay()

    def testSplitExpandableSnapshot(self):
        snapshot_path = current_dir / '../test-data/' / 'snapshot_expandable.pkl'
        snapshot = SimulateDeviceSnapshot(pd.read_pickle(snapshot_path), 0)
        total_entries = len(snapshot.device_snapshot.trace_entries)
        expect_slices = max(total_entries // 15000, 4)
        hooker = SliceDumpHooker(
            dump_dir=self.tmp_out_dir
        )
        snapshot.register_hooker(hooker)
        snapshot.replay()
        pkl_files = [f for f in self.tmp_out_dir.iterdir() if f.is_file() and f.suffix == '.pkl']
        self.assertEqual(len(pkl_files), expect_slices)
        for pkl_file in pkl_files:
            snapshot_slice = SimulateDeviceSnapshot(pd.read_pickle(pkl_file), 0)
            snapshot_slice.register_hooker(TestReplayEventHooker(self))
            snapshot_slice.replay()
