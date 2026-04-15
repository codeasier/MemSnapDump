[English](../../en/user-guide/split.md)

# 快照切片说明

快照切片可以在保持回放兼容性的前提下，缩小大型 snapshot 的工作数据规模。

## 适用场景
当出现以下情况时可以使用切片：
- 大型 snapshot 导致 `memory_viz` 使用迟缓
- 你只想分析较小的一段事件窗口
- 你需要多个更小的产物用于局部分析

## 命令

```bash
python -m memsnapdump.tools.split [-h] [--device DEVICE] [--slices SLICES] [--max_entries MAX_ENTRIES] [--dump_dir DUMP_DIR] [--dump_type {pkl,json}] snapshot_file
```

## 参数说明
| 参数 | 默认值 | 说明 |
|---|---:|---|
| `snapshot_file` | — | 输入的 snapshot pickle 文件 |
| `--dump_dir`, `-o` | snapshot 父目录 | 输出目录 |
| `--device`, `-d` | `0` | 从 `device_traces` 中选择的设备索引 |
| `--slices`, `-s` | `4` | 期望平均切分出的片段数量 |
| `--max_entries`, `-m` | `15000` | 单个切片允许包含的最大事件数 |
| `--dump_type`, `-t` | `pkl` | 输出格式：`pkl` 或 `json` |

## 示例

```bash
python -m memsnapdump.tools.split /data/snapshot.pickle --slices 4
```

```bash
python -m memsnapdump.tools.split /data/snapshot.pickle --max_entries 20
```

## 说明
- 切片功能依赖于回放能力，具体可参见回放文档。
- 如果所选设备没有历史事件，切片会提前退出。
- 该功能的实现位于 `src/memsnapdump/tools/slice_dump/`。
