import math
import copy
import bisect
from dataclasses import dataclass
from typing import Dict, Tuple, Optional, List

from base import DeviceSnapshot, BlockState, Block, Segment, TraceEntry
from util import get_logger

from .hooker_defs import AllocatorHooker

allocator_logger = get_logger("ALLOCATOR")


@dataclass
class BlockLoc:
    seg_idx: int = -1
    block_idx: int = -1


class AllocatorContext:
    def __init__(self, snapshot: DeviceSnapshot, block_align_size: int = 512):
        self.device_snapshot = snapshot
        self.block_align_size = block_align_size
        self.current_undo_event: TraceEntry = None

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
        # 新块对齐拆分重置大小
        new_block.size = self._get_aligned_size(new_block.requested_size)
        # 设置block的释放事件, 仿真内存分配器在alloc_block时实质对应的是回放到了内存释放事件，所以此处是设置释放事件id而不是分配事件id
        if self.ctx.current_undo_event:
            new_block.free_event_idx = self.ctx.current_undo_event.idx
        # 查找block分片位置
        reusable_block_loc = self._find_reusable_inactive_block(new_block)
        if reusable_block_loc.seg_idx == -1 or reusable_block_loc.block_idx == -1:
            allocator_logger.error(f"{_error}: cannot find usable segment or reusable block.")
            return False
        for hooker in self.hookers.values():
            hooker.pre_replay_alloc_block(new_block, self.ctx.device_snapshot)
        # 执行分配
        if not self._do_alloc_block(new_block, reusable_block_loc):
            return False
        for hooker in self.hookers.values():
            # new_block对象可能并不会被插入到内存池中（如已有完整内存块对象可复用，或拆解后使用原block缩小规模的形式）
            hooker.post_replay_alloc_block(new_block, self.ctx.device_snapshot)
        return True

    def free_block(self, alloc_event: TraceEntry) -> bool:
        """
            回放时模拟释放一个block，可能涉及到拆分合并
        :param alloc_event: 待回滚的alloc事件
        """
        _error = "Failed to simulate free block"
        free_block_loc = self._find_active_block(alloc_event.addr, self._get_aligned_size(alloc_event.size))
        if free_block_loc.seg_idx == -1 or free_block_loc.block_idx == -1:
            allocator_logger.error(f"{_error}: cannot find exist segment or active block.")
            return False
        exist_block = self._get_block_by_loc(free_block_loc)
        if exist_block is None:
            return False
        # 设置block的分配事件, 仿真内存分配器在free_block时实质对应的是回放到了内存分配事件，所以此处是设置分配事件id而不是释放事件id
        exist_block.alloc_event_idx = alloc_event.idx
        exist_block_copy = copy.copy(exist_block)
        for hooker in self.hookers.values():
            hooker.pre_replay_free_block(exist_block, self.ctx.device_snapshot)
        if not self._do_free_block(free_block_loc):
            return False
        for hooker in self.hookers.values():
            hooker.post_replay_free_block(exist_block_copy, self.ctx.device_snapshot)
        return True

    def active_block(self, free_requested_event: TraceEntry) -> bool:
        """
            回放时模拟active一个block
        :param free_requested_event: 待回放的free_requested请求
        """
        _error = "Failed to simulate active block"
        active_pending_free_block_loc = self._find_active_block(free_requested_event.addr, self._get_aligned_size(
            free_requested_event.size))
        active_pending_free_block = self._get_block_by_loc(active_pending_free_block_loc)
        if active_pending_free_block is None or active_pending_free_block.state != BlockState.ACTIVE_PENDING_FREE:
            allocator_logger.error(f"{_error}: cannot find the block or is not in {BlockState.ACTIVE_PENDING_FREE} "
                                   f"state.")
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
        segments = self.ctx.device_snapshot.segments
        idx = bisect.bisect_left([seg.address for seg in segments], new_segment.address)
        for hooker in self.hookers.values():
            hooker.pre_replay_map_or_alloc_segment(new_segment, self.ctx.device_snapshot)
        segments.insert(idx, new_segment)
        self.ctx.device_snapshot.total_reserved += new_segment.total_size
        # 设置seg的释放事件, 仿真内存分配器在alloc/map segment时实质对应的是回放到了free/unmap事件，所以此处是设置释放事件id而不是分配事件id
        if self.ctx.current_undo_event:
            new_segment.free_or_unmap_event_idx = self.ctx.current_undo_event.idx
        if not merge:
            for hooker in self.hookers.values():
                hooker.post_replay_map_or_alloc_segment(new_segment, self.ctx.device_snapshot)
            return True
        virtual_map_segment = copy.deepcopy(new_segment)
        # 尝试从前一个segment尽可能多的向后合并
        start_merge_idx = idx - 1 if idx > 0 else idx
        self._merge_consecutive_segments(start_merge_idx)
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
        idx = self.ctx.device_snapshot.find_segment_idx_by_addr(seg_addr)
        if idx < 0 or idx >= len(self.ctx.device_snapshot.segments):
            allocator_logger.error(f"{_error}: cannot found segment(addr={seg_addr})")
            return False
        exist_seg = self.ctx.device_snapshot.segments[idx]
        if exist_seg.address != seg_addr or exist_seg.total_size != alloc_seg_event.size:
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
        del self.ctx.device_snapshot.segments[idx]
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
        exist_seg_idx = self.ctx.device_snapshot.find_segment_idx_by_addr(seg_addr)
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
        if not self._do_unmap_segment(virtual_free_segment, exist_seg_idx):
            return False
        for hooker in self.hookers.values():
            hooker.post_replay_unmap_or_free_segment(virtual_free_segment, self.ctx.device_snapshot)
        return True

    def _get_aligned_size(self, requested_size: int):
        # 为算子末尾预留32字节，并按照align_size对齐
        return math.ceil((requested_size + 32) / self.ctx.block_align_size) * self.ctx.block_align_size

    def _find_reusable_inactive_block(self, block: Block) -> BlockLoc:
        """
            在缓存池中查找可用于分配的segment及block
        :param block: 待分配block
        :return: 可用于分配block的"坐标"
        """
        _error = "Failed to find reusable inactive block"
        seg_idx = self.ctx.device_snapshot.find_segment_idx_by_addr(block.address)
        if seg_idx == -1:
            allocator_logger.error(f"{_error}: cannot found the segment to which the block belongs, {block.to_dict()}")
            return BlockLoc()
        exist_segment = self.ctx.device_snapshot.segments[seg_idx]
        reusable_inactive_block_idx = exist_segment.find_block_idx_by_block_addr(block.address)
        exist_block = exist_segment.blocks[reusable_inactive_block_idx]
        if exist_block.state != BlockState.INACTIVE:
            allocator_logger.error(f"{_error}: cannot reuse block which is not inactive, {exist_block.to_dict()}")
            return BlockLoc(seg_idx, -1)
        if not exist_block.valid_sub_block(block.address, block.size):
            allocator_logger.error(f"{_error}: an abnormal block was found whose address is higher than the "
                                   f"existing block's offset address: {block.to_dict()}")
            return BlockLoc(seg_idx, -1)
        return BlockLoc(seg_idx, reusable_inactive_block_idx)

    def _find_active_block(self, block_addr: int, block_size: int) -> BlockLoc:
        _error = "Failed to find active block"
        exist_seg_idx = self.ctx.device_snapshot.find_segment_idx_by_addr(block_addr)
        if exist_seg_idx is None:
            allocator_logger.error(f"{_error}: cannot found the segment to which the active block belongs,"
                                   f" {block_addr}")
            return BlockLoc(-1, -1)
        exist_segment = self.ctx.device_snapshot.segments[exist_seg_idx]
        exist_block_idx = bisect.bisect_left([_block.address for _block in exist_segment.blocks], block_addr)
        exist_block = exist_segment.blocks[exist_block_idx]
        if exist_block.address != block_addr or self._get_aligned_size(exist_block.requested_size) != block_size:
            allocator_logger.error(f"{_error}: cannot found block (addr={block_addr}, size={block_size}) "
                                   f"in segment {exist_segment.to_dict()}")
            return BlockLoc(exist_seg_idx, -1)
        if exist_block.state == BlockState.INACTIVE:
            allocator_logger.error(f"{_error}: the block (addr = {block_addr}) is not an active block")
            return BlockLoc(exist_seg_idx, -1)
        return BlockLoc(exist_seg_idx, exist_block_idx)

    def _get_block_by_loc(self, block_loc: BlockLoc) -> Optional[Block]:
        _error = "Failed to get block by location"
        if block_loc.seg_idx < 0 or block_loc.seg_idx >= len(self.ctx.device_snapshot.segments):
            allocator_logger.error(f"{_error}: invalid segment idx")
            return None
        exist_segment = self.ctx.device_snapshot.segments[block_loc.seg_idx]
        if block_loc.block_idx < 0 or block_loc.block_idx >= len(exist_segment.blocks):
            allocator_logger.error(f"{_error}: invalid block idx")
            return None
        return exist_segment.blocks[block_loc.block_idx]

    def _insert_block_into_segment(self, segment: Segment, new_block: Block, insert_idx: int):
        segment.blocks.insert(insert_idx, new_block)
        if new_block.state != BlockState.INACTIVE:
            segment.active_size += new_block.size
            self.ctx.device_snapshot.total_activated += new_block.size
            if new_block.state == BlockState.ACTIVE_ALLOCATED:
                segment.allocated_size += new_block.size
                self.ctx.device_snapshot.total_allocated += new_block.size

    def _split_exist_inactive_block(self, block_loc: BlockLoc, slices: list) -> bool:
        """
            将现有的inactive大块拆分为多个小块。原block将被缩小为第一个块，剩余的块会新建
        :param block_loc: 坐标
        :param slices: 待拆分的大小分片，如[2, 4]代表拆成两个大小为2和4的块
        """
        _error = "Failed to split block"
        exist_segment = self.ctx.device_snapshot.segments[block_loc.seg_idx]
        original_block = exist_segment.blocks[block_loc.block_idx]
        if sum(slices) != original_block.size:
            allocator_logger.error(f"{_error}: the expected total size of the slices does not match the size of the "
                                   f"exist block.")
            return False
        # 1. 缩小原block
        original_block.size = slices[0]
        # 2. 拆分剩下的block
        current_idx = block_loc.block_idx
        offset_addr = original_block.address + original_block.size
        for new_block_size in slices[1:]:
            current_idx += 1
            new_block = Block(
                size=new_block_size,
                requested_size=new_block_size,
                address=offset_addr,
                state=BlockState.INACTIVE,
                segment_ptr=exist_segment
            )
            self._insert_block_into_segment(exist_segment, new_block, current_idx)
            offset_addr += new_block_size
        return True

    def _put_new_block_into_segment_block(self, origin_block: Block, new_block: Block):
        origin_block.requested_size = new_block.requested_size
        origin_block.frames = new_block.frames
        origin_block.state = new_block.state
        origin_block.free_event_idx = new_block.free_event_idx
        origin_block.alloc_event_idx = new_block.alloc_event_idx
        if new_block.state != BlockState.INACTIVE:
            origin_block.segment_ptr.active_size += new_block.size
            self.ctx.device_snapshot.total_activated += new_block.size
            if new_block.state == BlockState.ACTIVE_ALLOCATED:
                origin_block.segment_ptr.allocated_size += new_block.size
                self.ctx.device_snapshot.total_allocated += new_block.size

    def _split_exist_segment(self, origin_seg_idx: int, slices: list) -> bool:
        """
            将已有segment拆分成多个分段，需要完成：
            1. 根据slices总数和大小切分
            2. 切分后，需要重整segment
        :param origin_seg_idx:
        :param slices:
        :return:
        """
        _error = "Failed to split exist segment"
        origin_segment = self.ctx.device_snapshot.segments[origin_seg_idx]
        if sum(slices) != origin_segment.total_size:
            allocator_logger.error(f"{_error}: the expected total size of the slices does not match the size of the "
                                   f"origin segment.")
            return False
        # 1. 缩小原内存段, 并进行重整
        origin_segment.total_size = slices[0]
        origin_blocks = origin_segment.blocks
        origin_segment.blocks = list()
        if not self._reorganize_segment(origin_segment, origin_blocks):
            return False
        # 2. 实施拆分
        current_idx = origin_seg_idx
        offset_addr = origin_segment.address + origin_segment.total_size
        for new_seg_size in slices[1:]:
            current_idx += 1
            new_seg = Segment(
                address=offset_addr,
                total_size=new_seg_size,
                stream=origin_segment.stream,
                blocks=list(),
                device=origin_segment.device,
                frames=origin_segment.frames,
                is_expandable=True,
                free_or_unmap_event_idx=origin_segment.free_or_unmap_event_idx,
                alloc_or_map_event_idx=origin_segment.alloc_or_map_event_idx
            )
            if not self._reorganize_segment(new_seg, origin_blocks):
                return False
            self.ctx.device_snapshot.segments.insert(current_idx, new_seg)
            offset_addr += new_seg_size
        return True

    @staticmethod
    def merge_segments(target: Segment, source: Segment):
        target.total_size += source.total_size
        target.allocated_size += source.allocated_size
        target.active_size += source.active_size
        target_tail_block = target.blocks[-1]
        source_head_block = source.blocks[0]
        # 如果source的第一个block与target最后一个block同为inactive，则需要进行合并
        if target_tail_block.state == BlockState.INACTIVE and source_head_block.state == BlockState.INACTIVE:
            target_tail_block.size += source_head_block.size
            del source.blocks[0]
        for block in source.blocks:
            block.segment_ptr = target
            target.blocks.append(block)

    def _drop_exist_segment(self, exist_seg_idx: int) -> bool:
        """
            摘除一个segment
        :param exist_seg_idx: 索引
        :return:
        """
        _error = "Failed to drop exist segment"
        exist_seg = self.ctx.device_snapshot.segments[exist_seg_idx]
        if exist_seg.active_size > 0:
            allocator_logger.error(f"{_error}: cannot drop a segment that still has active allocations.")
            return False
        del self.ctx.device_snapshot.segments[exist_seg_idx]
        return True

    def _merge_consecutive_segments(self, start_merge_idx: int):
        segments = self.ctx.device_snapshot.segments
        while start_merge_idx + 1 < len(segments):
            cur_seg = segments[start_merge_idx]
            next_seg = segments[start_merge_idx + 1]
            # 如相同流且 当前seg的尾与next_seg头相接
            if cur_seg.stream == next_seg.stream and cur_seg.address + cur_seg.total_size == next_seg.address:
                SimulatedCachingAllocator.merge_segments(cur_seg, next_seg)
                del segments[start_merge_idx + 1]
            else:
                start_merge_idx += 1

    def _reorganize_segment(self, segment: Segment, origin_blocks: List[Block]) -> bool:
        """
            根据blocks、total_size重新整理内存段
        :param segment: 待重新整理的内存段
        :return: 是否成功
        """
        err = "Reorganize segment blocks failed"
        seg_addr_end = segment.address + segment.total_size
        segment.allocated_size = 0
        segment.active_size = 0
        # 仅摘取内部块
        pick_idx = 0
        while origin_blocks and pick_idx < len(origin_blocks) and origin_blocks[pick_idx].address < seg_addr_end:
            cur_block = origin_blocks[pick_idx]
            cur_block_addr_end = cur_block.address + cur_block.size
            # 完全无交集
            if cur_block_addr_end <= segment.address:
                pick_idx += 1
                continue
            # 正常内部block，摘取
            if segment.address <= cur_block.address and cur_block_addr_end <= seg_addr_end:
                cur_block.segment_ptr = segment
                segment.blocks.append(cur_block)
                del origin_blocks[pick_idx]
                continue
            # 有交集，则可以判断一下是否为inactive，如果是非inactive说明有异常，不可切分
            if cur_block.state != BlockState.INACTIVE:
                allocator_logger.error(f"{err}: an abnormal active block occurred whose address range exceeds the "
                                       f"segment.")
                return False
            pick_idx += 1
        self._padding_segment(segment)
        # 尝试校验并统计size
        offset_start = segment.address
        for block in segment.blocks:
            if block.address != offset_start:
                allocator_logger.error("Reorganize segment blocks failed.")
                return False
            if block.state != BlockState.INACTIVE:
                segment.active_size += block.size
                if block.state == BlockState.ACTIVE_ALLOCATED:
                    segment.allocated_size += block.size
            offset_start += block.size
        if offset_start != seg_addr_end:
            allocator_logger.error("Reorganize segment blocks failed.")
            return False
        return True

    def _padding_segment(self, segment: Segment):
        """
            重整过程中segment两端可能出现空白，padding空block
        :param segment: 内存段
        :return:
        """
        segment_start = segment.address
        segment_end = segment.address + segment.total_size
        # 可能出现两端有空白，padding一个空block
        padding_size = (segment.blocks[0].address - segment_start) if segment.blocks else segment.total_size
        if padding_size > 0:
            segment.blocks.insert(0, Block(
                size=padding_size,
                requested_size=padding_size,
                address=segment.address,
                state=BlockState.INACTIVE,
                frames=segment.frames,
                segment_ptr=segment
            ))
        last_block_end = segment.blocks[-1].address + segment.blocks[-1].size
        padding_size = segment_end - last_block_end
        if padding_size > 0:
            tail_block = Block(
                size=padding_size,
                requested_size=padding_size,
                address=last_block_end,
                state=BlockState.INACTIVE,
                frames=segment.frames,
                segment_ptr=segment
            )
            segment.blocks.append(tail_block)

    def _do_alloc_block(self, block: Block, alloc_block_loc: BlockLoc) -> bool:
        """
            在指定位置实施分配过程，注意！！！
            1. alloc_block_loc指定的是可用于分配新block的原始空闲块，可能会涉及大块拆分逻辑！
            2. 此过程中也会更新block所在segment的size统计值
        :param block: 待分配的block, 只读！！！
        :param alloc_block_loc: 待分配block的位置
        :return:
        """
        exist_segment = self.ctx.device_snapshot.segments[alloc_block_loc.seg_idx]
        origin_block = exist_segment.blocks[alloc_block_loc.block_idx]
        origin_block_start = origin_block.address
        origin_block_end = origin_block_start + origin_block.size
        new_block_start = block.address
        new_block_end = new_block_start + block.size
        # 左侧对齐
        if origin_block_start == new_block_start:
            # 如果不完全对齐
            if origin_block_end != new_block_end:
                # 拆成两块，执行完成后origin_block大小应与待分配块大小相同
                slices = [block.size, origin_block_end - new_block_end]
                if not self._split_exist_inactive_block(alloc_block_loc, slices):
                    return False
            # 将待分配block放置到空闲块中，注意此时不会替换对象而是将原有对象重新赋block的属性
            self._put_new_block_into_segment_block(origin_block, block)
            return True
        # 右侧对齐：拆成两块，执行完成后, 第二个块的大小应与待分配块大小相同
        # 无对齐：拆成三块，执行完成后，第二个块的大小应与待分配块大小相同
        slices = [new_block_start - origin_block_start, block.size] \
            if origin_block_end == new_block_end else \
            [new_block_start - origin_block_start, block.size, origin_block_end - new_block_end]
        if not self._split_exist_inactive_block(alloc_block_loc, slices):
            return False
        next_block = exist_segment.blocks[alloc_block_loc.block_idx + 1]
        self._put_new_block_into_segment_block(next_block, block)
        return True

    def _do_free_block(self, block_loc: BlockLoc) -> bool:
        free_block = self._get_block_by_loc(block_loc)
        if free_block is None:
            return False
        exist_segment = free_block.segment_ptr
        if exist_segment is None:
            return False
        # 更新统计值
        exist_segment.active_size -= free_block.size
        self.ctx.device_snapshot.total_activated -= free_block.size
        if free_block.state == BlockState.ACTIVE_ALLOCATED:
            exist_segment.allocated_size -= free_block.size
            self.ctx.device_snapshot.total_allocated -= free_block.size
        free_block.state = BlockState.INACTIVE
        # 前向查找inactive 进行合并
        start = block_loc.block_idx
        _seg_blocks = exist_segment.blocks
        while start >= 1:
            if _seg_blocks[start - 1].state != BlockState.INACTIVE:
                break
            start -= 1
        # 后向查找inactive 进行合并
        while start + 1 <= len(_seg_blocks) - 1 and _seg_blocks[start + 1].state == BlockState.INACTIVE:
            exist_segment.blocks[start].size += exist_segment.blocks[start + 1].size
            del exist_segment.blocks[start + 1]
        return True

    def _do_unmap_segment(self, virtual_unmap_segment: Segment, origin_seg_idx: int) -> bool:
        self.ctx.device_snapshot.total_reserved -= virtual_unmap_segment.total_size
        origin_seg = self.ctx.device_snapshot.segments[origin_seg_idx]
        origin_seg_start = origin_seg.address
        origin_seg_end = origin_seg.address + origin_seg.total_size
        unmap_seg_start = virtual_unmap_segment.address
        unmap_seg_end = virtual_unmap_segment.address + virtual_unmap_segment.total_size
        # 如果待释放的内存段在找到的内存段的左侧对齐
        if origin_seg_start == unmap_seg_start:
            # 如果右侧并不对齐，则需要拆成两段，第一段释放掉，第二段保留
            if origin_seg_end != unmap_seg_end:
                slices = [virtual_unmap_segment.total_size, origin_seg_end - unmap_seg_end]
                if not self._split_exist_segment(origin_seg_idx, slices):
                    return False
            return self._drop_exist_segment(origin_seg_idx)
        # 右侧对齐：拆成两块，执行完成后, 第二个块的大小应与待分配块大小相同
        # 无对齐：拆成三块，执行完成后，第二个块的大小应与待分配块大小相同
        slices = [unmap_seg_start - origin_seg_start, virtual_unmap_segment.total_size]
        if origin_seg_end != unmap_seg_end:
            slices.append(origin_seg_end - unmap_seg_end)
        if not self._split_exist_segment(origin_seg_idx, slices):
            return False
        return self._drop_exist_segment(origin_seg_idx + 1)
