"""Exercise native geometry, analytical SQL, DataFrames and Thrift on Android."""

import importlib.metadata
import json
import os
import sys
import tempfile
from pathlib import Path

import _duckdb
import duckdb
import numpy as np
import pandas as pd
import polars as pl
import shapely
from shapely import Point, STRtree, box
from thrift.protocol import TBinaryProtocol, TCompactProtocol, fastbinary
from thrift.Thrift import TType
from thrift.transport.TTransport import TMemoryBuffer


def check_geometry() -> None:
    assert shapely.geos_version_string == "3.15.0"
    left, right = box(0, 0, 2, 2), box(1, 1, 3, 3)
    assert left.intersection(right).area == 1
    assert left.union(right).area == 7
    assert left.difference(right).area == 3
    assert 3.0 < Point(0, 0).buffer(1).area < 3.2
    points = shapely.points([0.5, 2.5, 9], [0.5, 2.5, 9])
    np.testing.assert_array_equal(shapely.contains(left, points), [True, False, False])
    tree = STRtree([left, right])
    assert sorted(tree.query(Point(1.5, 1.5), predicate="intersects").tolist()) == [
        0,
        1,
    ]
    assert tree.nearest(Point(2.75, 2.75)) == 1
    assert shapely.from_wkb(shapely.to_wkb(left)).equals(left)
    assert shapely.from_wkt(shapely.to_wkt(left)).equals(left)


def check_database(root: Path) -> None:
    path = root / "database.duckdb"
    with duckdb.connect(
        str(path),
        config={
            "temp_directory": str(root / "duckdb-tmp"),
            "autoinstall_known_extensions": False,
            "autoload_known_extensions": False,
        },
    ) as connection:
        for extension in ("json", "parquet", "icu"):
            connection.execute("LOAD " + extension).fetchall()
        assert connection.execute(
            "select i % 3 as k, sum(i) from range(10) t(i) group by k order by k"
        ).fetchall() == [(0, 18), (1, 12), (2, 15)]
        connection.execute(
            "create table sample as select i, i * 2 as value from range(10) t(i)"
        )
        parquet = root / "data.parquet"
        connection.execute(f"copy sample to '{parquet}' (format parquet)")
        assert connection.execute(
            "select sum(value) from read_parquet(?)", [str(parquet)]
        ).fetchall() == [(90,)]
        assert connection.execute(
            """select json_extract('{"a": 3}', '$.a')::integer"""
        ).fetchall() == [(3,)]
        assert connection.execute(
            "select year(timestamptz '2026-10-31 00:00:00 UTC')"
        ).fetchall() == [(2026,)]
        connection.register(
            "frame", pd.DataFrame({"key": ["a", "a", "b"], "value": [1, 2, 4]})
        )
        result = connection.execute(
            "select key, sum(value)::bigint as total from frame group by key order by key"
        ).df()
        assert result.to_dict("list") == {"key": ["a", "b"], "total": [3, 4]}
    with duckdb.connect(str(path), read_only=True) as connection:
        assert connection.execute("select count(*) from sample").fetchall() == [(10,)]


def check_dataframe(root: Path) -> None:
    frame = pl.DataFrame({"key": ["a", "a", "b"], "value": [1, 2, 4]})
    result = (
        frame.lazy().group_by("key").agg(pl.col("value").sum()).sort("key").collect()
    )
    assert result.to_dict(as_series=False) == {"key": ["a", "b"], "value": [3, 4]}
    labels = pl.DataFrame({"key": ["a", "b"], "label": ["first", "second"]})
    assert frame.join(labels, on="key").sort("value")["label"].to_list() == [
        "first",
        "first",
        "second",
    ]
    for suffix, write, read in [
        ("parquet", frame.write_parquet, pl.read_parquet),
        ("ipc", frame.write_ipc, pl.read_ipc),
        ("csv", frame.write_csv, pl.read_csv),
    ]:
        path = root / ("polars." + suffix)
        write(path)
        assert read(path).equals(frame)
    np.testing.assert_array_equal(frame["value"].to_numpy(), [1, 2, 4])
    assert pl.Series([1, None, 3]).sum() == 4


class Payload:
    thrift_spec = (
        None,
        (1, TType.I64, "number", None, None),
        (2, TType.STRING, "text", "UTF8", None),
    )

    def __init__(self, number: int = 0, text: str = "") -> None:
        self.number = number
        self.text = text


def check_serialization() -> None:
    assert fastbinary.__file__.endswith(".so")
    value = Payload(2**40 + 27, "Android 数据")
    cases = [
        (TBinaryProtocol.TBinaryProtocol, TBinaryProtocol.TBinaryProtocolAccelerated),
        (
            TCompactProtocol.TCompactProtocol,
            TCompactProtocol.TCompactProtocolAccelerated,
        ),
    ]
    for plain, accelerated in cases:
        transport = TMemoryBuffer()
        reference = plain(transport)
        reference.writeStructBegin("Payload")
        reference.writeFieldBegin("number", TType.I64, 1)
        reference.writeI64(value.number)
        reference.writeFieldEnd()
        reference.writeFieldBegin("text", TType.STRING, 2)
        reference.writeString(value.text)
        reference.writeFieldEnd()
        reference.writeFieldStop()
        reference.writeStructEnd()
        protocol = accelerated(TMemoryBuffer(), fallback=False)
        encoded = protocol._fast_encode(value, [Payload, Payload.thrift_spec])
        assert encoded == transport.getvalue()
        decoded = Payload()
        protocol = accelerated(TMemoryBuffer(encoded), fallback=False)
        protocol._fast_decode(decoded, protocol, [Payload, Payload.thrift_spec])
        assert (decoded.number, decoded.text) == (value.number, value.text)


def main() -> None:
    assert hasattr(sys, "getandroidapilevel"), "运行检查必须在 Android 上执行"
    assert _duckdb.__file__.endswith(".so") and shapely.lib.__file__.endswith(".so")
    check_geometry()
    with tempfile.TemporaryDirectory(prefix="data-smoke-") as temporary:
        root = Path(temporary)
        check_database(root)
        check_dataframe(root)
    check_serialization()
    print(
        json.dumps(
            {
                "python": sys.version,
                "python_minimum_api": sys.getandroidapilevel(),
                "machine": os.uname().machine,
                "page_size": os.sysconf("SC_PAGE_SIZE"),
                "versions": {
                    name: importlib.metadata.version(name)
                    for name in [
                        "numpy",
                        "pandas",
                        "shapely",
                        "duckdb",
                        "polars",
                        "polars-runtime-32",
                        "thrift",
                    ]
                },
                "geos": shapely.geos_version_string,
                "checks": [
                    "geometry_operations",
                    "vectorized_predicates",
                    "spatial_index",
                    "wkb",
                    "wkt",
                    "sql_aggregation",
                    "duckdb_parquet",
                    "duckdb_json",
                    "duckdb_timezone",
                    "duckdb_pandas",
                    "database_reopen",
                    "polars_lazy_groupby",
                    "polars_join",
                    "polars_parquet",
                    "polars_ipc",
                    "polars_csv",
                    "polars_numpy",
                    "polars_nulls",
                    "thrift_binary",
                    "thrift_compact",
                ],
                "result": "passed",
            },
            indent=2,
        ),
        flush=True,
    )


if __name__ == "__main__":
    main()
