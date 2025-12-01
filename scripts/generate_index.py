import shutil
from collections import defaultdict
from pathlib import Path
import re
from datetime import datetime, timezone
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

def get_git_last_modified(file_path: Path) -> datetime:
    """
    Gets the last commit date of a file from git log.
    Returns a fallback datetime if git log fails.
    """
    try:
        # Use --follow to track renames, get committer date in ISO 8601 format
        iso_date_str = subprocess.check_output(
            ['git', 'log', '-1', '--pretty=format:%cI', '--follow', '--', str(file_path)]
        ).decode('utf-8').strip()
        return datetime.fromisoformat(iso_date_str)
    except (subprocess.CalledProcessError, FileNotFoundError, ValueError) as e:
        print(f"Warning: Could not get git last modified date for {file_path}: {e}", file=sys.stderr)
        # Fallback to a known old date to avoid showing current time
        return datetime.fromtimestamp(0, tz=timezone.utc)

def normalize_for_pep503(name):
    """Applies PEP 503 normalization to a project name."""
    return re.sub(r"[-_.]+", "-", name).lower()

def generate_root_html_lines(packages):
    """Generator for the root index.html content."""
    yield "<!DOCTYPE html>\n"
    yield "<html>\n"
    yield "<body>\n"
    yield "  <table>\n"
    for name in sorted(packages.keys()):
        wheel_files = packages[name]
        latest_date = max(get_git_last_modified(wheel) for wheel in wheel_files)
        yield f'    <tr>\n'
        yield f'      <td><a href="{name}/">{name}</a></td>\n'
        yield f'      <td>{latest_date.strftime("%Y-%m-%d %H:%M:%S %Z")}</td>\n'
        yield f'    </tr>\n'
    yield "  </table>\n"
    yield "</body>\n"
    yield "</html>\n"

def generate_pkg_html_lines(wheel_files, repo_base_url):
    """Generator for a package's index.html content."""
    yield "<!DOCTYPE html>\n"
    yield "<html>\n"
    yield "<body>\n"
    yield "  <table>\n"
    for wheel in sorted(wheel_files, key=lambda f: f.name):
        last_modified = get_git_last_modified(wheel)
        wheel_url = f"{repo_base_url}/{wheel.as_posix()}"
        yield f'    <tr>\n'
        yield f'      <td><a href="{wheel_url}">{wheel.name}</a></td>\n'
        yield f'      <td>{last_modified.strftime("%Y-%m-%d %H:%M:%S %Z")}</td>\n'
        yield f'    </tr>\n'
    yield "  </table>\n"
    yield "</body>\n"
    yield "</html>\n"

def main():
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
            # Use the parent directory name as the project name if available (and not root)
            # This supports the structure where wheels are organized in package-named folders
            if wheel.parent != wheels_root:
                project_name_from_file = wheel.parent.name
            else:
                project_name_from_file = wheel.name.split("-")[0]

            normalized_name = normalize_for_pep503(project_name_from_file)
            packages[normalized_name].append(wheel)
        except IndexError:
            print(f"Could not parse package name from {wheel.name}")

    if not packages:
        print("No wheels found. Exiting.")
        (public_dir / "index.html").write_text("<!DOCTYPE html><html><body>No wheels found.</body></html>")
    else:
        # Create the root index file using a generator
        with open(public_dir / "index.html", "w", encoding="utf-8") as f:
            f.writelines(generate_root_html_lines(packages))

        # Create a directory and index file for each package
        for name, wheel_files in packages.items():
            pkg_dir = public_dir / name
            pkg_dir.mkdir(exist_ok=True)
            with open(pkg_dir / "index.html", "w", encoding="utf-8") as f:
                f.writelines(generate_pkg_html_lines(wheel_files, repo_base_url))

    print(f"Generated index for {len(packages)} packages.")

if __name__ == "__main__":
    main()
