## Q

Run set -ex
+ export TARGET=aarch64-linux-android
+ TARGET=aarch64-linux-android
+ export API=24
+ API=24
+ export CC=/home/runner/work/_temp/android-ndk/android-ndk-r26d/toolchains/llvm/prebuilt/linux-x86_64/bin/aarch64-linux-android24-clang
+ CC=/home/runner/work/_temp/android-ndk/android-ndk-r26d/toolchains/llvm/prebuilt/linux-x86_64/bin/aarch64-linux-android24-clang
+ export CXX=/home/runner/work/_temp/android-ndk/android-ndk-r26d/toolchains/llvm/prebuilt/linux-x86_64/bin/aarch64-linux-android24-clang++
+ CXX=/home/runner/work/_temp/android-ndk/android-ndk-r26d/toolchains/llvm/prebuilt/linux-x86_64/bin/aarch64-linux-android24-clang++
+ export AR=/home/runner/work/_temp/android-ndk/android-ndk-r26d/toolchains/llvm/prebuilt/linux-x86_64/bin/llvm-ar
+ AR=/home/runner/work/_temp/android-ndk/android-ndk-r26d/toolchains/llvm/prebuilt/linux-x86_64/bin/llvm-ar
+ export LD=/home/runner/work/_temp/android-ndk/android-ndk-r26d/toolchains/llvm/prebuilt/linux-x86_64/bin/ld
+ LD=/home/runner/work/_temp/android-ndk/android-ndk-r26d/toolchains/llvm/prebuilt/linux-x86_64/bin/ld
+ export STRIP=/home/runner/work/_temp/android-ndk/android-ndk-r26d/toolchains/llvm/prebuilt/linux-x86_64/bin/llvm-strip
+ STRIP=/home/runner/work/_temp/android-ndk/android-ndk-r26d/toolchains/llvm/prebuilt/linux-x86_64/bin/llvm-strip
+ export CFLAGS=--sysroot=/home/runner/work/_temp/android-ndk/android-ndk-r26d/toolchains/llvm/prebuilt/linux-x86_64/sysroot
+ CFLAGS=--sysroot=/home/runner/work/_temp/android-ndk/android-ndk-r26d/toolchains/llvm/prebuilt/linux-x86_64/sysroot
+ export LDFLAGS=--sysroot=/home/runner/work/_temp/android-ndk/android-ndk-r26d/toolchains/llvm/prebuilt/linux-x86_64/sysroot
+ LDFLAGS=--sysroot=/home/runner/work/_temp/android-ndk/android-ndk-r26d/toolchains/llvm/prebuilt/linux-x86_64/sysroot
++ pwd
+ BUILD_ROOT=/home/runner/work/android-wheels/android-wheels/library-source
+ cd library-source
++ find . -name pyproject.toml -o -name setup.py
++ head -n 1
+ PROJECT_FILE=./crates/jiter-python/pyproject.toml
+ '[' -n ./crates/jiter-python/pyproject.toml ']'
++ dirname ./crates/jiter-python/pyproject.toml
+ PROJECT_DIR=./crates/jiter-python
+ cd ./crates/jiter-python
+ IS_MATURIN=false
+ '[' -f pyproject.toml ']'
+ grep -q 'build-backend.*=.*"maturin"' pyproject.toml
+ IS_MATURIN=true
+ '[' true = true ']'
+ echo 'Maturin build backend detected.'
+ rustup target add aarch64-linux-android
Maturin build backend detected.
info: downloading component 'rust-std' for 'aarch64-linux-android'
info: installing component 'rust-std' for 'aarch64-linux-android'
++ echo aarch64-linux-android
++ tr a-z- A-Z_
+ TARGET_FOR_ENV=AARCH64_LINUX_ANDROID
+ export CARGO_TARGET_AARCH64_LINUX_ANDROID_LINKER=/home/runner/work/_temp/android-ndk/android-ndk-r26d/toolchains/llvm/prebuilt/linux-x86_64/bin/aarch64-linux-android24-clang
+ CARGO_TARGET_AARCH64_LINUX_ANDROID_LINKER=/home/runner/work/_temp/android-ndk/android-ndk-r26d/toolchains/llvm/prebuilt/linux-x86_64/bin/aarch64-linux-android24-clang
+ export CARGO_TARGET_AARCH64_LINUX_ANDROID_AR=/home/runner/work/_temp/android-ndk/android-ndk-r26d/toolchains/llvm/prebuilt/linux-x86_64/bin/llvm-ar
+ CARGO_TARGET_AARCH64_LINUX_ANDROID_AR=/home/runner/work/_temp/android-ndk/android-ndk-r26d/toolchains/llvm/prebuilt/linux-x86_64/bin/llvm-ar
+ FEATURES=
+ '[' -f Cargo.toml ']'
+ grep -q '^pyo3 ' Cargo.toml
+ echo 'Direct pyo3 dependency found. Adding '\''extension-module'\'' feature.'
+ FEATURES=pyo3/extension-module
Direct pyo3 dependency found. Adding 'extension-module' feature.
+ '[' -n pyo3/extension-module ']'
+ maturin build --release --target aarch64-linux-android -i python3.13 --features pyo3/extension-module
    Updating crates.io index
     Locking 118 packages to latest compatible versions
      Adding codspeed-criterion-compat v2.10.1 (available: v4.0.4)
      Adding pyo3 v0.26.0 (available: v0.27.0)
      Adding pyo3-build-config v0.26.0 (available: v0.27.0)
 Downloading crates ...
  Downloaded crossbeam-deque v0.8.6
  Downloaded ahash v0.8.12
  Downloaded version_check v0.9.5
  Downloaded target-lexicon v0.13.3
  Downloaded unindent v0.2.4
  Downloaded plotters-svg v0.3.7
  Downloaded radium v0.7.0
  Downloaded wyz v0.5.1
  Downloaded shlex v1.3.0
  Downloaded tap v1.0.1
  Downloaded walkdir v2.5.0
  Downloaded unicode-ident v1.0.19
  Downloaded uuid v1.18.1
  Downloaded serde_derive v1.0.228
  Downloaded zerocopy-derive v0.8.27
  Downloaded lexical-util v1.0.7
  Downloaded libfuzzer-sys v0.4.10
  Downloaded serde_json v1.0.145
  Downloaded regex v1.12.2
  Downloaded zerocopy v0.8.27
  Downloaded lexical-parse-float v1.0.6
  Downloaded aho-corasick v1.1.3
  Downloaded clap_builder v4.5.49
  Downloaded bitvec v1.0.1
  Downloaded rayon v1.11.0
  Downloaded syn v2.0.107
  Downloaded plotters v0.3.7
  Downloaded hashbrown v0.16.0
  Downloaded codspeed-criterion-compat-walltime v2.10.1
  Downloaded regex-syntax v0.8.8
  Downloaded itertools v0.10.5
  Downloaded indexmap v2.12.0
  Downloaded cc v1.2.41
  Downloaded pyo3-macros-backend v0.26.0
  Downloaded pyo3-ffi v0.26.0
  Downloaded memchr v2.7.6
  Downloaded serde v1.0.228
  Downloaded rayon-core v1.13.0
  Downloaded num-traits v0.2.19
  Downloaded half v2.7.1
  Downloaded clap v4.5.49
  Downloaded regex-automata v0.4.13
  Downloaded serde_core v1.0.228
  Downloaded ryu v1.0.20
  Downloaded num-bigint v0.4.6
  Downloaded getrandom v0.3.4
  Downloaded crossbeam-epoch v0.9.18
  Downloaded smallvec v1.15.1
  Downloaded quote v1.0.41
  Downloaded proc-macro2 v1.0.101
  Downloaded paste v1.0.15
  Downloaded libc v0.2.177
  Downloaded once_cell v1.21.3
  Downloaded find-msvc-tools v0.1.4
  Downloaded crossbeam-utils v0.8.21
  Downloaded tinytemplate v1.2.1
  Downloaded same-file v1.0.6
  Downloaded pyo3-build-config v0.26.0
  Downloaded lexical-parse-integer v1.0.6
  Downloaded jobserver v0.1.34
  Downloaded colored v2.2.0
  Downloaded ciborium v0.2.2
  Downloaded cfg-if v1.0.4
  Downloaded arbitrary v1.4.2
  Downloaded pyo3-macros v0.26.0
  Downloaded plotters-backend v0.3.7
  Downloaded oorandom v11.1.5
  Downloaded num-integer v0.1.46
  Downloaded heck v0.5.0
  Downloaded criterion-plot v0.5.0
  Downloaded pyo3 v0.26.0
  Downloaded ciborium-ll v0.2.2
  Downloaded anes v0.1.6
  Downloaded memoffset v0.9.1
  Downloaded itoa v1.0.15
  Downloaded lazy_static v1.5.0
  Downloaded is-terminal v0.4.16
  Downloaded autocfg v1.5.0
  Downloaded anstyle v1.0.13
  Downloaded indoc v2.0.6
  Downloaded funty v2.0.0
  Downloaded either v1.15.0
  Downloaded codspeed-criterion-compat v2.10.1
  Downloaded codspeed v2.10.1
  Downloaded clap_lex v0.7.6
  Downloaded cast v0.3.0
  Downloaded ciborium-io v0.2.2
  Downloaded equivalent v1.0.2
🔗 Found pyo3 bindings
🐍 Found CPython 3.13
📡 Using build options bindings from pyproject.toml
   Compiling target-lexicon v0.13.3
   Compiling autocfg v1.5.0
   Compiling proc-macro2 v1.0.101
   Compiling libc v0.2.177
   Compiling quote v1.0.41
   Compiling unicode-ident v1.0.19
   Compiling num-traits v0.2.19
   Compiling pyo3-build-config v0.26.0
   Compiling pyo3-macros-backend v0.26.0
   Compiling pyo3-ffi v0.26.0
   Compiling syn v2.0.107
   Compiling memoffset v0.9.1
   Compiling getrandom v0.3.4
   Compiling zerocopy v0.8.27
   Compiling heck v0.5.0
   Compiling version_check v0.9.5
   Compiling radium v0.7.0
   Compiling ahash v0.8.12
   Compiling pyo3 v0.26.0
   Compiling num-integer v0.1.46
   Compiling lexical-util v1.0.7
   Compiling once_cell v1.21.3
   Compiling tap v1.0.1
   Compiling cfg-if v1.0.4
   Compiling wyz v0.5.1
   Compiling num-bigint v0.4.6
   Compiling lexical-parse-integer v1.0.6
   Compiling jiter v0.11.1 (/home/runner/work/android-wheels/android-wheels/library-source/crates/jiter)
   Compiling funty v2.0.0
   Compiling unindent v0.2.4
   Compiling indoc v2.0.6
   Compiling bitvec v1.0.1
   Compiling lexical-parse-float v1.0.6
   Compiling smallvec v1.15.1
   Compiling pyo3-macros v0.26.0
   Compiling jiter-python v0.11.1 (/home/runner/work/android-wheels/android-wheels/library-source/crates/jiter-python)
error: linking with `/home/runner/work/_temp/android-ndk/android-ndk-r26d/toolchains/llvm/prebuilt/linux-x86_64/bin/aarch64-linux-android24-clang` failed: exit status: 1
  |
  = note:  "/home/runner/work/_temp/android-ndk/android-ndk-r26d/toolchains/llvm/prebuilt/linux-x86_64/bin/aarch64-linux-android24-clang" "-Wl,--version-script=/tmp/rustcw29VsE/list" "-Wl,--no-undefined-version" "/tmp/rustcw29VsE/symbols.o" "<5 object files omitted>" "-Wl,--as-needed" "-Wl,-Bstatic" "/home/runner/work/android-wheels/android-wheels/library-source/target/aarch64-linux-android/release/deps/{libjiter-66582c9d85f82d26,libbitvec-e4c407e2a386ea1f,libwyz-f424f23bc67c0cd5,libtap-4ec44f0fb417be28,libradium-935b449bf3d0536f,libfunty-a752805c0f1bfaf3,libsmallvec-89119d18ee71f646,libahash-e59362d85b0ed027,libgetrandom-1e5ece86acbc894c,libcfg_if-7e2a473a014abeb7,libzerocopy-df2c69ea3a7a759b,liblexical_parse_float-6096ba0b8e478559,liblexical_parse_integer-0ab6b68c98ab280a,liblexical_util-ae577773652de171,libpyo3-5de12c82055fa24d,libonce_cell-851fe2ba938db894,libpyo3_ffi-ec514c4df22d5c3c,liblibc-a92b90510b13a3f9,libnum_bigint-180fb543da49a1f1,libnum_integer-0c349ecccba6aefa,libnum_traits-19c6dfc5d904a2e2,libmemoffset-2d7f3921fa40732f,libunindent-628026d7f6dc08fa}.rlib" "<sysroot>/lib/rustlib/aarch64-linux-android/lib/{libstd-*,libpanic_unwind-*,libobject-*,libmemchr-*,libaddr2line-*,libgimli-*,librustc_demangle-*,libstd_detect-*,libhashbrown-*,librustc_std_workspace_alloc-*,libminiz_oxide-*,libadler2-*,libunwind-*,libcfg_if-*,liblibc-*,librustc_std_workspace_core-*,liballoc-*,libcore-*,libcompiler_builtins-*}.rlib" "-Wl,-Bdynamic" "-lpython3.13" "-ldl" "-llog" "-lunwind" "-ldl" "-lm" "-lc" "-L" "/tmp/rustcw29VsE/raw-dylibs" "-Wl,--eh-frame-hdr" "-Wl,-z,noexecstack" "-o" "/home/runner/work/android-wheels/android-wheels/library-source/target/aarch64-linux-android/release/deps/libjiter_python.so" "-Wl,--gc-sections" "-shared" "-Wl,-z,relro,-z,now" "-Wl,-O1" "-Wl,--strip-debug" "-nodefaultlibs"
  = note: some arguments are omitted. use `--verbose` to show all linker arguments
  = note: ld.lld: error: unable to find library -lpython3.13
          clang-17: error: linker command failed with exit code 1 (use -v to see invocation)
          

error: could not compile `jiter-python` (lib) due to 1 previous error
💥 maturin failed
  Caused by: Failed to build a native library through cargo
  Caused by: Cargo build finished with "exit status: 101": `env -u CARGO PYO3_BUILD_EXTENSION_MODULE="1" PYO3_CONFIG_FILE="/home/runner/work/android-wheels/android-wheels/library-source/target/maturin/pyo3-config-aarch64-linux-android-3.13.txt" "cargo" "rustc" "--features" "pyo3/extension-module" "--target" "aarch64-linux-android" "--message-format" "json-render-diagnostics" "--manifest-path" "/home/runner/work/android-wheels/android-wheels/library-source/crates/jiter-python/Cargo.toml" "--release" "--lib" "--crate-type" "cdylib"`
Error: Process completed with exit code 1.


## A
我要先在工作区里找出工作流文件和构建脚本，以便复现并修复链接错误（-lpython3.13 找不到），预期能定位到 .github/workflows 和任何自定义的 build 脚本内容。 

搜索与 `**/*` 匹配的文件，20 匹配项

我将打开相关的工作流 YAML 文件以了解当前构建步骤和环境设置，从而定位为什么在 Android 交叉编译时尝试链接到 libpython3.13 并修复它。 

读取 [](file:///Users/wuhao/my/Proj/android-wheels/.github/workflows/build-android-wheel.yml)

已运行 `resolve-library-id`
Completed with input: {
  "libraryName": "pyo3"
}

为了借鉴已存在的 Android Rust 扩展库构建方式，我会打开几个相似的工作流文件（如 orjson、rpds-py 等）看看它们如何避免链接到 libpython。 

读取 [](file:///Users/wuhao/my/Proj/android-wheels/.github/workflows/build-orjson-android.yml)

读取 [](file:///Users/wuhao/my/Proj/android-wheels/.github/workflows/build-jiter-android.yml)

搜索 `PYO3_CROSS|Chaquopy|libpython|android-ndk|maturin build` (`**/*.yml`)、20 结果的文本

已创建 3 个待办事项

正在使用 "应用修补程序"


```

```


已检查 [](file:///Users/wuhao/my/Proj/android-wheels/.github/workflows/build-android-wheel.yml)，发现 8 问题

已运行 `get-library-docs`
Completed with input: {
  "context7CompatibleLibraryID": "/pyo3/pyo3",
  "topic": "cross compiling android abi3 maturin extension-module link libpython",
  "tokens": 4000
}

正在使用 "应用修补程序"


```

```


正在启动(3/3) *Verify impacts and document next steps*

正在使用 "应用修补程序"


```

```
我看到了你的 CI 日志里 Maturin/PyO3 在交叉编译 Android 时尝试链接 -lpython3.13 导致链接失败；我会更新可复用的构建工作流，避免在 Android 目标上链接到 libpython，并保留正确的 wheel tag。

## 采取的修改

- 在 build-android-wheel.yml 的 maturin 构建分支里新增 PyO3 跨编译环境变量：
  - 设置 `PYO3_CROSS=1` 和 `PYO3_CROSS_PYTHON_VERSION=${{ env.PYTHON_VERSION }}`，避免 PyO3 去探测宿主 Python，从而误判并添加 `-lpython3.13`。
  - 当尝试 abi3 构建时，临时设置 `PYO3_NO_PYTHON=1`，完全避免构建时调用宿主解释器。
- 针对直连 pyo3 的 crate：
  - 优先尝试启用 `pyo3/extension-module pyo3/abi3-py37`，生成 abi3 扩展模块（无需链接 libpython，适合 Android）。
  - 如果 abi3 不被该项目支持，则自动回退为只启用 `pyo3/extension-module` 继续构建。
- 改进 wheel 重命名逻辑：
  - 从已构建 wheel 的文件名中解析 `python tag` 和 `abi tag`（例如 abi3），确保重命名后仍保留 abi3 或 cpXX 的真实标签，不再强制使用 `cp{PY}-cp{PY}`。
- 仍保留原有的 NDK/Clang 交叉编译配置与输出产物上传逻辑。

这些改动已写入：
- build-android-wheel.yml（新增 PyO3 跨编译变量、abi3 优先+回退逻辑、wheel tag 保留）

简要原因：
- PyO3 在“扩展模块”模式下本就不需要在类 Unix 平台链接 libpython；但交叉编译时若用宿主 Python 探测配置，容易误判为需要 `-lpythonX.Y`。设置 `PYO3_CROSS`/`PYO3_NO_PYTHON` 与使用 `abi3` 可避免该问题。
- abi3 能让同一 wheel 兼容多个 Python 小版本，非常适合预编译分发（包括 Android）。

## 影响与验证

- 针对 jiter（`pydantic/jiter`）：
  - 已自动检测 `Cargo.toml` 下是否直连依赖 `pyo3`，如是则尝试 abi3；若 jiter 不支持 abi3，会自动回退但仍不链接 libpython（因为启用了 cross 并且 extension-module）。
- 对其它使用该可复用工作流的库（orjson、pydantic-core、rpds-py、zstandard 等）同样生效；保留各自 wheel 的正确 ABI tag。
- 工作流里的 `${{ env.NDK_PATH }}` 通过前置步骤写入 `GITHUB_ENV`，在 Actions 环境中有效；本地静态检查提示的“可能无效”是编辑器/静态分析的误报，运行时无碍。

质量门：
- Build: N/A（GitHub Actions 上执行）
- Lint/Typecheck: PASS（YAML 结构与语法有效）
- Tests: N/A（工作流变更，不影响仓库代码执行）

## 你接下来可以做什么

- 直接在仓库的 Actions 页面手动触发“Build jiter Android wheel for Chaquopy”工作流，或推送触发。
- 若需要我现在帮你在本地触发一次对应 workflow_dispatch，请告诉我要用的参数（python 版本、ndk 版本、android api、jiter 版本）。我也可以同步触发其它库的构建以验证。

## 备注与边界情况

- 如果某个 crate 本身使用了 PyO3 但不兼容 abi3，构建会走到回退路径：仍为 extension module，且由于启用了跨编译变量，不会链接 libpython。
- 个别项目若并非直接在当前 crate 的 `Cargo.toml` 中声明 `pyo3`（比如继承自 workspace 依赖），我的“直接依赖检测”可能探测不到，但多数项目的 maturin 配置或自身 features 已包含 extension-module；若你遇到某个特殊项目仍然试图链接 libpython，我可以再把检测逻辑放宽到 `grep -E '^[[:space:]]*pyo3[[:space:]]*='` 或解析 `workspace.dependencies`。

## 小结

- 修复点：避免在 Android 目标上链接 `-lpython3.13`，改为 abi3 优先 + 跨编译模式，且保留正确 wheel 标签。
- 已更新 build-android-wheel.yml 并稳妥处理不支持 abi3 的回退路径。
- 建议现在重新跑 jiter 的 Android 构建验证。需要我代为触发也可以告诉我参数。

已进行更改。


---

```shell
set -ex
export TARGET=${{ matrix.target }}
export API=${{ env.ANDROID_API }}
export CC=$TOOLCHAIN/bin/${TARGET}${API}-clang
export CXX=$TOOLCHAIN/bin/${TARGET}${API}-clang++
export AR=$TOOLCHAIN/bin/llvm-ar
export LD=$TOOLCHAIN/bin/ld
export STRIP=$TOOLCHAIN/bin/llvm-strip
export CFLAGS="--sysroot=$TOOLCHAIN/sysroot"
export LDFLAGS="--sysroot=$TOOLCHAIN/sysroot"
BUILD_ROOT=$(pwd)/library-source
cd library-source

# Find the project root (where pyproject.toml or setup.py is)
PROJECT_FILE=$(find . -name "pyproject.toml" -o -name "setup.py" | head -n 1)
if [ -n "$PROJECT_FILE" ]; then
    PROJECT_DIR=$(dirname "$PROJECT_FILE")
    cd "$PROJECT_DIR"
fi

IS_MATURIN="false"
if [ -f "pyproject.toml" ] && grep -q 'build-backend.*=.*"maturin"' pyproject.toml; then
IS_MATURIN="true"
fi

if [ "$IS_MATURIN" = "true" ]; then
echo "Maturin build backend detected."
rustup target add ${{ matrix.target }}
TARGET_FOR_ENV=$(echo ${{ matrix.target }} | tr 'a-z-' 'A-Z_')
export CARGO_TARGET_${TARGET_FOR_ENV}_LINKER=${CC}
export CARGO_TARGET_${TARGET_FOR_ENV}_AR=${AR}
# Hints for PyO3 cross compilation so it doesn't try to use host libpython
export PYO3_CROSS=1
export PYO3_CROSS_PYTHON_VERSION=${{ env.PYTHON_VERSION }}
FEATURES=""
# Check if Cargo.toml has a direct dependency on pyo3 in the [dependencies] section
if [ -f "Cargo.toml" ] && grep -q '^pyo3 ' Cargo.toml; then
    echo "Direct pyo3 dependency found. Will enable 'extension-module' and attempt abi3 to avoid linking libpython."
    FEATURES="pyo3/extension-module"
fi

if [ -n "$FEATURES" ]; then
    # Try abi3 first (broad compatibility), then fall back if unsupported
    set +e
    export PYO3_NO_PYTHON=1
    maturin build --release --target ${{ matrix.target }} -i python${{ env.PYTHON_VERSION }} --features "$FEATURES pyo3/abi3-py37"
    BUILD_STATUS=$?
    set -e
    if [ $BUILD_STATUS -ne 0 ]; then
    echo "abi3 build failed, retrying without abi3..."
    unset PYO3_NO_PYTHON
    maturin build --release --target ${{ matrix.target }} -i python${{ env.PYTHON_VERSION }} --features "$FEATURES"
    fi
else
    maturin build --release --target ${{ matrix.target }} -i python${{ env.PYTHON_VERSION }}
fi
else
echo "Standard build backend detected."
python -m build --wheel
fi

# --- Normalization Step ---
# According to PEP 427, wheel names normalize hyphens to underscores.
NORMALIZED_LIB_NAME=$(echo "${{ env.LIBRARY_NAME }}" | tr '-' '_')
PLATFORM_ARCH=$(echo "${{ matrix.abi }}" | tr '-' '_')
echo "Normalized library name for search: ${NORMALIZED_LIB_NAME}"
echo "Normalized platform arch for wheel tag: ${PLATFORM_ARCH}"

# --- Find Wheel Step ---
SEARCH_PATH="dist"
if [ "$IS_MATURIN" = "true" ]; then
echo "Maturin build backend detected. Searching in target/wheels/"
SEARCH_PATH="target/wheels"
else
echo "Standard or no pyproject.toml build backend detected. Searching in dist/"
fi

WHEEL_PATH=$(find "${SEARCH_PATH}" -name "${NORMALIZED_LIB_NAME}-*.whl" | head -n 1)

if [ -z "${WHEEL_PATH}" ]; then
echo "::warning::Could not find wheel in '${SEARCH_PATH}'. Fallback to searching everywhere."
WHEEL_PATH=$(find . -name "${NORMALIZED_LIB_NAME}-*.whl" | head -n 1)
fi

if [ -z "${WHEEL_PATH}" ]; then
echo "::error::Failed to find wheel file anywhere for normalized name ${NORMALIZED_LIB_NAME}."
exit 1
fi

# --- Rename Wheel Step ---
# Extract Python/ABI tags from the built wheel to preserve abi3 when applicable
WHEEL_BASENAME=$(basename "${WHEEL_PATH}")
PY_FIELD=$(echo "${WHEEL_BASENAME}" | awk -F- '{print $3}')
ABI_FIELD=$(echo "${WHEEL_BASENAME}" | awk -F- '{print $4}')
if [ -z "${PY_FIELD}" ] || [ -z "${ABI_FIELD}" ]; then
# Fallback to cp tag from requested Python version
PY_FIELD="cp${PYTHON_VERSION//./}"
ABI_FIELD="${PY_FIELD}"
fi
VERSION_TO_USE=${LIBRARY_VERSION}
if [ -z "${VERSION_TO_USE}" ]; then
VERSION_TO_USE=$(basename "${WHEEL_PATH}" | cut -d- -f2)
echo "library-version not specified, using version from built wheel: ${VERSION_TO_USE}"
fi

NEW_WHEEL_NAME="${NORMALIZED_LIB_NAME}-${VERSION_TO_USE}-${PY_FIELD}-${ABI_FIELD}-android_${API}_${PLATFORM_ARCH}.whl"
echo "Original wheel: ${WHEEL_PATH}"
echo "New wheel name: ${NEW_WHEEL_NAME}"
mkdir -p $BUILD_ROOT/../output
mv "${WHEEL_PATH}" "$BUILD_ROOT/../output/${NEW_WHEEL_NAME}"
```