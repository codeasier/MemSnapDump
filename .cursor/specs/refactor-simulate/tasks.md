# Tasks

- [x] Task 1: 建立重构保护网
  - [x] SubTask 1.1: 审视现有 `ut/simulate/test_simulate.py` 的覆盖范围，标记当前只覆盖全链路 replay 的部分
  - [x] SubTask 1.2: 新增 `ut/simulate/test_range_ops.py`，覆盖 `find_block_by_addr`、`find_gap_for_alloc_block`、`insert_segment_sorted`
  - [x] SubTask 1.3: 在 `ut/simulate/test_range_ops.py` 中补充 `merge_segments`、`split_segment_at`、`shrink_segment` 的正常与边界路径
  - [x] SubTask 1.4: 新增 `ut/simulate/test_snapshot_mutator.py`，覆盖 block/segment 状态变更后的统计量一致性
  - [x] SubTask 1.5: 新增 workspace 容忍场景与虚拟内存场景的专项断言，确保重构前后行为不变

- [x] Task 2: 抽离共享上下文与 allocator hook 分发
  - [x] SubTask 2.1: 新增 `simulate/allocator_context.py`，迁移 `AllocatorContext` 定义
  - [x] SubTask 2.2: 新增 `simulate/allocator_hook_dispatcher.py`，封装 hook 注册、注销与 pre/post 分发逻辑
  - [x] SubTask 2.3: 修改 `simulate/simulated_caching_allocator.py`，将内部 hookers 容器访问替换为 dispatcher 调用
  - [x] SubTask 2.4: 修改 `simulate/simulate.py`，更新对 `AllocatorContext` 的引用路径并保持外部接口不变
  - [x] SubTask 2.5: 验证 allocator hook 的调用顺序、时机与当前实现一致

- [x] Task 3: 抽离已排序区间数组操作能力
  - [x] SubTask 3.1: 新增 `simulate/range_ops.py`，承载 segment/block 的地址查找能力
  - [x] SubTask 3.2: 迁移 `find_segment_by_exact_addr`、`find_block_by_addr`、`find_gap_for_alloc_block`
  - [x] SubTask 3.3: 迁移 `insert_segment_sorted`、`merge_segments`、`split_segment_at`、`shrink_segment`
  - [x] SubTask 3.4: 梳理区间工具的输入输出与失败约定，避免直接耦合 hook 和 replay 语义
  - [x] SubTask 3.5: 修改 `simulate/simulated_caching_allocator.py` 以通过 `range_ops` 执行相关操作

- [x] Task 4: 收敛 snapshot 状态修改入口
  - [x] SubTask 4.1: 新增 `simulate/snapshot_mutator.py`，统一维护 block 与 segment 的插入、删除、状态变更
  - [x] SubTask 4.2: 将 `segment.active_size`、`segment.allocated_size`、`snapshot.total_activated`、`snapshot.total_allocated` 的更新迁移到 mutator
  - [x] SubTask 4.3: 将 `snapshot.total_reserved` 的更新迁移到 mutator
  - [x] SubTask 4.4: 统一处理 `block.segment_ptr` 的绑定与解绑逻辑
  - [x] SubTask 4.5: 修改 allocator 业务方法，移除散落的字段直接写入代码

- [x] Task 5: 解耦 replay 主流程与事件执行语义
  - [x] SubTask 5.1: 新增 `simulate/replay_executor.py`，承载 action -> allocator 动作映射
  - [x] SubTask 5.2: 将 `SimulateDeviceSnapshot._replay_single_event()` 迁移为 executor 的独立实现
  - [x] SubTask 5.3: 修改 `simulate/simulate.py`，让 `replay()` 调用 executor 执行单事件
  - [x] SubTask 5.4: 为 replay executor 新增单元测试，覆盖已支持 action 与未知 action 的处理
  - [x] SubTask 5.5: 验证 replay 主流程仍保持原有日志、hook 与事件 pop 时序

- [x] Task 6: 收尾整理与兼容性确认
  - [x] SubTask 6.1: 检查 `simulate/__init__.py` 是否需要补充新的导出或保持现状
  - [x] SubTask 6.2: 审查 `SimulatedCachingAllocator` 是否已退化为高层语义编排器
  - [x] SubTask 6.3: 清理迁移后遗留的重复逻辑与废弃私有方法
  - [x] SubTask 6.4: 运行 `ut/simulate` 相关测试并确认全绿
  - [x] SubTask 6.5: 对照 spec 与 checklist 完成最终自检与评审准备

# Task Dependencies
- [Task 2] depends on [Task 1]
- [Task 3] depends on [Task 1, Task 2]
- [Task 4] depends on [Task 1, Task 3]
- [Task 5] depends on [Task 1, Task 2, Task 4]
- [Task 6] depends on [Task 2, Task 3, Task 4, Task 5]
