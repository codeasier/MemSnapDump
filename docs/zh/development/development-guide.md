[English](../../en/development/development-guide.md)

# 开发指南

## 本地环境准备

```bash
python -m pip install -e .[dev]
```

## 质量检查

```bash
ruff check .
black --check .
pytest --cov=memsnapdump --cov-fail-under=85
```

自动修复格式化 / lint 问题：

```bash
ruff check . --fix
black .
```

## CI
GitHub workflow 会执行：
- `ruff check .`
- `black --check .`
- `pytest --cov=memsnapdump --cov-fail-under=85`

覆盖 Python 版本：
- 3.10
- 3.11
- 3.12

## 仓库结构
```text
MemSnapDump/
├── src/memsnapdump/
│   ├── base/        # snapshot 实体定义
│   ├── simulate/    # 回放与 allocator 模拟逻辑
│   ├── tools/       # CLI 入口与工具实现
│   └── util/        # logger、file、timer、sqlite 辅助模块
├── tests/           # 单元测试与测试数据
├── docs/            # 用户文档、参考文档与项目说明
├── pyproject.toml   # 打包与工具配置
└── README.md        # 英文首页
```

## 对贡献者的建议
- 用户文档尽量同步更新 `docs/en` 与 `docs/zh`。
- 保持 `README.md` 与 `README.zh.md` 简洁，以导航为主。
- 更深入的操作说明优先放在 `docs/` 下，而不是继续扩展根目录 README。
