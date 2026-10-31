# 机器学习、Arrow 与 PostgreSQL 扩展

## 收录范围

继续使用原生扩展下载量前 100 的快照，加入当前 PyPI 发行版。选取时核对了 PyPI 全部发行记录，三个包均未提供官方 Android wheel。只调整外部环境、构建参数与目标 SDK，不修改上游源码，不为旧 Python 降级包版本。

| 原生名次 | 包 | 当前版本 | Python | Android 目标 |
| --- | --- | --- | --- | --- |
| 20 | PyArrow | 26.0.0 | 3.12–3.15 | API 26，双 ABI |
| 34 | psycopg2-binary | 2.9.13 | 3.10–3.15 | API 26，双 ABI |
| 38 | scikit-learn | 1.9.1 | 3.12–3.15 | API 26，仅 ARM64 |

双 ABI 指 `arm64-v8a` 和 `x86_64`。PyArrow、scikit-learn 上游支持 Python ≥3.11，但当前 NumPy 2.5.4 要求 ≥3.12。scikit-learn 依赖的当前 SciPy 只提供 ARM64，限制原因见 [科学计算与数据处理扩展](data-processing.md)。

## 外部构建配置

scikit-learn 使用原始 Meson 后端，保留 OpenMP，通过 NDK 提供 LLVM OpenMP 运行库。没有关闭并行算法或改为纯 Python。旧构建器从实际目标编译器的 `--print-search-dirs` 输出获取运行库目录，供 auditwheel 发现 `libomp.so`，不硬编码 LLVM 版本目录。

PyArrow 使用当前官方 `scikit_build_core.build` 后端。Arrow C++ 26.0.0 与 OpenSSL 3.5.9 的源码 URL、SHA-256、构建参数和许可证固定在原生依赖 TOML。启用 Compute、CSV、JSON、Dataset、Acero、文件系统、Parquet、Parquet 加密，以及 Snappy、gzip、Zstandard、LZ4、Brotli；使用通用 CPU 配置，不声明 Flight 或云端对象存储能力。

Arrow C++ 使用上游 `BUILD_TZ_LIB` 编译宏。`nl_langinfo` 等接口要求 API 26，因此两个 ABI 都显式选择 API 26。CMake superbuild 的独立工具链文件固定 ABI、API、共享 C++ 运行库与 16 KB 配置，使其嵌套依赖保持相同目标。安装阶段剥离调试信息，并显式允许版本化 SONAME，使 Python wheel 中的文件名与原生依赖匹配，避免重复捆绑。

PyArrow 的版本检测通过 `SETUPTOOLS_SCM_PRETEND_VERSION_FOR_PYARROW=26.0.0` 绑定所选发行版，避免读取外层构建仓库的 Git 元数据。外部 CMake 文件分别提供实际目标 SDK 前缀和 Android 的 `$ORIGIN` 加载路径支持。auditwheel 修复前补齐包内唯一依赖的相对搜索路径，避免把已捆绑的 Arrow 库再次作为外部库复制；原搜索路径保留到外部库发现完成，最终再清理宿主路径。不改写上游 CMakeLists。绑定的 `build-dir` 显式位于声明的构建树内，使旧构建器保留生成头文件的搜索路径。

psycopg2-binary 使用原始 setuptools 后端，链接 PostgreSQL 18.6 的 libpq 与共享 OpenSSL 3.5.9。原生依赖构建只安装客户端库和头文件，不交叉编译数据库服务器。宿主 `pg_config` 只查询固定版本、目标头文件与库目录，未知查询直接失败；路径从自身位置计算，复制到目标前缀后仍有效。宿主工具放在 `host-tools/bin`，避免执行目标架构的 OpenSSL 程序。libpq 的 locale 接口要求 API 26。

## 原生 SDK 缓存

cibuildwheel 与旧版 Chaquopy 在后端探测依赖前准备原生 SDK，并在成功后立即缓存。缓存键覆盖原生依赖的固定配置、ABI、API、NDK、CMake、make、宿主架构、目标环境、安装位置和原生构建实现，不包含 Python 版本。

缓存遵循 GitHub 的分支作用域；没有可访问缓存时显式编译。命中缓存时核对完整文件清单、SHA-256、权限和符号链接；不匹配直接失败。没有模糊缓存键或校验失败后继续构建的分支。不同 Python 版本继续各自独立构建绑定，矩阵并行保持不变。Chaquopy 与 cibuildwheel 通过相同安装模块，将已校验 SDK 复制到各自的目标 Python 前缀。

## 许可证与运行检查

Arrow、OpenSSL、libpq 的许可证与来源元数据随 wheel 分发。scikit-learn 和 PyArrow 还携带固定 NDK r27d 的原始 `NOTICE.toolchain` 与来源清单，覆盖 LLVM OpenMP 和 C++ 运行库。对已编译 scikit-learn 的补充仅新增许可材料及清单、更新 RECORD，原有文件逐字节保持一致。

`learning` 套件组合已发布的 NumPy、SciPy 与固定纯 Python 依赖，验证 OpenMP 开启及双线程、标准化、分类流水线、概率、KMeans、PCA、随机森林、梯度提升、SVM、稀疏逻辑回归、KDTree 与 joblib 保存加载。

`analytics` 套件组合已发布的 NumPy、pandas，检查五种压缩编码、Arrow 聚合、Parquet、Dataset 过滤、IPC、CSV、NumPy 零拷贝、pandas 中文数据、夏令时时区以及 Parquet 加密往返。测试 KMS 仅用于格式往返验证，不作为生产密钥管理实现。

PostgreSQL 检查连接隔离的测试服务器，强制 `sslmode=verify-full`，验证测试 CA 与服务器身份；再检查 UTF-8、JSONB、保存点回滚、Decimal、UUID、数组参数和 COPY。测试服务只在按需运行的 analytics 验证任务中启动，不增加定时任务。设备资源部署逐文件检查哈希，拒绝覆盖运行程序；只部署公开测试证书与临时连接配置，不部署服务器私钥。

## 构建与发布记录

24 个目标全部构建并发布，包含 **532 个 ELF 文件**。完整目标与当前三个 TOML 逐项匹配；源码与文件哈希、版本、标签、RECORD、架构、16 KB 对齐、动态依赖闭合、相对加载路径及许可证均通过核验。所有 PyArrow wheel 均未重复捆绑 Arrow/Parquet 库。

20 个最终 wheel 与原始构建产物字节相同；4 个 scikit-learn wheel 仅补充许可证、来源清单并更新 RECORD，原有文件载荷逐字节不变。

最终机器学习套件在 Android API 34 ARM64 上通过 Python 3.13、3.14、3.15 各 13 项检查；Arrow/PostgreSQL 套件在相同环境通过三个 Python 版本各 15 项检查，并在 Python 3.13 x86_64 上通过同样 15 项检查。七份报告的测试脚本与已安装 wheel 哈希均与最终文件匹配。PostgreSQL 检查均使用 libpq 18.6、服务器 18.6、证书校验与 TLS 1.3。

其他 Python/ABI 组合的证据为构建与静态检查。模拟器为 4 KB 页；16 KB 支持只核验 ELF 加载段，尚未在 16 KB 页设备执行。没有执行上游完整测试集或性能评测。

| 证据 | 运行 |
| --- | --- |
| scikit-learn、psycopg2-binary 最终统一打包 | [41192407958](https://github.com/ririv/py-extra-wheels/actions/runs/41192407958) |
| PyArrow 8 个目标完整构建 | [41194396863](https://github.com/ririv/py-extra-wheels/actions/runs/41194396863) |
| PyArrow 最终统一打包 | [41194725058](https://github.com/ririv/py-extra-wheels/actions/runs/41194725058) |
| x86_64 Android 数据连接套件 | [41194846083](https://github.com/ririv/py-extra-wheels/actions/runs/41194846083) |
| 最终代码 CI | [41194400012](https://github.com/ririv/py-extra-wheels/actions/runs/41194400012)，Python 3.11、3.15 各 102 项组件测试，及 Ruff、TOML、actionlint 和构建工具补丁检查 |

ARM64 检查在本机专用模拟器执行。全部来源、原始构建运行、逐个 ELF 核验、许可补充差异、缓存命中、七份最终运行报告与发布状态见 [机器审计数据](data/analytics-2026-10.json)。

24 个 wheel 已通过提交 `2785bc5240a97b54513fc65ca4c99b194ae83d0e` 发布到 `wheels` 分支，远端 24 个 Git blob 与本地审计一致。仓库现有 **66 个 recipe**；发布分支保留 **754 个 wheel 文件**，包含历史版本。

[主索引部署](https://github.com/ririv/py-extra-wheels/actions/runs/41195395686)、[旧索引事件同步](https://github.com/ririv/ririv.github.io/actions/runs/41195411429) 与[旧站 Pages 发布](https://github.com/ririv/ririv.github.io/actions/runs/41195424583) 均成功。两处根页、三个新增包页与全部 24 个下载链接已核对；公开状态分别匹配 wheels 与 gh-pages Git 树。没有新增定时扫描。
