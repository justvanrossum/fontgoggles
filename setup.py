#!/usr/bin/env python
from distutils.command.build import build as _build
from setuptools import setup
import subprocess


class build(_build):
    def run(self):
        # Build our C library
        subprocess.check_call(['./Turbo/build_lib.sh'])
        _build.run(self)


setup(
    name="fontgoggles",
    description="fontgoggles is the main library for the FontGoggles application.",
    author="Just van Rossum",
    author_email="justvanrossum@gmail.com",
    url="https://github.com/justvanrossum/fontgoggles",
    package_dir={"": "Lib"},
    packages=[
        'fontgoggles',
        'fontgoggles.font',
        'fontgoggles.mac',
        'fontgoggles.misc',
    ],
    package_data={'fontgoggles.mac': ['*.dylib']},
    install_requires=[
    ],
    extras_require={
    },
    setup_requires=[
    ],
    python_requires=">=3.7",
    classifiers=[
    ],
    cmdclass={'build': build},
)
