# 科学计算与数据处理扩展

## 收录范围

沿用既有原生扩展下载量前 100 的快照，选择当前 PyPI 发行版。候选的 PyPI 全部发行记录均无官方 Android wheel；包源码保持原样，不为旧 Python 降级版本。

| 原生名次 | 包 | 当前版本 | 默认 Python | Android 目标 |
| --- | --- | --- | --- | --- |
| 27 | SciPy | 1.18.1 | 3.12–3.15 | API 26，仅 ARM64 |
| 83 | Shapely | 2.2.0 | 3.12–3.15 | API 24，双 ABI |
| 86 | DuckDB | 2.0.0 | 3.11–3.15 | API 24，双 ABI |
| 96 | polars-runtime-32 | 2.1.0 | 3.11–3.15 | API 24，双 ABI |
| 97 | Thrift | 0.25.0 | 3.10–3.15 | API 24，双 ABI |

双 ABI 指 `arm64-v8a` 和 `x86_64`。Shapely 上游支持 Python ≥3.11，但本仓库当前 NumPy 2.5.4 要求 ≥3.12，因此不声明 3.11 完整依赖栈。DuckDB 的 3.11 wheel 可独立运行；与当前 NumPy、pandas 的互操作从 3.12 开始。

## 构建配置

所有包继续使用 TOML recipe 与统一矩阵入口。包 × Python × ABI 各自在独立 runner 并行，没有新增包专用工作流或定时任务。

Shapely 使用 Meson，通过固定版本 GEOS 3.15.0 提供几何引擎。GEOS 的官方地址、SHA-256、CMake 参数和许可文件固定在 `scripts/build/native-libraries.toml`，共享库与许可证随 wheel 携带。Python 3.12 的旧构建路径显式提供目标 pkg-config 和 NumPy 官方 `numpy-config --pkgconfigdir` 返回的目录。

DuckDB 使用其原始 `duckdb_packaging.build_backend`，保留官方默认的 `core_functions`、Parquet、JSON、ICU 内置扩展。通过外部 CMake 参数链接目标 Python，并把并行编译限制为两个任务。构建与运行均不下载第三方 DuckDB 扩展。

Thrift 使用上游 setuptools 后端和 `CIBUILDWHEEL=1`，扩展编译失败会直接报错。旧构建器显式启用 `-O2`，解决未优化的 C++ 静态常量引用问题；没有调整上游类定义或关闭 `fastbinary`。

Polars 使用当前官方纯 Python `polars` 2.1.0 前端与本仓库 `polars-runtime-32` wheel。recipe 显式展开上游 full feature 集合，排除 Android 不支持的桌面剪贴板依赖；保留 CSV、JSON、Parquet、IPC、Avro、SQL、流式与其他数据处理 feature。编译使用上游固定的 nightly Rust、两个 Cargo 编译任务与 16 KB jemalloc 配置。项目内链接脚本将旧 `libgcc` 名称映射到 NDK `libunwind`；目标版本 Python 动态库仍显式链接，wheel 按实际依赖约束标签。

SciPy 使用现有 OpenBLAS 0.3.34、LP64、C 版 LAPACK 及 cibuildwheel 提供的 Android Flang 工具链，不关闭 Fortran 模块。当前源码使用的 `clog`、`cpow` 从 Android API 26 提供，因此 recipe 显式要求 API 26。C++ 参数 `-U_GNU_SOURCE` 使上游 ducc FFT 使用标准线程实现，避开 Android 缺少的 GNU pthread affinity API。

SciPy 暂不收录 x86_64：当前发行版固定的 Boost Math 1.91 将 x86 的 `long double` 假定为 80 位，Android x86_64 使用 128 位，编译时断言失败。没有伪造浮点 ABI、替换上游固定的 Boost 版本或修改头文件。

## 捆绑库许可证

原始 DuckDB 与 SciPy wheel 未完整携带其 sdist 内已有的捆绑库许可文件。复用 `scripts/build/bundled-licenses.toml`，分别绑定当前 sdist SHA-256，并逐文件固定 27 个、38 个原始许可文件或带许可声明的源文件。打包只新增 `.dist-info/licenses/bundled/` 与来源清单并更新 RECORD；逐文件核对原有二进制载荷保持不变。GEOS 与 OpenBLAS 则继续通过原生依赖的固定来源清单携带许可证。

## Android 运行检查

运行套件声明集中在 `scripts/testing/runtime_suites.py`。`plotting` 保留既有绘图检查，`data` 使用独立纯 Python 依赖锁与 `data_smoke.py`，共用相同的产物来源校验、离线安装与设备执行入口。

`data_smoke.py` 检查 GEOS 几何布尔运算、向量化谓词、STRtree、WKB/WKT；DuckDB SQL 聚合、Parquet、JSON、ICU 时区、pandas 互操作和文件重开；Polars lazy groupby、join、Parquet/IPC/CSV、NumPy 转换和空值；Thrift 的 Binary/Compact 原生编码解码与纯 Python 协议参考结果。

`numerical` 使用 `scipy_smoke.py`，检查 OpenBLAS/LAPACK、线性求解与逆矩阵、稀疏求解、FFT 单/双 worker 对照、积分、求根、复数特殊函数、统计、卷积、图像滤波、插值、KDTree、Delaunay 和 Fortran ODR。该套件仅在 ARM64 设备执行。

运行依赖必须具有相同 Python 与 ABI，最低 Android API 不能高于入口包。离线 pip 显式接受入口 API 及更低的 Android 平台标签；每个依赖仍按自身原始计划校验，不改变 wheel 标签。

## 运行与发布记录

44 个目标全部成功，最终产物包含 **526 个 ELF 文件**。来源、SHA-256、WHEEL/RECORD、架构、16 KB 加载段对齐、依赖闭合、相对加载路径和固定许可证均通过核验。最终目标集合与五个 TOML 的默认版本、ABI、API 逐项一致。

30 个 wheel 与原构建产物字节相同；另外 14 个 DuckDB/SciPy wheel 仅增加许可材料与来源清单，并更新 RECORD，原有文件载荷逐字节不变。最终 Python 3.13 数据套件在 Android API 34 双 ABI 上通过 20 项功能检查；SciPy 在同级 ARM64 模拟器上通过 17 项数值检查，包括单/双 worker FFT 对照。报告中所有本批原生依赖的 wheel 哈希与最终文件一致。

3.10–3.12、3.14、3.15 的其他组合证据为构建与静态检查。模拟器使用 4 KB 页，16 KB 支持仅核验 ELF 对齐；本轮没有执行上游完整测试集、性能评测或真实 16 KB 页设备测试。

| 证据 | 运行 |
| --- | --- |
| 最终统一重打包与校验 | [41172093566](https://github.com/ririv/py-extra-wheels/actions/runs/41172093566) |
| 最终数据套件 x86_64 Android 运行检查 | [41172658795](https://github.com/ririv/py-extra-wheels/actions/runs/41172658795) |
| 最终 CI | [41172635370](https://github.com/ririv/py-extra-wheels/actions/runs/41172635370)，Python 3.11、3.15 各 93 项组件测试，及 Ruff、TOML、actionlint 和构建工具补丁检查 |

ARM64 两个最终运行套件在本机专用模拟器执行。完整的原始构建运行编号、构建代码提交、上游源码与文件哈希、逐个 ELF 检查、许可材料差异及最终运行报告见 [机器审计数据](data/data-processing-2026-10.json)。

44 个 wheel 已以提交 `5ea179946a5a86f3e0e353f9f5a6b8960d8ea974` 发布到 `wheels` 分支；远端 44 个 Git blob 与本地审计逐一匹配。发布后分支保留 **730 个 wheel 文件**，包含历史版本；该数值与当前 recipe 版本矩阵数量不同。

[主索引部署](https://github.com/ririv/py-extra-wheels/actions/runs/41173670205)、[旧索引事件同步](https://github.com/ririv/ririv.github.io/actions/runs/41173686135) 和[旧站 Pages 发布](https://github.com/ririv/ririv.github.io/actions/runs/41173695671) 均成功。已核对两处根页、五个包页面和全部 44 个下载链接；主索引状态匹配 wheels Git 树，旧索引状态匹配 gh-pages Git 树。同步链路没有增加扫描任务。
