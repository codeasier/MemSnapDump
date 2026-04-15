[中文](../../zh/reference/snapshot-db-schema.md)

# SQLite Schema Reference

MemSnapDump exports replay data into per-device SQLite tables.

## Table naming
For each device index `N`, the exporter creates:
- `trace_entry_N`
- `block_N`

Legacy non-device-prefixed tables are cleared automatically when opening the DB.

## `trace_entry_<device>`
This table stores replay-related memory events.

### Columns
| Column | Meaning |
|---|---|
| `id` | Event identifier |
| `action` | Encoded action type |
| `address` | Memory address |
| `size` | Event size |
| `stream` | Stream identifier |
| `allocated` | Total allocated bytes at export time |
| `active` | Total active bytes at export time |
| `reserved` | Total reserved bytes at export time |
| `callstack` | Serialized call stack |

### Action mapping
| Action | Value |
|---|---:|
| `segment_map` | 0 |
| `segment_unmap` | 1 |
| `segment_alloc` | 2 |
| `segment_free` | 3 |
| `alloc` | 4 |
| `free_requested` | 5 |
| `free_completed` | 6 |
| `workspace_snapshot` | 7 |

## `block_<device>`
This table stores active block records reconstructed during replay/export.

### Columns
| Column | Meaning |
|---|---|
| `id` | Block identifier |
| `address` | Block address |
| `size` | Block size |
| `requestedSize` | Requested allocation size |
| `state` | Encoded block state |
| `allocEventId` | Allocation event identifier |
| `freeEventId` | Free event identifier |

### State mapping
| State | Value |
|---|---:|
| `inactive` | -1 |
| `active_pending_free` | 0 |
| `active_allocated` | 1 |

## Notes
- Table definitions are created by `SnapshotDb` in `src/memsnapdump/tools/adaptors/database/snapshot_db.py`.
- Records are generated via `event2record()` and `block2record()`.
- Multi-device snapshots produce one pair of tables per replayable device.
