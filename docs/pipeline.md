# 构建流水线

## 模块职责

| 模块 | 职责 |
| --- | --- |
| `scripts/recipes` | 严格解析 TOML、选择受影响包、解析手动选择 |
| `scripts/pipeline/model.py` | 固定源码、构建目标、构建器枚举与计划 |
| `scripts/pipeline/planning.py` | 把 Actions 事件转成完整目标矩阵 |
| `scripts/pipeline/source.py` | 解析上游 SHA、读取明确目录的后端、校验实际 checkout |
| `scripts/pipeline/cargo_env.py` | 组合 cibuildwheel 所需的 Cargo 环境配置，保留已有配置 |
| `scripts/build` | Android 运行库、maturin/Chaquopy 构建与 wheel 修复 |
| `scripts/pipeline/artifacts.py` | 记录并核验完整产物集合、来源与文件哈希 |
| `scripts/pipeline/wheel.py` | 核验 wheel 文件名、WHEEL 标签和全部 RECORD 条目 |
| `scripts/pipeline/notifications.py` | 根据下游实际发布状态发出可重试的同步事件 |
| `scripts/tooling.py` | 从项目配置读取固定工具版本并生成依赖清单 |
| `scripts/pipeline/publish.py` | 将完整构建汇总为一个 Git 提交 |
| `scripts/index` | 批量读取 Git 元数据，生成确定的 HTML 索引 |

模块通过明确的数据和文件交互，不提供任意 Shell hook、自定义参数或源码补丁入口。

## Actions 职责

主仓库保留五个工作流：recipe 入口、单目标 Android 构建器、临时仓库入口、索引部署、统一 CI。两个构建入口共享源码准备与发布 composite action。

构建计划记录在 `build-plan` artifact 内的 `build-plan.json`，源码 ref 在规划时解析为完整 SHA。不同 Python 和 ABI 使用同一个固定源码提交，构建器在编译前重新校验 checkout。临时仓库入口未填写 ref 时，显式读取上游默认分支后固定其提交。

每个目标使用独立 runner 编译。后端与 Python 版本决定 maturin、cibuildwheel 或 Chaquopy 路由，不改变原有交叉编译能力。驱动 Python 与目标 Python 分开设置。

所有目标成功后才进入汇总发布。发布会验证每个预期 artifact，缺少产物、源码错配、哈希不符、目标标签错误、同名内容冲突都会失败。校验通过后以一个提交更新 `wheels`，保留已有文件。不同工作流运行并发提交时，仅在远端确实前进后重新组合提交，最多三次；网络或权限失败直接报告。

`publication=build` 不进入发布。完整产物与远端相同时不创建新提交；发布步骤仍核对下游状态，只在尚未同步时补发事件。正常构建的仓库写权限和 Actions 触发权限只授予汇总发布任务。

## 索引与兼容地址

Pages 将代码与 wheel 元数据分目录检出，使用稀疏检出读取 Git 树和历史，不检出 wheel 二进制。索引元数据使用两次批量 Git 查询：当前文件列表和全部 wheel 修改日期；另读取一次 Git 树 SHA 写入状态标记，不再对每个 wheel 重复查询。保留提交历史是为了显示历史修改日期，稀疏克隆避免拉取 wheel 文件内容。删除或不存在的文件不会出现在新索引中；日期缺失或没有 wheel 时直接失败。

主索引的 `index-state.json` 记录已发布的 wheels Git 树；兼容索引的 `sync-state.json` 记录已同步的 gh-pages Git 树。发送端在事件处理时读取下游公开状态并比较：一致就结束，不一致就通知。通知失败后状态仍不一致，因此可以重跑发布或部署任务来补发，不依赖本次是否产生新提交。

首次尚无状态文件的 HTTP 404 被明确建模为未发布；其他 HTTP、网络和格式错误直接失败。每次事件只读取一次下游状态，不做轮询或定时扫描。不同构建运行的索引通知可合并，部署始终读取最新 wheels。详见 [地址迁移](index-migration.md)。

## 开发检查

工具版本统一保存在 `pyproject.toml`：依赖组由 `uv.lock` 锁定，`scripts.tooling` 按组生成构建器所需的 pip 清单；驱动 Python、Chaquopy 提交、uv 和 actionlint 由同一份工具配置提供。CI 在 Python 3.11 与 3.15 上运行组件测试，对整个 `scripts/` 检查 Ruff，并校验 TOML 与 actionlint。构建器以 `python -m scripts.build.<模块>` 运行，只接受明确的 `PROJECT_DIR`，不再保留平铺导入与目录缺省行为。

```sh
uv sync --locked --no-install-project
uv run python -B -m scripts.recipes validate
uv run ruff check scripts
uv run ruff format --check scripts
uv run python -B -m unittest discover -s scripts/build/tests -v
uv run python -B -m unittest discover -s scripts/recipes/tests -v
uv run python -B -m unittest discover -s scripts/pipeline/tests -v
uv run python -B -m unittest discover -s scripts/index/tests -v
go run github.com/rhysd/actionlint/cmd/actionlint@v1.7.7
```

测试覆盖目标路由、固定 SHA、产物缺失与篡改、稳定 ABI、Cargo 配置组合、汇总提交、并发更新重试、无变化不发布，以及不检出 wheel 时的索引生成。测试、字节码、发布与通知逻辑变化不触发 native 构建；这些变化由组件测试和工作流检查验证。编译、源码准备、目标规划和公共构建配置变化仍重建全部 recipe。

历史排障笔记位于 `docs/archive/`，不作为当前构建配置或使用说明。
