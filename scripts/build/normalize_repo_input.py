import re
import sys


def normalize_repo_input(repo_input: str) -> str:
    # Remove https://github.com/ or http://github.com/ prefix if present
    repo = re.sub(r"^(https?://github\.com/)", "", repo_input, flags=re.IGNORECASE)
    # Remove .git suffix if present
    repo = re.sub(r"\.git$", "", repo)
    if not re.fullmatch(r"[A-Za-z0-9][A-Za-z0-9-]*/[A-Za-z0-9_.-]+", repo):
        raise ValueError("仓库必须为 GitHub owner/repo 或对应的 HTTPS URL")
    return repo


if __name__ == "__main__":
    if len(sys.argv) > 1:
        original_repo = sys.argv[1]
        normalized_repo = normalize_repo_input(original_repo)
        print(normalized_repo)
    else:
        print(
            "Usage: python normalize_repo_input.py <git_repository_input>",
            file=sys.stderr,
        )
        sys.exit(1)
