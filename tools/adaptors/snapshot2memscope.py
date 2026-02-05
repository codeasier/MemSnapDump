import os
import argparse
from pathlib import Path
from simulate import SimulateHooker, SimulateDeviceSnapshot, AllocatorHooker
from base import DeviceSnapshot, TraceEntry, Block, Segment, BlockState
from util.file_util import check_dir_valid
from .snapshot_adaptor import MemScopeEntityBuilder as Builder
from .memscope.database import MemScopeDb
from .memscope.entities import MemoryBlock

from util.logger import get_logger
from util.timer import timer

dump_logger = get_logger("MemScopeDump")


class MemScopeDbHandler:
    def __init__(self, dump_dir: str, insert_cache_size: int = 1000):
        self.dump_dir = dump_dir
        self.db = MemScopeDb(dump_dir)
        self.db.create_allocation_table()
        self.db.create_memory_block_table()
        self._event_cache = list()
        self._block_cache = list()
        self._allocation_cache = list()
        self._insert_cache_size = insert_cache_size

    def insert_event(self, event_record: dict):
        self._event_cache.append(event_record)
        if len(self._event_cache) >= self._insert_cache_size:
            self._do_insert_events()

    def insert_allocation(self, allocation_record: dict):
        self._allocation_cache.append(allocation_record)
        if len(self._allocation_cache) >= self._insert_cache_size:
            self._do_insert_allocations()

    def insert_block(self, block_record: dict):
        self._block_cache.append(block_record)
        if len(self._block_cache) >= self._insert_cache_size:
            self._do_insert_blocks()

    def flush(self):
        if self._allocation_cache:
            self._do_insert_allocations()
        if self._event_cache:
            self._do_insert_events()
        if self._block_cache:
            self._do_insert_blocks()

    def _do_insert_events(self):
        self.db.get_dump_table().insert_records(self.db.conn, self._event_cache)
        self.db.conn.commit()
        self._event_cache.clear()

    def _do_insert_allocations(self):
        self.db.get_allocation_table().insert_records(self.db.conn, self._allocation_cache)
        self.db.conn.commit()
        self._allocation_cache.clear()

    def _do_insert_blocks(self):
        self.db.get_memory_block_table().insert_records(self.db.conn, self._block_cache)
        self.db.conn.commit()
        self._block_cache.clear()

    def __del__(self):
        self.db.conn.commit()
        self.db.conn.close()


class DumpEventAndAllocationHooker(SimulateHooker, AllocatorHooker):
    def __init__(self, dump_dir: str, dump_cache_size: int = 1000):
        self.db_handler = MemScopeDbHandler(dump_dir)
        self.current_total_size = {}

    def post_undo_event(self, already_undo_event: TraceEntry, current_snapshot: DeviceSnapshot) -> bool:
        # 每个事件回放后dump一次allocation
        self.db_handler.insert_allocation(
            Builder.build_memory_allocation(0, already_undo_event, current_snapshot).to_dict())
        # 回放完毕，dump剩余Segmen及block数据, 注意应该先插入blocks
        if not current_snapshot.trace_entries:
            for seg in current_snapshot.segments:
                for block in seg.blocks:
                    if block.state != BlockState.INACTIVE:
                        self.db_handler.insert_block(Builder.build_memory_block_from_snapshot_block(0, block).to_dict())
                # segment不插入block表，而是以模拟事件插入事件表，便于后续重建segment
                self.db_handler.insert_event(Builder.build_memory_event_from_snapshot_trace_entry(0, TraceEntry(
                    idx=None,
                    action='segment_map' if seg.is_expandable else 'segment_alloc',
                    addr=seg.address,
                    frames=seg.frames,
                    size=seg.total_size,
                    stream=seg.stream,
                )).to_dict())
        return True

    def pre_undo_event(self, wait4undo_event: TraceEntry, current_snapshot: DeviceSnapshot) -> bool:
        # 回放首个事件前将内存事件dump到memscopedb中
        self.db_handler.insert_event(Builder.build_memory_event_from_snapshot_trace_entry(0, wait4undo_event).to_dict())
        # 记录回放前的统计值
        self.current_total_size = {
            'total_allocated': current_snapshot.total_allocated,
            'total_reserved': current_snapshot.total_reserved,
            'total_activated': current_snapshot.total_activated
        }
        return True

    def post_replay_free_block(self, wait4free_block: Block, current_snapshot: DeviceSnapshot):
        super().pre_replay_free_block(wait4free_block, current_snapshot)
        block = Builder.build_memory_block_from_snapshot_block(0, wait4free_block)
        self._append_size_attr_to_mem_block(block)
        self.db_handler.insert_block(block.to_dict())

    def _append_size_attr_to_mem_block(self, ms_block: MemoryBlock):
        if isinstance(ms_block, MemoryBlock):
            ms_block.attr |= self.current_total_size

    def __del__(self):
        self.db_handler.flush()


def dump(pickle_file: str, dump_file: str):
    import pickle
    with open(pickle_file, 'rb') as f:
        data = pickle.load(f)
    # df = pd.read_pickle(pickle_file)
    snapshot = SimulateDeviceSnapshot(data, 0)
    hooker = DumpEventAndAllocationHooker(dump_file)
    snapshot.register_hooker(hooker)
    snapshot.register_allocator_hooker(hooker)
    snapshot.replay()


def get_args():
    parser = argparse.ArgumentParser(
        description="This script is used to parse and convert snapshot data into a database "
                    "format that is more convenient for visualization.")
    arg_snapshot = parser.add_argument("snapshot_file", type=str, help="Memory snapshot file path.")
    arg_dump_dir = parser.add_argument("--dump_dir", "-o",
                                       required=False,
                                       type=str,
                                       default='',
                                       help="Specify the directory to store the parsed database file. If not provided, "
                                            "the same directory as the specified snapshot file will be used by default.")
    args = parser.parse_args()
    snapshot_path = Path(args.snapshot_file)
    # 校验snapshot path
    if not snapshot_path.is_file() or not os.access(args.snapshot_file, os.R_OK):
        raise argparse.ArgumentError(arg_snapshot,
                                     "The specified snapshot file does not exist, or is not a file, or is not readable.")
    # 校验dump目标路径
    if not args.dump_dir:
        args.dump_dir = snapshot_path.parent
    if not Path(args.dump_dir).is_dir() or not check_dir_valid(args.dump_dir):
        raise argparse.ArgumentError(arg_dump_dir,
                                     "The specified directory does not exist, or is not a directory, "
                                     "or is not writable")
    return args


@timer
def main():
    args = get_args()
    dump(args.snapshot_file, Path(args.dump_dir) / f"{Path(args.snapshot_file).stem}.db")


if __name__ == '__main__':
    main()
