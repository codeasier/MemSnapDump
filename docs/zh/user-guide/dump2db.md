[English](../../en/user-guide/dump2db.md)

# 快照转数据库说明

该流程会将基于回放得到的 snapshot 数据导出为 SQLite 表，以支持结构化查询和后续分析。

## 适用场景
当你需要以下能力时，应使用数据库导出：
- 使用 SQL 查询事件与 block 数据
- 接入自定义分析脚本
- 为可视化或报告准备结构化数据

## 命令

```bash
python -m memsnapdump.tools.dump2db [-h] [--dump_dir DUMP_DIR] [--log LOG_FILE] [--device DEVICE] snapshot_file
```

## 参数说明
| 参数 | 默认值 | 说明 |
|---|---:|---|
| `snapshot_file` | — | 输入的 snapshot pickle 文件 |
| `--dump_dir`, `-o` | snapshot 父目录 | SQLite 文件输出目录 |
| `--log`, `-l` | — | 可选的日志文件路径 |
| `--device`, `-d` | 所有含 trace event 的设备 | 导出单个设备或所有可回放设备 |

## 示例

```bash
python -m memsnapdump.tools.dump2db /data/snapshot.pickle -o /data/output
```

带日志输出：

```bash
python -m memsnapdump.tools.dump2db /data/snapshot.pickle -o /data/output -l /data/output/dump.log
```

## 输出结果
会生成如下 SQLite 数据库文件：

```text
<dump_dir>/<snapshot_filename>.db
```

## 数据库内容
导出结果会按设备生成以下表：
- trace entry 表
- active block 表

参见：[SQLite Schema 参考](../reference/snapshot-db-schema.md)
