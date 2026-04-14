from memsnapdump.base import Block, BlockState, DeviceSnapshot, Segment
from . import range_ops


def attach_block(snapshot: DeviceSnapshot, segment: Segment, block: Block, insert_idx: int):
    block.segment_ptr = segment
    segment.blocks.insert(insert_idx, block)
    segment.active_size += block.size
    snapshot.total_activated += block.size
    if block.state == BlockState.ACTIVE_ALLOCATED:
        segment.allocated_size += block.size
        snapshot.total_allocated += block.size


def detach_block(snapshot: DeviceSnapshot, block: Block) -> bool:
    segment = block.segment_ptr
    if segment is None:
        return False
    segment.active_size -= block.size
    snapshot.total_activated -= block.size
    if block.state == BlockState.ACTIVE_ALLOCATED:
        segment.allocated_size -= block.size
        snapshot.total_allocated -= block.size
    segment.blocks.remove(block)
    block.segment_ptr = None
    return True


def promote_pending_free_block(snapshot: DeviceSnapshot, block: Block) -> bool:
    segment = block.segment_ptr
    if segment is None:
        return False
    block.state = BlockState.ACTIVE_ALLOCATED
    segment.allocated_size += block.size
    snapshot.total_allocated += block.size
    return True


def insert_segment(snapshot: DeviceSnapshot, segment: Segment):
    range_ops.insert_segment_sorted(snapshot, segment)
    snapshot.total_reserved += segment.total_size


def remove_segment(snapshot: DeviceSnapshot, segment: Segment):
    snapshot.total_reserved -= segment.total_size
    snapshot.segments.remove(segment)
    for block in segment.blocks:
        block.segment_ptr = None


def merge_mapped_segment(snapshot: DeviceSnapshot, new_segment: Segment, left_adjacent_idx: int, right_adjacent_idx: int) -> bool:
    segments = snapshot.segments
    left_seg = segments[left_adjacent_idx]
    left_seg.total_size += new_segment.total_size
    left_seg.allocated_size += new_segment.allocated_size
    left_seg.active_size += new_segment.active_size
    for block in new_segment.blocks:
        block.segment_ptr = left_seg
        left_seg.blocks.append(block)
    if right_adjacent_idx != -1:
        return range_ops.merge_segments(snapshot, left_adjacent_idx, right_adjacent_idx)
    return True


def split_or_shrink_segment(snapshot: DeviceSnapshot, seg_idx: int, seg_addr: int, unmap_size: int) -> bool:
    exist_seg = snapshot.segments[seg_idx]
    seg_start = exist_seg.address
    unmap_end = seg_addr + unmap_size
    if seg_addr == seg_start:
        return range_ops.shrink_segment(snapshot, seg_idx, seg_addr, unmap_size, 'left')
    if unmap_end == seg_start + exist_seg.total_size:
        return range_ops.shrink_segment(snapshot, seg_idx, seg_addr, unmap_size, 'right')
    return range_ops.split_segment_at(snapshot, seg_idx, seg_addr, unmap_size)


def increase_reserved(snapshot: DeviceSnapshot, size: int):
    snapshot.total_reserved += size


def decrease_reserved(snapshot: DeviceSnapshot, size: int):
    snapshot.total_reserved -= size

