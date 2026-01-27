import bisect
import copy
import math
from abc import ABC, abstractmethod
from typing import Dict

from util import get_logger

from base import *

loading_logger = get_logger("LOAD")
replay_logger = get_logger("REPLAY")


class SimulateHooker(ABC):
    @abstractmethod
    def pre_undo_event(self, wait4undo_event: TraceEntry, current_snapshot: DeviceSnapshot) -> bool:
        """
            【READONLY】在回放事件前回调，此时事件列表**并未POP**出该事件
        :param wait4undo_event: （只读）待回放的事件（仍在事件列表中）
        :param current_snapshot: （只读）当前的内存块快照
        :return 返回true继续执行，返回false将中断
        """
        ...

    @abstractmethod
    def post_undo_event(self, already_undo_event: TraceEntry, current_snapshot: DeviceSnapshot) -> bool:
        """
            【READONLY】在回放事件后回调，此时snapshot已经将该事件从事件列表中丢弃，且segments已回放到事件发生前
        :param already_undo_event: 已回放的事件
        :param current_snapshot: （只读）当前内存快照
        :return 返回true继续执行，返回false将中断
        """
        ...

    def pre_replay_alloc_block(self, wait4alloc_block: Block, current_snapshot: DeviceSnapshot):
        """
            在**回放时**分配一个内存块**前**回调，对应一个内存块释放事件回滚前
        :param wait4alloc_block: 待分配的block
        :param current_snapshot: 【只读】当前内存快照
        """
        ...

    def post_replay_alloc_block(self, allocated_block: Block, current_snapshot: DeviceSnapshot):
        """
            在**回放时**分配一个内存块**后**回调，对应一个内存块释放事件回滚后
        :param allocated_block: 【只读】新分配的block
        :param current_snapshot:【只读】分配block前内存快照
        """
        ...

    def pre_replay_free_block(self, wait4free_block: Block, current_snapshot: DeviceSnapshot):
        """
            在**回放时**释放一个内存块**前**回调，对应一个内存块申请事件回滚前
        :param wait4free_block: 【只读】待释放的block
        :param current_snapshot: 【只读】释放block前内存快照
        """
        ...

    def post_replay_free_block(self, released_block: Block, current_snapshot: DeviceSnapshot):
        """
            在回放时，释放一个内存块**后**回调，对应一个内存块申请事件回滚后
        :param released_block: 【副本】已释放的block（副本）
        :param current_snapshot: 【只读】释放block后内存快照
        """
        ...

    def pre_replay_map_or_alloc_segment(self, wait4alloc_map_segment: Segment, current_snapshot: DeviceSnapshot):
        """
            在回放时，分配或映射一个内存段**前**回调，对应一个内存段释放或unmap事件回滚前
        :param wait4alloc_map_segment: 【只读】待分配或map的内存段
        :param current_snapshot: 分配或map内存段前的内存快照
        """

    def post_replay_map_or_alloc_segment(self, allocated_mapped_segment: Segment, current_snapshot: DeviceSnapshot):
        """
            在回放时，分配或映射一个内存段**后**回调，对应一个内存段释放或unmap事件回滚后
        :param allocated_mapped_segment:【副本】已分配或map的内存段
        :param current_snapshot: 分配或map内存段后的内存快照
        """

    def pre_replay_unmap_or_free_segment(self, wait4release_segment: Segment, current_snapshot: DeviceSnapshot):
        """
            在回放时，释放或unmap一个内存段**前**回调，对应一个内存段申请或map事件前
        :param wait4release_segment:【只读】待释放的内存段
        :param current_snapshot: 释放或unmap内存段前的内存快照
        """
        ...

    def post_replay_unmap_or_free_segment(self, released_segment: Segment, current_snapshot: DeviceSnapshot):
        """
            在回放时，释放或unmap一个内存段**后**回调，对应一个内存段申请或map事件后
        :param released_segment:【副本】已释放的内存段
        :param current_snapshot: 释放或unmap内存段后的内存快照
        """
        ...


class SimulateDeviceSnapshot:
    device_snapshot: DeviceSnapshot
    hookers: Dict[int, SimulateHooker]

    def __init__(self, snapshot_dict: dict, device: int = 0):
        if not snapshot_dict:
            raise RuntimeError("Cannot init snapshot from empty data.")
        self.device_snapshot = DeviceSnapshot.from_dict(snapshot_dict, device)
        self.hookers = {}

    def register_hooker(self, hooker: SimulateHooker) -> int:
        idx = hash(hooker)
        self.hookers[idx] = hooker
        return idx

    def unregister_hooker(self, hooker_id: int):
        if hooker_id in self.hookers:
            del self.hookers

    def replay(self):
        """
            开始仿真回放内存事件
        """
        # 倒序遍历
        while self.device_snapshot.trace_entries:
            for hooker in self.hookers.values():
                if hooker and not hooker.pre_undo_event(self.device_snapshot.trace_entries[-1], self.device_snapshot):
                    replay_logger.error(f"An interruption occurred during the replay of the single event pre hook.")
                    return
            event = self.device_snapshot.trace_entries[-1]
            self._replay_single_event(event)
            self.device_snapshot.trace_entries.pop()
            for hooker in self.hookers.values():
                if hooker and not hooker.post_undo_event(event, self.device_snapshot):
                    replay_logger.error(f"An interruption occurred during the replay of the single event post hook.")
                    return

    def _replay_single_event(self, event: TraceEntry):
        if event.action in ["free", "free_completed"]:
            _block = Block.build_from_event(event)
            _block.state = BlockState.ACTIVE_ALLOCATED if event.action == "free" else BlockState.ACTIVE_PENDING_FREE
            self._alloc_block(_block)
        elif event.action == "free_requested":
            self.device_snapshot.block_map[event.addr].state = BlockState.ACTIVE_ALLOCATED
        elif event.action == "alloc":
            self._free_block(event.addr)
        elif event.action in ["segment_free", "segment_unmap"]:
            _segment = Segment.build_from_event(event)
            self._alloc_or_map_segment(_segment, merge=event.action == "segment_unmap")
            self.device_snapshot.block_map |= _segment.seg_block_map
        elif event.action == "segment_alloc":
            self._free_segment(event.addr)
        elif event.action == "segment_map":
            self._unmap_segment(event.addr, event.size)
        else:
            replay_logger.warning(f"Skip event{event.to_dict()} during replay.")

    def reorganize_segment_blocks(self, segment: Segment):
        seg_addr_end = segment.address + segment.total_size
        idx = 0
        # 自左向右
        while idx < len(segment.blocks):
            cur_block = segment.blocks[idx]
            cur_block_addr_end = cur_block.address + cur_block.size
            if not (segment.address <= cur_block.address and cur_block_addr_end <= seg_addr_end):
                del segment.blocks[idx]
            else:
                idx += 1
        offset_start = segment.address
        for block in segment.blocks:
            if block.address != offset_start:
                replay_logger.error("Reorganize segment blocks failed.")
            offset_start += block.size
        if offset_start != seg_addr_end:
            replay_logger.error("Reorganize segment blocks failed.")

    def _alloc_or_map_segment(self, segment: Segment, merge: bool = False):
        """
            回放时模拟alloc或map一个新的内存段
        :param segment: 新内存段
        :param merge: 是否合并，map时对应虚拟内存场景，否则仅为alloc
        """
        segments = self.device_snapshot.segments
        idx = bisect.bisect_left([seg.address for seg in segments], segment.address)
        for hooker in self.hookers.values():
            hooker.pre_replay_map_or_alloc_segment(segment, self.device_snapshot)
        segments.insert(idx, segment)
        allocated_or_mapped_segment_copy = copy.copy(segment)
        if not merge:
            return
            # 判断能否与后一个segment进行合并
        if idx + 1 < len(segments):
            next_seg = segments[idx + 1]
            # 如相同流且 当前seg的尾与next_seg头相接
            if segment.stream == next_seg.stream and segment.address + segment.total_size == next_seg.address:
                segment.total_size += next_seg.total_size
                segment.blocks += next_seg.blocks
                del segments[idx + 1]
        # 判断能否与前一个seg进行合并
        if idx == 0:
            for hooker in self.hookers.values():
                hooker.post_replay_map_or_alloc_segment(allocated_or_mapped_segment_copy, self.device_snapshot)
            return
        prev_seg = segments[idx - 1]
        # 如相同流且 当前seg的头与prev_seg尾相接
        if segment.stream == prev_seg.stream and segment.address == prev_seg.address + prev_seg.total_size:
            prev_seg.total_size += segment.total_size
            prev_seg.blocks += segment.blocks
            del segments[idx - 1]
        for hooker in self.hookers.values():
            hooker.post_replay_map_or_alloc_segment(allocated_or_mapped_segment_copy, self.device_snapshot)

    def _free_segment(self, seg_addr: int):
        """
            回放时模拟free一个内存段（非虚拟内存场景）
        :param seg_addr: 待释放段地址
        """
        _error = "Free segment failed"
        idx = self.device_snapshot.find_segment_idx_by_addr(seg_addr)
        if idx < 0 or idx >= len(self.device_snapshot.segments):
            replay_logger.error(f"{_error}: cannot found segment(addr={seg_addr})")
            return
        exist_seg = self.device_snapshot.segments[idx]
        if exist_seg.address != seg_addr:
            replay_logger.error(f"{_error}: cannot free segment(addr={seg_addr}) in exist segment({exist_seg.address})")
            return
        for hooker in self.hookers.values():
            hooker.pre_replay_unmap_or_free_segment(self.device_snapshot.segments[idx], self.device_snapshot)
        released_segment_copy = copy.copy(self.device_snapshot.segments[idx])
        del self.device_snapshot.segments[idx]
        for hooker in self.hookers.values():
            hooker.post_replay_unmap_or_free_segment(released_segment_copy, self.device_snapshot)

    def _unmap_segment(self, seg_addr: int, unmap_size: int):
        """
            回放时模拟unmap一个已有的内存段（虚拟内存场景）
        :param seg_addr: 待释放段的地址
        :param unmap_size: 待unmap的大小
        """
        _error = "Unmap segment failed"
        segments = self.device_snapshot.segments
        exist_seg_idx = self.device_snapshot.find_segment_idx_by_addr(seg_addr)
        if exist_seg_idx < 0 or exist_seg_idx >= len(segments):
            replay_logger.error(f"{_error}: cannot found segment(addr={seg_addr})")
            return
        exist_seg = segments[exist_seg_idx]
        if not (seg_addr >= exist_seg.address and seg_addr + unmap_size <= exist_seg.address + exist_seg.total_size):
            replay_logger.error(
                f"{_error}: cannot unmap segment(addr={seg_addr}, unmap_size={unmap_size}) in exist segment("
                f"addr={exist_seg.address}, total_size={exist_seg.total_size})")
            return
        for hooker in self.hookers.values():
            hooker.pre_replay_unmap_or_free_segment(exist_seg, self.device_snapshot)
        released_segment_copy = copy.copy(exist_seg)
        exist_seg_addr_end = exist_seg.address + exist_seg.total_size
        unmap_seg_addr_end = seg_addr + unmap_size
        # 如果待释放的内存段在找到的内存段的开头对齐
        if exist_seg.address == seg_addr:
            exist_seg.address = unmap_seg_addr_end
            exist_seg.total_size -= unmap_size
            # 如果释放后内存段size为0，则直接删除
            if exist_seg.total_size <= 0:
                del segments[exist_seg_idx]
                for hooker in self.hookers.values():
                    hooker.post_replay_unmap_or_free_segment(released_segment_copy, self.device_snapshot)
                return
        # 如果待释放的内存段在找到的内存段的结尾对齐
        if exist_seg_addr_end == unmap_seg_addr_end:
            exist_seg.total_size -= unmap_size
            for hooker in self.hookers.values():
                hooker.post_replay_unmap_or_free_segment(released_segment_copy, self.device_snapshot)
            return
        # 在中间的场景
        exist_seg.total_size = seg_addr - exist_seg.address
        remain_seg = Segment()
        remain_seg.address = unmap_seg_addr_end
        remain_seg.total_size = exist_seg_addr_end - unmap_seg_addr_end
        remain_seg.stream = exist_seg.stream
        remain_seg.frames = exist_seg.frames
        remain_seg.blocks = exist_seg.blocks
        self.reorganize_segment_blocks(exist_seg)
        self.reorganize_segment_blocks(remain_seg)
        segments.insert(exist_seg_idx + 1, remain_seg)
        for hooker in self.hookers.values():
            hooker.post_replay_unmap_or_free_segment(released_segment_copy, self.device_snapshot)

    def _alloc_block(self, block: Block, align_size: int = 512):
        """
            回放时模拟分配一个新的block
        :param block: 待分配的block
        :param align_size: 对齐大小，默认为512Bytes对齐
        """
        _error = "Failed to simulate alloc block"
        # 新块按照512对齐拆分
        block.size = math.ceil(block.requested_size / align_size) * align_size
        # 将block在所属segment中分配
        seg_idx = self.device_snapshot.find_segment_idx_by_addr(block.address)
        if seg_idx == -1:
            replay_logger.error(f"{_error}: cannot found the segment to which the block belongs, {block.to_dict()}")
            return
        _segment = self.device_snapshot.segments[seg_idx]
        idx = _segment.find_block_idx_by_block_addr(block.address)
        existing_block = _segment.blocks[idx]
        if existing_block.state != BlockState.INACTIVE:
            replay_logger.error(f"{_error}: cannot split block which is not inactive, {existing_block.to_dict()}")
            return
        if not existing_block.valid_sub_block(block.address, block.size):
            replay_logger.error(f"{_error}: an abnormal block was found whose address is higher than the "
                                f"existing block's offset address: {block.to_dict()}")
            return
        for hooker in self.hookers.values():
            hooker.pre_replay_alloc_block(block, self.device_snapshot)
        # 处理块拆分
        total_size = existing_block.size
        # 左对齐
        if existing_block.address == block.address:
            existing_block.state = block.state
            existing_block.frames = block.frames
            existing_block.requested_size = block.requested_size
            # 相同大小，则直接修改为新状态即可
            if existing_block.size == block.size:
                for hooker in self.hookers.values():
                    hooker.post_replay_alloc_block(existing_block, self.device_snapshot)
                return
            # 大小不同，需要拆分，原block基地址+新blocksize作为新block
            existing_block.size = block.size
            block.size = total_size - block.size
            block.address = existing_block.address + existing_block.size
            block.state = BlockState.INACTIVE
            _segment.blocks.insert(idx + 1, block)
            self.device_snapshot.block_map[block.address] = block
            for hooker in self.hookers.values():
                hooker.post_replay_alloc_block(existing_block, self.device_snapshot)
            return
        # 左侧未对齐
        existing_block.size = block.address - existing_block.address
        _segment.blocks.insert(idx + 1, block)
        self.device_snapshot.block_map[block.address] = block
        # 如果右侧也未对齐
        if total_size - existing_block.size - block.size > 0:
            r_block = Block(
                address=block.address + block.size,
                size=total_size - existing_block.size - block.size,
                requested_size=total_size - existing_block.size - block.size,
                state=BlockState.INACTIVE,
            )
            _segment.blocks.insert(idx + 2, r_block)
            self.device_snapshot.block_map[r_block.address] = r_block
        for hooker in self.hookers.values():
            hooker.post_replay_alloc_block(block, self.device_snapshot)

    def _free_block(self, block_addr: int):
        """
            回放时模拟释放一个block，可能涉及到拆分合并
        :param block_addr: 待释放block的地址
        """
        _error = "Failed to simulate free block"
        _seg_idx = self.device_snapshot.find_segment_idx_by_addr(block_addr)
        if _seg_idx is None:
            replay_logger.error(f"{_error}: cannot found the segment to which the block belongs, {block_addr}")
            return
        _segment = self.device_snapshot.segments[_seg_idx]
        idx = bisect.bisect_left([_block.address for _block in _segment.blocks], block_addr)
        if _segment.blocks[idx].address != block_addr:
            replay_logger.error(f"{_error}: cannot found block addr={block_addr}(hex={hex(block_addr)} "
                                f"in segment {_segment.to_dict()}")
            return
        # 前向查找inactive
        for hooker in self.hookers.values():
            hooker.pre_replay_free_block(_segment.blocks[idx], self.device_snapshot)
        _segment.blocks[idx].state = BlockState.INACTIVE
        released_block_copy = copy.copy(_segment.blocks[idx])
        start = idx
        while start >= 1:
            if _segment.blocks[start - 1].state != BlockState.INACTIVE:
                break
            start -= 1
        while start + 1 <= len(_segment.blocks) - 1 and _segment.blocks[start + 1].state == BlockState.INACTIVE:
            _segment.blocks[start].size += _segment.blocks[start + 1].size
            del self.device_snapshot.block_map[_segment.blocks[start + 1].address]
            del _segment.blocks[start + 1]
        for hooker in self.hookers.values():
            hooker.pre_replay_free_block(released_block_copy, self.device_snapshot)
