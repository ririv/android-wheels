# Py Extra Wheels

**English** | [简体中文](README.zh-CN.md)

This repository builds and hosts prebuilt Python wheels for Android, for example for the [Chaquopy](https://chaquo.com/chaquopy/) Python SDK for Android, or for embedding Python in an Android app manually. See [Using Python on Android](https://docs.python.org/3.14/using/android.html#using-python-on-android) for details.

Index URL: https://ririv.github.io/py-extra-wheels/

## Usage

To install these wheels, run `pip` with `--extra-index-url` pointing to this repository's package index:

```bash
pip install --extra-index-url https://ririv.github.io/py-extra-wheels/ <package-name>
```

For example, to install `zstandard`:

```bash
pip install --extra-index-url https://ririv.github.io/py-extra-wheels/ zstandard
```

### requirements.txt

You can also add the index URL to your `requirements.txt` file:

```txt
--extra-index-url https://ririv.github.io/py-extra-wheels/

zstandard
xxhash
```

## Supported ABIs

* `arm64-v8a`
* `x86_64`

## How it works

This repository uses GitHub Actions to automate building and publishing:

1. **Recipe / Matrix**: `recipes/*.toml` → `build-wheels.yml` → `build-android-wheel-dispatch.yml`. [配置与并行构建说明](docs/recipes.md)。
2. **Commit to the `wheels` branch**: Successfully built `.whl` files are committed to the `wheels` branch.
3. **Deploy the index**: Pushing to the `wheels` branch triggers the `pages.yml` workflow, which generates a PEP 503 compliant "simple" package index and deploys it to GitHub Pages.

This keeps the package index in sync with the latest successfully built wheels.

## Naming conventions

### Wheel file names

Wheel file names follow Python's [PEP 427](https://peps.python.org/pep-0427/#recommended-installer-features), usually in the form `{distribution}-{version}-{python tag}-{abi tag}-{platform tag}.whl`.

### Package index names

Package index names follow Python's [PEP 503](https://peps.python.org/pep-0503/) and the [wheel tag format for Android](https://peps.python.org/pep-0738/#packaging). Note the rules for [normalized names](https://peps.python.org/pep-0503/#normalized-names).

| API           | Purpose                                                     |
| ------------- | ----------------------------------------------------------- |
| PEP 503       | Index: serves HTML index files.                             |
| PEP 691       | Index: serves JSON index files.                             |
| PEP 658       | Index: serves metadata to speed up dependency resolution.   |
| PEP 738       | Platform: Android support, including the packaging format.  |

## Recipe / TOML

新增包请添加 `recipes/<包名>.toml`；统一入口为 `build-wheels.yml`。配置格式、手动构建及多 Python 版本并行见 [Recipe 与并行构建](docs/recipes.md)。
