# 重构变更摘要

## 建议 commit message

```text
refactor(simulate): split replay, range ops, and snapshot mutation responsibilities
```

或：

```text
refactor(simulate): decompose allocator internals into focused modules
```

## PR 标题建议

```text
Refactor simulate module by extracting context, dispatch, range ops, mutators, and replay executor
```

或中文：

```text
重构 simulate 模块：拆分上下文、hook 分发、区间操作、状态修改与 replay 执行
```

## PR 描述摘要

### 背景

这次重构聚焦 `simulate` 模块内部职责过于集中的问题。此前 `SimulatedCachingAllocator` 同时承担了：

- allocator hook 分发
- segment/block 的区间查找与变换
- snapshot 统计字段更新
- replay 单事件语义映射

这使得代码难以测试、难以维护，也增加了后续演进成本。

### 本次改动

本次重构将上述职责拆分为更清晰的模块边界：

- 新增 `simulate/allocator_context.py`
  - 承载 `AllocatorContext`
- 新增 `simulate/allocator_hook_dispatcher.py`
  - 统一管理 allocator hook 注册、注销与 pre/post 分发
- 新增 `simulate/range_ops.py`
  - 抽离 segment/block 的地址查找、插入、切分、收缩、合并等区间操作
- 新增 `simulate/snapshot_mutator.py`
  - 统一维护 block/segment 插入删除、引用绑定与 snapshot 统计量更新
- 新增 `simulate/replay_executor.py`
  - 抽离 replay 单事件执行语义，承载 `action -> allocator` 映射
- 修改 `simulate/simulated_caching_allocator.py`
  - 收敛为高层回放语义编排器
- 修改 `simulate/simulate.py`
  - `replay()` 委托 `ReplayExecutor` 执行单事件
- 新增测试：
  - `ut/simulate/test_range_ops.py`
  - `ut/simulate/test_snapshot_mutator.py`
  - `ut/simulate/test_replay_executor.py`

### 保持不变

- `SimulateDeviceSnapshot` 仍是对外 replay 入口
- `register_hooker()` / `register_allocator_hooker()` / `replay()` 外部调用方式保持兼容
- workspace 容忍逻辑保持不变
- 虚拟内存场景下的 split / shrink / merge 行为保持不变
- 未识别 action 仍然 warning 并跳过

### 测试

已通过以下回归验证：

```bash
source "/Users/test1/liuyekang/miniconda3/etc/profile.d/conda.sh" && conda activate pt-snap
python "/Users/test1/liuyekang/dev/code/MemSnapDump/ut/simulate/test.py"
python -m unittest discover -s ut/simulate -p "test_*.py"
```

结果：
- `ut/simulate` 共 24 个测试通过

### 重构收益

- 降低 `SimulatedCachingAllocator` 的职责密度
- 将底层区间算法、状态修改、事件执行语义解耦
- 增强可测试性与回归保护
- 为后续继续细化 replay / allocator 逻辑提供稳定边界
