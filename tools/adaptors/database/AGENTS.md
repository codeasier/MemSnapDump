# tools/adaptors/database 模块 Agent 指南

## 模块职责

`database` 子模块定义快照数据库的结构、字段映射和实体转换逻辑。

## 文件说明

### defs.py
数据库字段常量定义。

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

### entity2record.py
实体对象到数据库记录的转换函数。

```python
def event2record(event: TraceEntry, allocated: int, active: int, reserved: int) -> dict
def block2record(block: Block) -> dict
```

### snapshot_db.py
数据库和表结构定义。

## SnapshotDb 类

### 初始化
```python
class SnapshotDb(SqliteDB):
    def __init__(self, path: str):
        # 创建数据库，启用字典表
        super().__init__(path, auto_create=True, with_dictionary_table=True)
        self.create_trace_entry_table()
        self.create_block_table()
```

### 表结构

#### trace_entry 表
| 列名 | 类型 | 约束 | 说明 |
|-----|------|------|------|
| id | INTEGER | PRIMARY KEY | 事件ID |
| action | INTEGER | - | 动作类型（编码值）|
| address | INTEGER | - | 内存地址 |
| size | INTEGER | - | 大小 |
| stream | INTEGER | - | CUDA/CANN 流 |
| allocated | INTEGER | - | 已分配总量 |
| active | INTEGER | - | 活跃总量 |
| reserved | INTEGER | - | 内存池总量 |
| callstack | TEXT | - | 调用栈 |

#### block 表
| 列名 | 类型 | 约束 | 说明 |
|-----|------|------|------|
| id | INTEGER | PRIMARY KEY | 块ID |
| address | INTEGER | - | 地址 |
| size | INTEGER | - | 大小 |
| requestedSize | INTEGER | - | 请求大小 |
| state | INTEGER | DEFAULT 99 | 状态（编码值）|
| allocEventId | INTEGER | - | 分配事件ID |
| freeEventId | INTEGER | - | 释放事件ID |

### 值映射

#### 动作类型编码
```python
TRACE_ENTRY_ACTION_VALUE_MAP = {
    'segment_map': 0,
    'segment_unmap': 1,
    'segment_alloc': 2,
    'segment_free': 3,
    'alloc': 4,
    'free_requested': 5,
    'free_completed': 6,
    'workspace_snapshot': 7
}
```

#### 块状态编码
```python
BLOCK_STATE_VALUE_MAP = {
    'inactive': -1,
    'active_allocated': 1,
    'active_pending_free': 0
}
```

## 使用示例

### 创建数据库
```python
from tools.adaptors.database import SnapshotDb

db = SnapshotDb('/path/to/snapshot.db')
```

### 插入事件（多设备）
```python
from tools.adaptors.database import event2record, block2record

# 插入设备0的事件
db.create_trace_entry_table(device=0)
event_record = event2record(
    event=trace_entry,
    allocated=snapshot.total_allocated,
    active=snapshot.total_activated,
    reserved=snapshot.total_reserved
)
db.get_trace_entry_table(device=0).insert_record(db.conn, event_record)

# 插入设备1的块
db.create_block_table(device=1)
block_record = block2record(block)
db.get_block_table(device=1).insert_record(db.conn, block_record)
```

### 查询数据
```python
import sqlite3

conn = sqlite3.connect('/path/to/snapshot.db')

# 查询设备0的所有分配事件
cursor = conn.execute("SELECT * FROM trace_entry_0 WHERE action = 4")

# 查询设备1的活跃块
cursor = conn.execute("SELECT * FROM block_1 WHERE state = 1")

# 联表查询：设备0的块及其分配事件
cursor = conn.execute("""
    SELECT b.address, b.size, e.callstack
    FROM block_0 b
    JOIN trace_entry_0 e ON b.allocEventId = e.id
    WHERE b.state = 1
""")
```

### 解码值映射
```python
# 从 dictionary 表获取映射
cursor = conn.execute("""
    SELECT * FROM dictionary 
    WHERE `table` = 'trace_entry_0' AND `column` = 'action'
""")
for row in cursor.fetchall():
    print(f"{row['key']} -> {row['value']}")
```

## 注意事项

1. **字典表**: 自动创建 `dictionary` 表存储编码映射
2. **默认值**: block.state 默认值为 99（未知状态）
3. **类型转换**: 字符串值自动转换为整数编码存储
4. **多设备支持**: 每个设备独立建表，表名格式为 `{table_name}_{device}`
5. **旧版本兼容**: `_clear_old_tables()` 自动清理旧版本（不带设备后缀）的表格
6. **None值处理**: entity2record 函数会处理 event.idx 和 block.alloc_event_idx 为 None 的情况
