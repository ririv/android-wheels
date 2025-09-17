import shutil
from collections import defaultdict
from pathlib import Path

root_dir = Path(".")
public_dir = Path("public")
public_dir.mkdir(exist_ok=True)

wheels = sorted(root_dir.glob("*.whl"))
packages = defaultdict(list)

for wheel in wheels:
    try:
        pkg_name = wheel.name.split("-")[0]
        packages[pkg_name].append(wheel)
    except IndexError:
        print(f"Could not parse package name from {wheel.name}")

if not packages:
    print("No wheels found. Exiting.")
    (public_dir / "index.html").write_text("<!DOCTYPE html><html><body>No wheels found.</body></html>")
else:
    with open(public_dir / "index.html", "w") as f:
        f.write("<!DOCTYPE html><html><body>\n")
        for pkg_name in sorted(packages.keys()):
            f.write(f'<a href="{pkg_name}/">{pkg_name}</a><br/>\n')
        f.write("</body></html>")

    for pkg_name, wheel_files in packages.items():
        pkg_dir = public_dir / pkg_name
        pkg_dir.mkdir(exist_ok=True)
        with open(pkg_dir / "index.html", "w") as f:
            f.write("<!DOCTYPE html><html><body>\n")
            for wheel in sorted(wheel_files, key=lambda f: f.name):
                f.write(f'<a href="{wheel.name}">{wheel.name}</a><br/>\n')
            f.write("</body></html>")
        for wheel in wheel_files:
            shutil.copy(wheel, pkg_dir / wheel.name)
