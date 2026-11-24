"""Check the commit subjects in a pre-push range targeting main."""

import os
import re
import subprocess
import sys

SCOPE = r"[a-z][a-z0-9]*(?:-[a-z0-9]+)*"
SUBJECT = re.compile(rf"(?:\[BREAKING\] )?{SCOPE}(?:, {SCOPE})* - \S.*")


def main() -> int:
    if os.environ.get("PRE_COMMIT_REMOTE_BRANCH") != "refs/heads/main":
        return 0

    start = os.environ.get("PRE_COMMIT_FROM_REF")
    end = os.environ.get("PRE_COMMIT_TO_REF") or os.environ["PRE_COMMIT_LOCAL_BRANCH"]
    revision = f"{start}..{end}" if start else end
    result = subprocess.run(
        ["git", "log", "--format=%s", revision, "--"],
        check=True,
        capture_output=True,
        text=True,
    )
    invalid = [
        subject
        for subject in result.stdout.split("\n")[:-1]
        if not SUBJECT.fullmatch(subject)
    ]

    if invalid:
        print(
            "Use 'scope - description' or 'scope, scope - description'.",
            file=sys.stderr,
        )
        for subject in invalid:
            print(f"Invalid commit subject: {subject!r}", file=sys.stderr)
    return int(bool(invalid))


if __name__ == "__main__":
    sys.exit(main())
