# tools/adaptors 模块 Agent 指南

## 模块职责

`adaptors` 模块提供数据适配器，将内存快照数据转换为其他格式（如数据库）。支持多设备快照处理。

## 目录结构

```
adaptors/
├── snapshot2db.py     # 快照转数据库核心实现（支持多设备）
└── database/          # 数据库相关定义
    ├── defs.py        # 字段定义
    ├── entity2record.py # 实体到记录的转换
    └── snapshot_db.py   # 数据库表结构定义
```

## snapshot2db.py

### 核心类

#### SnapshotDbHandler
数据库写入处理器，管理批量写入缓存，支持多设备。

```python
class SnapshotDbHandler:
    def __init__(self, db_path: str, devices: list[int], insert_cache_size: int = 1000)
    def insert_event(self, event_record: dict, device: int = 0)
    def insert_block(self, block_record: dict, device: int = 0)
    def flush(device: int = 0)  # 强制刷新指定设备的缓存
```

**批量写入**: 默认每 1000 条记录提交一次，减少 IO 开销。每个设备独立缓存。

#### DumpEventHooker
事件转储钩子，同时继承 `SimulateHooker` 和 `AllocatorHooker`。

```python
class DumpEventHooker(SimulateHooker, AllocatorHooker):
    def __init__(self, db_path: str, devices: list[int], dump_cache_size: int = 1000)
    
    def pre_undo_event(self, event, snapshot) -> bool:
        """每个事件回放前写入数据库"""
        self.db_handler.insert_event(event2record(...), snapshot.device)
        
    def post_undo_event(self, event, snapshot) -> bool:
        """回放完毕时dump剩余Segment及block数据"""
        
    def post_replay_free_block(self, block, snapshot):
        """块释放后写入数据库"""
        self.db_handler.insert_block(block2record(block), snapshot.device)
```

### 主函数
```python
def dump(pickle_file: str, dump_file: str, device = None) -> bool:
    """将 pickle 文件转换为数据库
    
    Args:
        pickle_file: 快照文件路径
        dump_file: 数据库输出路径
        device: 指定设备ID，None表示dump所有有事件的设备
    """
    data = load_pickle_to_dict(Path(pickle_file))
    device_traces = data.get("device_traces", [])
    # 当指定device为空时dump所有记录了跟踪事件的device，否则仅dump指定device
    need_dump_devices = [device for device in range(len(device_traces)) if device_traces[device]]
    ...
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
        EventFieldDefs.ID: event.idx if event.idx is not None else next_default_event_id(),
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
        BlockFieldDefs.ID: block.alloc_event_idx if block.alloc_event_idx is not None else next_default_block_id(),
        BlockFieldDefs.ADDR: block.address,
        BlockFieldDefs.SIZE: block.size,
        BlockFieldDefs.REQUESTED_SIZE: block.requested_size,
        BlockFieldDefs.STATE: block.state,
        BlockFieldDefs.ALLOC_EVENT_ID: block.alloc_event_idx if block.alloc_event_idx is not None else -1,
        BlockFieldDefs.FREE_EVENT_ID: block.free_event_idx if block.free_event_idx is not None else -1
    }
```

### snapshot_db.py - 数据库定义
```python
class SnapshotDb(SqliteDB):
    TRACE_ENTRY_TABLE_NAME = "trace_entry"
    BLOCK_TABLE_NAME = "block"
    
    def __init__(self, path: str):
        super().__init__(path, auto_create=True, with_dictionary_table=True)
        self._clear_old_tables()  # 清理旧版本表格
    
    def create_trace_entry_table(self, device: int = 0):
        """创建指定设备的事件表"""
        
    def create_block_table(self, device: int = 0):
        """创建指定设备的块表"""
    
    @staticmethod
    def get_block_table_name_by_device(device: int = 0):
        return f"{SnapshotDb.BLOCK_TABLE_NAME}_{device}"
    
    @staticmethod
    def get_trace_table_name_by_device(device: int = 0):
        return f"{SnapshotDb.TRACE_ENTRY_TABLE_NAME}_{device}"
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
