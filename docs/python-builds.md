# Android Python 构建支持

## Python 版本

构建入口接受 Python `3.10`、`3.11`、`3.12`、`3.13`、`3.14`、`3.15`，默认仍为 `3.13`。版本必须使用 `主版本.次版本` 格式；不接受补丁版本、预发布标识或任意字符串。

按 [Python 官方维护状态](https://devguide.python.org/versions/)，2026 年 10 月仍在维护的稳定版本为 3.11–3.15。3.10 已结束维护，本仓库额外保留其构建能力。

| Python | Android 运行库 | maturin 配置 | 其他构建后端 |
| --- | --- | --- | --- |
| 3.10 | Chaquopy target 3.10.22-0 | 显式 PyO3 配置 | Chaquopy build-wheel |
| 3.11 | Chaquopy target 3.11.17-0 | 显式 PyO3 配置 | Chaquopy build-wheel |
| 3.12 | Chaquopy target 3.12.15-0 | 显式 PyO3 配置 | Chaquopy build-wheel |
| 3.13 | Chaquopy CPython 3.13.15，标准 prefix 布局 | 目标 sysconfigdata | cibuildwheel |
| 3.14 | python.org CPython 3.14.8 | 目标 sysconfigdata | cibuildwheel |
| 3.15 | python.org CPython 3.15.0 | 目标 sysconfigdata | cibuildwheel |

所有版本均面向 `arm64-v8a` 和 `x86_64`，默认 Android API 为 24。Python 运行库版本固定在 [android_python.py](../scripts/build/android_python.py)；不在每次构建时扫描最新标签。更新版本时应同时检查两个 ABI 的归档内容。

## 构建路由

`build-wheels.yml` 从 `recipes/*.toml` 生成包 × Python × ABI 的并行矩阵，规划时固定上游提交 SHA 并校验后端，再调用 `build-android-wheel-dispatch.yml` 编译单个目标。编译前再次核验源码提交和后端，声明与源码不一致时直接失败。配置格式、变更范围选择及 artifact 隔离方式见 [Recipe 与并行构建](recipes.md)。

- maturin 项目由 `build_android_wheel.py` 构建，支持上述全部版本。3.10–3.12 的 Chaquopy target 没有 sysconfigdata，因此使用包含 Python 版本、64 位指针宽度、共享库路径及扩展后缀的 `PYO3_CONFIG_FILE`。3.13–3.15 使用归档内的目标 sysconfigdata。
- 其他后端在 3.10–3.12 上使用固定提交的 [Chaquopy build-wheel](https://github.com/chaquo/chaquopy/blob/6e365e30f7199468d9fffe628fe9f0a7658fdbb3/server/pypi/README-old.md)。包版本由项目后端生成的元数据提供，Git 标签仅用于选择源码。
- 其他后端在 3.13–3.15 上使用 cibuildwheel。其 Android 支持从 Python 3.13 开始。

Chaquopy 构建工具应用仓库内的 `chaquopy-libpython-link.patch`：忽略稳定 ABI 桩库 `libpython3.so` 的普通库别名，只为版本专用库生成 `libpython.so`，避免同时存在两种库时重复创建符号链接。补丁必须适用于固定的上游提交；应用失败会中止构建。

源码项目仍须支持所选 Python 版本。构建器支持某个版本，并不代表任意上游库及其依赖已经适配；例如旧版 PyO3 可能拒绝 Python 3.15。此类错误会直接报告，不启用 `PYO3_USE_ABI3_FORWARD_COMPATIBILITY`，也不修改上游依赖来掩盖兼容性问题。有额外原生依赖的包仍需相应的构建配方或依赖产物。

旧的 `Build CPython for Android` 工作流已删除。当前构建直接使用上表固定的外部运行库，不再维护没有被消费的自建 CPython 产物。

## 缓存与产物

下载按完整补丁版本、构建号和 ABI 缓存，解包目录彼此隔离。下载文件在完成后才重命名；解包与运行库检查成功后才写入完成标记。下载、解包、版本选择或编译失败均直接中止，不更换 Python 版本或下载来源。

maturin 写入明确的本次构建目录。收集阶段要求恰好一个 wheel，不在源码树中递归寻找历史产物。Android 平台标签通过 `wheel tags` 同时写入文件名、`WHEEL` 和 `RECORD`，先保留上游生成的 Python/ABI 标签，再检查实际 ELF 动态依赖：链接 `libpython3.x.so` 的 wheel 只能声明对应的 `cp3x-cp3x`，不能以 `abi3` 承诺跨版本可用。Rust 的 `extension-module` / `abi3` 特性会关闭自动链接，因此由构建配置显式链接目标 Python；随后与 cibuildwheel 共用 auditwheel 修复步骤，将 NDK C++ 等非系统依赖打包进 wheel。

## 本地检查

构建脚本本身需要宿主 Python 3.11 以上，与目标 Python 版本独立。maturin 工作流在隔离的虚拟环境中安装驱动依赖，并通过 `HOST_PYTHON` 指定与目标次版本一致的宿主解释器。

```sh
python -m venv /tmp/android-wheel-tests
. /tmp/android-wheel-tests/bin/activate
python -m pip install tomli-w 'wheel==0.45.1'
python -B -m unittest discover -s scripts/build/tests -v
```

单元测试覆盖运行库来源、版本和 ABI 的缓存隔离、下载失败传播、解包中断后的重建、Cargo 配置组合、环境保留，以及 wheel 标签与内部元数据的一致性。交叉编译成功还需结合 Android 设备或模拟器上的导入与功能测试，才能确认运行时兼容性。

## 本次验证记录

2026-10-28 在 macOS 上完成以下本地验证。GitHub Actions 的运行结果另见仓库 Actions 页面；本次尚未在 Android 设备上执行导入测试。

| 验证项 | 结果 |
| --- | --- |
| 3.10–3.15 × 两种 ABI 的真实运行库下载与解包 | 12 组通过 |
| PyO3 0.29 最小扩展的交叉编译、打包、ELF 架构与 RECORD 校验 | 12 组通过 |
| pydantic-core 2.41.5，3.10/3.11 × 两种 ABI | 4 个 wheel 编译与产物校验通过 |
| xxhash 4.0.2，3.10/arm64-v8a 和 3.12/x86_64 | Chaquopy 构建、修复、打包与产物校验通过 |
| maturin 主脚本完整入口，3.10/arm64-v8a | 通过 |
| 单元测试 | 7 项分别在宿主 Python 3.11 和 3.15 上通过 |
| 修改的工作流与 Python 脚本 | actionlint、Ruff 检查通过 |

Rust 交叉编译使用本机 NDK r29。Chaquopy 的本地验证使用已安装的 NDK r27.0，仅在临时副本中调整其工具链版本；仓库 CI 继续使用上游固定的 r27.3。

原始失败运行使用的 pydantic-core 源码为 `383eb95a19433754c0cecf7025b50c26b6d97a36`。其 PyO3 0.26 在 Python 3.15 下明确报错，最高支持 3.14；该限制已实际复现，需要上游升级 PyO3 后才能构建这个包的 3.15 wheel。
