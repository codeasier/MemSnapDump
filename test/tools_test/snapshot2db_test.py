import os
import shutil
import unittest
from pathlib import Path
from util.file_util import load_pickle_to_dict
from base import TraceEntry, DeviceSnapshot, BlockState
from tools.adaptors import snapshot2db
from simulate import SimulateDeviceSnapshot, SimulateHooker

from .snapshot_db_analyze import TestSnapshotDbHandler


class TestSnapshotDbHooker(SimulateHooker):
    def __init__(self, dump_db_path: str, device: int, test_util: unittest.TestCase, is_expandable=False):
        self.db_handler = TestSnapshotDbHandler(dump_db_path, device)
        self.event_count = 0
        self.test_util = test_util
        self.is_expandable = is_expandable

    def pre_undo_event(self, wait4undo_event: TraceEntry, current_snapshot: DeviceSnapshot) -> bool:
        self.event_count += 1
        if self.event_count % 100 == 0:
            db_segments = self.db_handler.get_segments_by_event_id(wait4undo_event.idx)
            self.test_util.assertEqual(len(db_segments), len(current_snapshot.segments))
            for i in range(len(db_segments)):
                db_segment = db_segments[i]
                snapshot_segment = current_snapshot.segments[i]
                self.test_util.assertEqual(db_segment.active_size, snapshot_segment.active_size)
                self.test_util.assertEqual(db_segment.total_size, snapshot_segment.total_size)
                idx = 0
                for seg_block in snapshot_segment.blocks:
                    if seg_block.state == BlockState.INACTIVE:
                        continue
                    db_block = db_segment.blocks[idx]
                    idx += 1
                    self.test_util.assertEqual(seg_block.size, db_block.size)
                    self.test_util.assertEqual(seg_block.requested_size, db_block.requested_size)
                    self.test_util.assertEqual(seg_block.address, db_block.address)
        return True

    def post_undo_event(self, already_undo_event: TraceEntry, current_snapshot: DeviceSnapshot) -> bool:
        return True


current_dir = Path(__file__).parent.resolve()


class Snapshot2DbTest(unittest.TestCase):
    def setUp(self):
        self.test_data_path = (current_dir / '../test-data/').resolve()
        self.snapshot_path = self.test_data_path / 'snapshot_with_empty_cache.pkl'
        self.vmem_snapshot_path = self.test_data_path / 'snapshot_with_empty_cache_expandable.pkl'
        self.multi_devices_snapshot_path = self.test_data_path / 'snapshot_with_multi_devices.pkl'
        self.cache_dir = self.test_data_path / 'tmp'
        if os.path.exists(self.cache_dir):
            shutil.rmtree(self.cache_dir)
        os.mkdir(self.cache_dir)
        self.snapshot_dump_db = 'leaks_dump_1.db'
        self.vmem_snapshot_dump_db = 'leaks_dump_2.db'
        self.multi_devices_snapshot_dump_db = 'multi_devices_dump.db'

    def tearDown(self):
        shutil.rmtree(self.cache_dir)

    def testSnapshot2Db(self):
        self.assertTrue(snapshot2db.dump(self.snapshot_path, self.cache_dir / self.snapshot_dump_db, 0))
        self.assertTrue(os.path.exists(self.cache_dir / self.snapshot_dump_db))
        snapshot = SimulateDeviceSnapshot(load_pickle_to_dict(self.snapshot_path), 0)
        snapshot.register_hooker(TestSnapshotDbHooker(self.cache_dir / self.snapshot_dump_db, 0, self))
        self.assertTrue(snapshot.replay())

    def testVemSnapshot2Db(self):
        self.assertTrue(snapshot2db.dump(self.vmem_snapshot_path, self.cache_dir / self.vmem_snapshot_dump_db, 0))
        self.assertTrue(os.path.exists(self.cache_dir / self.vmem_snapshot_dump_db))
        vmem_snapshot = SimulateDeviceSnapshot(load_pickle_to_dict(self.vmem_snapshot_path), 0)
        vmem_snapshot.register_hooker(TestSnapshotDbHooker(self.cache_dir / self.vmem_snapshot_dump_db, 0, self,
                                                           is_expandable=True))
        self.assertTrue(vmem_snapshot.replay())

    def testEmptyDeviceSnapshot(self):
        self.assertFalse(snapshot2db.dump(self.snapshot_path, self.cache_dir / self.snapshot_dump_db, 1))
        self.assertFalse(os.path.exists(self.cache_dir / self.snapshot_dump_db))

    def testDumpAllMultipleDeviceSnapshot(self):
        self.assertTrue(snapshot2db.dump(self.multi_devices_snapshot_path,
                                         self.cache_dir / self.multi_devices_snapshot_dump_db))
        self.assertTrue(os.path.exists(self.cache_dir / self.multi_devices_snapshot_dump_db))
        snapshot_0 = SimulateDeviceSnapshot(load_pickle_to_dict(self.multi_devices_snapshot_path), 0)
        snapshot_0.register_hooker(TestSnapshotDbHooker(self.cache_dir / self.multi_devices_snapshot_dump_db, 0, self))
        self.assertTrue(snapshot_0.replay())
        snapshot_1 = SimulateDeviceSnapshot(load_pickle_to_dict(self.multi_devices_snapshot_path), 1)
        snapshot_1.register_hooker(TestSnapshotDbHooker(self.cache_dir / self.multi_devices_snapshot_dump_db, 1, self))
        self.assertTrue(snapshot_1.replay())
