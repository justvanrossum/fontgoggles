import os
import pathlib
import re


changelogPath = pathlib.Path(__file__).resolve().parent.parent.parent / "CHANGELOG.md"
changelog = changelogPath.read_text("utf-8")

changelogVersionPattern = re.compile(r"## \[(.+)\]")

gitTag = os.getenv("GITHUB_REF")
assert gitTag[0] == "v"
version = gitTag[1:]

notes = []

collecting = False
for line in changelog.splitlines():
    # print(line)
    m = changelogVersionPattern.match(line)
    if m is not None:
        if collecting:
            break
        elif m.group(1) == version:
            collecting = True
    elif collecting:
        notes.append(line)

print("\n".join(notes).strip())
