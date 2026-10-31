"""Exercise SciPy's BLAS, sparse, spatial, signal and Fortran paths on Android."""

import json
import os
import sys

import numpy as np
import scipy
from scipy import (
    fft,
    integrate,
    interpolate,
    linalg,
    ndimage,
    odr,
    optimize,
    signal,
    sparse,
    spatial,
    special,
    stats,
)
from scipy.sparse.linalg import spsolve


def main() -> None:
    assert hasattr(sys, "getandroidapilevel"), "运行检查必须在 Android 上执行"
    config = scipy.show_config(mode="dicts")
    for name in ("blas", "lapack"):
        assert config["Build Dependencies"][name]["name"] == "openblas"
    matrix = np.array([[4.0, 1.0], [1.0, 3.0]])
    expected = np.array([2.0, -1.0])
    rhs = matrix @ expected
    np.testing.assert_allclose(linalg.solve(matrix, rhs), expected)
    np.testing.assert_allclose(linalg.inv(matrix) @ rhs, expected)
    np.testing.assert_allclose(spsolve(sparse.csr_matrix(matrix), rhs), expected)
    values = np.array([1.0, 2.0, 3.0, 4.0])
    np.testing.assert_allclose(fft.ifft(fft.fft(values)).real, values)
    area, _ = integrate.quad(np.sin, 0, np.pi)
    np.testing.assert_allclose(area, 2.0)
    root = optimize.root(lambda x: matrix @ x - rhs, [0.0, 0.0])
    assert root.success
    np.testing.assert_allclose(root.x, expected)
    np.testing.assert_allclose(special.erf(0.0), 0.0)
    np.testing.assert_allclose(
        special.loggamma(1.0 + 1.0j),
        -0.650923199301856 + -0.301640320467533j,
        rtol=1e-12,
    )
    np.testing.assert_allclose(stats.norm.cdf(0.0), 0.5)
    np.testing.assert_allclose(signal.convolve([1, 2], [1, 1]), [1, 3, 2])
    image = np.zeros((9, 9))
    image[4, 4] = 1
    np.testing.assert_allclose(ndimage.gaussian_filter(image, 1).sum(), 1.0)
    spline = interpolate.CubicSpline([0, 1, 2], [0, 1, 4])
    np.testing.assert_allclose(spline(1.5), 2.25)
    tree = spatial.cKDTree([[0, 0], [1, 1], [3, 3]])
    distance, index = tree.query([0.9, 1.0])
    assert index == 1
    np.testing.assert_allclose(distance, 0.1)
    assert spatial.Delaunay([[0, 0], [1, 0], [0, 1], [1, 1]]).simplices.shape == (2, 3)
    x = np.arange(5, dtype=float)
    regression = odr.ODR(
        odr.RealData(x, 2 * x + 3),
        odr.Model(lambda beta, x: beta[0] * x + beta[1]),
        beta0=[1.0, 1.0],
    ).run()
    np.testing.assert_allclose(regression.beta, [2.0, 3.0], rtol=1e-8)
    print(
        json.dumps(
            {
                "python": sys.version,
                "python_minimum_api": sys.getandroidapilevel(),
                "machine": os.uname().machine,
                "page_size": os.sysconf("SC_PAGE_SIZE"),
                "versions": {"numpy": np.__version__, "scipy": scipy.__version__},
                "checks": [
                    "openblas",
                    "lapack",
                    "solve",
                    "inverse",
                    "sparse_solve",
                    "fft",
                    "quadrature",
                    "root",
                    "special_complex",
                    "statistics",
                    "convolution",
                    "image_filter",
                    "interpolation",
                    "kdtree",
                    "delaunay",
                    "fortran_odr",
                ],
                "result": "passed",
            },
            indent=2,
        ),
        flush=True,
    )


if __name__ == "__main__":
    main()
