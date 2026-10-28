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
| `scripts/pipeline/artifacts.py` | 记录并校验产物来源、完整性与目标标签 |
| `scripts/pipeline/publish.py` | 将完整构建汇总为一个 Git 提交 |
| `scripts/index` | 批量读取 Git 元数据，生成确定的 HTML 索引 |

模块通过明确的数据和文件交互，不提供任意 Shell hook、自定义参数或源码补丁入口。

## Actions 职责

主仓库保留五个工作流：recipe 入口、单目标 Android 构建器、临时仓库入口、索引部署、统一 CI。两个构建入口共享源码准备与发布 composite action。

构建计划记录在 `build-plan` artifact 内的 `build-plan.json`，源码 ref 在规划时解析为完整 SHA。不同 Python 和 ABI 使用同一个固定源码提交，构建器在编译前重新校验 checkout。临时仓库入口未填写 ref 时，显式读取上游默认分支后固定其提交。

每个目标使用独立 runner 编译。后端与 Python 版本决定 maturin、cibuildwheel 或 Chaquopy 路由，不改变原有交叉编译能力。驱动 Python 与目标 Python 分开设置。

所有目标成功后才进入汇总发布。发布会验证每个预期 artifact，缺少产物、源码错配、哈希不符、目标标签错误、同名内容冲突都会失败。校验通过后以一个提交更新 `wheels`，保留已有文件。不同工作流运行并发提交时，仅在远端确实前进后重新组合提交，最多三次；网络或权限失败直接报告。

`publication=build` 不进入发布。完整产物与远端相同时不创建新提交，也不触发索引部署。正常构建的仓库写权限和 Actions 触发权限只授予汇总发布任务。

## 索引与兼容地址

Pages 将代码与 wheel 元数据分目录检出，使用稀疏检出读取 Git 树和历史，不检出 wheel 二进制。索引生成只有两次批量 Git 查询：当前文件列表和全部 wheel 修改日期；不再对每个 wheel 重复查询。保留提交历史是为了显示历史修改日期，稀疏克隆避免拉取 wheel 文件内容。删除或不存在的文件不会出现在新索引中；日期缺失或没有 wheel 时直接失败。

汇总发布仅在内容变化后显式触发一次部署。不同构建运行的索引通知可合并，部署始终读取最新 wheels。兼容地址仍由新索引变化事件通知，不做定时扫描，详见 [地址迁移](index-migration.md)。

## 开发检查

开发依赖由 `pyproject.toml` 与 `uv.lock` 固定，maturin 构建依赖单独固定在 `requirements/build.txt`。CI 在 Python 3.11 与 3.15 上运行组件测试，并检查 TOML、Ruff 与 actionlint。

```sh
uv sync --locked --no-install-project
uv run python -B -m scripts.recipes validate
uv run ruff check scripts/pipeline scripts/recipes scripts/index scripts/generate_index.py
uv run ruff format --check scripts/pipeline scripts/recipes scripts/index scripts/generate_index.py
uv run python -B -m unittest discover -s scripts/build/tests -v
uv run python -B -m unittest discover -s scripts/recipes/tests -v
uv run python -B -m unittest discover -s scripts/pipeline/tests -v
uv run python -B -m unittest discover -s scripts/index/tests -v
go run github.com/rhysd/actionlint/cmd/actionlint@v1.7.7
```

测试覆盖目标路由、固定 SHA、产物缺失与篡改、稳定 ABI、Cargo 配置组合、汇总提交、并发更新重试、无变化不发布，以及不检出 wheel 时的索引生成。测试和字节码文件变化不触发 native 构建；公共构建逻辑变化仍重建全部 recipe。
