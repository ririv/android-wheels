"""Prepare public TLS fixtures and enable SSL on an isolated CI PostgreSQL service."""

import argparse
import json
import subprocess
import time
from pathlib import Path

from scripts.pipeline.artifacts import digest

TEST_CONNECTION = {
    "host": "10.0.2.2",
    "port": 15432,
    "dbname": "wheeltest",
    "user": "wheeltest",
    "password": "wheeltest-password",
}


def prepare_files(root: Path) -> None:
    root.mkdir(parents=True)
    configuration = root / "certificate.cnf"
    configuration.write_text(
        "[req]\nprompt=no\ndistinguished_name=subject\nx509_extensions=extensions\n"
        "[subject]\nCN=py-extra-wheels-test\n"
        "[extensions]\nbasicConstraints=critical,CA:TRUE\n"
        "keyUsage=critical,digitalSignature,keyEncipherment,keyCertSign\n"
        "extendedKeyUsage=serverAuth\nsubjectAltName=IP:10.0.2.2,DNS:localhost\n"
    )
    subprocess.run(
        [
            "openssl",
            "req",
            "-x509",
            "-newkey",
            "rsa:2048",
            "-nodes",
            "-sha256",
            "-days",
            "1",
            "-config",
            str(configuration),
            "-keyout",
            str(root / "server.key"),
            "-out",
            str(root / "test-ca.pem"),
        ],
        check=True,
    )
    (root / "server.key").chmod(0o600)
    (root / "postgres-test.json").write_text(
        json.dumps(TEST_CONNECTION, indent=2) + "\n"
    )
    (root / "resources.json").write_text(
        json.dumps(
            [
                {"filename": name, "sha256": digest(root / name)}
                for name in ("test-ca.pem", "postgres-test.json")
            ],
            indent=2,
        )
        + "\n"
    )


def enable_container_tls(root: Path, container: str) -> None:
    for source, destination in [
        ("test-ca.pem", "/tmp/wheel-server.crt"),
        ("server.key", "/tmp/wheel-server.key"),
    ]:
        subprocess.run(
            ["docker", "cp", str(root / source), container + ":" + destination],
            check=True,
        )
    subprocess.run(
        [
            "docker",
            "exec",
            "--user",
            "root",
            container,
            "chown",
            "postgres:postgres",
            "/tmp/wheel-server.crt",
            "/tmp/wheel-server.key",
        ],
        check=True,
    )
    subprocess.run(
        [
            "docker",
            "exec",
            "--user",
            "root",
            container,
            "chmod",
            "600",
            "/tmp/wheel-server.key",
        ],
        check=True,
    )
    command = [
        "docker",
        "exec",
        "--user",
        "postgres",
        container,
        "psql",
        "-X",
        "-v",
        "ON_ERROR_STOP=1",
        "-U",
        "wheeltest",
        "-d",
        "wheeltest",
    ]
    for statement in [
        "ALTER SYSTEM SET ssl_cert_file = '/tmp/wheel-server.crt'",
        "ALTER SYSTEM SET ssl_key_file = '/tmp/wheel-server.key'",
        "ALTER SYSTEM SET ssl = 'on'",
        "SELECT pg_reload_conf()",
    ]:
        subprocess.run([*command, "-c", statement], check=True)
    for _ in range(20):
        result = subprocess.run(
            [
                "docker",
                "exec",
                "-e",
                "PGPASSWORD=" + TEST_CONNECTION["password"],
                container,
                "psql",
                "host=127.0.0.1 user=wheeltest dbname=wheeltest sslmode=require",
                "-c",
                "SELECT 1",
            ],
            stdout=subprocess.DEVNULL,
            stderr=subprocess.PIPE,
        )
        if result.returncode == 0:
            return
        time.sleep(0.5)
    raise TimeoutError("PostgreSQL 测试服务未在限定时间内启用 TLS")


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--root", type=Path, required=True)
    parser.add_argument("--container", required=True)
    args = parser.parse_args()
    prepare_files(args.root)
    enable_container_tls(args.root, args.container)


if __name__ == "__main__":
    main()
