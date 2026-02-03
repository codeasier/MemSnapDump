import os
import shutil
import unittest
import json
import sqlite3
from typing import List
from pathlib import Path
from util.pickle_util import load_pickle_to_dict
from base import TraceEntry, DeviceSnapshot, Segment, Block, BlockState
from tools.adaptors import snapshot2memscope
from simulate import SimulateDeviceSnapshot, SimulateHooker


class TestMemscopeDbHandler:
    def __init__(self, db_path: str):
        self.conn = sqlite3.connect(db_path)

    @staticmethod
    def build_segment_by_row(row) -> Segment:
        segment = Segment(
            address=int(row[2]),
            total_size=int(row[3]),
            active_size=0,
            allocated_size=0
        )
        attr_dict = json.loads(row[8])
        segment.stream = attr_dict['stream']
        return segment

    @staticmethod
    def build_block_by_row(row) -> Block:
        block = Block(
            address=int(row[2]),
            size=int(row[3])
        )
        attr_dict = json.loads(row[8])
        block.state = attr_dict['state']
        block.requested_size = attr_dict['requested_size']
        return block

    @staticmethod
    def build_segments_by_rows(rows, is_expandable=False):
        current_seg: Segment = None
        results: List[Segment] = list()
        for row in rows:
            if row[6] == 'PTA':
                if current_seg is None:
                    raise RuntimeError("Error")
                block = TestMemscopeDbHandler.build_block_by_row(row)
                current_seg.blocks.append(block)
                current_seg.active_size += block.size
                if block.state == BlockState.ACTIVE_ALLOCATED:
                    current_seg.allocated_size += block.size
            elif row[6] == 'HAL':
                seg = TestMemscopeDbHandler.build_segment_by_row(row)
                if is_expandable and len(results) > 0:
                    prev_seg = results[-1]
                    if prev_seg.address + prev_seg.total_size == seg.address and prev_seg.stream == seg.stream:
                        prev_seg.total_size += seg.total_size
                        continue
                results.append(seg)
                current_seg = seg
        return results

    def query_segments_by_event_id(self, event_id: int, is_expandable=False):
        cursor = self.conn.cursor()
        query_sql = """
                    select *
                    from memory_block
                    where startTimestamp <= ?
                      and (endTimestamp > ? or endTimestamp < 0)
                    order by addr"""
        cursor.execute(query_sql, (event_id * 10, event_id * 10))
        rows = cursor.fetchall()
        return TestMemscopeDbHandler.build_segments_by_rows(rows, is_expandable=is_expandable)

    def __del__(self):
        self.conn.close()


class TestMemscopeDbHooker(SimulateHooker):
    def __init__(self, dump_db_path: str, test_util: unittest.TestCase, is_expandable=False):
        self.db_handler = TestMemscopeDbHandler(dump_db_path)
        self.event_count = 0
        self.test_util = test_util
        self.is_expandable = is_expandable

    def pre_undo_event(self, wait4undo_event: TraceEntry, current_snapshot: DeviceSnapshot) -> bool:
        self.event_count += 1
        if self.event_count % 100 == 0:
            db_segments = self.db_handler.query_segments_by_event_id(wait4undo_event.idx, self.is_expandable)
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


class Snapshot2MemscopeDbTest(unittest.TestCase):
    def setUp(self):
        self.test_data_path = (current_dir / '../test-data/').resolve()
        self.snapshot_path = self.test_data_path / 'snapshot_with_empty_cache.pkl'
        self.vmem_snapshot_path = self.test_data_path / 'snapshot_with_empty_cache_expandable.pkl'
        self.cache_dir = self.test_data_path / 'tmp'
        if os.path.exists(self.cache_dir):
            shutil.rmtree(self.cache_dir)
        os.mkdir(self.cache_dir)
        self.snapshot_dump_db = 'leaks_dump_1.db'
        self.vmem_snapshot_dump_db = 'leaks_dump_2.db'

    def tearDown(self):
        shutil.rmtree(self.cache_dir)

    def testSnapshot2MemscopeDb(self):
        snapshot2memscope.dump(self.snapshot_path, self.cache_dir / self.snapshot_dump_db)
        self.assertTrue(os.path.exists(self.cache_dir / self.snapshot_dump_db))
        snapshot = SimulateDeviceSnapshot(load_pickle_to_dict(self.snapshot_path))
        snapshot.register_hooker(TestMemscopeDbHooker(self.cache_dir / self.snapshot_dump_db, self))
        snapshot.replay()

    def testVemSnapshot2MemscopeDb(self):
        snapshot2memscope.dump(self.vmem_snapshot_path, self.cache_dir / self.vmem_snapshot_dump_db)
        self.assertTrue(os.path.exists(self.cache_dir / self.vmem_snapshot_dump_db))
        vmem_snapshot = SimulateDeviceSnapshot(load_pickle_to_dict(self.vmem_snapshot_path))
        vmem_snapshot.register_hooker(TestMemscopeDbHooker(self.cache_dir / self.vmem_snapshot_dump_db, self,
                                                           is_expandable=True))
        vmem_snapshot.replay()
