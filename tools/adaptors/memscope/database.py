"""
-------------------------------------------------------------------------
This file is part of the MindStudio project.
Copyright (c) 2026 Huawei Technologies Co.,Ltd.

MindStudio is licensed under Mulan PSL v2.
You can use this software according to the terms and conditions of the Mulan PSL v2.
You may obtain a copy of Mulan PSL v2 at:

         http://license.coscl.org.cn/MulanPSL2

THIS SOFTWARE IS PROVIDED ON AN "AS IS" BASIS, WITHOUT WARRANTIES OF ANY KIND,
EITHER EXPRESS OR IMPLIED, INCLUDING BUT NOT LIMITED TO NON-INFRINGEMENT,
MERCHANTABILITY OR FIT FOR A PARTICULAR PURPOSE.
See the Mulan PSL v2 for more details.
-------------------------------------------------------------------------
"""
from typing import List

from util.sqlite_meta import SqliteColumn, SqliteTable, SqliteDB
from .defs import (
    DumpEventFieldDefs,
    PythonTraceEventFieldDefs,
    MemoryBlockFieldDefs,
    MemoryAllocationFieldDefs
)

_MEMSCOPE_DUMP_TABLE_COLUMNS: List[SqliteColumn] = [
    SqliteColumn(name=DumpEventFieldDefs.ID, data_type=int, primary_key=True, autoincrement=True),
    SqliteColumn(DumpEventFieldDefs.EVENT),
    SqliteColumn(DumpEventFieldDefs.EVENT_TYPE),
    SqliteColumn(DumpEventFieldDefs.NAME),
    SqliteColumn(DumpEventFieldDefs.TIMESTAMP_NS, data_type=int),
    SqliteColumn(DumpEventFieldDefs.PID, data_type=int),
    SqliteColumn(DumpEventFieldDefs.TID, data_type=int),
    SqliteColumn(DumpEventFieldDefs.DEVICE_ID),
    SqliteColumn(DumpEventFieldDefs.PTR),
    SqliteColumn(DumpEventFieldDefs.ATTR),
    SqliteColumn(DumpEventFieldDefs.CALLSTACK_PYTHON),
    SqliteColumn(DumpEventFieldDefs.CALLSTACK_C)
]

_PYTHON_TRACE_TABLE_COLUMNS: List[SqliteColumn] = [
    SqliteColumn(PythonTraceEventFieldDefs.FUNC_INFO),
    SqliteColumn(PythonTraceEventFieldDefs.START_TIME_NS),
    SqliteColumn(PythonTraceEventFieldDefs.END_TIME_NS),
    SqliteColumn(PythonTraceEventFieldDefs.TID, data_type=int),
    SqliteColumn(PythonTraceEventFieldDefs.PID, data_type=int)
]

_MEMORY_BLOCK_TABLE_COLUMNS: List[SqliteColumn] = [
    SqliteColumn(MemoryBlockFieldDefs.ID, data_type=int, primary_key=True),
    SqliteColumn(MemoryBlockFieldDefs.DEVICE_ID),
    SqliteColumn(MemoryBlockFieldDefs.ADDR),
    SqliteColumn(MemoryBlockFieldDefs.SIZE, data_type=int),
    SqliteColumn(MemoryBlockFieldDefs.START_TIME_NS, data_type=int),
    SqliteColumn(MemoryBlockFieldDefs.END_TIME_NS, data_type=int),
    SqliteColumn(MemoryBlockFieldDefs.EVENT_TYPE),
    SqliteColumn(MemoryBlockFieldDefs.OWNER),
    SqliteColumn(MemoryBlockFieldDefs.ATTR),
    SqliteColumn(MemoryBlockFieldDefs.PID, data_type=int),
    SqliteColumn(MemoryBlockFieldDefs.TID, data_type=int),
    SqliteColumn(MemoryBlockFieldDefs.STREAM, data_type=int)
]

_MEMORY_ALLOCATION_TABLE_COLUMNS: List[SqliteColumn] = [
    SqliteColumn(MemoryAllocationFieldDefs.ID, data_type=int, primary_key=True),
    SqliteColumn(MemoryAllocationFieldDefs.TIME_NS, data_type=int),
    SqliteColumn(MemoryAllocationFieldDefs.TOTAL_SIZE, data_type=int),
    SqliteColumn(MemoryAllocationFieldDefs.OPTIMIZED, data_type=int),
    SqliteColumn(MemoryAllocationFieldDefs.DEVICE_ID),
    SqliteColumn(MemoryAllocationFieldDefs.EVENT_TYPE)
]


class MemScopeDb(SqliteDB):
    DUMP_TABLE_NAME = "leaks_dump"
    MEMORY_BLOCK_TABLE_NAME = "memory_block"
    MEMORY_ALLOC_TABLE_NAME = "memory_allocation"
    PYTHON_TRACE_TABLE_NAME_PREFIX = "python_trace"

    def __init__(self, path: str):
        super().__init__(path, auto_create=True)
        self.create_dump_table()
        self.create_allocation_table()
        self.create_memory_block_table()

    def create_dump_table(self):
        self.create_table(SqliteTable(MemScopeDb.DUMP_TABLE_NAME, _MEMSCOPE_DUMP_TABLE_COLUMNS),
                          delete_if_exists=True)

    def create_memory_block_table(self):
        self.create_table(SqliteTable(MemScopeDb.MEMORY_BLOCK_TABLE_NAME, _MEMORY_BLOCK_TABLE_COLUMNS),
                          delete_if_exists=True)

    def create_allocation_table(self):
        self.create_table(SqliteTable(MemScopeDb.MEMORY_ALLOC_TABLE_NAME, _MEMORY_ALLOCATION_TABLE_COLUMNS),
                          delete_if_exists=True)

    def create_python_trace_table(self, pid: int):
        self.create_table(SqliteTable(MemScopeDb.get_python_trace_table_name(pid), _PYTHON_TRACE_TABLE_COLUMNS),
                          delete_if_exists=True)

    def get_dump_table(self):
        return self.get_table_by_name(MemScopeDb.DUMP_TABLE_NAME)

    def get_allocation_table(self):
        return self.get_table_by_name(MemScopeDb.MEMORY_ALLOC_TABLE_NAME)

    def get_memory_block_table(self):
        return self.get_table_by_name(MemScopeDb.MEMORY_BLOCK_TABLE_NAME)

    def get_python_trace_table(self, pid: int):
        python_trace_table_name = MemScopeDb.get_python_trace_table_name(pid)
        if not self.is_table_exists(python_trace_table_name):
            self.create_python_trace_table(pid)
        return self.get_table_by_name(python_trace_table_name)

    @classmethod
    def get_python_trace_table_name(cls, pid: int):
        return f"{cls.PYTHON_TRACE_TABLE_NAME_PREFIX}_{pid}"
