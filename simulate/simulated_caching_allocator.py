import copy
import bisect
from typing import Dict, Tuple, Optional, List

from base import DeviceSnapshot, BlockState, Block, Segment, TraceEntry
from util import get_logger

from .hooker_defs import AllocatorHooker

allocator_logger = get_logger("ALLOCATOR")


class AllocatorContext:
    def __init__(self, snapshot: DeviceSnapshot):
        self.device_snapshot = snapshot
        self.current_undo_event: TraceEntry = None
        self.workspace_flag = False

    def set_current_undo_event(self, undo_event: TraceEntry):
        self.current_undo_event = undo_event


class SimulatedCachingAllocator:
    def __init__(self, ctx: AllocatorContext):
        self.ctx = ctx
        self.hookers: Dict[int, AllocatorHooker] = {}

    def register_hooker(self, hooker: AllocatorHooker) -> int:
        idx = hash(hooker)
        self.hookers[idx] = hooker
        return idx

    def unregister_hooker(self, hooker_id: int):
        if hooker_id in self.hookers:
            del self.hookers[hooker_id]

    def alloc_block(self, new_block: Block) -> bool:
        """
            回放时模拟分配一个新的block
        :param new_block: 待分配的block
        """
        _error = "Failed to simulate alloc block"
        gap_result = self.find_gap_for_alloc_block(new_block.address, new_block.size,
                                                    self.ctx.current_undo_event.stream if self.ctx.current_undo_event else None)
        if gap_result is None:
            allocator_logger.error(f"{_error}: cannot find gap for block (addr={new_block.address}, size={new_block.size})")
            return False
        segment, insert_idx = gap_result
        if self.ctx.current_undo_event:
            new_block.free_event_idx = self.ctx.current_undo_event.idx
        if self.ctx.current_undo_event and self.ctx.current_undo_event.action == 'free_completed':
            new_block.state = BlockState.ACTIVE_PENDING_FREE
        else:
            new_block.state = BlockState.ACTIVE_ALLOCATED
        new_block.segment_ptr = segment
        for hooker in self.hookers.values():
            hooker.pre_replay_alloc_block(new_block, self.ctx.device_snapshot)
        blocks = segment.blocks
        blocks.insert(insert_idx, new_block)
        segment.active_size += new_block.size
        self.ctx.device_snapshot.total_activated += new_block.size
        if new_block.state == BlockState.ACTIVE_ALLOCATED:
            segment.allocated_size += new_block.size
            self.ctx.device_snapshot.total_allocated += new_block.size
        for hooker in self.hookers.values():
            hooker.post_replay_alloc_block(new_block, self.ctx.device_snapshot)
        return True

    def free_block(self, alloc_event: TraceEntry) -> bool:
        """
            回放时模拟释放一个block，可能涉及到拆分合并
        :param alloc_event: 待回滚的alloc事件
        """
        _error = "Failed to simulate free block"
        seg_idx = self.ctx.device_snapshot.find_segment_idx_by_addr(alloc_event.addr, alloc_event.stream)
        if seg_idx == -1:
            allocator_logger.error(f"{_error}: cannot find segment for block (addr={alloc_event.addr})")
            return False
        exist_block = self.find_block_by_addr(seg_idx, alloc_event.addr)
        if exist_block is None:
            # workspace场景容忍
            if self.ctx.workspace_flag:
                allocator_logger.warning(f"{_error}: cannot find block (addr={alloc_event.addr}), workspace scenario tolerance")
                return True
            allocator_logger.error(f"{_error}: cannot find block (addr={alloc_event.addr})")
            return False
        if exist_block.size < alloc_event.size:
            allocator_logger.error(f"{_error}: block size ({exist_block.size}) < event size ({alloc_event.size})")
            return False
        exist_block.alloc_event_idx = alloc_event.idx
        exist_block_copy = copy.copy(exist_block)
        for hooker in self.hookers.values():
            hooker.pre_replay_free_block(exist_block, self.ctx.device_snapshot)
        segment = exist_block.segment_ptr
        if segment is None:
            allocator_logger.error(f"{_error}: block has no segment_ptr")
            return False
        segment.active_size -= exist_block.size
        self.ctx.device_snapshot.total_activated -= exist_block.size
        if exist_block.state == BlockState.ACTIVE_ALLOCATED:
            segment.allocated_size -= exist_block.size
            self.ctx.device_snapshot.total_allocated -= exist_block.size
        segment.blocks.remove(exist_block)
        for hooker in self.hookers.values():
            hooker.post_replay_free_block(exist_block_copy, self.ctx.device_snapshot)
        return True

    def active_block(self, free_requested_event: TraceEntry) -> bool:
        """
            回放时模拟active一个block
        :param free_requested_event: 待回放的free_requested请求
        """
        _error = "Failed to simulate active block"
        seg_idx = self.ctx.device_snapshot.find_segment_idx_by_addr(free_requested_event.addr, free_requested_event.stream)
        if seg_idx == -1:
            allocator_logger.error(f"{_error}: cannot find segment for block (addr={free_requested_event.addr})")
            return False
        active_pending_free_block = self.find_block_by_addr(seg_idx, free_requested_event.addr)
        if active_pending_free_block is None:
            allocator_logger.error(f"{_error}: cannot find block (addr={free_requested_event.addr})")
            return False
        if active_pending_free_block.state != BlockState.ACTIVE_PENDING_FREE:
            # workspace场景容忍异常
            if self.ctx.workspace_flag:
                allocator_logger.warning(
                    f"{_error}: block (addr={free_requested_event.addr}) is not in {BlockState.ACTIVE_PENDING_FREE} state, "
                    f"but workspace_flag is True, skipping")
                return True
            allocator_logger.error(
                f"{_error}: block (addr={free_requested_event.addr}) is not in {BlockState.ACTIVE_PENDING_FREE} state, "
                f"current state: {active_pending_free_block.state}")
            return False
        if active_pending_free_block.segment_ptr is None:
            allocator_logger.error(f"{_error}: the found active pending block's segment is none.")
            return False
        active_pending_free_block.state = BlockState.ACTIVE_ALLOCATED
        active_pending_free_block.segment_ptr.allocated_size += active_pending_free_block.size
        self.ctx.device_snapshot.total_allocated += active_pending_free_block.size
        return True

    def alloc_or_map_segment(self, new_segment: Segment, merge: bool = False) -> bool:
        """
            回放时模拟alloc或map一个新的内存段
        :param new_segment: 新内存段
        :param merge: 是否合并，map时对应虚拟内存场景，否则仅为alloc
        """
        _error = "Failed to alloc or map segment"
        segments = self.ctx.device_snapshot.segments
        for hooker in self.hookers.values():
            hooker.pre_replay_map_or_alloc_segment(new_segment, self.ctx.device_snapshot)
        if self.ctx.current_undo_event:
            new_segment.free_or_unmap_event_idx = self.ctx.current_undo_event.idx
        if not merge:
            self.insert_segment_sorted(new_segment)
            self.ctx.device_snapshot.total_reserved += new_segment.total_size
            for hooker in self.hookers.values():
                hooker.post_replay_map_or_alloc_segment(new_segment, self.ctx.device_snapshot)
            return True
        new_seg_start = new_segment.address
        new_seg_end = new_seg_start + new_segment.total_size
        left_adjacent_idx = -1
        right_adjacent_idx = -1
        for i, seg in enumerate(segments):
            if seg.stream != new_segment.stream:
                continue
            if seg.address + seg.total_size == new_seg_start:
                left_adjacent_idx = i
            elif new_seg_end == seg.address:
                right_adjacent_idx = i
        if left_adjacent_idx == -1 and right_adjacent_idx == -1:
            self.insert_segment_sorted(new_segment)
            self.ctx.device_snapshot.total_reserved += new_segment.total_size
            for hooker in self.hookers.values():
                hooker.post_replay_map_or_alloc_segment(new_segment, self.ctx.device_snapshot)
            return True
        virtual_map_segment = copy.deepcopy(new_segment)
        if left_adjacent_idx != -1:
            left_seg = segments[left_adjacent_idx]
            left_seg.total_size += new_segment.total_size
            left_seg.allocated_size += new_segment.allocated_size
            left_seg.active_size += new_segment.active_size
            for block in new_segment.blocks:
                block.segment_ptr = left_seg
                left_seg.blocks.append(block)
            new_segment = left_seg
            if right_adjacent_idx != -1:
                if not self.merge_segments(left_adjacent_idx, right_adjacent_idx):
                    allocator_logger.error(f"{_error}: failed to merge right segment")
                    return False
        else:
            self.insert_segment_sorted(new_segment)
            new_idx = segments.index(new_segment)
            if not self.merge_segments(new_idx, right_adjacent_idx if right_adjacent_idx > new_idx else right_adjacent_idx + 1):
                allocator_logger.error(f"{_error}: failed to merge right segment")
                return False
        self.ctx.device_snapshot.total_reserved += virtual_map_segment.total_size
        for hooker in self.hookers.values():
            hooker.post_replay_map_or_alloc_segment(virtual_map_segment, self.ctx.device_snapshot)
        return True

    def free_segment(self, alloc_seg_event: TraceEntry) -> bool:
        """
            回放时模拟free一个内存段（非虚拟内存场景）
        :param alloc_seg_event: 待回滚的alloc事件
        """
        _error = "Free segment failed"
        seg_addr = alloc_seg_event.addr
        exist_seg = self.find_segment_by_exact_addr(seg_addr, alloc_seg_event.stream)
        if exist_seg is None:
            allocator_logger.error(f"{_error}: cannot found segment(addr={seg_addr}, stream={alloc_seg_event.stream})")
            return False
        if exist_seg.total_size != alloc_seg_event.size:
            allocator_logger.error(f"{_error}: cannot free segment(addr={seg_addr}, size={alloc_seg_event.size}) in "
                                   f"exist segment(addr={exist_seg.address}, size={exist_seg.total_size})")
            return False
        if exist_seg.active_size > 0:
            allocator_logger.error(f"{_error}: cannot free a segment that still has active allocations.")
            return False

        exist_seg.alloc_or_map_event_idx = alloc_seg_event.idx
        for hooker in self.hookers.values():
            hooker.pre_replay_unmap_or_free_segment(exist_seg, self.ctx.device_snapshot)
        self.ctx.device_snapshot.total_reserved -= exist_seg.total_size
        self.ctx.device_snapshot.segments.remove(exist_seg)
        for hooker in self.hookers.values():
            hooker.post_replay_unmap_or_free_segment(exist_seg, self.ctx.device_snapshot)
        return True

    def unmap_segment(self, map_event):
        """
            回放时模拟unmap一个已有的内存段（虚拟内存场景）
        :param map_event: 待回滚的map事件
        """
        _error = "Unmap segment failed"
        segments = self.ctx.device_snapshot.segments
        virtual_free_segment = Segment.build_from_event(map_event)
        seg_addr = virtual_free_segment.address
        unmap_size = virtual_free_segment.total_size
        exist_seg_idx = self.ctx.device_snapshot.find_segment_idx_by_addr(seg_addr, map_event.stream)
        if exist_seg_idx < 0 or exist_seg_idx >= len(segments):
            allocator_logger.error(f"{_error}: cannot found segment(addr={seg_addr})")
            return False
        exist_seg = segments[exist_seg_idx]
        virtual_free_segment.free_or_unmap_event_idx = exist_seg.free_or_unmap_event_idx
        virtual_free_segment.alloc_or_map_event_idx = map_event.idx
        if not (seg_addr >= exist_seg.address and seg_addr + unmap_size <= exist_seg.address + exist_seg.total_size):
            allocator_logger.error(
                f"{_error}: cannot unmap segment(addr={seg_addr}, unmap_size={unmap_size}) in exist segment("
                f"addr={exist_seg.address}, total_size={exist_seg.total_size})")
            return False
        for hooker in self.hookers.values():
            hooker.pre_replay_unmap_or_free_segment(virtual_free_segment, self.ctx.device_snapshot)
        seg_start = exist_seg.address
        seg_end = seg_start + exist_seg.total_size
        unmap_end = seg_addr + unmap_size
        if exist_seg.stream != map_event.stream:
            allocator_logger.error(f"{_error}: stream mismatch (segment: {exist_seg.stream}, event: {map_event.stream})")
            return False
        if seg_addr == seg_start:
            if not self.shrink_segment(exist_seg_idx, seg_addr, unmap_size, 'left'):
                allocator_logger.error(f"{_error}: failed to shrink segment from left")
                return False
        elif unmap_end == seg_end:
            if not self.shrink_segment(exist_seg_idx, seg_addr, unmap_size, 'right'):
                allocator_logger.error(f"{_error}: failed to shrink segment from right")
                return False
        else:
            if not self.split_segment_at(exist_seg_idx, seg_addr, unmap_size):
                allocator_logger.error(f"{_error}: failed to split segment")
                return False
        self.ctx.device_snapshot.total_reserved -= unmap_size
        for hooker in self.hookers.values():
            hooker.post_replay_unmap_or_free_segment(virtual_free_segment, self.ctx.device_snapshot)
        return True

    def find_segment_by_exact_addr(self, addr: int, stream: int) -> Optional[Segment]:
        for segment in self.ctx.device_snapshot.segments:
            if segment.address == addr and segment.stream == stream:
                return segment
        return None

    def find_block_by_addr(self, seg_idx: int, block_addr: int) -> Optional[Block]:
        if seg_idx < 0 or seg_idx >= len(self.ctx.device_snapshot.segments):
            return None
        segment = self.ctx.device_snapshot.segments[seg_idx]
        blocks = segment.blocks
        left, right = 0, len(blocks) - 1
        while left <= right:
            mid = (left + right) // 2
            if blocks[mid].address == block_addr:
                return blocks[mid]
            elif blocks[mid].address < block_addr:
                left = mid + 1
            else:
                right = mid - 1
        return None

    def find_gap_for_alloc_block(self, event_addr: int, event_size: int, stream: int = None) -> Optional[Tuple[Segment, int]]:
        seg_idx = self.ctx.device_snapshot.find_segment_idx_by_addr(event_addr, stream)
        if seg_idx == -1:
            return None
        segment = self.ctx.device_snapshot.segments[seg_idx]
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

    def insert_segment_sorted(self, segment: Segment):
        segments = self.ctx.device_snapshot.segments
        keys = [(seg.address, seg.stream) for seg in segments]
        idx = bisect.bisect_left(keys, (segment.address, segment.stream))
        segments.insert(idx, segment)

    def split_segment_at(self, seg_idx: int, cut_addr: int, cut_size: int) -> bool:
        _error = "Failed to split segment"
        segments = self.ctx.device_snapshot.segments
        if seg_idx < 0 or seg_idx >= len(segments):
            allocator_logger.error(f"{_error}: invalid segment index {seg_idx}")
            return False
        original_segment = segments[seg_idx]
        seg_start = original_segment.address
        seg_end = seg_start + original_segment.total_size
        cut_end = cut_addr + cut_size
        if cut_addr < seg_start or cut_end > seg_end:
            allocator_logger.error(f"{_error}: cut range [{cut_addr}, {cut_end}) is outside segment [{seg_start}, {seg_end})")
            return False
        if cut_addr == seg_start and cut_end == seg_end:
            allocator_logger.warning(f"Split Seg: cut range covers entire segment, nothing to split, just remove it")
            del self.ctx.device_snapshot.segments[seg_idx]
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
            alloc_or_map_event_idx=original_segment.alloc_or_map_event_idx
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
            alloc_or_map_event_idx=original_segment.alloc_or_map_event_idx
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
                allocator_logger.warning(f"{_error}: active block [{block_start}, {block_end}) overlaps with cut range [{cut_addr}, {cut_end}), just drop it.")
        del segments[seg_idx]
        if left_segment.total_size > 0:
            self.insert_segment_sorted(left_segment)
        if right_segment.total_size > 0:
            self.insert_segment_sorted(right_segment)
        return True

    def shrink_segment(self, seg_idx: int, shrink_addr: int, shrink_size: int, direction: str) -> bool:
        _error = "Failed to shrink segment"
        segments = self.ctx.device_snapshot.segments
        if seg_idx < 0 or seg_idx >= len(segments):
            allocator_logger.error(f"{_error}: invalid segment index {seg_idx}")
            return False
        if direction not in ['left', 'right']:
            allocator_logger.error(f"{_error}: invalid direction '{direction}', must be 'left' or 'right'")
            return False
        segment = segments[seg_idx]
        seg_start = segment.address
        seg_end = seg_start + segment.total_size
        shrink_end = shrink_addr + shrink_size
        if direction == 'left':
            if shrink_addr < seg_start or shrink_end > seg_end:
                allocator_logger.error(f"{_error}: shrink range [{shrink_addr}, {shrink_end}) is outside segment [{seg_start}, {seg_end})")
                return False
            new_start = shrink_end
            new_size = seg_end - new_start
            if new_size < 0:
                allocator_logger.error(f"{_error}: shrink results in negative segment size")
                return False
            for block in segment.blocks:
                block_start = block.address
                block_end = block_start + block.size
                if block_end <= shrink_end:
                    allocator_logger.error(f"{_error}: active block [{block_start}, {block_end}) in shrink range [{shrink_addr}, {shrink_end})")
                    return False
            segment.address = new_start
            segment.total_size = new_size
            new_blocks = []
            for block in segment.blocks:
                if block.address >= new_start:
                    new_blocks.append(block)
            segment.blocks = new_blocks
        else:
            if shrink_addr < seg_start or shrink_end > seg_end:
                allocator_logger.error(f"{_error}: shrink range [{shrink_addr}, {shrink_end}) is outside segment [{seg_start}, {seg_end})")
                return False
            new_size = shrink_addr - seg_start
            if new_size < 0:
                allocator_logger.error(f"{_error}: shrink results in negative segment size")
                return False
            for block in segment.blocks:
                block_start = block.address
                block_end = block_start + block.size
                if block_start >= shrink_addr:
                    allocator_logger.error(f"{_error}: active block [{block_start}, {block_end}) in shrink range [{shrink_addr}, {shrink_end})")
                    return False
            new_blocks = []
            for block in segment.blocks:
                if block.address + block.size <= shrink_addr:
                    new_blocks.append(block)
            segment.blocks = new_blocks
            segment.total_size = new_size
        segment.allocated_size = sum(b.size for b in segment.blocks if b.state == BlockState.ACTIVE_ALLOCATED)
        segment.active_size = sum(b.size for b in segment.blocks)
        if segment.total_size == 0:
            del segments[seg_idx]
        return True

    def merge_segments(self, target_idx: int, source_idx: int) -> bool:
        _error = "Failed to merge segments"
        segments = self.ctx.device_snapshot.segments
        if target_idx < 0 or target_idx >= len(segments):
            allocator_logger.error(f"{_error}: invalid target segment index {target_idx}")
            return False
        if source_idx < 0 or source_idx >= len(segments):
            allocator_logger.error(f"{_error}: invalid source segment index {source_idx}")
            return False
        if target_idx == source_idx:
            allocator_logger.error(f"{_error}: target and source are the same segment")
            return False
        target = segments[target_idx]
        source = segments[source_idx]
        if target.stream != source.stream:
            allocator_logger.error(f"{_error}: segments have different streams (target: {target.stream}, source: {source.stream})")
            return False
        are_adjacent = (target.address + target.total_size == source.address or 
                       source.address + source.total_size == target.address)
        if not are_adjacent:
            allocator_logger.error(f"{_error}: segments are not adjacent (target: [{target.address}, {target.address + target.total_size}), source: [{source.address}, {source.address + source.total_size}))")
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
