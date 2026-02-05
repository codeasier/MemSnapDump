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
import json
from dataclasses import dataclass

from .defs import (
    DumpEventFieldDefs,
    PythonTraceEventFieldDefs,
    MemoryBlockFieldDefs,
    MemoryAllocationFieldDefs
)


@dataclass
class MallocFreeEventAttr:
    addr: str
    size: str
    used: str
    total: str
    stream_ptr: str = "N/A"
    owner: str = "PTA"


@dataclass
class MemoryEvent:
    _id: int
    event: str
    event_type: str
    name: str
    timestamp: int
    pid: int
    tid: int
    did: int
    ptr: str
    attr: dict
    callstack_c: str = ""
    callstack_py: str = ""

    def to_dict(self):
        return {
            DumpEventFieldDefs.ID: self._id,
            DumpEventFieldDefs.EVENT: self.event,
            DumpEventFieldDefs.EVENT_TYPE: self.event_type,
            DumpEventFieldDefs.NAME: self.name,
            DumpEventFieldDefs.TIMESTAMP_NS: self.timestamp,
            DumpEventFieldDefs.PID: self.pid,
            DumpEventFieldDefs.TID: self.tid,
            DumpEventFieldDefs.DEVICE_ID: self.did,
            DumpEventFieldDefs.PTR: self.ptr,
            DumpEventFieldDefs.ATTR: json.dumps(self.attr),
            DumpEventFieldDefs.CALLSTACK_C: self.callstack_c,
            DumpEventFieldDefs.CALLSTACK_PYTHON: self.callstack_py
        }


@dataclass
class PythonTraceEvent:
    func_info: str
    start_time_ns: int
    end_time_ns: int
    tid: int
    pid: int

    def to_dict(self):
        return {
            PythonTraceEventFieldDefs.FUNC_INFO: self.func_info,
            PythonTraceEventFieldDefs.START_TIME_NS: self.start_time_ns,
            PythonTraceEventFieldDefs.END_TIME_NS: self.end_time_ns,
            PythonTraceEventFieldDefs.TID: self.tid,
            PythonTraceEventFieldDefs.PID: self.pid
        }


@dataclass
class MemoryBlock:
    block_id: int
    device_id: int
    addr: str
    size: int
    start_time_ns: int
    end_time_ns: int
    event_type: str
    owner: str
    attr: dict
    pid: int
    tid: int
    stream: int

    def to_dict(self):
        return {
            MemoryBlockFieldDefs.ID: self.block_id,
            MemoryBlockFieldDefs.DEVICE_ID: self.device_id,
            MemoryBlockFieldDefs.ADDR: self.addr,
            MemoryBlockFieldDefs.SIZE: self.size,
            MemoryBlockFieldDefs.START_TIME_NS: self.start_time_ns,
            MemoryBlockFieldDefs.END_TIME_NS: self.end_time_ns,
            MemoryBlockFieldDefs.EVENT_TYPE: self.event_type,
            MemoryBlockFieldDefs.OWNER: self.owner,
            MemoryBlockFieldDefs.ATTR: json.dumps(self.attr),
            MemoryBlockFieldDefs.PID: self.pid,
            MemoryBlockFieldDefs.TID: self.tid,
            MemoryBlockFieldDefs.STREAM: self.stream,
        }


@dataclass
class MemoryAllocation:
    alloc_id: int
    timestamp: int
    total_size: int
    device_id: int
    event_type: str
    optimized: int = 0

    def to_dict(self):
        return {
            MemoryAllocationFieldDefs.ID: self.alloc_id,
            MemoryAllocationFieldDefs.TIME_NS: self.timestamp,
            MemoryAllocationFieldDefs.TOTAL_SIZE: self.total_size,
            MemoryAllocationFieldDefs.OPTIMIZED: self.optimized,
            MemoryAllocationFieldDefs.DEVICE_ID: self.device_id,
            MemoryAllocationFieldDefs.EVENT_TYPE: self.event_type
        }
