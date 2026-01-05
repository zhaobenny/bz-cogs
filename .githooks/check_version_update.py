#!/usr/bin/env python3
"""
Pre-commit hook to ensure __version__ is updated when aiuser/ files change.
"""

import re
import subprocess
import sys


def get_staged_files():
    """Get list of staged files in aiuser directory."""
    result = subprocess.run(
        ["git", "diff", "--cached", "--name-only", "--diff-filter=ACM"],
        capture_output=True,
        text=True,
    )
    files = result.stdout.strip().split("\n")
    return [
        f
        for f in files
        if f.startswith("aiuser/") and not f.startswith("aiuser/tests/")
    ]


def check_version_in_staged():
    """Check if __version__ is modified in staged changes."""
    result = subprocess.run(
        ["git", "diff", "--cached", "aiuser/core/aiuser.py"],
        capture_output=True,
        text=True,
    )

    diff_output = result.stdout

    # Look for changes to __version__ line
    # This regex matches lines that were added (start with +) and contain __version__
    version_pattern = re.compile(r'^\+.*__version__\s*=\s*["\'].*["\']', re.MULTILINE)

    return bool(version_pattern.search(diff_output))


def main():
    staged_aiuser_files = get_staged_files()

    # If no aiuser files are staged, pass
    if not staged_aiuser_files:
        return 0

    # Check if __version__ is updated
    if not check_version_in_staged():
        print("❌ ERROR: Changes detected in aiuser/ but __version__ not updated!")
        print("   Please update __version__ in aiuser/core/aiuser.py")
        print("\n   Staged aiuser files:")
        for f in staged_aiuser_files:
            print(f"   - {f}")
        return 1

    print("✅ __version__ updated in aiuser/core/aiuser.py")
    return 0


if __name__ == "__main__":
    sys.exit(main())
