import shutil
from collections import defaultdict
from pathlib import Path
import re

def normalize_for_pep503(name):
    """Applies PEP 503 normalization to a project name."""
    return re.sub(r"[-_.]+", "-", name).lower()

root_dir = Path(".")
public_dir = Path("public")
if public_dir.exists():
    shutil.rmtree(public_dir)
public_dir.mkdir(exist_ok=True)

# Find all wheel files from the 'wheels' branch checkout
wheels_root = Path(".")
all_wheels = list(wheels_root.glob("**/*.whl"))

# Group wheels by their PEP 503 normalized project name
packages = defaultdict(list)
for wheel in all_wheels:
    try:
        # Extract the project name part from the wheel filename (e.g., "rpds_py")
        project_name_from_file = wheel.name.split("-")[0]
        # Normalize it according to PEP 503 (e.g., "rpds-py")
        normalized_name = normalize_for_pep503(project_name_from_file)
        packages[normalized_name].append(wheel)
    except IndexError:
        print(f"Could not parse package name from {wheel.name}")

if not packages:
    print("No wheels found. Exiting.")
    (public_dir / "index.html").write_text("<!DOCTYPE html><html><body>No wheels found.</body></html>")
else:
    # Create the root index file
    with open(public_dir / "index.html", "w") as f:
        f.write("<!DOCTYPE html><html><body>\n")
        for name in sorted(packages.keys()):
            f.write(f'<a href="{name}/">{name}</a><br/>\n')
        f.write("</body></html>")

    # Create a directory and index file for each package
    for name, wheel_files in packages.items():
        pkg_dir = public_dir / name
        pkg_dir.mkdir(exist_ok=True)
        with open(pkg_dir / "index.html", "w") as f:
            f.write("<!DOCTYPE html><html><body>\n")
            for wheel in sorted(wheel_files, key=lambda f: f.name):
                # The link inside the package page is just the filename
                f.write(f'<a href="{wheel.name}">{wheel.name}</a><br/>\n')
            f.write("</body></html>")
        
        # Copy the wheel files into the package directory
        for wheel in wheel_files:
            shutil.copy(wheel, pkg_dir / wheel.name)

print(f"Generated index for {len(packages)} packages.")
