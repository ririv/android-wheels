import shutil
from collections import defaultdict
from pathlib import Path
import re
from datetime import datetime
import subprocess
import sys

def get_github_repo_url():
    """
    Determines the GitHub repository's base URL for raw file access.
    e.g., https://github.com/owner/repo/raw/wheels
    """
    try:
        remote_url = subprocess.check_output(['git', 'remote', 'get-url', 'origin']).decode('utf-8').strip()
        match = re.search(r'(?:[:/])([^/]+/[^/]+?)(?:\.git)?$', remote_url)
        if match:
            owner_repo = match.group(1)
            # Assuming the wheels are in a branch named 'wheels'
            return f"https://github.com/{owner_repo}/raw/wheels"
        print("Could not parse owner/repo from git remote URL.")
        return None
    except (subprocess.CalledProcessError, FileNotFoundError):
        print("Could not get git remote URL. Make sure you are in a git repository.")
        return None

def normalize_for_pep503(name):
    """Applies PEP 503 normalization to a project name."""
    return re.sub(r"[-_.]+", "-", name).lower()

# Determine the base URL for wheel links
repo_base_url = get_github_repo_url()
if not repo_base_url:
    sys.exit(1)

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
        project_name_from_file = wheel.name.split("-")[0]
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
        f.write("<!DOCTYPE html>\n")
        f.write("<html>\n")
        f.write("<body>\n")
        f.write("  <table>\n")
        for name in sorted(packages.keys()):
            # Find the most recent modification time among all wheels for this package
            wheel_files = packages[name]
            latest_mtime = max(wheel.stat().st_mtime for wheel in wheel_files)
            last_modified = datetime.fromtimestamp(latest_mtime)
            
            f.write(f'    <tr>\n')
            f.write(f'      <td><a href="{name}/">{name}</a></td>\n')
            f.write(f'      <td>{last_modified.strftime("%Y-%m-%d %H:%M:%S")}</td>\n')
            f.write(f'    </tr>\n')
        f.write("  </table>\n")
        f.write("</body>\n")
        f.write("</html>\n")

    # Create a directory and index file for each package
    for name, wheel_files in packages.items():
        pkg_dir = public_dir / name
        pkg_dir.mkdir(exist_ok=True)
        with open(pkg_dir / "index.html", "w") as f:
            f.write("<!DOCTYPE html>\n")
            f.write("<html>\n")
            f.write("<body>\n")
            f.write("  <table>\n")
            for wheel in sorted(wheel_files, key=lambda f: f.name):
                last_modified = datetime.fromtimestamp(wheel.stat().st_mtime)
                wheel_url = f"{repo_base_url}/{wheel.as_posix()}"
                f.write(f'    <tr>\n')
                f.write(f'      <td><a href="{wheel_url}">{wheel.name}</a></td>\n')
                f.write(f'      <td>{last_modified.strftime("%Y-%m-%d %H:%M:%S")}</td>\n')
                f.write(f'    </tr>\n')
            f.write("  </table>\n")
            f.write("</body>\n")
            f.write("</html>\n")
        
        # No longer need to copy files, as we are linking directly to the 'wheels' branch

print(f"Generated index for {len(packages)} packages.")
