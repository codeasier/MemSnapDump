import os.path
import sqlite3
from typing import Any, Dict, List, Optional, Type, Union, Iterable, get_origin, get_args

# 支持的 Python 类型映射
_PY_TYPE_TO_SQLITE = {
    int: "INTEGER",
    float: "REAL",
    str: "TEXT",
    bool: "INTEGER",  # SQLite 没有 BOOLEAN，用 0/1
    bytes: "BLOB",
}


def _map_py_type_to_sqlite(py_type: Type) -> str:
    """将 Python 类型转换为 SQLite 类型"""
    origin = get_origin(py_type) or py_type
    if origin in _PY_TYPE_TO_SQLITE:
        return _PY_TYPE_TO_SQLITE[origin]
    # 处理 Optional[T] => T（Optional 是 Union[T, None]）
    if origin is Union:
        args = get_args(py_type)
        non_none = [t for t in args if t is not type(None)]
        if len(non_none) == 1:
            return _map_py_type_to_sqlite(non_none[0])
    # 默认 fallback
    return "TEXT"


def _sqlite_type_to_py_type(sqlite_type: str) -> type:
    """将 SQLite 声明类型映射为最可能的 Python 类型"""
    if not sqlite_type:
        return str  # 无类型默认为 TEXT
    upper = sqlite_type.upper()
    if "INT" in upper:
        return int
    if "CHAR" in upper or "CLOB" in upper or "TEXT" in upper:
        return str
    if "BLOB" in upper:
        return bytes
    if "REAL" in upper or "FLOA" in upper or "DOUB" in upper:
        return float
    # 兜底：可能是 NUMERIC 或自定义类型，按 TEXT 处理
    return str


import ast


def _parse_default_value(dflt_str: str) -> Any:
    """将 PRAGMA 返回的默认值字符串转为 Python 对象"""
    if dflt_str is None:
        return None

    # 尝试解析为字面量（支持数字、字符串、布尔、None）
    try:
        # 处理 SQLite 中的布尔：'1'/'0' 或 'true'/'false'（但 SQLite 实际存整数）
        if dflt_str == '1':
            return True
        elif dflt_str == '0':
            return False
        elif dflt_str.lower() in ('true', 'false'):
            return dflt_str.lower() == 'true'
        # 尝试用 ast.literal_eval 安全解析
        return ast.literal_eval(dflt_str)
    except (ValueError, SyntaxError):
        # 如果不是合法字面量，当作字符串处理（去掉外层引号）
        if dflt_str.startswith("'") and dflt_str.endswith("'"):
            return dflt_str[1:-1].replace("''", "'")
        elif dflt_str.startswith('"') and dflt_str.endswith('"'):
            return dflt_str[1:-1].replace('""', '"')
        else:
            return dflt_str


class SqliteColumn:
    def __init__(
            self,
            name: str,
            data_type: Type = str,
            primary_key: bool = False,  # 是否主键
            autoincrement: bool = False,  # 是否自增
            not_null: bool = False,  # 是否不可为空
            unique: bool = False,  # 是否唯一
            default: Optional[Any] = None,  # 缺省值,
            value_map: Dict[Any, Any] = None,
    ):
        if autoincrement and not primary_key:
            raise ValueError("autoincrement requires primary_key=True")
        if autoincrement and data_type is not int:
            raise ValueError("autoincrement only supported for INTEGER type")
        self.name = name
        self.data_type = data_type
        self.primary_key = primary_key
        self.autoincrement = autoincrement
        self.not_null = not_null
        self.unique = unique
        self.default = default
        self.value_map = value_map

    def _format_default(self) -> str:
        """格式化默认值为 SQL 字面量"""
        val = self.default
        if val is None:
            return "NULL"
        elif isinstance(val, bool):
            return "1" if val else "0"
        elif isinstance(val, str):
            # 转义单引号（简单处理）
            escaped = val.replace("'", "''")
            return f"'{escaped}'"
        elif isinstance(val, (int, float)):
            return str(val)
        else:
            # 兜底：转为字符串并加引号
            return f"'{str(val)}'"

    def to_sql_def(self) -> str:
        parts = [f"`{self.name}`", _map_py_type_to_sqlite(self.data_type)]

        if self.primary_key:
            parts.append("PRIMARY KEY")
        if self.autoincrement:
            parts.append("AUTOINCREMENT")
        if self.not_null:
            parts.append("NOT NULL")
        if self.unique:
            parts.append("UNIQUE")
        if self.default is not None:
            parts.append(f"DEFAULT {self._format_default()}")

        return " ".join(parts)


class SqliteTable:
    name: str
    column_dict: Dict[str, SqliteColumn]
    _column_value_map: Dict[str, Dict[Any, Any]]

    def __init__(self, table_name: str, columns: Iterable[SqliteColumn] = None):
        self.name = table_name
        self.column_dict = {}
        self._column_value_map = dict()
        if columns:
            for column in columns:
                self.column_dict[column.name] = column
                if column.value_map:
                    self._column_value_map[column.name] = column.value_map

    def to_sql_def(self, delete_if_exists: bool = False) -> str:
        """
        生成创建表的 SQL 语句
        :param delete_if_exists: 是否先 DROP TABLE IF EXISTS
        """
        column_defs = [col.to_sql_def() for _, col in self.column_dict.items()]
        create_sql = f"CREATE TABLE {self.name} ({', '.join(column_defs)});"

        if delete_if_exists:
            drop_sql = f"DROP TABLE IF EXISTS {self.name};"
            return f"{drop_sql}\n{create_sql}"
        else:
            # 使用 IF NOT EXISTS 更安全
            create_sql = create_sql.replace("CREATE TABLE", "CREATE TABLE IF NOT EXISTS", 1)
            return create_sql

    def create_table(self, conn: sqlite3.Connection, delete_if_exists: bool = False):
        """
        在数据库中创建表
        :param conn: sqlite3.Connection 对象
        :param delete_if_exists: 是否先删除已存在的表
        """
        sql = self.to_sql_def(delete_if_exists=delete_if_exists)
        conn.executescript(sql)  # 支持多条 SQL（如 DROP + CREATE）
        conn.commit()

    def insert_record(self, conn: sqlite3.Connection, record: Dict[str, Any]):
        """插入单条记录"""
        self.insert_records(conn, [record])

    def insert_records(self, conn: sqlite3.Connection, records: List[Dict[str, Any]]):
        """批量插入多条记录"""
        if not records:
            return
        columns = SqliteTable.get_insert_columns_by_record(records[0])
        placeholders = SqliteTable.get_insert_placeholder_by_record(records[0])
        sql = f"INSERT INTO {self.name} ({', '.join(columns)}) VALUES ({placeholders})"
        values = self.get_insert_values_by_records(records)
        conn.executemany(sql, values)
        conn.commit()

    @staticmethod
    def get_insert_columns_by_record(record: Dict[str, Any]):
        return [f"`{key}`" for key in record.keys()]

    @staticmethod
    def get_insert_placeholder_by_record(record: Dict[str, Any]):
        return ', '.join(['?' for _ in record.keys()])

    def get_insert_values_by_records(self, records: List[Dict[str, Any]]):
        if not records:
            return []
        return [tuple(self._column_value_map.get(k, {}).get(r[k], r[k]) for k in records[0].keys()) for r in records]


class SqliteDB:
    path: str
    conn: sqlite3.Connection
    table_cache: Dict[str, SqliteTable]

    def __init__(self, path: str, auto_create: bool = True, with_dictionary_table: bool = False):
        self.path = os.path.realpath(path)
        if not os.path.exists(self.path):
            if not auto_create:
                raise FileNotFoundError(f"Db file not found: {self.path}.")
            dir_path = os.path.dirname(self.path)
            if not os.path.exists(dir_path):
                os.makedirs(dir_path, exist_ok=True)

        self.conn = sqlite3.connect(self.path)
        self.table_cache = {}
        self.with_dictionary_table = with_dictionary_table
        if self.with_dictionary_table:
            self._create_dictionary_table()

    def create_table(self, table: SqliteTable, delete_if_exists: bool = True):
        table.create_table(self.conn, delete_if_exists)
        self.table_cache[table.name] = table
        if not self.with_dictionary_table:
            return
        dictionary_table = self.get_table_by_name('dictionary')
        for column_name, value_map in table._column_value_map.items():
            for key, value in value_map.items():
                dictionary_table.insert_record(self.conn, dict(
                    table=table.name,
                    column=column_name,
                    key=value,
                    value=key
                ))
        self.conn.commit()

    def _create_dictionary_table(self):
        _table_columns = [
            SqliteColumn(name='table'),
            SqliteColumn(name='column'),
            SqliteColumn(name='key'),
            SqliteColumn(name='value')
        ]
        _dictionary_table = SqliteTable('dictionary', _table_columns)
        _dictionary_table.create_table(self.conn, delete_if_exists=True)
        self.table_cache[_dictionary_table.name] = _dictionary_table

    def is_table_exists(self, table_name: str) -> bool:
        if table_name in self.table_cache:
            return True
        cursor = self.conn.cursor()
        cursor.execute("""
                       SELECT name
                       FROM sqlite_master
                       WHERE type = 'table'
                         AND name = ?
                       """, (table_name,))
        exist = cursor.fetchone() is not None
        if exist:
            self.table_cache[table_name] = self.get_table_by_name(table_name)
        return exist

    def get_table_by_name(self, table_name: str) -> SqliteTable:
        """
            从数据库中读取表结构，还原为 SqliteTable 对象
        """
        if table_name in self.table_cache:
            return self.table_cache[table_name]
        # 获取列信息
        cur = self.conn.execute(f"PRAGMA table_info({table_name});")
        rows = cur.fetchall()

        if not rows:
            raise ValueError(f"Table '{table_name}' does not exist.")
        table = SqliteTable(table_name)
        for row in rows:
            cid, name, type_affinity, notnull, dflt_value, pk = row

            py_type = _sqlite_type_to_py_type(type_affinity)
            default_val = _parse_default_value(dflt_value)

            # 检测是否为自增（仅当 INTEGER 主键且有 sqlite_sequence 记录）
            autoincrement = False
            if pk and py_type is int:
                # 检查是否存在 sqlite_sequence 表且包含该表
                seq_cur = self.conn.execute(
                    "SELECT 1 FROM sqlite_master WHERE type='table' AND name='sqlite_sequence';"
                )
                if seq_cur.fetchone():
                    seq_cur = self.conn.execute(
                        "SELECT 1 FROM sqlite_sequence WHERE name = ?;", (table_name,)
                    )
                    autoincrement = seq_cur.fetchone() is not None

            column = SqliteColumn(
                name=name,
                data_type=py_type,
                primary_key=bool(pk),
                autoincrement=autoincrement,
                not_null=bool(notnull),
                default=default_val,
                # 注意：UNIQUE、COLLATE 无法从 table_info 获取，需解析 CREATE SQL
            )
            table.column_dict[column.name] = column
        self.table_cache[table_name] = table
        return table
