import sqlite3
from pathlib import Path
from typing import Optional

import pytest

from memsnapdump.util.sqlite_meta import (
    SqliteColumn,
    SqliteDB,
    SqliteTable,
    _map_py_type_to_sqlite,
    _parse_default_value,
    _sqlite_type_to_py_type,
)


def test_type_mapping_helpers_cover_supported_and_fallback_types():
    assert _map_py_type_to_sqlite(int) == "INTEGER"
    assert _map_py_type_to_sqlite(float) == "REAL"
    assert _map_py_type_to_sqlite(str) == "TEXT"
    assert _map_py_type_to_sqlite(bytes) == "BLOB"
    assert _map_py_type_to_sqlite(Optional[int]) == "INTEGER"
    assert _map_py_type_to_sqlite(list) == "TEXT"

    assert _sqlite_type_to_py_type("INTEGER") is int
    assert _sqlite_type_to_py_type("TEXT") is str
    assert _sqlite_type_to_py_type("BLOB") is bytes
    assert _sqlite_type_to_py_type("REAL") is float
    assert _sqlite_type_to_py_type("") is str
    assert _sqlite_type_to_py_type("NUMERIC") is str


def test_parse_default_value_handles_literals_bool_and_strings():
    assert _parse_default_value(None) is None
    assert _parse_default_value("1") is True
    assert _parse_default_value("0") is False
    assert _parse_default_value("true") is True
    assert _parse_default_value("false") is False
    assert _parse_default_value("123") == 123
    assert _parse_default_value("'hello'") == "hello"
    assert _parse_default_value('"world"') == "world"
    assert _parse_default_value("CURRENT_TIMESTAMP") == "CURRENT_TIMESTAMP"


def test_sqlite_column_validation_and_sql_generation():
    with pytest.raises(ValueError):
        SqliteColumn("id", int, autoincrement=True)

    with pytest.raises(ValueError):
        SqliteColumn("id", str, primary_key=True, autoincrement=True)

    col = SqliteColumn(
        "name",
        str,
        not_null=True,
        unique=True,
        default="O'Reilly",
    )
    sql = col.to_sql_def()
    assert "`name` TEXT" in sql
    assert "NOT NULL" in sql
    assert "UNIQUE" in sql
    assert "DEFAULT 'O''Reilly'" in sql

    assert SqliteColumn("flag", bool, default=True)._format_default() == "1"
    assert SqliteColumn("score", float, default=1.5)._format_default() == "1.5"
    assert SqliteColumn("misc", dict, default={"a": 1})._format_default() == "'{\'a\': 1}'"


def test_sqlite_table_helpers_create_insert_and_index(tmp_path: Path):
    db_path = tmp_path / "table.sqlite"
    conn = sqlite3.connect(db_path)
    table = SqliteTable(
        "users",
        [
            SqliteColumn("id", int, primary_key=True),
            SqliteColumn("name", str, not_null=True),
            SqliteColumn("active", bool, default=False, value_map={True: 1, False: 0}),
        ],
    )

    sql = table.to_sql_def(delete_if_exists=True)
    assert "DROP TABLE IF EXISTS users;" in sql
    assert "CREATE TABLE users" in sql

    table.create_table(conn, delete_if_exists=True)
    table.create_index(conn, "name")
    table.insert_record(conn, {"id": 1, "name": "Alice", "active": True})
    table.insert_records(
        conn,
        [
            {"id": 2, "name": "Bob", "active": False},
            {"id": 3, "name": "Cara", "active": True},
        ],
    )

    rows = conn.execute("SELECT id, name, active FROM users ORDER BY id").fetchall()
    assert rows == [(1, "Alice", 1), (2, "Bob", 0), (3, "Cara", 1)]

    assert SqliteTable.get_insert_columns_by_record({"a": 1, "b": 2}) == ["`a`", "`b`"]
    assert SqliteTable.get_insert_placeholder_by_record({"a": 1, "b": 2}) == "?, ?"
    assert table.get_insert_values_by_records([
        {"id": 4, "name": "Dan", "active": True},
        {"id": 5, "name": "Eve", "active": False},
    ]) == [(4, "Dan", 1), (5, "Eve", 0)]
    assert table.get_insert_values_by_records([]) == []

    conn.close()


def test_sqlite_db_create_get_delete_and_dictionary_table(tmp_path: Path):
    db = SqliteDB(str(tmp_path / "meta.sqlite"), with_dictionary_table=True)

    assert db.is_table_exists("dictionary") is True
    dictionary = db.get_table_by_name("dictionary")
    assert dictionary.name == "dictionary"

    table = SqliteTable(
        "events",
        [
            SqliteColumn("id", int, primary_key=True, autoincrement=True),
            SqliteColumn("status", str, default="new", value_map={"ALLOC": "alloc"}),
            SqliteColumn("enabled", bool, default=True),
        ],
    )
    db.create_table(table, delete_if_exists=True)

    assert db.is_table_exists("events") is True

    restored = db.get_table_by_name("events")
    assert restored.name == "events"
    assert restored.column_dict["id"].primary_key is True
    assert restored.column_dict["id"].autoincrement is True
    assert restored.column_dict["status"].default == "new"
    assert restored.column_dict["enabled"].default is True

    dict_rows = db.conn.execute(
        "SELECT `table`, `column`, `key`, `value` FROM dictionary ORDER BY rowid"
    ).fetchall()
    assert ("events", "status", "alloc", "ALLOC") in dict_rows

    db.delete_table("events")
    exists_in_db = db.conn.execute(
        "SELECT name FROM sqlite_master WHERE type='table' AND name='events'"
    ).fetchone()
    assert exists_in_db is None
    db.conn.close()


def test_sqlite_db_missing_file_without_auto_create_raises(tmp_path: Path):
    missing = tmp_path / "missing" / "db.sqlite"
    with pytest.raises(FileNotFoundError):
        SqliteDB(str(missing), auto_create=False)


def test_get_table_by_name_raises_for_missing_table(tmp_path: Path):
    db = SqliteDB(str(tmp_path / "empty.sqlite"))
    with pytest.raises(ValueError):
        db.get_table_by_name("missing_table")
    db.conn.close()
