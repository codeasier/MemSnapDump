[English](../../en/reference/snapshot-db-schema.md)

# SQLite Schema 参考

MemSnapDump 会将回放结果导出为按设备划分的 SQLite 表。

## 表命名规则
对于设备索引 `N`，导出器会创建：
- `trace_entry_N`
- `block_N`

打开数据库时，会自动清理旧版本中不带设备前缀的表。

## `trace_entry_<device>`
该表存储与回放相关的内存事件。

### 字段说明
| 字段 | 含义 |
|---|---|
| `id` | 事件标识 |
| `action` | 编码后的动作类型 |
| `address` | 内存地址 |
| `size` | 事件大小 |
| `stream` | Stream 标识 |
| `allocated` | 导出时刻的总 allocated 字节数 |
| `active` | 导出时刻的总 active 字节数 |
| `reserved` | 导出时刻的总 reserved 字节数 |
| `callstack` | 序列化后的调用栈 |

### 动作映射
| 动作 | 值 |
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
该表存储在回放/导出过程中重建出的 active block 记录。

### 字段说明
| 字段 | 含义 |
|---|---|
| `id` | Block 标识 |
| `address` | Block 地址 |
| `size` | Block 大小 |
| `requestedSize` | 请求分配大小 |
| `state` | 编码后的 block 状态 |
| `allocEventId` | 分配事件标识 |
| `freeEventId` | 释放事件标识 |

### 状态映射
| 状态 | 值 |
|---|---:|
| `inactive` | -1 |
| `active_pending_free` | 0 |
| `active_allocated` | 1 |

## 说明
- 表定义由 `src/memsnapdump/tools/adaptors/database/snapshot_db.py` 中的 `SnapshotDb` 创建。
- 记录由 `event2record()` 与 `block2record()` 生成。
- 多设备 snapshot 会为每个可回放设备生成一组表。
