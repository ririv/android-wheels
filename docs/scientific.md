# 科学计算与绘图依赖栈

## 收录范围

本批使用当前 PyPI 官方发行版，不修改包源码，也不选择旧版本。三个包仍位于既有原生扩展下载量前 100 的筛选范围内；核查时 PyPI 没有对应的官方 Android wheel。

| 包 | 版本 | 上游最低 Python | 用途 |
| --- | --- | --- | --- |
| ContourPy | 1.4.0 | 3.12 | 二维等值线 |
| pandas | 3.1.0 | 3.11 | 表格、CSV、分组聚合和时间序列 |
| Matplotlib | 3.11.2 | 3.11 | Agg 绘图及 PNG、SVG、PDF 导出 |

本仓库当前 NumPy 2.5.4 要求 Python ≥3.12；当前 ContourPy 也要求 ≥3.12。因此三个 recipe 显式选择 Python **3.12–3.15**，Android API **24**，`arm64-v8a` 与 `x86_64`，共 **24 个目标**。不为 3.10/3.11 降级依赖，也不把这些组合列为可用的完整依赖栈。

## 构建配置

三个包均使用 Meson 后端及仓库现有 Android cross file。Python 3.12 使用 Chaquopy，3.13–3.15 使用 cibuildwheel；包 × Python × ABI 仍各自在独立 runner 并行。

pandas 通过 `PIP_EXTRA_INDEX_URL` 显式加入本仓库索引。cibuildwheel 的 `xbuild-files` 使用与宿主 NumPy 相同版本的 Android wheel，提供目标 `_numpyconfig.h`、`numpyconfig.h` 和原生静态库；构建钩子继续在宿主解释器上运行。目标 wheel 缺失时直接失败。

Matplotlib 使用其官方 sdist 内已有的依赖配置，构建 FreeType 2.14.3、HarfBuzz 14.1.0、SheenBidi 3.0.0、libraqm 0.10.5、Qhull 8.0.2，以及发行源码自带的 Agg。外部源码的地址、SHA-256 及上游提供的构建适配由该发行版的 Meson wrap 固定；本仓库没有额外的源码补丁。默认后端通过 `-DrcParams-backend=Agg` 设置，`-Dmacosx=false`，并限制 Ninja 并行为两个任务。

本批复用了已经发布的 NumPy、Pillow、fonttools、kiwisolver；纯 Python 运行依赖直接使用官方 wheel，测试用版本、地址和 SHA-256 固定在 `scripts/testing/scientific-pure-dependencies.json`。

## 捆绑库许可证

原始 Matplotlib wheel 仅携带主许可证，未包含全部捆绑库的许可文件。因此打包阶段补入发行源码和上述原生库原始压缩包中的 **24 个文件**，同时写入 `.dist-info/bundled-libraries.json`。

`scripts/build/bundled-licenses.toml` 将配置绑定到 Matplotlib sdist SHA-256，逐项固定压缩包与许可文件哈希。来源变化时必须显式更新配置。补充文件位于 `.dist-info/licenses/bundled/`，不改变扩展或动态库字节；RECORD 重新生成，发布阶段再次核验内容和来源。

`repackage-wheels.yml` 复用编译成功的 artifact。默认要求输入计划的完整并集；需要只采用某次运行的部分包时，使用 `recipe_selections` 明确给出运行编号到包名列表的 JSON 对象。未选中的失败试构建不进入最终计划，同名不同来源的目标仍会报错。不会因构建失败而自动挑选其他版本或产物。

## Android 运行检查

`scripts/testing/android_runtime.py` 通过明确的构建计划和 artifact 安装原生依赖；纯 Python wheel 必须给出 SHA-256。安装前验证 wheel、RECORD、目标版本与 ABI，并按 Android 环境标记核对传递依赖是否齐全。安装只读取已验证的本地文件，不联网解析依赖。

`scripts/testing/scientific_smoke.py` 在 Android API 34、CPython 3.13 的双 ABI 上检查：

- ContourPy 的单线程、多线程等值线与填充区域。
- pandas 的 CSV 往返、groupby、merge、rolling、NumPy 转换、可空整数、日期解析、分类编码和排名。
- Matplotlib 的 Agg 绘图、FreeType 文字、Qhull 三角剖分和 constrained layout。
- PNG 实际解码与像素内容、SVG XML 解析、PDF 文件标识。

`verify-scientific-android.yml` 仅按需运行 x86_64 模拟器检查；ARM64 使用本机专用模拟器。没有定时扫描。本次不覆盖 GUI 集成、上游完整测试集、pandas 的可选文件格式后端或性能评测。3.12、3.14、3.15 的证据为构建和静态检查；16 KB 页仅检查 ELF 对齐，运行模拟器为 4 KB 页。

## 构建与发布记录

24 个目标全部成功，最终产物共含 **456 个 ELF 文件**：ContourPy 16、pandas 368、Matplotlib 72。全部通过来源、SHA-256、WHEEL/RECORD、目标架构、16 KB 对齐、依赖闭合、相对加载路径和许可证检查。

补入许可证后逐文件对比：8 个 Matplotlib wheel 原有文件仅 RECORD 改变，增加 24 个许可文件和一份来源清单；其余 16 个 wheel 字节完全不变。最终 Python 3.13 双 ABI 运行报告与最终 wheel 哈希匹配。

| 证据 | 运行 |
| --- | --- |
| ContourPy 3.13 双 ABI | [41163226911](https://github.com/ririv/py-extra-wheels/actions/runs/41163226911)，该次 pandas 失败，最终仅显式采用 ContourPy |
| Matplotlib 3.13 双 ABI | [41163243230](https://github.com/ririv/py-extra-wheels/actions/runs/41163243230) |
| pandas 3.13 双 ABI | [41163413379](https://github.com/ririv/py-extra-wheels/actions/runs/41163413379)，配置 NumPy 目标索引后通过 |
| 三个包 3.12 双 ABI | [41163728071](https://github.com/ririv/py-extra-wheels/actions/runs/41163728071) |
| 三个包 3.14/3.15 双 ABI | [41163819544](https://github.com/ririv/py-extra-wheels/actions/runs/41163819544) |
| 最终重打包与校验 | [41164261117](https://github.com/ririv/py-extra-wheels/actions/runs/41164261117) |
| 最终 x86_64 组合运行检查 | [41164415351](https://github.com/ririv/py-extra-wheels/actions/runs/41164415351) |
| CI | [41164815545](https://github.com/ririv/py-extra-wheels/actions/runs/41164815545)，Python 3.11/3.15 各 87 项测试，以及 Ruff、TOML、actionlint、工具补丁检查 |

完整来源、逐个 wheel 的 SHA-256、Git blob、ELF 检查、双 ABI 运行报告及发布记录见 [机器审计数据](data/scientific-2026-10.json)。

24 个 wheel 已以提交 `a8d35c6bebeeb1a6468f71c66649b1eebce77f3d` 发布到 `wheels` 分支。远端 24 个 Git blob 与本地审计一致；主索引部署 [41164751647](https://github.com/ririv/py-extra-wheels/actions/runs/41164751647)、旧索引同步 [41164768939](https://github.com/ririv/ririv.github.io/actions/runs/41164768939) 及其 Pages 发布均成功。

已确认新旧索引的根目录、三个包的页面和全部 24 个下载链接；主索引状态等于 `wheels` Git 树，旧索引状态等于 `gh-pages` Git 树。本批发布后仓库保留 686 个 wheel 文件，包含历史版本；该数值与当前 recipe 版本矩阵的数量不同。
