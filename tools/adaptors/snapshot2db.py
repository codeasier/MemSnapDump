import os
import sys
import argparse
from pathlib import Path
from simulate import SimulateHooker, SimulateDeviceSnapshot, AllocatorHooker
from base import DeviceSnapshot, TraceEntry, Block, BlockState
from util.file_util import check_dir_valid, load_pickle_to_dict

from tools.adaptors.database import SnapshotDb, block2record, event2record

from util.logger import get_logger, set_global_log_file
from util.timer import timer

dump_logger = get_logger("DatabaseDump")


class SnapshotDbHandler:
    def __init__(self, dump_dir: str, insert_cache_size: int = 1000):
        self.dump_dir = dump_dir
        self.db = SnapshotDb(dump_dir)
        self._event_cache = list()
        self._block_cache = list()
        self._insert_cache_size = insert_cache_size

    def insert_event(self, event_record: dict):
        self._event_cache.append(event_record)
        if len(self._event_cache) >= self._insert_cache_size:
            self._do_insert_events()

    def insert_block(self, block_record: dict):
        self._block_cache.append(block_record)
        if len(self._block_cache) >= self._insert_cache_size:
            self._do_insert_blocks()

    def flush(self):
        if self._event_cache:
            self._do_insert_events()
        if self._block_cache:
            self._do_insert_blocks()

    def _do_insert_events(self):
        self.db.get_trace_entry_table().insert_records(self.db.conn, self._event_cache)
        self.db.conn.commit()
        self._event_cache.clear()

    def _do_insert_blocks(self):
        self.db.get_block_table().insert_records(self.db.conn, self._block_cache)
        self.db.conn.commit()
        self._block_cache.clear()

    def __del__(self):
        self.db.conn.commit()
        self.db.conn.close()


class DumpEventHooker(SimulateHooker, AllocatorHooker):
    def __init__(self, dump_dir: str, dump_cache_size: int = 1000):
        self.db_handler = SnapshotDbHandler(dump_dir, insert_cache_size=dump_cache_size)

    def post_undo_event(self, already_undo_event: TraceEntry, current_snapshot: DeviceSnapshot) -> bool:
        # 每个事件回放后dump一次event
        self.db_handler.insert_event(event2record(
            event=already_undo_event,
            allocated=current_snapshot.total_allocated,
            active=current_snapshot.total_activated,
            reserved=current_snapshot.total_reserved
        ))
        # 回放完毕，dump剩余Segment及block数据, 注意应该先插入blocks
        if not current_snapshot.trace_entries:
            dump_logger.info("Finished ")
            for seg in current_snapshot.segments:
                for block in seg.blocks:
                    if block.state != BlockState.INACTIVE:
                        self.db_handler.insert_block(block2record(block))
                # segment不插入block表，而是以模拟事件插入事件表，便于后续重建segment
                mock_segment_alloc_event = TraceEntry(
                    idx=None,
                    action='segment_map' if seg.is_expandable else 'segment_alloc',
                    addr=seg.address,
                    frames=seg.frames,
                    size=seg.total_size,
                    stream=seg.stream,
                )
                self.db_handler.insert_event(event2record(
                    event=mock_segment_alloc_event,
                    allocated=current_snapshot.total_allocated,
                    active=current_snapshot.total_activated,
                    reserved=current_snapshot.total_reserved
                ))
        return True

    def pre_undo_event(self, wait4undo_event: TraceEntry, current_snapshot: DeviceSnapshot) -> bool:
        return True

    def post_replay_free_block(self, released_block: Block, current_snapshot: DeviceSnapshot):
        self.db_handler.insert_block(block2record(released_block))

    def __del__(self):
        self.db_handler.flush()


def dump(pickle_file: str, dump_file: str) -> bool:
    try:
        data = load_pickle_to_dict(Path(pickle_file))
    except Exception as e:
        dump_logger.error("Failed to load pickle file: {}".format(e))
        return False
    snapshot = SimulateDeviceSnapshot(data, 0)
    hooker = DumpEventHooker(dump_file)
    snapshot.register_hooker(hooker)
    snapshot.register_allocator_hooker(hooker)
    return snapshot.replay()


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
    arg_log_file = parser.add_argument("--log", "-l",
                                       required=False,
                                       type=str,
                                       default='',
                                       help="Specify the log file path. If provided, all logs will be written to this file.")
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
    if args.log:
        try:
            set_global_log_file(args.log)
        except OSError as e:
            raise argparse.ArgumentError(arg_log_file, str(e))
    return args


class ExistCode:
    SUCCESS = 0
    FAILED = -1

@timer(name="Dump snapshot to database.", logger=dump_logger)
def main():
    args = get_args()
    if not dump(args.snapshot_file, Path(args.dump_dir) / f"{Path(args.snapshot_file).name}.db"):
        dump_logger.error("Failed to dump the snapshot to database.")
        sys.exit(ExistCode.FAILED)
    sys.exit(ExistCode.SUCCESS)


if __name__ == '__main__':
    main()
