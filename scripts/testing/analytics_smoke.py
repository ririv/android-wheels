"""Exercise Arrow data paths and a real PostgreSQL TLS connection on Android."""

import base64
import datetime as dt
import importlib.metadata
import io
import json
import os
import sys
import tempfile
import uuid
from decimal import Decimal
from pathlib import Path

import numpy as np
import pandas as pd
import psycopg2
import psycopg2.extras
import pyarrow as pa
import pyarrow.compute as pc
import pyarrow.csv as csv
import pyarrow.dataset as ds
import pyarrow.ipc as ipc
import pyarrow.parquet as pq
import pyarrow.parquet.encryption as pe


class TestKms(pe.KmsClient):
    """Use a reversible test-only key wrapper for the native encryption roundtrip."""

    def __init__(self, configuration):
        super().__init__()

    def wrap_key(self, key_bytes, master_key_identifier):
        return base64.b64encode(key_bytes)

    def unwrap_key(self, wrapped_key, master_key_identifier):
        return base64.b64decode(wrapped_key)


def check_arrow(root: Path) -> None:
    for codec in ("snappy", "gzip", "zstd", "lz4", "brotli"):
        assert pa.Codec.is_available(codec), codec
    table = pa.table(
        {
            "key": ["a", "a", "b", "b"],
            "value": [1, 2, 3, 4],
            "nullable": [1, None, 3, 4],
        }
    )
    grouped = table.group_by("key").aggregate([("value", "sum")]).sort_by("key")
    assert grouped.to_pydict() == {"key": ["a", "b"], "value_sum": [3, 7]}
    path = root / "data.parquet"
    pq.write_table(table, path, compression="zstd")
    assert pq.read_table(path).equals(table)
    assert ds.dataset(path, format="parquet").to_table(filter=ds.field("value") > 2)[
        "value"
    ].to_pylist() == [3, 4]
    sink = pa.BufferOutputStream()
    with ipc.new_stream(sink, table.schema) as writer:
        writer.write_table(table)
    assert ipc.open_stream(sink.getvalue()).read_all().equals(table)
    csv_path = root / "data.csv"
    csv.write_csv(table, csv_path)
    assert csv.read_csv(csv_path).equals(table)
    values = np.arange(8, dtype=np.int64)
    np.testing.assert_array_equal(
        pa.array(values).to_numpy(zero_copy_only=True), values
    )
    frame = pd.DataFrame({"name": ["中文", "Arrow"], "value": [3, 7]})
    pd.testing.assert_frame_equal(pa.Table.from_pandas(frame).to_pandas(), frame)
    times = pc.assume_timezone(
        pa.array([dt.datetime(2026, 1, 1), dt.datetime(2026, 7, 1)]), "America/New_York"
    ).to_pylist()
    assert [value.utcoffset().total_seconds() for value in times] == [-18000, -14400]
    factory = pe.CryptoFactory(TestKms)
    connection = pe.KmsConnectionConfig(kms_instance_id="local-test")
    encrypted = root / "encrypted.parquet"
    properties = factory.file_encryption_properties(
        connection,
        pe.EncryptionConfiguration(
            footer_key="footer",
            column_keys={"column": ["value"]},
            double_wrapping=False,
        ),
    )
    pq.write_table(table, encrypted, encryption_properties=properties)
    decryption = factory.file_decryption_properties(connection)
    assert pq.read_table(encrypted, decryption_properties=decryption).equals(table)


def check_postgresql(expected_libpq: int = 180006) -> dict:
    root = Path(__file__).parent
    parameters = json.loads((root / "postgres-test.json").read_text())
    parameters.update(
        sslmode="verify-full", sslrootcert=str(root / "test-ca.pem"), connect_timeout=10
    )
    assert psycopg2.extensions.libpq_version() == expected_libpq
    assert psycopg2.__libpq_version__ == expected_libpq
    with psycopg2.connect(**parameters) as connection:
        assert connection.info.ssl_in_use
        assert connection.encoding == "UTF8"
        psycopg2.extras.register_uuid(conn_or_curs=connection)
        with connection.cursor() as cursor:
            cursor.execute(
                "create temporary table sample (id integer, name text, payload jsonb)"
            )
            rows = [
                (1, "中文", psycopg2.extras.Json({"value": 3})),
                (2, "Arrow", psycopg2.extras.Json({"value": 7})),
            ]
            psycopg2.extras.execute_values(cursor, "insert into sample values %s", rows)
            cursor.execute(
                "select id, name, (payload->>'value')::integer from sample order by id"
            )
            assert cursor.fetchall() == [(1, "中文", 3), (2, "Arrow", 7)]
            cursor.execute("savepoint validation")
            cursor.execute("insert into sample values (3, 'rollback', '{}')")
            cursor.execute("rollback to savepoint validation")
            cursor.execute("select count(*) from sample")
            assert cursor.fetchone() == (2,)
            identifier = uuid.UUID("12345678-1234-5678-1234-567812345678")
            cursor.execute(
                "select %s::numeric, %s::uuid, %s::integer[]",
                (Decimal("12345.6789"), identifier, [1, 2, 3]),
            )
            assert cursor.fetchone() == (Decimal("12345.6789"), identifier, [1, 2, 3])
            cursor.execute("create temporary table copied (id integer, name text)")
            cursor.copy_expert(
                "copy copied from stdin", io.StringIO("1\tUTF8 数据\n2\tTLS\n")
            )
            cursor.execute("select * from copied order by id")
            assert cursor.fetchall() == [(1, "UTF8 数据"), (2, "TLS")]
        return {
            "server_version": connection.server_version,
            "libpq_version": psycopg2.extensions.libpq_version(),
            "ssl_protocol": connection.info.ssl_attribute("protocol"),
            "ssl_cipher": connection.info.ssl_attribute("cipher"),
        }


def main() -> None:
    assert hasattr(sys, "getandroidapilevel")
    with tempfile.TemporaryDirectory() as temporary:
        check_arrow(Path(temporary))
    server = check_postgresql()
    print(
        json.dumps(
            {
                "python": sys.version,
                "python_minimum_api": sys.getandroidapilevel(),
                "machine": os.uname().machine,
                "page_size": os.sysconf("SC_PAGE_SIZE"),
                "versions": {
                    name: importlib.metadata.version(name)
                    for name in ["numpy", "pandas", "pyarrow", "psycopg2-binary"]
                },
                "postgresql": server,
                "checks": [
                    "compression_codecs",
                    "arrow_groupby",
                    "parquet",
                    "dataset_filter",
                    "ipc",
                    "csv",
                    "numpy_zero_copy",
                    "pandas_roundtrip",
                    "timezone_dst",
                    "parquet_encryption",
                    "postgresql_tls_verified",
                    "postgresql_utf8_json",
                    "postgresql_savepoint",
                    "postgresql_numeric_uuid_arrays",
                    "postgresql_copy",
                ],
                "result": "passed",
            },
            indent=2,
        ),
        flush=True,
    )


if __name__ == "__main__":
    main()
