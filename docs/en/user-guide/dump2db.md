[中文](../../zh/user-guide/dump2db.md)

# Dump-to-Database Guide

This workflow exports snapshot replay data into SQLite tables for structured querying and downstream analysis.

## Use cases
Use DB export when you need to:
- query events and blocks with SQL
- integrate with custom analysis scripts
- prepare structured data for visual tooling or reporting

## Command

```bash
python -m memsnapdump.tools.dump2db [-h] [--dump_dir DUMP_DIR] [--log LOG_FILE] [--device DEVICE] snapshot_file
```

## Arguments
| Argument | Default | Description |
|---|---:|---|
| `snapshot_file` | — | Input snapshot pickle file |
| `--dump_dir`, `-o` | snapshot parent directory | Output directory for the SQLite file |
| `--log`, `-l` | — | Optional log file path |
| `--device`, `-d` | all devices with trace events | Export one device or all replayable devices |

## Example

```bash
python -m memsnapdump.tools.dump2db /data/snapshot.pickle -o /data/output
```

With logging:

```bash
python -m memsnapdump.tools.dump2db /data/snapshot.pickle -o /data/output -l /data/output/dump.log
```

## Output
A SQLite database is produced as:

```text
<dump_dir>/<snapshot_filename>.db
```

## Database contents
The export produces per-device tables for:
- trace entries
- active block records

See: [SQLite schema reference](../reference/snapshot-db-schema.md)
