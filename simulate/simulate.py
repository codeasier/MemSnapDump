from typing import Dict

from util import get_logger
from base import *

from .simulated_caching_allocator import SimulatedCachingAllocator, AllocatorContext
from .hooker_defs import SimulateHooker, AllocatorHooker

loading_logger = get_logger("LOAD")
replay_logger = get_logger("REPLAY")


class SimulateDeviceSnapshot:
    device_snapshot: DeviceSnapshot
    hookers: Dict[int, SimulateHooker]

    def __init__(self, snapshot_dict: dict, device: int = 0):
        if not snapshot_dict:
            raise RuntimeError("Cannot init snapshot from empty data.")
        self.device_snapshot = DeviceSnapshot.from_dict(snapshot_dict, device)
        self.hookers = {}
        self.simulated_allocator_context = AllocatorContext(snapshot=self.device_snapshot)
        self.simulated_allocator = SimulatedCachingAllocator(self.simulated_allocator_context)

    def register_hooker(self, hooker: SimulateHooker) -> int:
        idx = hash(hooker)
        self.hookers[idx] = hooker
        return idx

    def unregister_hooker(self, hooker_id: int):
        if hooker_id in self.hookers:
            del self.hookers[hooker_id]

    def register_allocator_hooker(self, hooker: AllocatorHooker) -> int:
        return self.simulated_allocator.register_hooker(hooker)

    def unregister_allocator_hooker(self, hooker_id: int):
        self.simulated_allocator.unregister_hooker(hooker_id)

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
            self.simulated_allocator_context.set_current_undo_event(event)
            if not self._replay_single_event(event):
                replay_logger.error(f"An interruption occurred during the replay of the single event.")
                return
            self.device_snapshot.trace_entries.pop()
            for hooker in self.hookers.values():
                if hooker and not hooker.post_undo_event(event, self.device_snapshot):
                    replay_logger.error(f"An interruption occurred during the replay of the single event post hook.")
                    return

    def _replay_single_event(self, event: TraceEntry) -> bool:
        if event.action in ["free", "free_completed"]:
            _block = Block.build_from_event(event)
            _block.state = BlockState.ACTIVE_ALLOCATED if event.action == "free" else BlockState.ACTIVE_PENDING_FREE
            return self.simulated_allocator.alloc_block(_block)
        if event.action == "free_requested":
            return self.simulated_allocator.active_block(event)
        if event.action == "alloc":
            return self.simulated_allocator.free_block(event)
        if event.action in ["segment_free", "segment_unmap"]:
            _segment = Segment.build_from_event(event)
            _segment.free_or_unmap_event_idx = event.idx
            return self.simulated_allocator.alloc_or_map_segment(_segment, merge=event.action == "segment_unmap")
        elif event.action == "segment_alloc":
            return self.simulated_allocator.free_segment(event)
        elif event.action == "segment_map":
            return self.simulated_allocator.unmap_segment(event)
        else:
            replay_logger.warning(f"Skip event{event.to_dict()} during replay.")
            return False
