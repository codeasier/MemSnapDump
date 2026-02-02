from base import TraceEntry, Block, Segment, DeviceSnapshot
from .memscope.entities import (
    MemoryEvent as MSEvent,
    MemoryBlock as MSBlock,
    MemoryAllocation as MSAllocation
)


def make_default_block_id_counter(start: int = -1):
    count = start

    def next_block_id():
        nonlocal count
        current = count
        count -= 1
        return current

    return next_block_id


def get_timestamp_by_event_idx(event_idx: int) -> int:
    return event_idx * 10 if event_idx is not None else -1


class MemScopeEntityBuilder:
    next_default_block_id = make_default_block_id_counter()

    @staticmethod
    def build_memory_event_from_snapshot_trace_entry(device: int, trace: TraceEntry) -> MSEvent:
        return MSEvent(
            _id=trace.idx,
            event=trace.action,
            event_type='PTA' if trace.action in ['free', 'free_requested', 'free_completed', 'alloc'] else trace.action,
            name='N/A',
            timestamp=trace.idx * 10,
            pid=device,  # snapshot中无pid数据，取为deviceId
            tid=device,  # snapshot中无tid数据，取为deviceId
            did=device,
            ptr=trace.addr,
            callstack_py=trace.get_callstack(),
            attr={
                'stream': str(trace.stream),
                'addr': str(trace.addr),
                'size': str(trace.size)
            }
        )

    @staticmethod
    def build_memory_block_from_snapshot_block(device: int, block: Block):
        return MSBlock(
            block_id=block.alloc_event_idx if block.alloc_event_idx is not None else
            MemScopeEntityBuilder.next_default_block_id(),
            device_id=device,
            addr=block.address,
            size=block.size,
            start_time_ns=get_timestamp_by_event_idx(block.alloc_event_idx),
            end_time_ns=get_timestamp_by_event_idx(block.free_event_idx),
            event_type='PTA',
            owner=block.segment_ptr.address if block.segment_ptr else '',  # 暂定为segment地址
            pid=device,
            tid=device,
            attr={
                'free_event_id': block.free_event_idx,
                'alloc_event_id': block.alloc_event_idx,
                'requested_size': block.requested_size,
                'state': block.state
            }
        )

    @staticmethod
    def build_memory_block_from_snapshot_segment(device: int, seg: Segment):
        return MSBlock(
            block_id=seg.alloc_or_map_event_idx if seg.alloc_or_map_event_idx is not None else
            MemScopeEntityBuilder.next_default_block_id(),
            device_id=device,
            addr=seg.address,
            size=seg.total_size,
            start_time_ns=get_timestamp_by_event_idx(seg.alloc_or_map_event_idx),
            end_time_ns=get_timestamp_by_event_idx(seg.free_or_unmap_event_idx),
            event_type='HAL',
            owner='',  # snapshot暂时无法支持内存拆解数据，暂时固定为空
            pid=device,
            tid=device,
            attr={
                'stream': seg.stream
            }
        )

    @staticmethod
    def build_memory_allocation(device: int, event: TraceEntry, snapshot: DeviceSnapshot):
        return MSAllocation(
            alloc_id=event.idx,
            timestamp=get_timestamp_by_event_idx(event.idx),
            total_size=snapshot.total_allocated if 'segment' not in event.action else snapshot.total_reserved,
            device_id=device,
            event_type='PTA' if 'segment' not in event.action else 'HAL',
            optimized=0  # 非优化后曲线
        )
