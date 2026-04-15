[中文](../../zh/user-guide/split.md)

# Split Guide

Snapshot slicing helps you reduce the working size of a large snapshot while preserving a replay-compatible subset of data.

## Use cases
Use slicing when:
- `memory_viz` becomes slow on a large snapshot
- you want to inspect a smaller event window
- you need multiple smaller artifacts for localized analysis

## Command

```bash
python -m memsnapdump.tools.split [-h] [--device DEVICE] [--slices SLICES] [--max_entries MAX_ENTRIES] [--dump_dir DUMP_DIR] [--dump_type {pkl,json}] snapshot_file
```

## Arguments
| Argument | Default | Description |
|---|---:|---|
| `snapshot_file` | — | Input snapshot pickle file |
| `--dump_dir`, `-o` | snapshot parent directory | Output directory |
| `--device`, `-d` | `0` | Device index selected from `device_traces` |
| `--slices`, `-s` | `4` | Target number of evenly split pieces |
| `--max_entries`, `-m` | `15000` | Upper bound for events in a single slice |
| `--dump_type`, `-t` | `pkl` | Output format: `pkl` or `json` |

## Example

```bash
python -m memsnapdump.tools.split /data/snapshot.pickle --slices 4
```

```bash
python -m memsnapdump.tools.split /data/snapshot.pickle --max_entries 20
```

## Notes
- Slicing depends on the same replay capability described in the replay guide.
- If the selected device has no event history, slicing exits early.
- This feature is implemented in `src/memsnapdump/tools/slice_dump/`.
