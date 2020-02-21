import os
import pathlib
import re


changelogVersionPattern = re.compile(r"## \[(.+)\]")
githubRefPattern = re.compile(r"refs/tags/v(.*)")


changelogPath = pathlib.Path(__file__).resolve().parent.parent.parent / "CHANGELOG.md"
changelog = changelogPath.read_text("utf-8")

m = githubRefPattern.match(os.getenv("GITHUB_REF"))
version = m.group(1)

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

print("\n".join(notes).strip().replace("\n", "%0A"))
