import argparse
import json
import pathlib
import re
import sys
from tempfile import TemporaryDirectory
from urllib.request import urlopen

from delocate.fuse import fuse_wheels
from packaging.utils import parse_wheel_filename

#
# The problem we are trying to solve is:
# - To build a universal2 app with py2app or PyInstaller, we need _all_ compiled packages
#   to be universal2
# - This is hard for two reasons:
#   - Not all packages offer universal2 wheels
#   - When running on x86, pip will serve x86, even if universal2 is available
#
# We take the following approach:
# - Run `pip install -r requirements.txt` and capture the output
# - Find and parse all wheel filenames
# - Any wheel that is x86 or arm64 needs attention (eg. we ignore "any" and "universal2"):
#   - Check the pypi json for the package + version
#   - If there is a universal2 wheel, download it, write to `build/universal_wheels/*.whl`
#   - Else if there are x86 and arm64 wheels, download both and merge, write to
#     `build/universal_wheels/*.whl`
#   - Else: error
# - `pip install --force build/universal_wheels/*.whl`
#

python_versions = {f"cp{sys.version_info.major}{sys.version_info.minor}", "py3"}


class IncompatibleWheelError(Exception):
    pass


def url_filename(url):
    return url.rsplit("/", 1)[-1]


def download_file(url, dest_dir):
    filename = url_filename(url)
    print("downloading wheel", filename)
    response = urlopen(url)
    with open(dest_dir / filename, "wb") as f:
        f.write(response.read())


def merge_wheels(url1, url2, dest_dir):
    wheel_name1 = url_filename(url1)
    wheel_name2 = url_filename(url2)
    print("merging wheels", wheel_name1, "and", wheel_name2)

    with TemporaryDirectory() as tmpdir:
        tmpdir = pathlib.Path(tmpdir)

        download_file(url1, tmpdir)
        download_file(url2, tmpdir)

        wheel_names = [wheel_name1, wheel_name2]
        wheel_names.sort()

        assert any("x86" in name for name in wheel_names)
        assert any("arm64" in name for name in wheel_names)

        package, version, build, tags = parse_wheel_filename(wheel_names[0])

        wheel_base, platform = wheel_names[0].rsplit("-", 1)
        platform_base_parts = platform.split("_")
        platform_base = "_".join(platform_base_parts[:3])

        universal_wheel_path = (
            dest_dir / f"{wheel_base.lower()}-{platform_base}_universal2.whl"
        )
        print("writing universal wheel", universal_wheel_path.name)
        fuse_wheels(tmpdir / wheel_name1, tmpdir / wheel_name2, universal_wheel_path)


wheel_filename_pattern = re.compile(r"[^\s=]+.whl")


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("pip_log")
    parser.add_argument("--wheels-dir", default="build/universal_wheels")

    args = parser.parse_args()

    wheels_dir = pathlib.Path(args.wheels_dir).resolve()
    wheels_dir.mkdir(exist_ok=True, parents=True)

    pip_log_path = args.pip_log
    with open(pip_log_path) as f:
        pip_log = f.read()

    non_portable_wheels = {}

    for wheel_filename in wheel_filename_pattern.findall(pip_log):
        package, version, build, tags = parse_wheel_filename(wheel_filename)
        package = package.lower()
        if any("x86" in tag.platform or "arm64" in tag.platform for tag in tags):
            assert non_portable_wheels.get(package, wheel_filename) == wheel_filename
            non_portable_wheels[package] = wheel_filename

    for wheel_filename in non_portable_wheels.values():
        package, version, build, tags = parse_wheel_filename(wheel_filename)
        response = urlopen(f"https://pypi.org/pypi/{package}/{version}/json")
        data = json.load(response)

        universal_wheels = []
        platform_wheels = []

        for file_descriptor in data["urls"]:
            if file_descriptor["python_version"] not in python_versions:
                continue
            wheel_filename = file_descriptor["filename"]
            package, version, build, tags = parse_wheel_filename(wheel_filename)
            if any("macosx" in tag.platform for tag in tags):
                if any("universal2" in tag.platform for tag in tags):
                    universal_wheels.append(file_descriptor["url"])
                else:
                    platform_wheels.append(file_descriptor["url"])

        if universal_wheels:
            assert len(universal_wheels) == 1
            download_file(universal_wheels[0], wheels_dir)
        elif platform_wheels:
            assert len(platform_wheels) == 2
            merge_wheels(platform_wheels[0], platform_wheels[1], wheels_dir)
        else:
            raise IncompatibleWheelError(
                f"No universal2 solution found for non-portable wheel {wheel_filename}"
            )


if __name__ == "__main__":
    main()
