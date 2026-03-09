# tools/adaptors 模块 Agent 指南

## 模块职责

`adaptors` 模块提供数据适配器，将内存快照数据转换为其他格式（如数据库）。

## 目录结构

```
adaptors/
├── snapshot2db.py     # 快照转数据库核心实现
└── database/          # 数据库相关定义
    ├── defs.py        # 字段定义
    ├── entity2record.py # 实体到记录的转换
    └── snapshot_db.py   # 数据库表结构定义
```

## snapshot2db.py

### 核心类

#### SnapshotDbHandler
数据库写入处理器，管理批量写入缓存。

```python
class SnapshotDbHandler:
    def __init__(self, dump_dir: str, insert_cache_size: int = 1000)
    def insert_event(self, event_record: dict)
    def insert_block(self, block_record: dict)
    def flush()  # 强制刷新缓存
```

**批量写入**: 默认每 1000 条记录提交一次，减少 IO 开销。

#### DumpEventHooker
事件转储钩子，同时继承 `SimulateHooker` 和 `AllocatorHooker`。

```python
class DumpEventHooker(SimulateHooker, AllocatorHooker):
    def post_undo_event(self, event, snapshot) -> bool:
        """每个事件回放后写入数据库"""
        self.db_handler.insert_event(event2record(event, ...))
        
    def post_replay_free_block(self, block, snapshot):
        """块释放后写入数据库"""
        self.db_handler.insert_block(block2record(block))
```

### 主函数
```python
def dump(pickle_file: str, dump_file: str) -> bool:
    """将 pickle 文件转换为数据库"""
    data = load_pickle_to_dict(Path(pickle_file))
    snapshot = SimulateDeviceSnapshot(data, 0)
    hooker = DumpEventHooker(dump_file)
    snapshot.register_hooker(hooker)
    snapshot.register_allocator_hooker(hooker)
    return snapshot.replay()
```

## database 子模块

### defs.py - 字段定义
```python
class EventFieldDefs:
    ID = "id"
    ACTION = "action"
    ADDR = "address"
    SIZE = "size"
    STREAM = "stream"
    ALLOCATED = "allocated"
    ACTIVE = "active"
    RESERVED = "reserved"
    CALLSTACK = "callstack"

class BlockFieldDefs:
    ID = "id"
    ADDR = "address"
    SIZE = "size"
    REQUESTED_SIZE = "requestedSize"
    STATE = "state"
    ALLOC_EVENT_ID = "allocEventId"
    FREE_EVENT_ID = "freeEventId"
```

### entity2record.py - 实体转换
```python
def event2record(event: TraceEntry, allocated: int, active: int, reserved: int) -> dict:
    """将 TraceEntry 转换为数据库记录"""
    return {
        EventFieldDefs.ID: event.idx,
        EventFieldDefs.ACTION: event.action,
        EventFieldDefs.ADDR: event.addr,
        EventFieldDefs.SIZE: event.size,
        EventFieldDefs.STREAM: event.stream,
        EventFieldDefs.ALLOCATED: allocated,
        EventFieldDefs.ACTIVE: active,
        EventFieldDefs.RESERVED: reserved,
        EventFieldDefs.CALLSTACK: event.get_callstack()
    }

def block2record(block: Block) -> dict:
    """将 Block 转换为数据库记录"""
    return {
        BlockFieldDefs.ID: block.alloc_event_idx,
        BlockFieldDefs.ADDR: block.address,
        BlockFieldDefs.SIZE: block.size,
        BlockFieldDefs.REQUESTED_SIZE: block.requested_size,
        BlockFieldDefs.STATE: block.state,
        BlockFieldDefs.ALLOC_EVENT_ID: block.alloc_event_idx,
        BlockFieldDefs.FREE_EVENT_ID: block.free_event_idx
    }
```

### snapshot_db.py - 数据库定义
```python
class SnapshotDb(SqliteDB):
    TRACE_ENTRY_TABLE_NAME = "trace_entry"
    BLOCK_TABLE_NAME = "block"
    
    def __init__(self, path: str):
        super().__init__(path, auto_create=True, with_dictionary_table=True)
        self.create_block_table()
        self.create_trace_entry_table()
```

**值映射表**:
```python
TRACE_ENTRY_ACTION_VALUE_MAP = {
    'segment_map': 0, 'segment_unmap': 1, 'segment_alloc': 2,
    'segment_free': 3, 'alloc': 4, 'free_requested': 5,
    'free_completed': 6, 'workspace_snapshot': 7
}

BLOCK_STATE_VALUE_MAP = {
    'inactive': -1, 'active_allocated': 1, 'active_pending_free': 0
}
```

## 使用示例

### 命令行
```bash
python tools.dump2db /data/snapshot.pkl -o /output
```

### 编程接口
```python
from tools.adaptors.snapshot2db import dump

dump('/data/snapshot.pkl', '/output/snapshot.pkl.db')
```

### 查询数据库
```python
import sqlite3

conn = sqlite3.connect('/output/snapshot.pkl.db')

# 查询峰值分配
cursor = conn.execute("""
    SELECT id, action, allocated, active, reserved 
    FROM trace_entry 
    ORDER BY allocated DESC LIMIT 10
""")

# 查询大块分配
cursor = conn.execute("""
    SELECT address, size, state 
    FROM block 
    WHERE size > 1048576
""")
```

## 注意事项

1. **字典表**: 数据库自动创建 `dictionary` 表存储值映射
2. **Segment 处理**: Segment 不直接插入 block 表，而是模拟为事件插入
3. **缓存刷新**: 程序结束时自动调用 `flush()` 刷新剩余缓存
