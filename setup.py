#!/usr/bin/env python
from distutils.command.install import install as _install
from setuptools import setup
import subprocess


class install(_install):
    def run(self):
        subprocess.call(['./Turbo/build_lib.sh'])
        _install.run(self)


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
    package_data={'': ['*.dylib']},
    install_requires=[
    ],
    extras_require={
    },
    setup_requires=[
    ],
    python_requires=">=3.7",
    classifiers=[
    ],
    cmdclass={'install': install},
)
