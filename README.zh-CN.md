# Py Extra Wheels

[English](README.md) | **简体中文**

本仓库用于为 Android 构建和托管预编译的 Python wheel 文件，例如用于 [Chaquopy](https://chaquo.com/chaquopy/) 安卓 Python SDK、或手动嵌入方式启动Python，具体请看[在安卓上使用Python](https://docs.python.org/zh-cn/3.14/using/android.html#using-python-on-android)。

索引地址：https://ririv.github.io/py-extra-wheels/

旧地址 https://ririv.github.io/android-wheels/ 继续可用。兼容站点不做定时扫描，新索引内容发布后通过事件通知同步。详见 [包索引地址迁移](docs/index-migration.md)。

## 如何使用

使用 `pip` 并指定 `--extra-index-url` 参数指向本仓库的包索引地址，即可安装这些 wheel 文件。

```bash
pip install --extra-index-url https://ririv.github.io/py-extra-wheels/ <包名>
```

例如，安装 `zstandard`:

```bash
pip install --extra-index-url https://ririv.github.io/py-extra-wheels/ zstandard
```

### requirements.txt

您也可以将索引地址添加到您的 `requirements.txt` 文件中：

```txt
--extra-index-url https://ririv.github.io/py-extra-wheels/

zstandard
xxhash
```

## 支持的 ABI:

* `arm64-v8a`
* `x86_64`

## 构建支持的 Python 版本

构建入口支持 Python **3.10–3.15**，默认版本为 **3.13**。其中 3.10 为额外保留的兼容版本；每个包及其依赖仍须支持所选 Python 版本。运行库来源、后端路由和验证方法见 [Android Python 构建支持](docs/python-builds.md)。

## 工作原理

本仓库使用 GitHub Actions 实现自动化构建和发布流程：

1. **Recipe 与构建矩阵**：每个包的配置位于 `recipes/<包名>.toml`。统一入口 `build-wheels.yml` 选择变更的包并生成并行矩阵，再调用现有 Android 构建器。包、Python 版本和 ABI 均可并行。
2. **统一发布**：所有目标成功后，按固定源码与哈希清单校验完整产物，再以一个提交更新 `wheels` 分支。
3. **部署索引**：汇总发布确认内容变化后，显式触发一次 `pages.yml`，生成 PEP 503 索引并部署。新索引内容变化时，再通知旧地址同步。

这确保了包索引始终与最新成功构建的 wheel 文件保持同步。

## 命名规范

### wheel 文件命名规范

wheel 文件命名遵循 Python 的 [PEP 427](https://peps.python.org/pep-0427/#recommended-installer-features) 规范，格式通常是：{distribution}-{version}-{python tag}-{abi tag}-{platform tag}.whl。

### 包索引命名规范

包索引命名遵循 Python 的 [PEP 503](https://peps.python.org/pep-0503/) 规范和用于[安卓的wheel tag格式](https://peps.python.org/pep-0738/#packaging)
规范化命名需要注意 [Normalized Names](https://peps.python.org/pep-0503/#normalized-names)

| API           | 作用                                                |
| ------------- | --------------------------------------------------- |
| PEP 503       | 索引：提供 HTML 索引文件。                          |
| PEP 691       | 索引：提供 JSON 索引文件。                          |
| PEP 658       | 索引：提供元数据，加速依赖解析。                    |
| PEP 738       | 平台：安卓平台支持，包含Packaging格式               |

## 如何添加新的包

在 `recipes/` 新增 `<包名>.toml`，显式填写源码仓库、Git ref、Python 项目目录、构建后端及 Android 默认目标。不要为每个包新增工作流。

配置合并到 `main` 后，只构建变更对应的包。手动构建、多 Python 版本、仅生成 Actions 产物和配置校验见 [Recipe 与并行构建](docs/recipes.md)。

```sh
gh workflow run build-wheels.yml -f recipes=pydantic-core -f python_versions=3.10 -f version_tag=v2.41.5
```

模块划分与开发检查见 [构建流水线](docs/pipeline.md)。
