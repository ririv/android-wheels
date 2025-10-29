## 报错log
```log
       Running `/home/runner/.rustup/toolchains/stable-x86_64-unknown-linux-gnu/bin/rustc --crate-name orjson --edition=2024 src/lib.rs --error-format=json --json=diagnostic-rendered-ansi,artifacts,future-incompat --crate-type cdylib --emit=dep-info,link -C opt-level=3 -C panic=abort -C lto=fat -C codegen-units=1 --cfg 'feature="default"' --check-cfg 'cfg(docsrs,test)' --check-cfg 'cfg(feature, values("avx512", "cold_path", "default", "generic_simd", "inline_int", "optimize", "unwind", "unwinding"))' -C metadata=d1db575af8d7fc8b --out-dir /home/runner/work/android-wheels/android-wheels/library-source/target/aarch64-linux-android/release/deps --target aarch64-linux-android -C linker=/usr/local/lib/android/sdk/ndk/27.3.13750724/toolchains/llvm/prebuilt/linux-x86_64/bin/aarch64-linux-android24-clang -C strip=debuginfo -L dependency=/home/runner/work/android-wheels/android-wheels/library-source/target/aarch64-linux-android/release/deps -L dependency=/home/runner/work/android-wheels/android-wheels/library-source/target/release/deps --extern associative_cache=/home/runner/work/android-wheels/android-wheels/library-source/target/aarch64-linux-android/release/deps/libassociative_cache-f3de9d5ab36124ee.rlib --extern bytecount=/home/runner/work/android-wheels/android-wheels/library-source/target/aarch64-linux-android/release/deps/libbytecount-2cb07bff1bc6b9c8.rlib --extern bytes=/home/runner/work/android-wheels/android-wheels/library-source/target/aarch64-linux-android/release/deps/libbytes-6bab462990b7b99a.rlib --extern encoding_rs=/home/runner/work/android-wheels/android-wheels/library-source/target/aarch64-linux-android/release/deps/libencoding_rs-5f4d0d9214daf52a.rlib --extern half=/home/runner/work/android-wheels/android-wheels/library-source/target/aarch64-linux-android/release/deps/libhalf-1871943e82680c7a.rlib --extern itoa=/home/runner/work/android-wheels/android-wheels/library-source/target/aarch64-linux-android/release/deps/libitoa-136f3f866bfe1e34.rlib --extern itoap=/home/runner/work/android-wheels/android-wheels/library-source/target/aarch64-linux-android/release/deps/libitoap-60407c202af4b144.rlib --extern jiff=/home/runner/work/android-wheels/android-wheels/library-source/target/aarch64-linux-android/release/deps/libjiff-a6338c591268650f.rlib --extern once_cell=/home/runner/work/android-wheels/android-wheels/library-source/target/aarch64-linux-android/release/deps/libonce_cell-ab2aa730ef3df36b.rlib --extern pyo3=/home/runner/work/android-wheels/android-wheels/library-source/target/aarch64-linux-android/release/deps/libpyo3-4c547259dcf78068.rlib --extern pyo3_ffi=/home/runner/work/android-wheels/android-wheels/library-source/target/aarch64-linux-android/release/deps/libpyo3_ffi-7d569534324c9f44.rlib --extern ryu=/home/runner/work/android-wheels/android-wheels/library-source/target/aarch64-linux-android/release/deps/libryu-250d74e85b294299.rlib --extern serde=/home/runner/work/android-wheels/android-wheels/library-source/target/aarch64-linux-android/release/deps/libserde-c64d9e3053e0fcc0.rlib --extern serde_json=/home/runner/work/android-wheels/android-wheels/library-source/target/aarch64-linux-android/release/deps/libserde_json-667be421edec2ac8.rlib --extern simdutf8=/home/runner/work/android-wheels/android-wheels/library-source/target/aarch64-linux-android/release/deps/libsimdutf8-2f93e745164dfa54.rlib --extern smallvec=/home/runner/work/android-wheels/android-wheels/library-source/target/aarch64-linux-android/release/deps/libsmallvec-d0cf64f0b3866b20.rlib --extern uuid=/home/runner/work/android-wheels/android-wheels/library-source/target/aarch64-linux-android/release/deps/libuuid-c684efd30dd220be.rlib --extern xxhash_rust=/home/runner/work/android-wheels/android-wheels/library-source/target/aarch64-linux-android/release/deps/libxxhash_rust-3d56505fbf2c0e45.rlib -L native=/home/runner/work/android-wheels/android-wheels/library-source/target/aarch64-linux-android/release/build/orjson-0fc44c855f1c42d3/out -L native=/tmp/cibw-run-h69b74gb/cp313-android_arm64_v8a/python/prefix/lib -l static=yyjson --cfg Py_3_7 --cfg Py_3_8 --cfg Py_3_9 --cfg Py_3_10 --cfg Py_3_11 --cfg Py_3_12 --cfg Py_3_13 --cfg CPython --cfg 'feature="inline_int"' --cfg 'feature="avx512"' --check-cfg 'cfg(cold_path)' --check-cfg 'cfg(CPython)' --check-cfg 'cfg(GraalPy)' --check-cfg 'cfg(optimize)' --check-cfg 'cfg(Py_3_10)' --check-cfg 'cfg(Py_3_11)' --check-cfg 'cfg(Py_3_12)' --check-cfg 'cfg(Py_3_13)' --check-cfg 'cfg(Py_3_14)' --check-cfg 'cfg(Py_3_15)' --check-cfg 'cfg(Py_3_9)' --check-cfg 'cfg(Py_GIL_DISABLED)' --check-cfg 'cfg(PyPy)'`
  error: This macro cannot be used on the current target.
                                     You can prevent it from being used in other architectures by
                                     guarding it behind a cfg(any(target_arch = "x86", target_arch = "x86_64")).
    --> src/str/pystr.rs:33:12
     |
  33 |         if std::is_x86_feature_detected!("avx512vl") {
     |            ^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^
     |
     = note: this error originates in the macro `std::is_x86_feature_detected` (in Nightly builds, run with -Z macro-backtrace for more info)
  
  error[E0432]: unresolved import `core::arch::x86_64`
   --> src/str/avx512.rs:5:17
    |
  5 | use core::arch::x86_64::{
    |                 ^^^^^^ could not find `x86_64` in `arch`
  
  error: the feature named `avx512f` is not valid for this target
    --> src/str/avx512.rs:11:18
     |
  11 | #[target_feature(enable = "avx512f,avx512bw,avx512vl,bmi2")]
     |                  ^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^ `avx512f` is not valid for this target
  
  error: the feature named `avx512bw` is not valid for this target
    --> src/str/avx512.rs:11:18
     |
  11 | #[target_feature(enable = "avx512f,avx512bw,avx512vl,bmi2")]
     |                  ^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^ `avx512bw` is not valid for this target
  
  error: the feature named `avx512vl` is not valid for this target
    --> src/str/avx512.rs:11:18
     |
  11 | #[target_feature(enable = "avx512f,avx512bw,avx512vl,bmi2")]
     |                  ^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^ `avx512vl` is not valid for this target
  
  error: the feature named `bmi2` is not valid for this target
    --> src/str/avx512.rs:11:18
     |
  11 | #[target_feature(enable = "avx512f,avx512bw,avx512vl,bmi2")]
     |                  ^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^ `bmi2` is not valid for this target
  
  For more information about this error, try `rustc --explain E0432`.
  error: could not compile `orjson` (lib) due to 6 previous errors
  
  Caused by:
    process didn't exit successfully: `/home/runner/.rustup/toolchains/stable-x86_64-unknown-linux-gnu/bin/rustc --crate-name orjson --edition=2024 src/lib.rs --error-format=json --json=diagnostic-rendered-ansi,artifacts,future-incompat --crate-type cdylib --emit=dep-info,link -C opt-level=3 -C panic=abort -C lto=fat -C codegen-units=1 --cfg 'feature="default"' --check-cfg 'cfg(docsrs,test)' --check-cfg 'cfg(feature, values("avx512", "cold_path", "default", "generic_simd", "inline_int", "optimize", "unwind", "unwinding"))' -C metadata=d1db575af8d7fc8b --out-dir /home/runner/work/android-wheels/android-wheels/library-source/target/aarch64-linux-android/release/deps --target aarch64-linux-android -C linker=/usr/local/lib/android/sdk/ndk/27.3.13750724/toolchains/llvm/prebuilt/linux-x86_64/bin/aarch64-linux-android24-clang -C strip=debuginfo -L dependency=/home/runner/work/android-wheels/android-wheels/library-source/target/aarch64-linux-android/release/deps -L dependency=/home/runner/work/android-wheels/android-wheels/library-source/target/release/deps --extern associative_cache=/home/runner/work/android-wheels/android-wheels/library-source/target/aarch64-linux-android/release/deps/libassociative_cache-f3de9d5ab36124ee.rlib --extern bytecount=/home/runner/work/android-wheels/android-wheels/library-source/target/aarch64-linux-android/release/deps/libbytecount-2cb07bff1bc6b9c8.rlib --extern bytes=/home/runner/work/android-wheels/android-wheels/library-source/target/aarch64-linux-android/release/deps/libbytes-6bab462990b7b99a.rlib --extern encoding_rs=/home/runner/work/android-wheels/android-wheels/library-source/target/aarch64-linux-android/release/deps/libencoding_rs-5f4d0d9214daf52a.rlib --extern half=/home/runner/work/android-wheels/android-wheels/library-source/target/aarch64-linux-android/release/deps/libhalf-1871943e82680c7a.rlib --extern itoa=/home/runner/work/android-wheels/android-wheels/library-source/target/aarch64-linux-android/release/deps/libitoa-136f3f866bfe1e34.rlib --extern itoap=/home/runner/work/android-wheels/android-wheels/library-source/target/aarch64-linux-android/release/deps/libitoap-60407c202af4b144.rlib --extern jiff=/home/runner/work/android-wheels/android-wheels/library-source/target/aarch64-linux-android/release/deps/libjiff-a6338c591268650f.rlib --extern once_cell=/home/runner/work/android-wheels/android-wheels/library-source/target/aarch64-linux-android/release/deps/libonce_cell-ab2aa730ef3df36b.rlib --extern pyo3=/home/runner/work/android-wheels/android-wheels/library-source/target/aarch64-linux-android/release/deps/libpyo3-4c547259dcf78068.rlib --extern pyo3_ffi=/home/runner/work/android-wheels/android-wheels/library-source/target/aarch64-linux-android/release/deps/libpyo3_ffi-7d569534324c9f44.rlib --extern ryu=/home/runner/work/android-wheels/android-wheels/library-source/target/aarch64-linux-android/release/deps/libryu-250d74e85b294299.rlib --extern serde=/home/runner/work/android-wheels/android-wheels/library-source/target/aarch64-linux-android/release/deps/libserde-c64d9e3053e0fcc0.rlib --extern serde_json=/home/runner/work/android-wheels/android-wheels/library-source/target/aarch64-linux-android/release/deps/libserde_json-667be421edec2ac8.rlib --extern simdutf8=/home/runner/work/android-wheels/android-wheels/library-source/target/aarch64-linux-android/release/deps/libsimdutf8-2f93e745164dfa54.rlib --extern smallvec=/home/runner/work/android-wheels/android-wheels/library-source/target/aarch64-linux-android/release/deps/libsmallvec-d0cf64f0b3866b20.rlib --extern uuid=/home/runner/work/android-wheels/android-wheels/library-source/target/aarch64-linux-android/release/deps/libuuid-c684efd30dd220be.rlib --extern xxhash_rust=/home/runner/work/android-wheels/android-wheels/library-source/target/aarch64-linux-android/release/deps/libxxhash_rust-3d56505fbf2c0e45.rlib -L native=/home/runner/work/android-wheels/android-wheels/library-source/target/aarch64-linux-android/release/build/orjson-0fc44c855f1c42d3/out -L native=/tmp/cibw-run-h69b74gb/cp313-android_arm64_v8a/python/prefix/lib -l static=yyjson --cfg Py_3_7 --cfg Py_3_8 --cfg Py_3_9 --cfg Py_3_10 --cfg Py_3_11 --cfg Py_3_12 --cfg Py_3_13 --cfg CPython --cfg 'feature="inline_int"' --cfg 'feature="avx512"' --check-cfg 'cfg(cold_path)' --check-cfg 'cfg(CPython)' --check-cfg 'cfg(GraalPy)' --check-cfg 'cfg(optimize)' --check-cfg 'cfg(Py_3_10)' --check-cfg 'cfg(Py_3_11)' --check-cfg 'cfg(Py_3_12)' --check-cfg 'cfg(Py_3_13)' --check-cfg 'cfg(Py_3_14)' --check-cfg 'cfg(Py_3_15)' --check-cfg 'cfg(Py_3_9)' --check-cfg 'cfg(Py_GIL_DISABLED)' --check-cfg 'cfg(PyPy)'` (exit status: 1)
  error: `cargo rustc --lib --message-format=json-render-diagnostics --manifest-path Cargo.toml --target aarch64-linux-android --release -v --features pyo3/extension-module --crate-type cdylib --` failed with code 101
  
  ERROR Backend subprocess exited when trying to invoke build_wheel
```


## issues
https://github.com/ijl/orjson/issues/603

## Rust 1.89 对于 AVX512 的行为
https://releases.rs/docs/1.89.0/
https://blog.rust-lang.org/2025/08/07/Rust-1.89.0/


## orsjon 相关文件
https://github.com/ijl/orjson/blob/master/build.rs
https://github.com/ijl/orjson/blob/master/src/str/avx512.rs
https://github.com/ijl/orjson/blob/master/src/str/pystr.rs
