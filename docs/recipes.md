# Recipe 与并行构建

## 配置与调度分离

每个包的源码、后端和默认构建目标存放在 `recipes/<包名>.toml`。统一入口 `.github/workflows/build-wheels.yml` 生成包与 Python 版本的矩阵，再调用现有 `build-android-wheel-dispatch.yml`。

TOML 只描述数据，现有 maturin、cibuildwheel 和旧版 Chaquopy 构建器保持原有实现。解析器只生成任务清单，真正的编译仍分发到独立的 Actions job。

```text
recipes/*.toml
       ↓
统一入口生成包 × Python 矩阵
       ↓
各任务调用现有 Android 构建工作流
       ↓
每个任务继续按 ABI 并行构建
       ↓
按包和 Python 版本收集产物并发布
```

两层矩阵均设置 `fail-fast: false`。一个任务失败不会取消其他任务；实际同时运行数量仍受 GitHub runner 和账户并发配额限制。

## TOML 格式

```toml
name = "pydantic-core"
repository = "pydantic/pydantic-core"
ref = "main"
directory = "."
backend = "maturin"

[android]
python = ["3.13"]
abis = ["arm64-v8a", "x86_64"]
api = 24
```

所有字段都必须显式提供，未知字段、重复目标和非法值会使规划阶段失败。

| 字段 | 含义 |
| --- | --- |
| `name` | 规范化包名，必须与 TOML 文件名一致 |
| `repository` | GitHub `owner/repo`，不带 URL 前缀 |
| `ref` | 明确的分支、tag 或提交 SHA |
| `directory` | Python 项目在源码仓库内的相对目录；根目录填写 `.` |
| `backend` | 项目实际的 PEP 517 后端，与源码检测结果不一致时直接失败 |
| `android.python` | 默认构建集合，不是上游支持版本的声明；手动任务可覆盖 |
| `android.abis` | ABI 构建集合，支持 `arm64-v8a`、`x86_64` |
| `android.api` | Android API 整数，至少为 24 |

目前显式建模的后端为 `maturin`、`setuptools.build_meta`、`_pyyaml_pep517`。新增已有后端的包只需添加 TOML；其他后端须先扩展枚举并验证构建路径。

`jiter` 使用 `directory = "crates/jiter-python"`。迁移保留了原有默认分支的行为，包括 `regex` 的 `hg`、`orjson` 和 `xxhash` 的 `master`；`ormsgpack` 使用原仓库重定向后的规范地址 `ormsgpack/ormsgpack`。

配置只支持当前已实现的 Android 目标；未来添加其他平台时应新增对应的目标类型和构建器，不能依赖缺省字段把其他平台当作 Android 执行。

## 自动选择构建范围

只有相关文件推送到 `main` 才启动统一构建入口，没有定时扫描。

- 修改某个 TOML，只构建对应的包及其默认目标。
- 修改共享构建代码、规划代码或统一构建工作流，构建所有现存 recipe，延续原来共享代码变化时全量构建的行为。
- 删除 recipe 不会重新构建已删除的包；仅删除文件时，空矩阵直接跳过构建。
- 文档变化不会触发 native wheel 构建。

规划会先校验全部 recipe，再根据 Git diff 选择目标。新增或重命名的 TOML 可以被识别，不依赖 GitHub push 事件里可能被截断的文件列表。

规划任务采用浅克隆，并显式获取推送前的提交，只读取比较前后源码树所需的对象。

## 手动构建

单包、单 Python 版本并覆盖 Git tag：

```sh
gh workflow run build-wheels.yml \
  -f recipes=pydantic-core \
  -f python_versions=3.10 \
  -f version_tag=v2.41.5
```

多包、多版本并行，仅保留 Actions 产物：

```sh
gh workflow run build-wheels.yml \
  -f recipes=pydantic-core,xxhash \
  -f python_versions=3.10,3.13 \
  -f publication=build
```

`recipes` 可为逗号分隔的包名或 `all`；`python_versions=recipe` 使用各 TOML 的默认集合，也可填写无空格的版本列表。覆盖 `version_tag` 时必须只选择一个包，可以同时构建该包的多个 Python 版本。

`publication=publish` 是默认值，会提交 wheel 并触发现有索引发布链路；`publication=build` 只上传 Actions artifacts，跳过 `wheels` 分支和索引发布。

`manual-wheel-build.yml` 保留为临时仓库构建入口，用于尚未收录进 recipe 的源码；原来的 `wheel-*.yml` 包专用入口由 `build-wheels.yml` 替代。

## Artifact 隔离

artifact 名称由目标规划模块统一生成，三个构建器使用同一字段，收集阶段使用同一前缀：

```text
pydantic-core-android-3.10-wheel-arm64-v8a
pydantic-core-android-3.10-wheel-x86_64
pydantic-core-android-3.13-wheel-arm64-v8a
pydantic-core-android-3.13-wheel-x86_64
```

每个发布任务只下载自己的包与 Python 版本的产物。多版本构建不会出现同名 artifact 或误收集其他 Python 版本的问题。

## 本地校验

```sh
python -B -m scripts.recipes validate
python -B -m unittest discover -s scripts/recipes/tests -v
python -B -m scripts.recipes plan \
  --recipes pydantic-core,xxhash \
  --python-versions 3.10,3.13 \
  --publication build \
  --github-output /tmp/wheel-matrix-output
```

规划输出独立任务的 JSON，不在本地编译。运行这些命令的 Python 至少为 3.11，且不需要安装 TOML 第三方库。
