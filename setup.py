#!/usr/bin/env python
import re
from setuptools import setup, find_packages
import subprocess


_versionRE = re.compile(r'__version__\s*=\s*\"([^\"]+)\"')
with open('Lib/fontgoggles/__init__.py', "r") as fg_init:
    match = _versionRE.search(fg_init.read())
    assert match is not None, "fontgoggles.__version__ not found"
    fg_version = match.group(1)


setup(
    name="fontgoggles",
    use_scm_version={"write_to": "Lib/fontgoggles/_version.py"},
    version=fg_version,
    description="fontgoggles is the main library for the FontGoggles application.",
    author="Just van Rossum",
    author_email="justvanrossum@gmail.com",
    url="https://github.com/justvanrossum/fontgoggles",
    package_dir={"": "Lib"},
    packages=find_packages("Lib"),
    package_data={'fontgoggles.mac': ['*.dylib']},
    install_requires=[
    ],
    extras_require={
    },
    setup_requires=["setuptools_scm"],
    python_requires=">=3.7",
    classifiers=[
    ],
)
