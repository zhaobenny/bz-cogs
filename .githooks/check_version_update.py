#!/usr/bin/env python3
"""
Pre-push hook to ensure __version__ is updated when aiuser/ files change.
"""

import re
import subprocess
import sys


def get_compare_range() -> str:
    """Get a sensible diff range for pre-push checks."""
    upstream = subprocess.run(
        ["git", "rev-parse", "--verify", "@{upstream}"],
        capture_output=True,
        text=True,
    )
    if upstream.returncode == 0:
        return "@{upstream}..HEAD"

    parent = subprocess.run(
        ["git", "rev-parse", "--verify", "HEAD^"],
        capture_output=True,
        text=True,
    )
    if parent.returncode == 0:
        return "HEAD^..HEAD"

    return "HEAD"


def get_changed_aiuser_files(diff_range: str):
    """Get changed files in aiuser directory for the diff range."""
    result = subprocess.run(
        ["git", "diff", "--name-only", "--diff-filter=ACM", diff_range],
        capture_output=True,
        text=True,
    )
    files = [f for f in result.stdout.strip().split("\n") if f]
    return [
        f
        for f in files
        if f.startswith("aiuser/") and not f.startswith("aiuser/tests/")
    ]


def check_version_in_diff(diff_range: str):
    """Check if __version__ is modified in the diff range."""
    result = subprocess.run(
        ["git", "diff", diff_range, "--", "aiuser/core/aiuser.py"],
        capture_output=True,
        text=True,
    )

    diff_output = result.stdout

    # Look for changes to __version__ line
    # This regex matches lines that were added (start with +) and contain __version__
    version_pattern = re.compile(r'^\+.*__version__\s*=\s*["\'].*["\']', re.MULTILINE)

    return bool(version_pattern.search(diff_output))


def main():
    diff_range = get_compare_range()
    changed_aiuser_files = get_changed_aiuser_files(diff_range)

    # If no aiuser files are in the push diff, pass
    if not changed_aiuser_files:
        return 0

    # Check if __version__ is updated
    if not check_version_in_diff(diff_range):
        print("❌ ERROR: Changes detected in aiuser/ but __version__ not updated!")
        print("   Please update __version__ in aiuser/core/aiuser.py")
        print(f"   Diff range checked: {diff_range}")
        print("\n   Changed aiuser files in push range:")
        for f in changed_aiuser_files:
            print(f"   - {f}")
        return 1

    print("✅ __version__ updated in aiuser/core/aiuser.py")
    return 0


if __name__ == "__main__":
    sys.exit(main())
