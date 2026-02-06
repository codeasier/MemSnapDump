from util.sqlite_meta import SqliteColumn, SqliteTable, SqliteDB
from .defs import (
    EventFieldDefs,
    BlockFieldDefs
)

_TRACE_ENTRY_TABLE_COLUMNS = [
    SqliteColumn(name=EventFieldDefs.ID, data_type=int, primary_key=True),
    SqliteColumn(name=EventFieldDefs.ACTION),
    SqliteColumn(name=EventFieldDefs.ADDR, data_type=int),
    SqliteColumn(name=EventFieldDefs.SIZE, data_type=int),
    SqliteColumn(name=EventFieldDefs.STREAM, data_type=int),
    SqliteColumn(name=EventFieldDefs.ALLOCATED, data_type=int),
    SqliteColumn(name=EventFieldDefs.ACTIVE, data_type=int),
    SqliteColumn(name=EventFieldDefs.RESERVED, data_type=int),
    SqliteColumn(name=EventFieldDefs.CALLSTACK)
]

_BLOCK_TABLE_COLUMNS = [
    SqliteColumn(name=BlockFieldDefs.ID, data_type=int, primary_key=True),
    SqliteColumn(name=BlockFieldDefs.ADDR, data_type=int),
    SqliteColumn(name=BlockFieldDefs.SIZE, data_type=int),
    SqliteColumn(name=BlockFieldDefs.REQUESTED_SIZE, data_type=int),
    SqliteColumn(name=BlockFieldDefs.STATE, default="null"),
    SqliteColumn(name=BlockFieldDefs.ALLOC_EVENT_ID, data_type=int),
    SqliteColumn(name=BlockFieldDefs.FREE_EVENT_ID, data_type=int),
]


class SnapshotDb(SqliteDB):
    TRACE_ENTRY_TABLE_NAME = "trace_entry"
    BLOCK_TABLE_NAME = "block"

    def __init__(self, path: str):
        super().__init__(path, auto_create=True)
        self.create_block_table()
        self.create_trace_entry_table()

    def create_trace_entry_table(self):
        self.create_table(SqliteTable(SnapshotDb.TRACE_ENTRY_TABLE_NAME, _TRACE_ENTRY_TABLE_COLUMNS),
                          delete_if_exists=True)

    def create_block_table(self):
        self.create_table(SqliteTable(SnapshotDb.BLOCK_TABLE_NAME, _BLOCK_TABLE_COLUMNS),
                          delete_if_exists=True)

    def get_trace_entry_table(self):
        return self.get_table_by_name(SnapshotDb.TRACE_ENTRY_TABLE_NAME)

    def get_block_table(self):
        return self.get_table_by_name(SnapshotDb.BLOCK_TABLE_NAME)
