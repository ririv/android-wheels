# NumPy 与 OpenBLAS

## 构建范围

NumPy 2.5.4 使用 PyPI 官方 sdist，OpenBLAS 固定为 0.3.34，两个源码包均校验 SHA-256。没有修改上游源码，没有使用较早的 NumPy 版本，也没有关闭 BLAS/LAPACK。

recipe 请求 Python 3.10–3.15；当前 NumPy 声明 `Requires-Python >=3.12`，因此跳过 3.10、3.11。Python 3.12–3.15 各构建 Android API 24 的 `arm64-v8a`、`x86_64` wheel，共 8 个目标。

## 外部构建配置

- OpenBLAS 使用 CMake 与 Android NDK，显式选择 LP64、上游附带的 C 版 LAPACK、CBLAS 和 LAPACKE；不需要 Fortran 编译器或 Fortran 动态运行库。
- ARM 使用 ARMV8 目标，x86_64 使用符合 Android x86-64-v2 基线的 NEHALEM 目标。使用 pthread，最多支持 8 个 OpenBLAS 工作线程，不引入 OpenMP。
- NumPy 明确设置 `blas=openblas`、`lapack=openblas`、`use-ilp64=false`、`allow-noblas=false`。PEP 517 数组参数逐项传递，保留每个参数的边界。
- 仓库中的 Meson cross file 声明 Android 机器属性和 `longdouble_format='IEEE_QUAD_LE'`，避免在宿主上执行 Android 探测程序。两个 64 位 Android ABI 的 `long double` 都是小端 IEEE binary128，不能沿用 Linux x86_64 的扩展精度格式。
- `{abi}` 在规划时替换，`{workspace}` 在构建时解析为明确的仓库根路径；Chaquopy 切换工作目录后仍使用同一根路径。
- OpenBLAS 和 C++ 共享运行库通过共用的 wheel repair 打包；OpenBLAS 的许可证和固定来源清单一同写入 wheel。
- wheel repair 还会清理 Meson 留下的构建机绝对 RPATH/RUNPATH，保留 `$ORIGIN` 相对路径并重新生成 RECORD；发布校验拒绝不可移植的搜索路径。

配置入口为 [`recipes/numpy.toml`](../recipes/numpy.toml)、[`native-libraries.toml`](../scripts/build/native-libraries.toml) 和 [`Meson 配置目录`](../scripts/build/meson)。此处使用 NumPy 官方支持的 [cross file 接口](https://numpy.org/doc/stable/building/cross_compilation.html)；机器格式依据 [Android ABI 规范](https://developer.android.com/ndk/guides/abis)。

## 构建记录

- [Python 3.13 双 ABI](https://github.com/ririv/py-extra-wheels/actions/runs/41158539798)：两个目标成功。
- [Python 3.14、3.15 双 ABI](https://github.com/ririv/py-extra-wheels/actions/runs/41158984712)：四个目标成功。同次运行中 3.12 的配置路径错误已在下面的定向验证中修复，不重新构建已成功的四个目标。
- [Python 3.12 定向验证](https://github.com/ririv/py-extra-wheels/actions/runs/41159165854)：修正旧构建器切换目录后的配置路径，两个目标成功。
- [流水线 CI](https://github.com/ririv/py-extra-wheels/actions/runs/41160689247)：Python 3.11、3.15 各通过 79 项测试，以及 Ruff、TOML、工作流和构建工具补丁适用性检查。

最终审计发现原始 wheel 中部分扩展保留了构建机 `/tmp/...` 路径。通过 [仅重新打包的工作流](https://github.com/ririv/py-extra-wheels/actions/runs/41160688726) 复用上述 8 个成功产物：先核对原构建计划、目标和输入 SHA-256，再清理路径、重新生成 RECORD 并完整校验。没有重新编译，输入和输出哈希及逐文件路径变更保存在审计记录中。后续构建会在共用 repair 阶段自动完成相同处理。

发布前按照同一组固定源码目标汇总，核验产物来源、SHA-256、WHEEL/RECORD、ELF 架构、动态依赖闭合、相对加载路径和 16 KB 加载段对齐。各 wheel 的目标、哈希和逐个 ELF 结果见 [审计记录](data/numpy-2026-10.json)。

## Android 运行验证

Python 3.13 的两个最终修复产物在 Android API 34 模拟器中通过检查：arm64 使用本地独立模拟器，x86_64 使用 [GitHub KVM 验证工作流](https://github.com/ririv/py-extra-wheels/actions/runs/41160801916)。两份报告的 wheel 哈希均与重新打包后的待发布文件一致。测试前重新核验构建计划、来源清单、wheel 哈希、内部元数据和 ELF 对齐；测试环境不预装 OpenBLAS 或 C++ 运行库，使用 wheel 中携带的库。

检查包含 float32、float64、complex64、complex128 的矩阵乘法、方程求解、求逆、特征值分解、SVD、QR、Cholesky、最小二乘和 FFT，以及四个 Python 线程并发调用数值运算。另检查实际加载的 OpenBLAS 为 LP64，并验证 `long double` 的 16 字节存储、112 位显式尾数和超过 float64 的实际运算精度。

模拟器使用 4 KB 页；16 KB 页仅完成 ELF 静态对齐检查。运行检查通过 adb 部署独立 Python 启动器，未覆盖嵌入式应用加载流程、上游完整测试集或性能基准。3.12、3.14、3.15 的本次结果限于构建和静态校验。

## 发布与索引

8 个最终 wheel 已在 [发布提交](https://github.com/ririv/py-extra-wheels/commit/b9da31b3c73d111609c01d962dfa982e0a812c08) 中原子上传；远端 Git blob 与经过运行和静态验证的文件一致。

[主索引部署](https://github.com/ririv/py-extra-wheels/actions/runs/41161674103) 和 [旧地址事件同步](https://github.com/ririv/ririv.github.io/actions/runs/41161692479) 成功。两处根页与 NumPy 包页均返回 HTTP 200，8 个下载链接齐全，分别位于 [主包索引](https://ririv.github.io/py-extra-wheels/numpy/) 与 [兼容包索引](https://ririv.github.io/android-wheels/numpy/)。主站通过 `index-state.json` 标记 wheels 源码树，旧站通过 `sync-state.json` 标记同步的主站 Pages 树。

## 按需复验

构建使用现有入口，不触发其他包：

```sh
gh workflow run build-wheels.yml \
  -f recipes=numpy \
  -f python_versions=3.13 \
  -f publication=build
```

构建完成后，将运行编号传给独立的 x86_64 模拟器验证入口：

```sh
gh workflow run verify-numpy-android.yml -f build_run=<build-run-id>
```

该工作流只接受手动触发，没有定时扫描。输出的 JSON 包含 wheel、测试脚本和 Python 运行归档的哈希、设备信息及数值测试结果。

需要仅修复已有构建的打包问题时，可使用 `repackage-wheels.yml` 的 `build_runs` 输入。多个输入运行的目标定义必须完全一致，成功产物的并集必须覆盖所有计划目标；缺失、额外目标或冲突内容会失败。产物采用 `repackaged-wheels` 布局，运行验证时显式选择 `artifact_layout=repackaged`。
