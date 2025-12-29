import os
import pathlib
import re
import sys


changelogVersionPattern = re.compile(r"## \[(.+)\]")


changelogPath = pathlib.Path(__file__).resolve().parent.parent.parent / "CHANGELOG.md"
changelog = changelogPath.read_text("utf-8")

version = sys.argv[1]
assert version[0] == "v", "bad version tag"
version = version[1:]

notes = []

collecting = False
for line in changelog.splitlines():
    m = changelogVersionPattern.match(line)
    if m is not None:
        if collecting:
            break
        elif m.group(1) == version:
            collecting = True
    elif collecting:
        notes.append(line)

print("\n".join(notes).strip())
