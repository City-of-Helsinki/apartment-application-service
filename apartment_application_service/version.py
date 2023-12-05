import os
import subprocess

# Environment variable for the commit used for build
#
# Value could be e.g. "382b1d3ee9a4ee3c3a5c0c52f03ad2c7b7b5b365"
commit_var = "OPENSHIFT_BUILD_COMMIT"

# Environment variable for the ref used for build
#
# Value could be e.g. "refs/heads/main" or "refs/tags/release-1.0.4".
ref_var = "OPENSHIFT_BUILD_REFERENCE"


def get_version() -> str:
    commit = os.getenv(commit_var)
    ref = os.getenv(ref_var)

    if commit and ref:  # Has commit and ref in env vars
        if ref.startswith("refs/tags/"):
            return ref.split("refs/tags/", 1)[-1].replace("/", "_")
        return commit[:7]

    try:
        return get_version_with_git()
    except Exception:
        return "UNKNOWN"


def get_version_with_git(rev="HEAD") -> str:
    git_cmd = ["git", "rev-parse", "--short", rev]
    git_output = subprocess.check_output(git_cmd)
    decoded = git_output.decode("utf-8", errors="replace")
    return decoded.strip()
