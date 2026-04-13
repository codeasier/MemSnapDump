import bisect
from typing import Optional, Tuple

from base import Block, BlockState, DeviceSnapshot, Segment
from util import get_logger

range_ops_logger = get_logger("ALLOCATOR")


def find_segment_by_exact_addr(snapshot: DeviceSnapshot, addr: int, stream: int) -> Optional[Segment]:
    seg_idx = snapshot.find_segment_idx_by_addr(addr, stream)
    if seg_idx != -1:
        seg = snapshot.segments[seg_idx]
        if seg.address == addr and seg.stream == stream:
            return seg
    return None


def find_block_by_addr(snapshot: DeviceSnapshot, seg_idx: int, block_addr: int) -> Optional[Block]:
    if seg_idx < 0 or seg_idx >= len(snapshot.segments):
        return None
    segment = snapshot.segments[seg_idx]
    blocks = segment.blocks
    left, right = 0, len(blocks) - 1
    while left <= right:
        mid = (left + right) // 2
        if blocks[mid].address == block_addr:
            return blocks[mid]
        if blocks[mid].address < block_addr:
            left = mid + 1
        else:
            right = mid - 1
    return None


def find_gap_for_alloc_block(snapshot: DeviceSnapshot, event_addr: int, event_size: int, stream: int = None) -> Optional[Tuple[Segment, int]]:
    seg_idx = snapshot.find_segment_idx_by_addr(event_addr, stream)
    if seg_idx == -1:
        return None
    segment = snapshot.segments[seg_idx]
    blocks = segment.blocks
    event_end = event_addr + event_size
    seg_start = segment.address
    seg_end = seg_start + segment.total_size
    if len(blocks) == 0:
        if seg_start <= event_addr and event_end <= seg_end:
            return segment, 0
        return None

    if blocks[0].address >= event_end:
        if seg_start <= event_addr:
            return segment, 0
        return None

    left, right = 0, len(blocks) - 1
    while left < right:
        mid = (left + right + 1) // 2
        if blocks[mid].address <= event_addr:
            left = mid
        else:
            right = mid - 1

    gap_start = blocks[left].address + blocks[left].size
    if left + 1 < len(blocks):
        gap_end = blocks[left + 1].address
        if gap_start <= event_addr and event_end <= gap_end:
            return segment, left + 1
    else:
        if gap_start <= event_addr and event_end <= seg_end:
            return segment, len(blocks)

    return None


def insert_segment_sorted(snapshot: DeviceSnapshot, segment: Segment):
    segments = snapshot.segments
    keys = [(seg.address, seg.stream) for seg in segments]
    idx = bisect.bisect_left(keys, (segment.address, segment.stream))
    segments.insert(idx, segment)


def split_segment_at(snapshot: DeviceSnapshot, seg_idx: int, cut_addr: int, cut_size: int) -> bool:
    _error = "Failed to split segment"
    segments = snapshot.segments
    if seg_idx < 0 or seg_idx >= len(segments):
        range_ops_logger.error(f"{_error}: invalid segment index {seg_idx}")
        return False
    original_segment = segments[seg_idx]
    seg_start = original_segment.address
    seg_end = seg_start + original_segment.total_size
    cut_end = cut_addr + cut_size
    if cut_addr < seg_start or cut_end > seg_end:
        range_ops_logger.error(f"{_error}: cut range [{cut_addr}, {cut_end}) is outside segment [{seg_start}, {seg_end})")
        return False
    if cut_addr == seg_start and cut_end == seg_end:
        range_ops_logger.warning("Split Seg: cut range covers entire segment, nothing to split, just remove it")
        del snapshot.segments[seg_idx]
        return True
    left_segment = Segment(
        address=seg_start,
        total_size=cut_addr - seg_start,
        stream=original_segment.stream,
        segment_type=original_segment.segment_type,
        allocated_size=0,
        active_size=0,
        blocks=[],
        device=original_segment.device,
        frames=original_segment.frames,
        is_expandable=original_segment.is_expandable,
        free_or_unmap_event_idx=original_segment.free_or_unmap_event_idx,
        alloc_or_map_event_idx=original_segment.alloc_or_map_event_idx,
    )
    right_segment = Segment(
        address=cut_end,
        total_size=seg_end - cut_end,
        stream=original_segment.stream,
        segment_type=original_segment.segment_type,
        allocated_size=0,
        active_size=0,
        blocks=[],
        device=original_segment.device,
        frames=original_segment.frames,
        is_expandable=original_segment.is_expandable,
        free_or_unmap_event_idx=original_segment.free_or_unmap_event_idx,
        alloc_or_map_event_idx=original_segment.alloc_or_map_event_idx,
    )
    for block in original_segment.blocks:
        block_start = block.address
        block_end = block_start + block.size
        if block_end <= cut_addr:
            block.segment_ptr = left_segment
            left_segment.blocks.append(block)
            left_segment.active_size += block.size
            if block.state == BlockState.ACTIVE_ALLOCATED:
                left_segment.allocated_size += block.size
        elif block_start >= cut_end:
            block.segment_ptr = right_segment
            right_segment.blocks.append(block)
            right_segment.active_size += block.size
            if block.state == BlockState.ACTIVE_ALLOCATED:
                right_segment.allocated_size += block.size
        else:
            range_ops_logger.warning(
                f"{_error}: active block [{block_start}, {block_end}) overlaps with cut range [{cut_addr}, {cut_end}), just drop it."
            )
    del segments[seg_idx]
    if left_segment.total_size > 0:
        insert_segment_sorted(snapshot, left_segment)
    if right_segment.total_size > 0:
        insert_segment_sorted(snapshot, right_segment)
    return True


def shrink_segment(snapshot: DeviceSnapshot, seg_idx: int, shrink_addr: int, shrink_size: int, direction: str) -> bool:
    _error = "Failed to shrink segment"
    segments = snapshot.segments
    if seg_idx < 0 or seg_idx >= len(segments):
        range_ops_logger.error(f"{_error}: invalid segment index {seg_idx}")
        return False
    if direction not in ['left', 'right']:
        range_ops_logger.error(f"{_error}: invalid direction '{direction}', must be 'left' or 'right'")
        return False
    segment = segments[seg_idx]
    seg_start = segment.address
    seg_end = seg_start + segment.total_size
    shrink_end = shrink_addr + shrink_size
    if direction == 'left':
        if shrink_addr < seg_start or shrink_end > seg_end:
            range_ops_logger.error(f"{_error}: shrink range [{shrink_addr}, {shrink_end}) is outside segment [{seg_start}, {seg_end})")
            return False
        new_start = shrink_end
        new_size = seg_end - new_start
        if new_size < 0:
            range_ops_logger.error(f"{_error}: shrink results in negative segment size")
            return False
        for block in segment.blocks:
            block_start = block.address
            block_end = block_start + block.size
            if block_end <= shrink_end:
                range_ops_logger.error(f"{_error}: active block [{block_start}, {block_end}) in shrink range [{shrink_addr}, {shrink_end})")
                return False
        segment.address = new_start
        segment.total_size = new_size
        segment.blocks = [block for block in segment.blocks if block.address >= new_start]
    else:
        if shrink_addr < seg_start or shrink_end > seg_end:
            range_ops_logger.error(f"{_error}: shrink range [{shrink_addr}, {shrink_end}) is outside segment [{seg_start}, {seg_end})")
            return False
        new_size = shrink_addr - seg_start
        if new_size < 0:
            range_ops_logger.error(f"{_error}: shrink results in negative segment size")
            return False
        for block in segment.blocks:
            block_start = block.address
            block_end = block_start + block.size
            if block_start >= shrink_addr:
                range_ops_logger.error(f"{_error}: active block [{block_start}, {block_end}) in shrink range [{shrink_addr}, {shrink_end})")
                return False
        segment.blocks = [block for block in segment.blocks if block.address + block.size <= shrink_addr]
        segment.total_size = new_size
    segment.allocated_size = sum(b.size for b in segment.blocks if b.state == BlockState.ACTIVE_ALLOCATED)
    segment.active_size = sum(b.size for b in segment.blocks)
    if segment.total_size == 0:
        del segments[seg_idx]
    return True


def merge_segments(snapshot: DeviceSnapshot, target_idx: int, source_idx: int) -> bool:
    _error = "Failed to merge segments"
    segments = snapshot.segments
    if target_idx < 0 or target_idx >= len(segments):
        range_ops_logger.error(f"{_error}: invalid target segment index {target_idx}")
        return False
    if source_idx < 0 or source_idx >= len(segments):
        range_ops_logger.error(f"{_error}: invalid source segment index {source_idx}")
        return False
    if target_idx == source_idx:
        range_ops_logger.error(f"{_error}: target and source are the same segment")
        return False
    target = segments[target_idx]
    source = segments[source_idx]
    if target.stream != source.stream:
        range_ops_logger.error(f"{_error}: segments have different streams (target: {target.stream}, source: {source.stream})")
        return False
    are_adjacent = target.address + target.total_size == source.address or source.address + source.total_size == target.address
    if not are_adjacent:
        range_ops_logger.error(
            f"{_error}: segments are not adjacent (target: [{target.address}, {target.address + target.total_size}), source: [{source.address}, {source.address + source.total_size}))"
        )
        return False
    if target.address > source.address:
        target, source = source, target
        target_idx, source_idx = source_idx, target_idx
    target.total_size += source.total_size
    target.allocated_size += source.allocated_size
    target.active_size += source.active_size
    for block in source.blocks:
        block.segment_ptr = target
        target.blocks.append(block)
    del segments[source_idx]
    return True
