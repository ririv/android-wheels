"""Exercise contour generation, DataFrame kernels and headless plotting on Android."""

import io
import json
import os
import shutil
import sys
import tempfile
import xml.etree.ElementTree as ET
from pathlib import Path

# 必须先设置可写字体缓存目录，再加载 Matplotlib。
# ruff: noqa: E402

assert hasattr(sys, "getandroidapilevel"), "运行检查必须在 Android 上执行"
os.environ["MPLCONFIGDIR"] = tempfile.mkdtemp(prefix="matplotlib-")
os.environ["MPLBACKEND"] = "Agg"

import contourpy
import matplotlib
import numpy as np
import pandas as pd
from matplotlib import pyplot as plt
from PIL import Image


def check_contours() -> None:
    z = np.array([[0.0, 1.0], [1.0, 2.0]])
    for name in ("serial", "threaded"):
        generator = contourpy.contour_generator(z=z, name=name)
        lines = generator.lines(1.0)
        assert len(lines) == 1
        np.testing.assert_allclose(np.sort(lines[0], axis=0), [[0.0, 0.0], [1.0, 1.0]])
        assert len(generator.filled(0.5, 1.5)) == 2


def check_dataframe() -> None:
    frame = pd.read_csv(io.StringIO("group,value\na,1\nb,2\na,3\nb,4\n"))
    assert frame.groupby("group")["value"].sum().to_dict() == {"a": 4, "b": 6}
    labels = pd.DataFrame({"group": ["a", "b"], "label": ["first", "second"]})
    merged = frame.merge(labels, on="group").sort_values("value")
    assert merged["label"].tolist() == ["first", "second", "first", "second"]
    assert pd.read_csv(io.StringIO(merged.to_csv(index=False))).equals(
        merged.reset_index(drop=True)
    )
    np.testing.assert_allclose(frame["value"].rolling(2).mean()[1:], [1.5, 2.5, 3.5])
    np.testing.assert_allclose(
        frame["value"].astype(float).to_numpy() * 2, [2, 4, 6, 8]
    )
    nullable = pd.Series([1, None, 3], dtype="Int64")
    assert nullable.sum() == 4 and nullable.isna().sum() == 1
    dates = pd.to_datetime(["2026-10-31T00:00:00Z", "2026-11-01T00:00:00Z"])
    assert (dates[1] - dates[0]).days == 1
    assert pd.Categorical(["a", "b", "a"]).codes.tolist() == [0, 1, 0]
    assert frame["value"].rank().tolist() == [1.0, 2.0, 3.0, 4.0]


def check_plotting() -> dict:
    assert matplotlib.get_backend().lower() == "agg"
    figure, axes = plt.subplots(1, 2, figsize=(6, 3), layout="constrained")
    x = np.linspace(-1, 1, 16)
    xx, yy = np.meshgrid(x, x)
    axes[0].contourf(xx, yy, xx * xx + yy * yy)
    axes[0].set_title("Contour and text")
    # 三角剖分覆盖 Qhull；文字和 constrained layout 覆盖字体栅格化与 kiwi。
    axes[1].tricontourf(
        [0.0, 1.0, 0.0, 1.0, 0.5], [0.0, 0.0, 1.0, 1.0, 0.5], [0.0, 1.0, 1.0, 2.0, 0.5]
    )
    axes[1].set_title("Triangulation")
    outputs = {}
    for format in ("png", "svg", "pdf"):
        buffer = io.BytesIO()
        figure.savefig(buffer, format=format)
        content = buffer.getvalue()
        assert len(content) > 1000
        outputs[format] = len(content)
        if format == "png":
            with Image.open(io.BytesIO(content)) as image:
                image.load()
                assert image.size == (600, 300)
                assert np.asarray(image).std() > 10
        elif format == "svg":
            assert ET.fromstring(content).tag == "{http://www.w3.org/2000/svg}svg"
        else:
            assert content.startswith(b"%PDF-")
    plt.close(figure)
    return outputs


def main() -> None:
    check_contours()
    check_dataframe()
    outputs = check_plotting()
    print(
        json.dumps(
            {
                "python": sys.version,
                "python_minimum_api": sys.getandroidapilevel(),
                "machine": os.uname().machine,
                "page_size": os.sysconf("SC_PAGE_SIZE"),
                "versions": {
                    name: module.__version__
                    for name, module in [
                        ("numpy", np),
                        ("contourpy", contourpy),
                        ("pandas", pd),
                        ("matplotlib", matplotlib),
                    ]
                },
                "checks": [
                    "serial_contours",
                    "threaded_contours",
                    "csv",
                    "groupby",
                    "merge",
                    "rolling",
                    "nullable_integer",
                    "datetime",
                    "categorical",
                    "rank",
                    "agg",
                    "freetype_text",
                    "qhull_triangulation",
                    "constrained_layout",
                    "png_decode",
                    "svg_parse",
                    "pdf_signature",
                ],
                "output_bytes": outputs,
                "result": "passed",
            },
            indent=2,
        ),
        flush=True,
    )
    shutil.rmtree(Path(os.environ["MPLCONFIGDIR"]))


if __name__ == "__main__":
    main()
