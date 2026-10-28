# 热门原生扩展库收录

## 筛选口径

以 [Top PyPI Packages](https://hugovk.dev/top-pypi-packages/) 2026-10-01 月度快照的包下载量排序，先核对总榜前 300 个项目，识别出 66 个当前发行版提供 CPython 原生 wheel 的项目，再取其中前 50。这里的名次是原生扩展候选子榜，不是 PyPI 总榜前 50。

候选识别条件为 wheel ABI 不等于 `none`、平台不等于 `any`；真正收录还须核对上游源码和实际 ELF 扩展，排除仅包含 CLI 二进制的情况。下载量按包计算，不等于独立用户数。

2026-10-28 通过 [PyPI JSON API](https://docs.pypi.org/api/json/) 核对所有历史发行文件：各批新增项目均没有官方 `android_*` wheel。已存在官方 Android wheel 的包不纳入新增范围。

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

同样的链接核验也修正了已有 `watchfiles` 产物。`tokenizers`、`wcwidth`、`watchfiles` 之前的 6 个过宽 `abi3` 文件已撤下，替换为与实际 Python 动态库一致的产物；归档保留审计证据。

sdist 的地址、SHA-256、排名及全部预验证 wheel 记录见 [第二批审计记录](data/native-second-batch-2026-10.json)。原先失败的 Git 构建记录保留在首批审计文件中，并标注已解决。

## 第三批收录

继续沿用原生候选下载量前 50 的同一快照，本轮预验证通过的包如下。全部使用官方 PyPI sdist；编译期间只配置环境、工具链和外部原生依赖，不对上游源码打补丁。

| 原生候选名次 | 包 | 版本 | 快照下载量 | 原生依赖或配置 |
| --- | --- | --- | --- | --- |
| 2 | [cryptography](https://pypi.org/project/cryptography/) | 50.0.2 | 1,070,154,291 | OpenSSL 3.5.9；运行依赖本批 CFFI |
| 3 | [cffi](https://pypi.org/project/cffi/) | 2.1.1 | 949,615,436 | libffi 3.8.0 |
| 37 | [hf-xet](https://pypi.org/project/hf-xet/) | 1.7.0 | 188,604,448 | 沿用 maturin，补齐 Python 链接与运行库打包 |
| 42 | [pynacl](https://pypi.org/project/pynacl/) | 1.6.2 | 166,088,922 | libsodium 1.0.22；运行依赖本批 CFFI |
| 43 | [chardet](https://pypi.org/project/chardet/) | 7.7.0 | 165,621,246 | 同时开启 mypyc 与 Cython；宿主 mypy 显式从源码安装 |
| 49 | [google-crc32c](https://pypi.org/project/google-crc32c/) | 1.9.0 | 140,796,400 | CRC32C 1.1.2；共享库及 C++ 运行库随 wheel 打包 |

宿主 mypy 的已编译 wheel 在目标平台模拟环境中导入失败，因此 chardet 使用 `PIP_NO_BINARY=mypy` 明确安装宿主工具源码，并启用 `HATCH_BUILD_HOOK_ENABLE_MYPYC=true` 与 `HATCH_BUILD_HOOK_ENABLE_CUSTOM=true`。最终 chardet wheel 同时包含 pipeline 和检测内核的原生扩展，没有用纯 Python 产品产物替代。

原生依赖版本、下载地址、SHA-256、构建参数和许可证统一保存在 `scripts/build/native-libraries.toml`。cibuildwheel 使用目标 Python 开发前缀，maturin 使用任务独立前缀，避免混入宿主 Linux 头文件或库。依赖来源和许可证随 wheel 保存，发布阶段核对固定配置。新增原生依赖本身不作为 Python 包计数。

所有新增 wheel 均验证了实际 ELF、正确的 Android 架构、版本专用 Python 动态库与标签，以及依赖库打包和相对加载路径。本轮默认 Python 3.13 / API 24 / 双 ABI，不表示新增包的其他 Python 版本已通过测试；未在设备或模拟器中运行功能测试。完整来源和哈希见 [本批审计记录](data/native-third-batch-2026-10.json)。

## 第四批收录

沿用原生候选下载量前 50 的同一快照，新增以下四个包。固定 PyPI 官方 sdist，保持源码与元数据原样，默认 Python 3.13 / Android API 24 / 双 ABI。

| 原生候选名次 | 包 | 版本 | 快照下载量 | 配置或原生依赖 |
| --- | --- | --- | --- | --- |
| 7 | [protobuf](https://pypi.org/project/protobuf/) | 7.36.2 | 619,205,877 | sdist 原有的 upb C 扩展 |
| 15 | [Pillow](https://pypi.org/project/pillow/) | 13.0.0 | 425,694,980 | libjpeg-turbo 3.2.1、NDK zlib；PEP 517 参数关闭宿主路径猜测 |
| 23 | [lxml](https://pypi.org/project/lxml/) | 6.1.3 | 313,948,323 | libiconv 1.19、libxml2 2.15.4、libxslt 1.1.45 |
| 36 | [fonttools](https://pypi.org/project/fonttools/) | 4.68.0 | 193,015,590 | `FONTTOOLS_WITH_CYTHON=1` 明确要求扩展成功 |

fonttools、protobuf、lxml 的发行源码没有显式 `build-backend`，因此 recipe 明确选择 `setuptools.build_meta:__legacy__`。只有存在 `setup.py` 且没有已声明后端时才接受，不创建或改写上游 `pyproject.toml`。Pillow 使用其原有本地 `backend`，通过 `[config-settings]` 传入构建参数。

Pillow 本轮包含 JPEG、ZLIB（PNG/ZIP）能力；没有提供 WebP、JPEG2000、TIFF、AVIF、FreeType、Raqm、LittleCMS、libimagequant 或 XCB。构建日志确认 JPEG/zlib 可用，编译失败不会改用纯 Python 产品。其他可选格式与字体支持不在本次验证范围内。

lxml 需要在后端查询构建依赖之前找到目标原生库。流水线先在任务独立前缀编译，并通过 pkg-config 供早期检查使用，再核对并安装到目标 Python 开发前缀；宿主构建钩子需要的 Android shell 路径显式映射到宿主 shell。libxslt 通过上游 `LIBXSLT_WITH_DEBUGGER=ON` 正常生成导出表中的符号，没有移除符号检查或修改源码。

八个预验证 wheel 均含实际 ELF，来源、发行版本、SHA-256、WHEEL/RECORD、架构、版本专用 Python 链接、依赖闭合和相对加载路径通过核验；尚未进行设备或模拟器功能测试。来源、原生库许可证、配置和产物哈希见 [第四批审计记录](data/native-fourth-batch-2026-10.json)。

- [fonttools、protobuf 双 ABI](https://github.com/ririv/py-extra-wheels/actions/runs/40678542449)：四个目标全部成功。
- [Pillow 双 ABI](https://github.com/ririv/py-extra-wheels/actions/runs/40681765323)：两个目标成功并独立核验；该次包含随后修复的 lxml，整体失败且未发布。
- [lxml 双 ABI](https://github.com/ririv/py-extra-wheels/actions/runs/40682056639)：两个目标全部成功。

## 暂缓项目

| 包或类别 | 本次处理 |
| --- | --- |
| charset-normalizer、MarkupSafe、multidict、aiohttp、coverage | 当前 PyPI 已有官方 Android wheel，排除新增 |
| grpcio 1.85.0 | 外部 OpenSSL 和 c-ares 均已编译，但上游硬编码宿主 `/usr/include`；调整搜索顺序后仍未通过，暂缓 |
| mypy 2.4.0 | 运行依赖 librt 与 ast-serialize 尚无官方 Android wheel，本轮不单独发布主包 |
| NumPy | 已尝试 Meson 构建，但缺少 Android BLAS；不发布关闭 BLAS 的构建 |
| contourpy | 双 ABI 编译通过，因依赖 NumPy 暂缓发布 |
| psutil | 上游明确拒绝 Android 平台，不修改源码中的平台判断 |
| uvloop | 外部配置已解决 libuv 交叉编译识别，但上游仍硬编码链接 Android 不提供的独立 pthread 库 |
| pandas、SciPy、PyArrow、scikit-learn、matplotlib 等 | 数值/图形依赖需专项适配 |
| 其余前 50 项目 | 保留在审计表中，本轮尚未收录 |

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

- [Android 链接与 ABI 修复预验证](https://github.com/ririv/py-extra-wheels/actions/runs/40660301805)：tokenizers、wcwidth、pydantic-core 共 6 个目标全部通过。

## 第二批回归与发布

[全量构建与发布](https://github.com/ririv/py-extra-wheels/actions/runs/40660865533) 的 24 个 recipe、48 个目标全部成功；[CI](https://github.com/ririv/py-extra-wheels/actions/runs/40660865506) 在 Python 3.11 与 3.15 上通过组件测试、Ruff 与工作流检查。

下载全部最终产物后，核验了来源清单、SHA-256、包与版本、WHEEL、RECORD、ELF 架构、Python 动态库与标签，以及运行库打包情况。其中 46 个 wheel 含 ELF；已有 PyYAML 的两个产物沿用上游允许的纯 Python 构建行为，不计入新增原生扩展。新增八包的十六个最终产物全部含 ELF。所有 ELF 的外部依赖均为 Android 系统库、对应 Python 或已打包到 wheel 的库。

[Python 3.10 的 pydantic-core 2.41.5 双 ABI 回归](https://github.com/ririv/py-extra-wheels/actions/runs/40661343355) 也已成功，仅保留验证产物。此项验证维护共享构建器的既有 3.10 能力，不表示本轮八个新增包已验证 3.10。

[主索引](https://ririv.github.io/py-extra-wheels/) 与 [旧地址](https://ririv.github.io/android-wheels/) 均已通过事件链路自动发布。两处根页和八个新增包页均返回 HTTP 200，双 ABI 链接齐全，旧 abi3 文件已移除；公开状态标记与对应源码树一致。最终 wheel 清单、哈希和状态树见第二批审计记录的 `published_wheels` 与 `regression`。

## 本轮预验证记录

- [hf-xet 双 ABI](https://github.com/ririv/py-extra-wheels/actions/runs/40662930657)：全部成功。
- [chardet 双 ABI](https://github.com/ririv/py-extra-wheels/actions/runs/40666525022)：全部成功；该次还包含其他失败或后续修复的候选，整体运行未发布。
- [CFFI、PyNaCl、cryptography 双 ABI](https://github.com/ririv/py-extra-wheels/actions/runs/40668003736)：六个收录目标全部成功；同次 CRC32C 随后单独修复，整体运行未发布。
- [google-crc32c 双 ABI](https://github.com/ririv/py-extra-wheels/actions/runs/40672514748)：全部成功，包含共享 CRC32C 和 C++ 运行库。
- [Python 3.10 pydantic-core 回归](https://github.com/ririv/py-extra-wheels/actions/runs/40666954200)：两种 ABI 均成功，保留原有构建能力。
- [gRPC 最后一次配置验证](https://github.com/ririv/py-extra-wheels/actions/runs/40673736717)：未通过，不收录失败 recipe。

## 第三批回归与发布

本轮新增 **6 个包**，仓库共 **30 个 recipe**；三批累计新增 20 个 Python 包。原生依赖库不计入此数量。

[全量构建与发布](https://github.com/ririv/py-extra-wheels/actions/runs/40675141301) 的 60 个目标全部成功，[CI](https://github.com/ririv/py-extra-wheels/actions/runs/40675141332) 也已通过。下载全部最终产物后复核：58 个含 ELF，两个已有 PyYAML 产物沿用纯 Python 构建；本轮新增的十二个 wheel 全部含原生扩展。来源、版本、SHA-256、WHEEL/RECORD、架构、Python 动态库与标签、依赖闭合和相对加载路径均通过检查。新增文件的已发布 Git blob 与 Actions 核验产物逐字节一致。

[主索引](https://ririv.github.io/py-extra-wheels/) 和 [旧索引](https://ririv.github.io/android-wheels/) 已由事件链路自动更新。两处根页和六个新增包页均返回 HTTP 200，版本及双 ABI 链接齐全；公开状态标记与对应源码树一致。发布文件、哈希和状态树详见本批审计记录的 `published_wheels` 与 `regression`。

## 第四批回归与发布

本轮新增 **4 个包**，仓库共 **34 个 recipe**；四批累计新增 24 个 Python 包。

[全量构建与发布](https://github.com/ririv/py-extra-wheels/actions/runs/40683994208) 的 68 个目标全部成功，[CI](https://github.com/ririv/py-extra-wheels/actions/runs/40683994049) 在 Python 3.11 与 3.15 上通过 65 个组件测试、Ruff、TOML 与工作流检查。下载全部最终产物后复核：66 个含 ELF，两个已有 PyYAML 产物沿用纯 Python 构建；本轮新增八个 wheel 全部含原生扩展。固定来源、SHA-256、版本、WHEEL/RECORD、架构、Python 链接、依赖闭合与相对加载路径检查全部通过。

初次全量运行在发布前复核时发现外部共享库、部分已有 Rust 扩展及 patchelf 新增段存在 4 KB 对齐，因此[取消该次发布](https://github.com/ririv/py-extra-wheels/actions/runs/40682586892)。随后按 [Android 官方说明](https://developer.android.com/guide/practices/page-sizes) 补齐 C/C++、Rust 和 patchelf 参数，并增加发布阶段的 ELF 加载段检查。最终 66 个原生 wheel 中的所有 ELF 加载段均满足至少 16 KB 对齐，文件偏移与虚拟地址关系也通过核验。这不代替设备功能测试，也不表示其他历史 Python 版本产物已全量重建。

[Python 3.10 pydantic-core 2.41.5 双 ABI 回归](https://github.com/ririv/py-extra-wheels/actions/runs/40684018312) 同样通过来源、哈希、标签、ELF、16 KB 对齐和依赖闭合检查，仅保留验证产物。

[主索引](https://ririv.github.io/py-extra-wheels/) 和 [旧索引](https://ririv.github.io/android-wheels/) 已由事件链路自动更新。两处根页及四个新增包页均返回 HTTP 200，版本与双 ABI 链接齐全；两个公开状态标记分别匹配 wheels 和 gh-pages 源码树。八个新增 wheel 的已发布 Git blob 与 Actions 核验产物逐字节一致。最终文件、哈希、加载段对齐和状态树见第四批审计记录的 `published_wheels`、`python310_regression` 与 `regression`。
