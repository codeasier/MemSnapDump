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


class Event:
    ALLOC = "MALLOC"
    FREE = "FREE"
    OP_LAUNCH = "OP_LAUNCH"


class EventType:
    PTA = "PTA"


class DumpEventFieldDefs:
    ID = "ID"
    EVENT = "Event"
    EVENT_TYPE = "Event Type"
    NAME = "Name"
    TIMESTAMP_NS = "Timestamp(ns)"
    PID = "Process Id"
    TID = "Thread Id"
    DEVICE_ID = "Device Id"
    PTR = "Ptr"
    ATTR = "Attr"
    CALLSTACK_PYTHON = "Call Stack(Python)"
    CALLSTACK_C = "Call Stack(C)"


class PythonTraceEventFieldDefs:
    FUNC_INFO = "FuncInfo"
    START_TIME_NS = "StartTime(ns)"
    END_TIME_NS = "EndTime(ns)"
    TID = "Thread Id"
    PID = "Process Id"


class MemoryBlockFieldDefs:
    ID = "id"
    DEVICE_ID = "deviceId"
    ADDR = "addr"
    SIZE = "size"
    START_TIME_NS = "startTimestamp"
    END_TIME_NS = "endTimestamp"
    EVENT_TYPE = "eventType"
    OWNER = "owner"
    ATTR = "attr"
    PID = "processId"
    TID = "threadId"
    STREAM = "stream"


class MemoryAllocationFieldDefs:
    ID = "id"
    TIME_NS = "timestamp"
    TOTAL_SIZE = "totalSize"
    OPTIMIZED = "optimized"
    DEVICE_ID = "deviceId"
    EVENT_TYPE = "eventType"
