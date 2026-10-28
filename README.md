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

1. **Build workflows**: Each package has its own workflow file (e.g. `wheel-zstandard.yml`). It fetches the library's source code and uses a reusable workflow (`build-android-wheel-dispatch.yml`) to cross-compile it for each Android ABI with the Android NDK.
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

## How to add a new package

Community contributions of new packages are welcome. To add a new package to this repository's build system, follow these steps:

1.  **Fork this repository**
    Click the "Fork" button at the top right of the page to fork this repository to your own GitHub account.

2.  **Create a new workflow file**
    In your fork, go to the `.github/workflows/` directory. Copy an existing workflow file (e.g. `wheel-zstandard.yml`) and rename it after the package you want to add, e.g. `wheel-<new-package>.yml`.

3.  **Edit the workflow file**
    Open the new file and edit the parameters in the `with:` section:
    *   `library_name`: The name of the package to build (usually its name on PyPI).
    *   `git_repository`: The package's source Git repository (e.g. `author/repo`).
    *   `version_tag`: (Optional) A fixed Git tag or branch to build. If empty, the latest code on the default branch is used.
    *   `package_dir`: (Optional) The subdirectory of the source repository that contains the Python project (`pyproject.toml`/`setup.py`), e.g. `crates/jiter-python` for jiter. If empty, it is detected automatically.

4.  **Open a pull request**
    Commit your changes and open a pull request against the upstream repository (`ririv/py-extra-wheels`).

After your pull request is merged, a maintainer will manually trigger the workflow to build your package. Once the build succeeds, the new wheels are automatically published to the package index.
