from typing import Dict, List, Literal, Optional, Any


class Frame:
    filename: str = ""
    line: int = -1
    name: str = ""

    _origin: dict = None  # Readonly

    @classmethod
    def from_dict(cls, frame_dict: dict):
        frame = cls()
        frame.filename = frame_dict["filename"]
        frame.line = frame_dict["line"]
        frame.name = frame_dict["name"]
        frame._origin = frame_dict["origin"]
        return frame

    def to_dict(self):
        return self._origin if self._origin else {
            "filename": self.filename,
            "line": self.line,
            "name": self.name
        }


class TraceEntry:
    # When `torch.npu.memory._record_memory_history()` is enabled,
    # the snapshot will contain TraceEntry objects that record each
    # action the allocator took.
    """
    action: Literal[
        'alloc'  # memory allocated
        'free_requested',  # the allocated received a call to free memory
        'free_completed',  # the memory that was requested to be freed is now
            # able to be used in future allocation calls
        'segment_alloc',  # the caching allocator ask aclrtMalloc for more memory
            # and added it as a segment in its cache
        'segment_free',  # the caching allocator called aclrtFree to return memory
            # to npu possibly trying free up memory to
            # allocate more segments or because empty_caches was called
        'oom',  # the allocator threw an OOM exception. 'size' is
            # the requested number of bytes that did not succeed
        'snapshot'  # the allocator generated a memory snapshot
        # useful to coorelate a previously taken
        # snapshot with this trace
    ]
    """
    action: str = ""
    addr: int = -1  # not present for OOM
    frames: List[Frame] = []
    size: int = -1
    stream: int = -1
    device_free: int = -1  # only present for OOM, the amount of
    # memory npu still reports to be free

    _origin: dict = None  # Readonly

    @classmethod
    def from_dict(cls, trace_dict: dict):
        trace_entry = cls()
        trace_entry.action = trace_dict["action"]
        trace_entry.addr = int(trace_dict["addr"])
        trace_entry.size = int(trace_dict["size"])
        trace_entry.stream = int(trace_dict["stream"])
        trace_entry._origin = trace_dict
        trace_entry.frames = [_trace_dict.to_dict() for _trace_dict in trace_dict.get("frames", [])]
        return trace_entry

    def to_dict(self):
        return self._origin if self._origin else dict(
            action=self.action,
            addr=self.addr,
            size=self.size,
            stream=self.stream,
            frames=[frame.to_dict() for frame in self.frames]
        )


class BlockState:
    ACTIVE_PENDING_FREE = "active_pending_free"
    ACTIVE_ALLOCATED = "active_allocated"
    INACTIVE = "inactive"


class Block:
    # A piece of memory returned from the allocator, or
    # current cached but inactive.
    size: int = -1
    requested_size: int = -1  # size requested during malloc, may be smaller than
    # size due to rounding
    address: int = -1
    state: Literal['active_allocated',  # used by a tensor
    'active_pending_free',  # waiting for another stream to finish using
        # this, then it will become free
    'inactive',] = ""  # free for reuse
    frames: List[Frame]  # stack trace from where the allocation occurred

    # 指向持有该block的segment对象
    segment_ptr: Any = None

    def __init__(self, size: int, requested_size: int, address: int, state=BlockState.INACTIVE, frames=None):
        if frames is None:
            frames = []
        self.size = size
        self.requested_size = requested_size
        self.address = address
        self.state = state
        self.frames = frames

    @classmethod
    def from_dict(cls, block_dict: dict):
        block = cls(
            size=block_dict["size"],
            requested_size=block_dict["requested_size"],
            address=block_dict["address"],
            state=block_dict["state"],
            frames=[frame.to_dict() for frame in block_dict.get("frames", [])]
        )
        return block

    @classmethod
    def build_from_event(cls, event: TraceEntry):
        block = cls(
            size=event.size,
            requested_size=event.size,
            address=event.addr,
            frames=event.frames
        )
        return block

    def to_dict(self):
        return dict(
            size=self.size,
            requested_size=self.requested_size,
            address=self.address,
            state=self.state,
            frames=[frame.to_dict() for frame in self.frames]
        )


class Segment:
    # Segments are memory returned from a aclrtMalloc call.
    # The size of reserved memory is the sum of all Segments.
    # Segments are cached and reused for future allocations.
    # If the reuse is smaller than the segment, the segment
    # is split into more then one Block.
    # empty_cache() frees Segments that are entirely inactive.
    address: int = -1
    total_size: int = -1  # aclrtMalloc'd size of segment
    stream: int = -1
    segment_type: Literal['small', 'large'] = ""  # 'large' (>1MB)
    allocated_size: int = -1  # size of memory in use
    active_size: int = -1  # size of memory in use or in active_awaiting_free state
    blocks: List[Block] = []
    device: int = 0
    frames: List[Frame] = []

    _origin: dict = None  # Readonly
    _block_map: Dict[int, Block] = {}

    @classmethod
    def from_dict(cls, segment_dict: dict):
        segment = cls()
        segment.address = segment_dict["address"]
        segment.total_size = segment_dict["total_size"]
        segment.stream = segment_dict["stream"]
        segment.segment_type = segment_dict["segment_type"]
        segment.allocated_size = segment_dict["allocated_size"]
        segment.active_size = segment_dict["active_size"]
        segment.frames = [Frame.from_dict(_frame) for _frame in segment_dict.get("frames", [])]
        segment.device = segment_dict.get("device", 0)
        segment._origin = segment_dict
        segment.blocks = []
        for block in segment_dict["blocks"]:
            _block = Block.from_dict(block)
            _block.segment_ptr = segment
            segment._block_map[_block.address] = _block
            segment.blocks.append(_block)
        return segment

    @classmethod
    def build_from_event(cls, event: TraceEntry):
        segment = cls()
        segment.address = event.addr
        segment.total_size = event.size
        segment.stream = event.stream
        segment.frames = event.frames
        segment.device = event.device if hasattr(event, 'device') else 0
        # 为回放时模拟创建的segment增加一个模拟block
        segment.blocks = [Block(
            size=segment.total_size,
            requested_size=segment.total_size,
            address=segment.address,
            state=BlockState.INACTIVE
        )]
        segment._block_map[segment.address] = segment.blocks[0]
        return segment

    def to_dict(self):
        return dict(
            address=self.address,
            total_size=self.total_size,
            stream=self.stream,
            segment_type=self.segment_type,
            allocated_size=self.allocated_size,
            active_size=self.active_size,
            device=self.device,
            frames=[frame.to_dict() for frame in self.frames],
            blocks=[block.to_dict() for block in self.blocks]
        )

    def find_block_idx_by_block_addr(self, block_addr: int):
        left = 0
        right = len(self.blocks) - 1
        while left < right:
            mid = (left + right) // 2
            if block_addr < self.blocks[mid].address:
                right = mid - 1
            elif block_addr >= self.blocks[mid].address + self.blocks[mid].size:
                left = mid + 1
            else:
                return mid
        return -1


class DeviceSnapshot:
    segments: List[Segment]
    trace_entries: List[TraceEntry]
    block_map: Dict[int, Block] = {}

    @classmethod
    def from_dict(cls, device_snapshot_dict: dict, device: int = 0):
        segments_dict = device_snapshot_dict["segments"]
        device_trace_list = device_snapshot_dict["trace_entries"][device]
        snapshot = cls()
        snapshot.segments = []
        snapshot.trace_entries = []
        snapshot.block_map = {}
        # 读取dump时内存状态
        for segment_dict in segments_dict:
            _segment = Segment.from_dict(segment_dict)
            snapshot.block_map |= _segment._block_map
        snapshot.segments.sort(key=lambda segment: segment.address)
        # 读取事件序列
        for idx, trace_entry_dict in enumerate(device_trace_list):
            snapshot.trace_entries.append(TraceEntry.from_dict(trace_entry_dict))
        return snapshot

    def to_dict(self):
        return {
            'segments': [segment.to_dict() for segment in self.segments],
            'device_traces': [[trace.to_dict() for trace in self.trace_entries]]
        }

    def find_segment_by_block_addr(self, block_addr: int) -> Optional[Segment]:
        left = 0
        segments = self.segments
        right = len(segments) - 1
        while left <= right:
            mid = (left + right) // 2
            if block_addr < segments[mid].address:
                right = mid - 1
            elif block_addr >= segments[mid].address + segments[mid].total_size:
                left = mid + 1
            else:
                return segments[mid]
        return None
