# Python 完整构建矩阵

本页保留 2026-10-29 的 54 包构建快照。2026-10-31 新增 NumPy 的 8 个目标及双 ABI 运行验证见 [NumPy 与 OpenBLAS](numpy.md)，对应记录单独保存，不改写此前审计数据。

## 构建范围

54 个 recipe 请求 Python 3.10–3.15、Android API 24、`arm64-v8a` 和 `x86_64`。每个包沿用当前 recipe 的源码版本，不为旧 Python 选择较早发行版，不修改上游源码。

原始矩阵为 648 个目标。当前源码的 `Requires-Python` 排除 10 个包的 3.10 组合，共 20 个 ABI 目标；已实际复现的 PyO3 限制排除 pydantic-core、fastuuid 的 3.15 组合，共 4 个 ABI 目标。完整构建计划因此包含 624 个目标。

| Python | 包数 | 双 ABI 目标数 |
| --- | --- | --- |
| 3.10 | 44 | 88 |
| 3.11 | 54 | 108 |
| 3.12 | 54 | 108 |
| 3.13 | 54 | 108 |
| 3.14 | 54 | 108 |
| 3.15 | 52 | 104 |

## 上游限制

fonttools、ormsgpack、Pillow、PyMongo、RapidFuzz、rpds-py、SQLAlchemy、Tornado、websockets、zope.interface 的当前源码要求 Python ≥3.11，因此跳过 3.10。

pydantic-core 当前 Git 提交和 fastuuid 0.14.0 锁定的 PyO3 0.26.0 拒绝 Python 3.15。证据和不可变源码标识存放在 [`build-compatibility.toml`](../build-compatibility.toml)，规划结果记录在 `build-plan.json` 的 `skipped` 中。上游源码更新后旧记录不再匹配，会重新尝试构建。

## 构建与静态验证

- [Python 3.15 预验证](https://github.com/ririv/py-extra-wheels/actions/runs/40713525681)：52 个包、104 个目标全部构建成功。
- [旧版环境回归](https://github.com/ririv/py-extra-wheels/actions/runs/40713528180)：cryptography、xxhash、fonttools 的 3.11/3.12 双 ABI 共 12 个目标成功，下载后验证了来源、哈希、WHEEL/RECORD、实际 ELF 架构、动态依赖闭合、相对加载路径及 16 KB 对齐。
- [主分支 CI](https://github.com/ririv/py-extra-wheels/actions/runs/40720138233)：Python 3.11 与 3.15 各通过 73 项组件测试，以及 Ruff、TOML、工作流与构建工具补丁适用性检查。
- [首次完整矩阵](https://github.com/ririv/py-extra-wheels/actions/runs/40715348884)：620 个目标成功；Pillow 的 3.11/3.12 双 ABI 因旧版环境缺少 NDK zlib 搜索路径失败，未进入发布。
- [Pillow 定向修复验证](https://github.com/ririv/py-extra-wheels/actions/runs/40718723911)：补齐所选 NDK 的系统库搜索路径，原先失败的 4 个目标全部成功；下载后静态复核通过。
- 将上述 620 + 4 个成功产物按原始固定源码计划汇总，每份来源清单必须精确匹配原计划。全部 624 个 wheel 已通过来源、SHA-256、WHEEL/RECORD、实际架构、动态依赖闭合、相对加载路径及 16 KB 对齐检查；不重跑已成功的 620 个目标。其中 612 个 wheel 含 ELF，12 个为既有 PyYAML 配方允许的纯 Python wheel。最终以 [单个发布提交](https://github.com/ririv/py-extra-wheels/commit/81214d693848502c0e11f9709c3ebfa76a3b5405) 原子更新 `wheels`。

[主索引部署](https://github.com/ririv/py-extra-wheels/actions/runs/40731306891) 和 [旧地址同步](https://github.com/ririv/ririv.github.io/actions/runs/40731356410) 均已成功。两处根页及各 54 个包页均返回 HTTP 200，624 个当前矩阵下载链接齐全，状态树与对应 Git 树一致；远端 624 个 wheel 的 Git blob 与核验文件逐字节一致。两个地址为 [主索引](https://ririv.github.io/py-extra-wheels/) 和 [兼容索引](https://ririv.github.io/android-wheels/)。

完整来源、目标、跳过原因、SHA-256、Git blob、ELF 依赖与对齐结果见 [矩阵审计记录](data/python-matrix-2026-10.json)。发布数据由同一固定源码计划下的 620 + 4 个成功产物组成，上传前完整校验；环境重启后从已准备的不可变发布提交重新导出并复核，没有重新编译或改变源码版本。

构建成功和静态检查不等同于设备功能验证；当前尚未在 Android 设备或模拟器上测试完整矩阵。
