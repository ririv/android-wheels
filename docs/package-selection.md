# 热门原生扩展库收录

## 筛选口径

以 [Top PyPI Packages](https://hugovk.dev/top-pypi-packages/) 2026-10-01 月度快照的包下载量排序，先核对总榜前 300 个项目，识别出 66 个当前发行版提供 CPython 原生 wheel 的项目，再取其中前 50。这里的名次是原生扩展候选子榜，不是 PyPI 总榜前 50。

候选识别条件为 wheel ABI 不等于 `none`、平台不等于 `any`；真正收录还须核对上游源码和实际 ELF 扩展，排除仅包含 CLI 二进制的情况。下载量按包计算，不等于独立用户数。

2026-10-28 通过 [PyPI JSON API](https://docs.pypi.org/api/json/) 核对所有历史发行文件：两批新增项目均没有官方 `android_*` wheel。已存在官方 Android wheel 的包不纳入新增范围。

排名、下载量、官方文件列表、源码提交和预验证产物哈希保存在 [机器可读审计记录](data/native-top50-2026-10.json)。这是一份本次快照，不设置定时扫描。

## 首批收录

| 原生候选名次 | PyPI 总榜 | 包 | 稳定版本 | 快照下载量 | 用途 |
| --- | --- | --- | --- | --- | --- |
| 17 | 68 | [websockets](https://pypi.org/project/websockets/) | 17.3 | 398,431,816 | WebSocket 协议与 C 加速 |
| 18 | 70 | [wrapt](https://pypi.org/project/wrapt/) | 2.5.1 | 392,118,252 | 装饰器、对象包装与 C 扩展 |
| 21 | 87 | [sqlalchemy](https://pypi.org/project/sqlalchemy/) | 2.1.6 | 331,730,354 | 数据库工具及 Cython 加速模块 |
| 26 | 94 | [watchfiles](https://pypi.org/project/watchfiles/) | 1.3.0 | 305,158,420 | Rust 文件变更监听 |
| 32 | 134 | [httptools](https://pypi.org/project/httptools/) | 0.9.0 | 212,349,802 | HTTP 协议解析器 |
| 48 | 182 | [bcrypt](https://pypi.org/project/bcrypt/) | 5.0.0 | 154,218,667 | Rust 密码哈希绑定 |

六个包均固定到对应稳定版 Git tag，保持上游源码不变，使用现有 setuptools/maturin 构建路径，不添加补丁或包专用参数。默认 Python 3.13、Android API 24，同时构建 `arm64-v8a` 与 `x86_64`。

预验证共 12 个 wheel 全部通过源码 SHA、发行版本、文件名、WHEEL 标签、RECORD 哈希与大小检查。每个 wheel 都含实际原生 `.so`，ELF 架构分别为 AArch64（183）和 x86-64（62），没有以纯 Python wheel 代替原生扩展。

本次验证包含交叉编译、包元数据及 ELF 静态核验；尚未在 Android 设备或模拟器上运行完整功能测试。SQLAlchemy 的数据库驱动及 asyncio 可选依赖不属于本批收录；watchfiles 的 `anyio` 等普通依赖仍由 PyPI 提供。

## 第二批收录

继续使用同一份原生候选前 50 快照，新增 8 个包。全部使用固定版本的 PyPI 官方 sdist，保持上游源码和元数据原样；没有源码补丁，也不通过开发版本改标稳定版。

| 原生候选名次 | PyPI 总榜 | 包 | 稳定版本 | 快照下载量 |
| --- | --- | --- | --- | --- |
| 12 | 50 | [yarl](https://pypi.org/project/yarl/) | 1.25.1 | 459,889,343 |
| 14 | 55 | [propcache](https://pypi.org/project/propcache/) | 0.5.4 | 442,913,585 |
| 16 | 61 | [frozenlist](https://pypi.org/project/frozenlist/) | 1.8.0 | 417,051,290 |
| 19 | 77 | [greenlet](https://pypi.org/project/greenlet/) | 3.5.6 | 369,974,693 |
| 31 | 118 | [wcwidth](https://pypi.org/project/wcwidth/) | 0.9.4 | 240,279,397 |
| 35 | 145 | [msgpack](https://pypi.org/project/msgpack/) | 1.2.4 | 193,313,294 |
| 41 | 164 | [tokenizers](https://pypi.org/project/tokenizers/) | 0.23.3 | 166,389,324 |
| 47 | 179 | [kiwisolver](https://pypi.org/project/kiwisolver/) | 1.5.1 | 156,347,414 |

默认 Python 3.13、Android API 24，同时构建 `arm64-v8a` 与 `x86_64`，保留原有独立并行矩阵。16 个 wheel 均通过发行版本、源码哈希、wheel 哈希、WHEEL、RECORD 和实际 ELF 架构静态核验；尚未进行设备运行测试。初步产物中 `tokenizers` 与 `wcwidth` 使用上游的 `cp310-abi3` 标签，最终静态复核发现 Android 的版本专用 Python 链接约束；流水线据此补齐链接、打包 C++ 依赖，并将实际链接 `libpython3.13.so` 的最终产物收窄为 `cp313-cp313`。本轮新增包只完成 Python 3.13 构建验证。

`msgpack` 的 Git tag 缺少生成的 C 文件，但官方 sdist 已包含 `_cmsgpack.c`。`kiwisolver` 的官方 sdist 保留稳定版发行元数据，不依赖浅克隆中的 Git 标签。两者均通过双 ABI 构建，`kiwisolver` 的最终版本为 `1.5.1`。

`frozenlist` 的上游 cibuildwheel 发布配置含当前工具不再接受的 `cpython-freethreading` 选项。流水线通过 `--config-file` 读取仓库独立配置，PEP 517 后端继续使用原始项目文件。`wcwidth` 在 cibuildwheel 发布模式下要求 C 扩展成功，不允许缺少扩展仍产出 wheel；本次也实际核对了扩展 ELF。

sdist 的地址、SHA-256、排名及全部预验证 wheel 记录见 [第二批审计记录](data/native-second-batch-2026-10.json)。原先失败的 Git 构建记录保留在首批审计文件中，并标注已解决。

## 暂缓项目

| 包或类别 | 本次处理 |
| --- | --- |
| charset-normalizer、MarkupSafe、multidict、aiohttp、coverage | 当前 PyPI 已有官方 Android wheel，排除新增 |
| CFFI | 缺少 Android libffi 与 ffi.h，需先提供真实的目标平台依赖 |
| cryptography、Pillow、lxml、PyNaCl、google-crc32c 等 | 外部原生依赖与构建步骤需单独核验 |
| NumPy | 已尝试 Meson 构建，但缺少 Android BLAS；不发布关闭 BLAS 的构建 |
| contourpy | 双 ABI 编译通过，因依赖 NumPy 暂缓发布 |
| psutil | 上游明确拒绝 Android 平台，不修改源码中的平台判断 |
| uvloop | 外部配置已解决 libuv 交叉编译识别，但上游仍硬编码链接 Android 不提供的独立 pthread 库 |
| pandas、SciPy、PyArrow、scikit-learn、matplotlib 等 | 数值/图形依赖需专项适配 |
| 其余前 50 项目 | 保留在审计表中，本轮未作为易移植首批准入 |

## 预验证记录

- [bcrypt 双 ABI 构建](https://github.com/ririv/py-extra-wheels/actions/runs/40653014430)
- [httptools 双 ABI 构建](https://github.com/ririv/py-extra-wheels/actions/runs/40653012691)
- [sqlalchemy 双 ABI 构建](https://github.com/ririv/py-extra-wheels/actions/runs/40653007969)
- [watchfiles 双 ABI 构建](https://github.com/ririv/py-extra-wheels/actions/runs/40653006143)
- [websockets 双 ABI 构建](https://github.com/ririv/py-extra-wheels/actions/runs/40653007438)
- [wrapt 双 ABI 构建](https://github.com/ririv/py-extra-wheels/actions/runs/40653007909)
- [第二批 sdist 预验证](https://github.com/ririv/py-extra-wheels/actions/runs/40656541328)：6 个收录包双 ABI 成功；同次运行包含失败或暂缓候选，整体状态为失败，未发布。
- [frozenlist 与 wcwidth 双 ABI 预验证](https://github.com/ririv/py-extra-wheels/actions/runs/40659064598)：4 个目标全部成功，未发布。
- [外部依赖与链接参数试构建](https://github.com/ririv/py-extra-wheels/actions/runs/40657971703)：NumPy、CFFI、uvloop 暂缓原因的日志；frozenlist 的配置冲突随后已解决。
