# 热门原生扩展库首批收录

## 筛选口径

以 [Top PyPI Packages](https://hugovk.dev/top-pypi-packages/) 2026-10-01 月度快照的包下载量排序，先核对总榜前 300 个项目，识别出 66 个当前发行版提供 CPython 原生 wheel 的项目，再取其中前 50。这里的名次是原生扩展候选子榜，不是 PyPI 总榜前 50。

候选识别条件为 wheel ABI 不等于 `none`、平台不等于 `any`；真正收录还须核对上游源码和实际 ELF 扩展，排除仅包含 CLI 二进制的情况。下载量按包计算，不等于独立用户数。

2026-10-28 通过 [PyPI JSON API](https://docs.pypi.org/api/json/) 核对所有历史发行文件：首批新增项目均没有官方 `android_*` wheel。已存在官方 Android wheel 的包不纳入新增范围。

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

## 暂缓项目

| 包或类别 | 本次处理 |
| --- | --- |
| charset-normalizer、MarkupSafe、multidict、aiohttp、coverage | 当前 PyPI 已有官方 Android wheel，排除新增 |
| yarl、propcache、frozenlist | 使用 `pep517_backend.hooks` 自定义后端，留待单独接入与验证 |
| msgpack 1.2.4 | Git tag 缺少生成的 `_cmsgpack.c`，双 ABI 试构建失败；不修改源码，暂不收录 |
| kiwisolver 1.5.1 | 编译成功但版本元数据不正确；拒绝把开发版本标成稳定版本发布 |
| cryptography、cffi、Pillow、lxml、PyNaCl、google-crc32c 等 | 外部原生依赖与构建步骤需单独核验 |
| NumPy、pandas、SciPy、PyArrow、scikit-learn、matplotlib、contourpy 等 | 构建后端及数值/图形依赖需专项适配 |
| 其余前 50 项目 | 保留在审计表中，本轮未作为易移植首批准入 |

## 预验证记录

- [bcrypt 双 ABI 构建](https://github.com/ririv/py-extra-wheels/actions/runs/40653014430)
- [httptools 双 ABI 构建](https://github.com/ririv/py-extra-wheels/actions/runs/40653012691)
- [sqlalchemy 双 ABI 构建](https://github.com/ririv/py-extra-wheels/actions/runs/40653007969)
- [watchfiles 双 ABI 构建](https://github.com/ririv/py-extra-wheels/actions/runs/40653006143)
- [websockets 双 ABI 构建](https://github.com/ririv/py-extra-wheels/actions/runs/40653007438)
- [wrapt 双 ABI 构建](https://github.com/ririv/py-extra-wheels/actions/runs/40653007909)
