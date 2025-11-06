# Android Wheels

本仓库用于为 Android 构建和托管预编译的 Python wheel 文件，例如用于 [Chaquopy](https://chaquo.com/chaquopy/) 安卓 Python SDK、或手动嵌入方式启动Python，具体请看[在安卓上使用Python](https://docs.python.org/zh-cn/3.14/using/android.html#using-python-on-android)。

索引地址：https://ririv.github.io/android-wheels/

## 如何使用

使用 `pip` 并指定 `--extra-index-url` 参数指向本仓库的包索引地址，即可安装这些 wheel 文件。

```bash
pip install --extra-index-url https://ririv.github.io/android-wheels/ <包名>
```

例如，安装 `zstandard`:

```bash
pip install --extra-index-url https://ririv.github.io/android-wheels/ zstandard
```

### requirements.txt

您也可以将索引地址添加到您的 `requirements.txt` 文件中：

```txt
--extra-index-url https://ririv.github.io/android-wheels/

zstandard
xxhash
```

## 支持的 ABI:

* `arm64-v8a`
* `x86_64`

## 工作原理

本仓库使用 GitHub Actions 实现自动化构建和发布流程：

1. **构建工作流**: 每个包都有一个对应的工作流文件（例如 `wheel-zstandard.yml`），它会获取库的源码，并使用一个可复用的工作流（`build-android-wheel.yml`）通过 Android NDK为不同的 Android ABI 进行交叉编译。
2. **提交到 `wheels` 分支**: 成功构建的 `.whl` 文件会被提交到 `wheels` 分支。
3. **部署索引**: 推送到 `wheels` 分支会触发 `pages.yml` 工作流，该工作流会生成一个符合 PEP 503 规范的“简单”包索引，并将其部署到 GitHub Pages。

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

我们欢迎社区贡献新的包。如果您想添加一个新的包到本仓库的构建系统中，请遵循以下步骤：

1.  **Fork 本仓库**
    点击页面右上角的 "Fork" 按钮，将此仓库复刻到您自己的 GitHub 账户下。

2.  **创建新的工作流文件**
    在您的 Fork 中，进入 `.github/workflows/` 目录。复制一个现有的工作流文件（例如 `wheel-zstandard.yml`）并将其重命名为您想添加的包名，例如 `wheel-<new-package>.yml`。

3.  **修改工作流文件**
    打开您新创建的文件，并修改 `with:` 部分的参数：
    *   `library-name`: 设置为您要构建的包的名称（通常是 PyPI 上的名称）。
    *   `git-repository`: 设置为该包的源码 Git 仓库地址（例如 `author/repo`）。
    *   `library-version`: (可选) 您可以指定一个固定的 Git 标签或分支。如果留空，将使用默认分支的最新代码。

    例如：
    ```yaml
    jobs:
      build-new-package:
        uses: ./.github/workflows/build-android-wheel-dispatch.yml
        permissions:
          contents: write
        with:
          library-name: 'your-package-name'
          git-repository: 'github_user/repo_name'
          library-version: 'v1.2.3' # 可选
    ```

4.  **提交 Pull Request**
    提交您的更改，并向上游仓库（`ririv/android-wheels`）发起一个 Pull Request。

在您的 Pull Request 被合并后，仓库维护者会手动触发一次新的工作流来构建您的包。构建成功后，新的 wheel 文件会自动发布到包索引中。