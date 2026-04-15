import argparse
import os.path
from pathlib import Path

from memsnapdump.util import get_logger
from memsnapdump.util.file_util import (
    load_pickle_to_dict,
    check_file_valid,
    check_dir_valid,
)
from memsnapdump.simulate import SimulateDeviceSnapshot
from .hooker import SliceDumpHooker

dump_logger = get_logger("DUMP")


def get_args():
    parser = argparse.ArgumentParser(
        description="This script is used for memory snapshot output files(typically in "
        "pickle format captured by torch/torch_npu."
    )
    arg_snapshot = parser.add_argument(
        "snapshot_file", type=str, help="Memory snapshot file path."
    )
    parser.add_argument(
        "--device",
        "-d",
        required=False,
        default=0,
        type=lambda x: (
            int(x) if int(x) >= 0 else parser.error("The device id must be at least 0")
        ),
    )
    parser.add_argument(
        "--slices",
        "-s",
        required=False,
        type=lambda x: (
            int(x)
            if int(x) >= 1
            else parser.error("The number of slices must be at least 1")
        ),
        default=4,
        help="Specify the number of files to be evenly split; must be at least 1, default is 4.",
    )
    parser.add_argument(
        "--max_entries",
        "-m",
        required=False,
        type=int,
        default=15000,
        help="Specify the maximum number of events to be dumped in single file, default is 15000.",
    )
    arg_dump_dir = parser.add_argument(
        "--dump_dir",
        "-o",
        required=False,
        type=str,
        default="",
        help="Specify the directory to dump snapshot files, default is the snapshot file directory.",
    )
    parser.add_argument(
        "--dump_type",
        "-t",
        required=False,
        type=str,
        choices=["pkl", "json"],
        default="pkl",
        help="Specify output dump file format; must be either 'pkl' or 'json' (default: pkl).",
    )
    args = parser.parse_args()
    # 校验snapshot path
    if not (args.snapshot_file and check_file_valid(args.snapshot_file)):
        raise argparse.ArgumentError(
            arg_snapshot,
            "The specified snapshot file does not exist, or is not a file, or is not readable.",
        )
    # 校验dump目标路径
    if not args.dump_dir:
        args.dump_dir = os.path.dirname(args.snapshot_file)
    if not check_dir_valid(args.dump_dir):
        raise argparse.ArgumentError(
            arg_dump_dir,
            "The dump directory does not exist, or is not a directory, or is not writable",
        )

    return args


def slice_dump():
    args = get_args()
    dump_logger.info(
        f"Start to dump snapshot slice, reading pickle file '{args.snapshot_file}'."
    )
    df = load_pickle_to_dict(Path(args.snapshot_file))
    if "segments" not in df or "device_traces" not in df or not df["device_traces"]:
        dump_logger.warning(
            "Snapshot files with no event records cannot be replayed or split. You may have disabled "
            "history event recoding during collection."
        )
        return
    if len(df["device_traces"]) <= args.device or not df["device_traces"][args.device]:
        dump_logger.warning(
            f"The snapshot file did not record any event data for the specified device {args.device}."
        )
        return
    dump_logger.info(
        f"Start loading snapshot with {len(df['segments'])} segments, "
        f"{len(df['device_traces'][args.device])} events"
    )
    snapshot = SimulateDeviceSnapshot(df, args.device)
    dump_logger.info("Successfully loaded snapshot, starting to replay and dump.")
    slice_dump_hooker = SliceDumpHooker(
        dump_dir=args.dump_dir,
        num_of_slices=args.slices,
        max_entries=args.max_entries,
        dump_type=args.dump_type,
    )
    snapshot.register_hooker(slice_dump_hooker)
    snapshot.replay()
    dump_logger.info("Successfully replay and dump snapshot.")


if __name__ == "__main__":
    slice_dump()
