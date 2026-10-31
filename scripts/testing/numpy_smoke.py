"""Exercise Android NumPy's BLAS, LAPACK and concurrent numerical operations."""

import ctypes
import json
import os
import sys
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path

import numpy as np


def check_dtype(dtype: str) -> None:
    a = np.array([[4, 1, 2], [1, 5, 1], [2, 1, 6]], dtype=dtype)
    x = np.array([1, 2, 3], dtype=dtype)
    if np.iscomplexobj(a):
        a[0, 1] += 1j
        a[1, 0] -= 1j
        x += np.array([1j, -2j, 3j], dtype=dtype)
    b = a @ x
    tolerance = 3e-5 if a.real.dtype.itemsize == 4 else 1e-11

    def close(actual, expected):
        np.testing.assert_allclose(actual, expected, rtol=tolerance, atol=tolerance)

    # 独立逐项计算，避免用相同 BLAS 调用生成期望值。
    close(b, [sum(a[i, j] * x[j] for j in range(3)) for i in range(3)])
    close(np.linalg.solve(a, b), x)
    close(a @ np.linalg.inv(a), np.eye(3))
    values, vectors = np.linalg.eig(a)
    close(a @ vectors, vectors * values)
    values, vectors = np.linalg.eigh(a)
    close(a @ vectors, vectors * values)
    u, s, vh = np.linalg.svd(a)
    close((u * s) @ vh, a)
    q, r = np.linalg.qr(a)
    close(q @ r, a)
    lower = np.linalg.cholesky(a)
    close(lower @ lower.conj().T, a)
    rectangular = np.vstack([a, a * 2])
    solution, _, rank, _ = np.linalg.lstsq(rectangular, rectangular @ x, rcond=None)
    close(solution, x)
    assert rank == 3
    close(np.fft.ifft(np.fft.fft(x)), x)


def check_concurrent(seed: int) -> None:
    random = np.random.default_rng(seed)
    a = random.normal(size=(128, 128))
    a = a.T @ a + np.eye(128)
    x = random.normal(size=128)
    np.testing.assert_allclose(np.linalg.solve(a, a @ x), x, rtol=1e-10, atol=1e-10)


def main() -> None:
    assert hasattr(sys, "getandroidapilevel"), "运行测试必须在 Android 上执行"
    config = np.show_config(mode="dicts")
    for name in ("blas", "lapack"):
        dependency = config["Build Dependencies"][name]
        assert dependency["found"] and dependency["name"] == "openblas", dependency
    mapped = {
        line.split()[-1]
        for line in Path("/proc/self/maps").read_text().splitlines()
        if "openblas" in line and ".so" in line
    }
    assert len(mapped) == 1, mapped
    library = ctypes.CDLL(mapped.pop())
    library.openblas_get_config.restype = ctypes.c_char_p
    openblas = library.openblas_get_config().decode()
    assert "USE64BITINT" not in openblas, openblas
    assert "NO_LAPACK" not in openblas, openblas
    wide = np.finfo(np.longdouble)
    assert np.dtype(np.longdouble).itemsize == 16 and wide.nmant == 112, wide
    one = np.longdouble(1)
    increment = np.ldexp(one, -100)
    assert (one + increment) - one == increment
    for dtype in ("float32", "float64", "complex64", "complex128"):
        check_dtype(dtype)
    with ThreadPoolExecutor(max_workers=4) as executor:
        list(executor.map(check_concurrent, range(8)))
    print(
        json.dumps(
            {
                "numpy": np.__version__,
                "python": sys.version,
                "python_minimum_api": sys.getandroidapilevel(),
                "page_size": os.sysconf("SC_PAGE_SIZE"),
                "machine": os.uname().machine,
                "openblas": openblas,
                "openblas_threads": library.openblas_get_num_threads(),
                "longdouble_mantissa_bits": wide.nmant,
                "dtypes": ["float32", "float64", "complex64", "complex128"],
                "operations": [
                    "matmul",
                    "solve",
                    "inv",
                    "eig",
                    "eigh",
                    "svd",
                    "qr",
                    "cholesky",
                    "lstsq",
                    "fft",
                    "concurrent_solve",
                ],
                "result": "passed",
            },
            indent=2,
        ),
        flush=True,
    )


if __name__ == "__main__":
    main()
