# util 模块 Agent 指南

## 模块职责

`util` 模块提供通用工具函数和辅助类，包括日志、计时、文件操作和 SQLite 封装。

## 文件说明

### logger.py
日志记录器工厂函数。

```python
def get_logger(name: str, level: int = logging.INFO) -> logging.Logger:
    """
    创建并返回配置好的 Logger 实例。
    
    Args:
        name: logger 名称
        level: 日志级别，默认 INFO
    
    Returns:
        配置好的 Logger 对象
    """
```

**输出格式**:
```
2024-01-01 12:00:00 [ INFO ][ module_name ]: message
```

**使用示例**:
```python
from util import get_logger

logger = get_logger(__name__)
logger.info("Processing started")
logger.error("Failed to process")
```

### timer.py
函数执行时间计时装饰器。

```python
def timer(name: Optional[str] = None, logger: Optional[logging.Logger] = None):
    """
    函数执行时间计时装饰器。
    
    Args:
        name: 计时器名称，默认使用函数名
        logger: 日志记录器，若提供则用 logger.info 输出
    """
```

**使用示例**:
```python
from util import get_logger, timer

logger = get_logger(__name__)

@timer(name="数据处理", logger=logger)
def process_data():
    time.sleep(1)
# 输出: 数据处理 took 1.0012 seconds

@timer()
def simple_func():
    pass
# 输出: simple_func took 0.0001 seconds
```

### file_util.py
文件和目录操作工具函数。

```python
def load_pickle_to_dict(pickle_file: Path) -> dict:
    """加载 pickle 文件为字典"""

def save_dict_to_pickle(data: dict, path: Path, protocol: int = 4) -> None:
    """保存字典为 pickle 文件"""

def check_dir_valid(path: str | Path, need_readable: bool = True, 
                    need_writable: bool = True) -> bool:
    """校验目录是否合法"""

def check_file_valid(path: str | Path, need_readable: bool = True,
                     need_writable: bool = False) -> bool:
    """校验文件是否合法"""
```

**使用示例**:
```python
from util.file_util import load_pickle_to_dict, save_dict_to_pickle, check_dir_valid

# 加载快照
data = load_pickle_to_dict(Path('snapshot.pkl'))

# 保存数据
save_dict_to_pickle(data, Path('output.pkl'))

# 校验目录
if check_dir_valid('/data/output'):
    print("目录可读写")
```

### sqlite_meta.py
SQLite 数据库元数据管理模块，提供表结构定义和操作封装。

## sqlite_meta.py 详解

### SqliteColumn
列定义类。

```python
class SqliteColumn:
    def __init__(
        self,
        name: str,
        data_type: Type = str,
        primary_key: bool = False,
        autoincrement: bool = False,
        not_null: bool = False,
        unique: bool = False,
        default: Optional[Any] = None,
        value_map: Dict[Any, Any] = None
    )
    
    def to_sql_def(self) -> str:
        """生成列的 SQL 定义"""
```

**使用示例**:
```python
from util.sqlite_meta import SqliteColumn

col = SqliteColumn('id', int, primary_key=True, autoincrement=True)
print(col.to_sql_def())
# `id` INTEGER PRIMARY KEY AUTOINCREMENT

col = SqliteColumn('status', str, not_null=True, default='pending')
print(col.to_sql_def())
# `status` TEXT NOT NULL DEFAULT 'pending'
```

### SqliteTable
表定义和管理类。

```python
class SqliteTable:
    def __init__(self, table_name: str, columns: Iterable[SqliteColumn] = None)
    
    def to_sql_def(self, delete_if_exists: bool = False) -> str:
        """生成创建表的 SQL"""
    
    def create_table(self, conn: sqlite3.Connection, delete_if_exists: bool = False):
        """在数据库中创建表"""
    
    def insert_record(self, conn: sqlite3.Connection, record: Dict[str, Any]):
        """插入单条记录"""
    
    def insert_records(self, conn: sqlite3.Connection, records: List[Dict[str, Any]]):
        """批量插入记录"""
```

**使用示例**:
```python
from util.sqlite_meta import SqliteColumn, SqliteTable
import sqlite3

columns = [
    SqliteColumn('id', int, primary_key=True, autoincrement=True),
    SqliteColumn('name', str, not_null=True),
    SqliteColumn('age', int, default=0)
]

table = SqliteTable('users', columns)
conn = sqlite3.connect(':memory:')
table.create_table(conn)

# 插入数据
table.insert_records(conn, [
    {'name': 'Alice', 'age': 30},
    {'name': 'Bob', 'age': 25}
])
```

### SqliteDB
数据库管理类。

```python
class SqliteDB:
    def __init__(self, path: str, auto_create: bool = True, 
                 with_dictionary_table: bool = False)
    
    def create_table(self, table: SqliteTable, delete_if_exists: bool = True):
        """创建表并缓存"""
    
    def is_table_exists(self, table_name: str) -> bool:
        """检查表是否存在"""
    
    def get_table_by_name(self, table_name: str) -> SqliteTable:
        """获取表对象"""
```

**使用示例**:
```python
from util.sqlite_meta import SqliteDB, SqliteTable, SqliteColumn

db = SqliteDB('/path/to/db.sqlite', with_dictionary_table=True)

table = SqliteTable('events', [
    SqliteColumn('id', int, primary_key=True),
    SqliteColumn('type', str, value_map={'alloc': 0, 'free': 1})
])
db.create_table(table)

# 值映射自动存入 dictionary 表
```

## 类型映射

Python 类型到 SQLite 类型的自动映射:
- `int` → `INTEGER`
- `float` → `REAL`
- `str` → `TEXT`
- `bool` → `INTEGER` (0/1)
- `bytes` → `BLOB`
- `Optional[T]` → 自动提取 T 类型

## 注意事项

1. **日志单例**: 同名 logger 会复用，避免重复添加 handler
2. **全局日志文件**: `set_global_log_file()` 可设置全局日志文件，所有 logger 都会输出到该文件
3. **pickle 版本**: 默认使用 protocol=4，兼容 Python 3.4+
4. **字典表**: 启用 `with_dictionary_table` 会自动创建值映射表
5. **表缓存**: SqliteDB 会缓存表结构，避免重复查询
