import bisect
import sqlite3
from typing import List

from memsnapdump.base import Segment, Block, TraceEntry
from memsnapdump.simulate.snapshot_lookup import find_overlapping_segment
from memsnapdump.tools.adaptors.database import (
    TRACE_ENTRY_ACTION_VALUE_MAP,
    BLOCK_STATE_VALUE_MAP,
)


class BlockRowDefs:
    ID = 0
    ADDR = 1
    SIZE = 2
    REQUESTED_SIZE = 3
    STATE = 4
    ALLOC_EVENT_ID = 5
    FREE_EVENT_ID = 6


class EventRowDefs:
    ID = 0
    ACTION = 1
    ADDR = 2
    SIZE = 3
    STREAM = 4
    ALLOCATED = 5
    ACTIVE = 6
    RESERVED = 7
    CALLSTACK = 8


class SnapshotDbHandler:
    def __init__(self, db_path: str, device: int):
        self.conn = sqlite3.connect(db_path)
        self.device = device

    @staticmethod
    def _block_state_by_value_map(state_code: int):
        for k, v in BLOCK_STATE_VALUE_MAP.items():
            if v == state_code:
                return k
        return state_code

    @staticmethod
    def _event_action_by_value_map(action_code: int):
        for k, v in TRACE_ENTRY_ACTION_VALUE_MAP.items():
            if v == action_code:
                return k
        return action_code

    @staticmethod
    def build_block_by_row(row) -> Block:
        return Block(
            address=row[BlockRowDefs.ADDR],
            size=row[BlockRowDefs.SIZE],
            requested_size=row[BlockRowDefs.REQUESTED_SIZE],
            state=SnapshotDbHandler._block_state_by_value_map(row[BlockRowDefs.STATE]),
            alloc_event_idx=row[BlockRowDefs.ALLOC_EVENT_ID],
            free_event_idx=row[BlockRowDefs.FREE_EVENT_ID],
        )

    @staticmethod
    def build_trace_entry_by_row(row) -> TraceEntry:
        return TraceEntry(
            idx=row[EventRowDefs.ID],
            action=SnapshotDbHandler._event_action_by_value_map(
                row[EventRowDefs.ACTION]
            ),
            addr=row[EventRowDefs.ADDR],
            size=row[EventRowDefs.SIZE],
            stream=row[EventRowDefs.STREAM],
        )

    @staticmethod
    def find_segment_idx_by_addr(segments, addr: int, stream: int = None) -> int:
        snapshot = type("SnapshotLike", (), {"segments": segments})()
        seg_idx, _ = find_overlapping_segment(snapshot, addr, stream)
        return seg_idx

    @staticmethod
    def build_segments_by_events(events: List[TraceEntry]):
        segments: List[Segment] = list()
        for evt in events:
            if evt.action == "segment_alloc":
                insert_idx = bisect.bisect_left(
                    [(seg.address, seg.stream) for seg in segments],
                    (evt.addr, evt.stream),
                )
                segment = Segment.build_from_event(evt)
                segment.blocks = list()
                segments.insert(insert_idx, segment)
            elif evt.action == "segment_free":
                idx = bisect.bisect_left(
                    [(seg.address, seg.stream) for seg in segments],
                    (evt.addr, evt.stream),
                )
                del segments[idx]
            elif evt.action == "segment_map":
                idx = bisect.bisect_left(
                    [(seg.address, seg.stream) for seg in segments],
                    (evt.addr, evt.stream),
                )
                seg = Segment.build_from_event(evt)
                seg.blocks = list()
                segments.insert(idx, seg)
                cur = idx - 1
                while 0 <= cur < len(segments) - 1:
                    cur_seg = segments[cur]
                    next_seg = segments[cur + 1]
                    if (
                        next_seg.stream == evt.stream
                        and cur_seg.address + cur_seg.total_size == next_seg.address
                    ):
                        cur_seg.total_size += next_seg.total_size
                        del segments[cur + 1]
                    else:
                        break
            elif evt.action == "segment_unmap":
                exist_seg_idx = SnapshotDbHandler.find_segment_idx_by_addr(
                    segments, evt.addr, evt.stream
                )
                exist_seg = segments[exist_seg_idx]
                if evt.addr > exist_seg.address:
                    exist_seg_idx += 1
                    total_size = exist_seg.total_size
                    exist_seg.total_size = evt.addr - exist_seg.address
                    segments.insert(
                        exist_seg_idx,
                        Segment(
                            total_size=total_size - exist_seg.total_size,
                            address=evt.addr,
                            is_expandable=True,
                            stream=evt.stream,
                        ),
                    )
                    exist_seg = segments[exist_seg_idx]
                if exist_seg.total_size == evt.size:
                    del segments[exist_seg_idx]
                    continue
                exist_seg.address += evt.size
                exist_seg.total_size -= evt.size
        return segments

    @staticmethod
    def build_segments(segments: List[Segment], blocks: List[Block]):
        for block in blocks:
            exist_seg_idx = SnapshotDbHandler.find_segment_idx_by_addr(
                segments, block.address
            )
            exist_seg = segments[exist_seg_idx]
            exist_seg.blocks.append(block)
            exist_seg.active_size += block.size
            exist_seg.allocated_size += (
                block.size if block.state == "active_allocated" else 0
            )
        for seg in segments:
            seg.blocks.sort(key=lambda b: b.address)

    def query_segment_events_until(self, event_id: int) -> List[TraceEntry]:
        query_events_sql = f"""
                           select *
                           from trace_entry_{self.device}
                           where id <= ?
                             and (action between 0 and 3) \
                           """
        cursor = self.conn.cursor()
        cursor.execute(query_events_sql, (event_id,))
        rows = cursor.fetchall()
        return [SnapshotDbHandler.build_trace_entry_by_row(row) for row in rows]

    def query_blocks_by_event_id(self, event_id) -> List[Block]:
        query_block_sql = f"""
                          select *
                          from block_{self.device}
                          where allocEventId <= ?
                            and (freeEventId > ? or freeEventId < 0)
                          """
        cursor = self.conn.cursor()
        cursor.execute(query_block_sql, (event_id, event_id))
        rows = cursor.fetchall()
        return [SnapshotDbHandler.build_block_by_row(row) for row in rows]

    def get_segments_by_event_id(self, event_id: int):
        segment_events = self.query_segment_events_until(event_id)
        segments = self.build_segments_by_events(segment_events)
        blocks = self.query_blocks_by_event_id(event_id)
        self.build_segments(segments, blocks)
        return segments

    def __del__(self):
        self.conn.close()
