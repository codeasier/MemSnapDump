import bisect
import logging
import math
from abc import ABC, abstractmethod
from typing import Optional

from logger import get_logger

from entities import *

loading_logger = get_logger("LOADING")
replay_logger = get_logger("REPLAY")


class SimulateHooker(ABC):
    @abstractmethod
    def pre_undo_event(self, wait4undo_event: TraceEntry, current_snapshot: DeviceSnapshot) -> bool:
        """
            【READONLY】在回放事件前毁掉，此时事件列表**并未POP**出该事件
        :param wait4undo_event: （只读）待回放的事件（仍在事件列表中）
        :param current_snapshot: （制度）当前的内存块快照
        :return 返回true继续执行，返回false将中断
        """
        ...

    @abstractmethod
    def post_undo_event(self, already_undo_event: TraceEntry, current_snapshot: DeviceSnapshot):
        """
            【READONLY】在回放事件后毁掉，此时snapshot已经将该事件从事件列表中丢弃，且segments已回放到事件发生前
        :param already_undo_event: 已回放的事件
        :param current_snapshot: （只读）当前内存快照
        :return 返回true继续执行，返回false将中断
        """
        ...


class SimulateDeviceSnapshot:
    device_snapshot: DeviceSnapshot
    hookers: Dict[int, SimulateHooker]

    def __init__(self, snapshot_dict: dict, device: int = 0):
        if not snapshot_dict:
            raise RuntimeError("Cannot init snapshot from empty data.")
        self.device_snapshot = DeviceSnapshot.from_dict(snapshot_dict, device)

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
                    replay_logger.error(f"An interruption occurred during the replay of the pre hook.")
                    return
            event = self.device_snapshot.trace_entries.pop()
            self._replay_single_event(event)
            for hooker in self.hookers.values():
                if hooker and not hooker.post_undo_event(event, self.device_snapshot):
                    replay_logger.error(f"An interruption occurred during the replay of the post hook.")
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
            self._map_segment(_segment, merge=event.action == "segment_unmap")
            self.device_snapshot.block_map |= _segment.seg_block_map
        elif event.action in ["segment_alloc", "segment"]:
            self._unmap_segment(event.addr, merge=event.action == "segment_map")
        else:
            replay_logger.warning(f"Skip event{event.to_dict()} during replay.")

    def _map_segment(self, segment: Segment, merge: bool = False):
        """
            回放时模拟alloc/map一个新的内存段
        :param segment: 新内存段
        :param merge: 是否开启合并（虚拟内存场景），缺省不合并
        """
        segments = self.device_snapshot.segments
        idx = bisect.bisect_left([seg.address for seg in segments], segment.address)
        segments.insert(idx, segment)
        # 非虚拟内存场景
        if not merge:
            return
            # 虚拟内存，非段列表尾部场景
        if idx + 1 < len(segments):
            next_seg = segments[idx + 1]
            if segment.stream != next_seg.stream:
                return
                # 如果首尾相接
            if segment.address + segment.total_size == next_seg.address:
                segment.total_size += next_seg.total_size
                segment.blocks += next_seg.blocks
                del segments[idx + 1]
            return
            # 虚拟内存，且在段列表尾部
        prev = segments[idx - 1] if idx > 0 else None
        if segment.stream != prev.stream:
            return
        if prev and segment.address == prev.address + prev.total_size:
            prev.total_size += segment.total_size
            prev.blocks += segment.blocks
            del segments[idx - 1]

    def _unmap_segment(self, seg_addr, merge: bool = False):
        """
            回放时模拟free/unmap一个已有的内存段（虚拟内存场景可能是被合并过之后的大段的某一段）
        :param seg_addr: 待释放段的地址
        :param merge: 是否虚拟内存场景
        """
        segments = self.device_snapshot.segments
        idx = bisect.bisect_left([seg.address for seg in segments], seg_addr)
        if idx == len(segments) or (idx == 0 and segments[idx].address != seg_addr):
            logging.error(f"[REPLAYING] Unmap segment failed: cannot found segment(addr={seg_addr})")
            return
        # 非合并场景，直接找到内存地址相同的段并删除
        if not merge:
            del segments[idx]
            return
        seg = segments[idx]
        # 合并场景，找到第一个内存地址+size包含了该内存段的segment
        existing_seg_idx = -1
        seg_address_end = seg.address + seg.total_size
        for i in range(len(segments) - 1, -1, -1):
            _seg = segments[i]
            if _seg.address <= seg.address < seg_address_end <= _seg.address + _seg.total_size:
                existing_seg_idx = i
                break
        if existing_seg_idx == -1:
            logging.error(f"[REPLAYING] Unmap segment failed: cannot found segment(addr={seg_addr})")
            return
        existing_seg = segments[existing_seg_idx]
        existing_seg_addr_end = existing_seg.address + existing_seg.total_size
        # 如果待释放的内存段在找到的内存段的开头对齐
        if existing_seg.address == seg.address:
            existing_seg.address = seg_address_end
            existing_seg.total_size -= seg.total_size
            # 如果释放后内存段size为0，则直接删除
            if existing_seg.total_size <= 0:
                del segments[existing_seg_idx]
                return
                # 如果待释放的内存段在找到的内存段的结尾对齐
        if existing_seg_addr_end == seg_address_end:
            existing_seg.total_size -= seg.total_size
            return
            # 在中间的场景
        existing_seg.total_size = seg.address - existing_seg.address
        seg.address = seg_address_end
        seg.total_size = existing_seg_addr_end - seg_address_end
        segments.insert(existing_seg_idx + 1, seg)

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
        _segment = self.device_snapshot.find_segment_by_block_addr(block.address)
        if _segment is None:
            replay_logger.error(f"{_error}: cannot found the segment to which the block belongs, {block.to_dict()}")
            return
        idx = _segment.find_block_idx_by_block_addr(block.address)
        existing_block = _segment.blocks[idx]
        if existing_block.state != BlockState.INACTIVE:
            replay_logger.error(f"{_error}: cannot split block which is not inactive, {existing_block.to_dict()}")
            return
        # 处理块拆分
        total_size = existing_block.size
        # 左对齐
        if existing_block.address == block.address:
            # 相同大小，则直接修改为新状态即可
            if existing_block.size == block.size:
                existing_block.state = block.state
                return
            # 大小不同，需要拆分，原block基地址+新blocksize作为新block
            existing_block.size = block.size
            existing_block.state = block.state
            block.size = total_size - block.size
            block.address = existing_block.address + existing_block.size
            block.state = BlockState.INACTIVE
            _segment.blocks.insert(idx + 1, block)
            self.device_snapshot.block_map[block.address] = block
            return
        # 左侧未对齐
        total_size = existing_block.size
        existing_block.state = block.state
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

    def _free_block(self, block_addr: int):
        """
            回放时模拟释放一个block，可能涉及到拆分合并
        :param block_addr: 待释放block的地址
        """
        _error = "Failed to simulate free block"
        _segment = self.device_snapshot.find_segment_by_block_addr(block_addr)
        if _segment is None:
            replay_logger.error(f"{_error}: cannot found the segment to which the block belongs, {block_addr}")
            return
        idx = bisect.bisect_left([_block.address for _block in _segment.blocks], block_addr)
        if _segment.blocks[idx].address != block_addr:
            replay_logger.error(f"{_error}: cannot found block addr={block_addr}(hex={hex(block_addr)} "
                                f"in segment {_segment.to_dict()}")
            return
        # 前向查找inactive
        _segment.blocks[idx].state = BlockState.INACTIVE
        start = idx
        while start >= 1:
            if _segment.blocks[start - 1].state != BlockState.INACTIVE:
                break
            start -= 1
        while start + 1 <= len(_segment.blocks) - 1 and _segment.blocks[start + 1].state == BlockState.INACTIVE:
            _segment.blocks[start].size += _segment.blocks[start + 1].size
            del self.device_snapshot.block_map[_segment.blocks[start + 1].address]
            del _segment.blocks[start + 1]
