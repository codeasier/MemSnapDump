import unittest
import pandas as pd
from pathlib import Path
from base import TraceEntry, DeviceSnapshot, Segment, Block, BlockState
from simulate import SimulateDeviceSnapshot, SimulateHooker
from test.common import valid_segments

current_dir = Path(__file__).parent.resolve()

class TestReplayEventHooker(SimulateHooker):
    def __init__(self, test_util, valid_interval: int = 100):
        self.test_util = test_util
        self.replay_count = 0
        self.valid_interval = valid_interval

    def pre_undo_event(self, wait4undo_event: TraceEntry, current_snapshot: DeviceSnapshot) -> bool:
        return True

    def post_undo_event(self, already_undo_event: TraceEntry, current_snapshot: DeviceSnapshot) -> bool:
        # 每经历100个事件校验一次segment
        if self.replay_count % self.valid_interval == 0:
            valid_segments(current_snapshot.segments, self.test_util)
        return True


class TestSimulate(unittest.TestCase):

    def setUp(self):
        # 普通未开启虚拟内存snapshot
        snapshot_path = current_dir / 'test-data/snapshot_1768383987920985470.pkl'
        vmem_snapshot_path = current_dir / 'test-data/snapshot_expandable.pkl'
        self.snapshot = SimulateDeviceSnapshot(pd.read_pickle(snapshot_path), 0)
        # 开启虚拟内存的snapshot
        self.vmem_snapshot = SimulateDeviceSnapshot(pd.read_pickle(vmem_snapshot_path), 0)

    def tearDown(self):
        ...

    def testRawSnapshotValidity(self):
        valid_segments(self.snapshot.device_snapshot.segments, self)
        valid_segments(self.vmem_snapshot.device_snapshot.segments, self)

    def testReplaySnapshot(self):
        self.snapshot.register_hooker(TestReplayEventHooker(self))
        self.snapshot.replay()

    def testReplayVMemSnapshot(self):
        self.vmem_snapshot.register_hooker(TestReplayEventHooker(self))
        self.vmem_snapshot.replay()
