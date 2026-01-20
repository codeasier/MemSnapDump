import argparse
import copy
import json
import math
import os.path
from typing import Literal

import pandas as pd

from base import TraceEntry, DeviceSnapshot
from simulate import SimulateDeviceSnapshot, SimulateHooker
from util import get_logger

dump_logger = get_logger("DUMP")


class SliceDumpHooker(SimulateHooker):
    """
    按照事件顺序平均切分固定个数，或按照固定最大事件数量切分
    定义：
        - seg.x表示第x个事件发生，第x+1个事件未发生时的内存段状态
        - evt[x1:x2]表示第x1个到第x2个事件
    假设有61个事件 原始数据为：seg.61 + evt[1:61]
    1 ----------------- 15 ------------------ 30 ----------------- 45 ----------------- 60
    | ----------------- << ------------------ << ----------------- << ----------------- |
    方式一. 采用固定切分文件数(以4份为例)
    则切分结果为：
        - seg.13 + evt[1:13]
        - seg.29 + evt[14:29]
        - seg.45 + evt[30:45]
        - seg.61 + evt[46:61]
    方式二. 采用固定最大事件数切分(以最大事件数为20为例)
    则切分结果为
        - seg.20 + evt[1:20]
        - seg.40 + evt[21:40]
        - seg.60 + evt[46:60]
    """

    def __init__(self, dump_dir: str,
                 num_of_slices: int = 4,
                 max_entries: int = 15000,
                 dump_type: Literal["json", "pkl"] = "pkl",
                 dump_progress_point=None):
        if dump_progress_point is None:
            dump_progress_point = [0.75, 0.5, 0.25]
        if num_of_slices <= 0:
            raise ValueError("The number of slices must be a positive integer and cannot be non-positive, at least 1.")
        if (not os.path.exists(dump_dir)) or not os.path.isdir(dump_dir) or not os.access(dump_dir, os.W_OK):
            raise ValueError(f"The dump dir {dump_dir} does not exist, is not a directory, or is not writable.")
        self.num_of_slices = num_of_slices
        self.max_entries = max_entries
        self.num_of_events = -1
        self.events_buffer = []  # 缓存从上一次dump点到当前的事件
        self.prev_segments = None  # 缓存上一次dump点的内存段状态
        self.dump_dir = dump_dir
        self.dump_count = 0
        self.dump_type = dump_type
        self.dump_progress_point = dump_progress_point
        self.dump_progress_point.sort()

    def pre_undo_event(self, wait4undo_event: TraceEntry, current_snapshot: DeviceSnapshot) -> bool:
        if self.num_of_events == -1:
            # lazy init
            self.num_of_events = len(current_snapshot.trace_entries)
            self._init_splitting_strategy()
            self.prev_segments = copy.deepcopy(current_snapshot.segments)
        current_num_of_events = len(current_snapshot.trace_entries)
        if self.dump_progress_point and current_num_of_events <= self.dump_progress_point[-1] * self.num_of_events:
            _done_point = self.dump_progress_point.pop()
            dump_logger.info(f"Progressing: {(1 - _done_point) * 100}%")
        return True

    def _init_splitting_strategy(self):
        if self.num_of_slices == -1:
            raise RuntimeError("Cannot init splitting strategy before init total entries")
        if math.ceil(self.num_of_events / self.num_of_slices) > self.max_entries:
            dump_logger.warning("The expected number of slices may leads the single snapshot file exceeds the "
                                "max_entries limit.Splitting will be performed based on max_entries, or you may try "
                                "increasing the max_entries value.")
        self.max_entries = min(math.ceil(self.num_of_events / self.num_of_slices), self.max_entries)
        self.num_of_slices = max(self.num_of_slices, math.ceil(self.num_of_events / self.max_entries))

    def post_undo_event(self, already_undo_event: TraceEntry, current_snapshot: DeviceSnapshot):
        self.events_buffer.insert(0, already_undo_event)
        if self._is_need_dump(current_snapshot):
            self.dump()
            self.prev_segments = copy.deepcopy(current_snapshot.segments)
            self.events_buffer.clear()
        return True

    def _is_need_dump(self, current_snapshot: DeviceSnapshot) -> bool:
        # 如果回放事件数量已经达到了单分片最大长度
        if len(self.events_buffer) >= self.max_entries:
            return True
        # 如果此时events_buffer并为达到最大分片长度，但已无事件，则代表剩余部分，仍然需要dump
        if self.events_buffer and not current_snapshot.trace_entries:
            return True
        return False

    def dump(self):
        slice_snapshot_name = self._get_dump_filename()
        slice_snapshot = DeviceSnapshot()
        slice_snapshot.segments = self.prev_segments
        slice_snapshot.trace_entries = self.events_buffer
        slice_snapshot_dict = slice_snapshot.to_dict()
        del self.prev_segments
        self.events_buffer.clear()
        dump_logger.info(f"Start to dump snapshot slice: {slice_snapshot_name}")
        if self.dump_type == "pkl":
            pd.to_pickle(slice_snapshot_dict, slice_snapshot_name, protocol=4)
        else:
            with open(slice_snapshot_name, 'w') as f:
                json.dump(slice_snapshot_dict, f)
        self.dump_count += 1
        dump_logger.info(f"Successfully saved slice to file: {slice_snapshot_name}")

    def _get_dump_filename(self) -> str:
        slice_num = self.num_of_slices - self.dump_count
        entry_idx_start = max(self.num_of_events - (self.dump_count + 1) * self.max_entries + 1, 0)
        entry_idx_end = self.num_of_events - self.dump_count * self.max_entries
        return os.path.join(self.dump_dir,
                            f"slice_{slice_num}_entry_{entry_idx_start}_{entry_idx_end}.{self.dump_type}")


def get_args():
    parser = argparse.ArgumentParser(description="This script is used for memory snapshot output files(typically in "
                                                 "pickle format captured by torch/torch_npu.")
    parser.add_argument("snapshot_file", type=str, help="Memory snapshot file path.")
    parser.add_argument("--device", "-d",
                        required=False,
                        default=0,
                        type=lambda x: int(x) if int(x) >= 0 else parser.error("The device id must be at least 0"))
    parser.add_argument("--slices", "-s",
                        required=False,
                        type=lambda x: int(x) if int(x) >= 1 else parser.error(
                            "The number of slices must be at least 1"),
                        default=4,
                        help="Specify the number of files to be evenly split; must be at least 1, default is 4.")
    parser.add_argument("--max_entries", "-m",
                        required=False,
                        type=int,
                        default=15000,
                        help="Specify the maximum number of events to be dumped in single file, default is 15000.")
    parser.add_argument("--dump_dir", "-o",
                        required=False,
                        type=str,
                        default='',
                        help="Specify the directory to dump snapshot files, default is the snapshot file directory.")
    parser.add_argument("--dump_type", "-t",
                        required=False,
                        type=str,
                        choices=["pkl", "json"],
                        default="pkl",
                        help="Specify output dump file format; must be either 'pkl' or 'json' (default: pkl).")
    args = parser.parse_args()
    # 校验snapshot path
    if (not args.snapshot_file or
            not os.path.exists(args.snapshot_file) or
            not os.path.isfile(args.snapshot_file) or
            not os.access(args.snapshot_file, os.R_OK)):
        raise argparse.ArgumentError("snapshot_file",
                                     "The specified snapshot file does not exist, or is not a file, or is not readable.")
    # 校验dump目标路径
    if not args.dump_dir:
        args.dump_dir = os.path.dirname(args.snapshot_file)
    if (not os.path.exists(args.dump_dir) or
            not os.path.isdir(args.dump_dir) or
            not os.access(args.dump_dir, os.W_OK)):
        raise argparse.ArgumentError("dump_dir",
                                     "The dump directory does not exist, or is not a directory, "
                                     "or is not writable")
    return args


def main():
    args = get_args()
    dump_logger.info(f"Start to dump snapshot slice, reading pickle file '{args.snapshot_file}'.")
    df = pd.read_pickle(args.snapshot_file)
    if 'segments' not in df or 'device_traces' not in df or not df['device_traces']:
        dump_logger.warning("Snapshot files with no event records cannot be replayed or split. You may have disabled "
                            "history event recoding during collection.")
        return
    if len(df['device_traces']) <= args.device or not df['device_traces'][args.device]:
        dump_logger.warning(f"The snapshot file did not record any event data for the specified device {args.device}.")
        return
    dump_logger.info(f"Start loading snapshot with {len(df['segments'])} segments, "
                     f"{len(df['device_traces'][0])} events")
    snapshot = SimulateDeviceSnapshot(df, 0)
    dump_logger.info("Successfully loaded snapshot, starting to replay and dump.")
    slice_dump_hooker = SliceDumpHooker(dump_dir=args.dump_dir,
                                        num_of_slices=args.slices,
                                        max_entries=args.max_entries,
                                        dump_type=args.dump_type)
    snapshot.register_hooker(slice_dump_hooker)
    snapshot.replay()
    dump_logger.info("Successfully replay and dump snapshot.")


if __name__ == '__main__':
    main()
