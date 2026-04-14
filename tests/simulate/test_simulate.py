import os
from pathlib import Path

import unittest
import copy
from memsnapdump.base import TraceEntry, DeviceSnapshot, Segment, Block, BlockState
from memsnapdump.util.file_util import load_pickle_to_dict
from memsnapdump.util.logger import suppress_logs, restore_logs
from memsnapdump.simulate import SimulateDeviceSnapshot, SimulateHooker
from memsnapdump.simulate.hooker_defs import AllocatorHooker
from tests.common import valid_segments

test_data_dir = Path(__file__).parent.parent.resolve() / 'test_data'

class ReplayEventHooker(SimulateHooker):
    def __init__(self, test_util, valid_interval: int = 100):
        self.test_util = test_util
        self.replay_count = 0
        self.valid_interval = valid_interval

    def pre_undo_event(self, wait4undo_event: TraceEntry, current_snapshot: DeviceSnapshot) -> bool:
        return True

    def post_undo_event(self, already_undo_event: TraceEntry, current_snapshot: DeviceSnapshot) -> bool:
        if self.replay_count % self.valid_interval == 0:
            valid_segments(current_snapshot.segments, self.test_util)
        self.replay_count += 1
        return True


class ReplayBlockHooker(AllocatorHooker):
    def __init__(self, test_util: unittest.TestCase):
        self.test_util = test_util
        self._segment = None
        self.pre_seg_allocated_size = 0
        self.pre_seg_active_size = 0
        self.pre_snapshot_total_allocated_size = 0
        self.pre_snapshot_total_active_size = 0

    def pre_replay_alloc_block(self, wait4alloc_block: Block, current_snapshot: DeviceSnapshot):
        super().pre_replay_alloc_block(wait4alloc_block, current_snapshot)
        self.test_util.assertNotEqual(wait4alloc_block.state, BlockState.INACTIVE)
        _segment_idx = current_snapshot.find_segment_idx_by_addr(wait4alloc_block.address)
        self.test_util.assertTrue(0 <= _segment_idx < len(current_snapshot.segments))
        self._segment = current_snapshot.segments[_segment_idx]
        self.pre_seg_allocated_size = self._segment.allocated_size
        self.pre_seg_active_size = self._segment.active_size
        self.pre_snapshot_total_allocated_size = current_snapshot.total_allocated
        self.pre_snapshot_total_active_size = current_snapshot.total_activated

    def post_replay_alloc_block(self, allocated_block: Block, current_snapshot: DeviceSnapshot):
        super().post_replay_alloc_block(allocated_block, current_snapshot)
        self.test_util.assertEqual(self.pre_seg_active_size + allocated_block.size, self._segment.active_size)
        self.test_util.assertEqual(self.pre_snapshot_total_active_size + allocated_block.size,
                                   current_snapshot.total_activated)
        if allocated_block.state == BlockState.ACTIVE_ALLOCATED:
            self.test_util.assertEqual(self.pre_seg_allocated_size + allocated_block.size, self._segment.allocated_size)
            self.test_util.assertEqual(self.pre_snapshot_total_allocated_size + allocated_block.size,
                                       current_snapshot.total_allocated)

    def pre_replay_free_block(self, wait4free_block: Block, current_snapshot: DeviceSnapshot):
        super().pre_replay_free_block(wait4free_block, current_snapshot)

    def post_replay_free_block(self, released_block: Block, current_snapshot: DeviceSnapshot):
        super().post_replay_free_block(released_block, current_snapshot)


class TestSimulate(unittest.TestCase):

    snapshot_path = test_data_dir / 'snapshot_1768383987920985470.pkl'
    vmem_snapshot_path = test_data_dir / 'snapshot_expandable.pkl'
    snapshot_with_empty_cache_path = test_data_dir / 'snapshot_with_empty_cache.pkl'
    vmem_snapshot_with_empty_cache_path = test_data_dir / 'snapshot_with_empty_cache_expandable.pkl'

    @classmethod
    def setUpClass(cls):
        if os.getenv("UT_VERBOSE_LOG") != "1":
            suppress_logs()

    @classmethod
    def tearDownClass(cls):
        restore_logs()

    @staticmethod
    def get_simulate_snapshot(snapshot_path: Path):
        return SimulateDeviceSnapshot(load_pickle_to_dict(snapshot_path), 0)

    def testBlockHookerInSnapshot(self):
        snapshot = TestSimulate.get_simulate_snapshot(self.snapshot_path)
        valid_segments(snapshot.device_snapshot.segments, self)
        snapshot.register_allocator_hooker(ReplayBlockHooker(self))
        self.assertTrue(snapshot.replay())

    def testBlockHookerInVmemSnapshot(self):
        snapshot = TestSimulate.get_simulate_snapshot(self.vmem_snapshot_path)
        valid_segments(snapshot.device_snapshot.segments, self)
        snapshot.register_allocator_hooker(ReplayBlockHooker(self))
        self.assertTrue(snapshot.replay())

    def testBlockHookerInSnapshotWithEmptyCache(self):
        snapshot = TestSimulate.get_simulate_snapshot(self.snapshot_with_empty_cache_path)
        valid_segments(snapshot.device_snapshot.segments, self)
        snapshot.register_allocator_hooker(ReplayBlockHooker(self))
        self.assertTrue(snapshot.replay())

    def testBlockHookerInVmemSnapshotWithEmptyCache(self):
        snapshot = TestSimulate.get_simulate_snapshot(self.vmem_snapshot_with_empty_cache_path)
        valid_segments(snapshot.device_snapshot.segments, self)
        snapshot.register_allocator_hooker(ReplayBlockHooker(self))
        self.assertTrue(snapshot.replay())

    def testReplaySnapshot(self):
        snapshot = TestSimulate.get_simulate_snapshot(self.snapshot_path)
        snapshot.register_hooker(ReplayEventHooker(self))
        self.assertTrue(snapshot.replay())

    def testReplayVmemSnapshot(self):
        snapshot = TestSimulate.get_simulate_snapshot(self.vmem_snapshot_path)
        snapshot.register_hooker(ReplayEventHooker(self))
        self.assertTrue(snapshot.replay())

    def testReplaySnapshotWithEmptyCache(self):
        snapshot = TestSimulate.get_simulate_snapshot(self.snapshot_with_empty_cache_path)
        snapshot.register_hooker(ReplayEventHooker(self))
        self.assertTrue(snapshot.replay())

    def testReplayVmemSnapshotWithEmptyCache(self):
        snapshot = TestSimulate.get_simulate_snapshot(self.vmem_snapshot_with_empty_cache_path)
        snapshot.register_hooker(ReplayEventHooker(self))
        self.assertTrue(snapshot.replay())


if __name__ == "__main__":
    import unittest
    unittest.main(verbosity=2, module="test_simulate")
