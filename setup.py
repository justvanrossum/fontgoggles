#!/usr/bin/env python
from setuptools import setup, find_packages


setup(
    name="fontgoggles",
    description="fontgoggles is the main library for the FontGoggles application.",
    author="Just van Rossum",
    author_email="justvanrossum@gmail.com",
    url="https://github.com/justvanrossum/fontgoggles",
    package_dir={"": "Lib"},
    packages=find_packages("Lib"),
    install_requires=[
    ],
    extras_require={
    },
    setup_requires=[
    ],
    python_requires=">=3.7",
    classifiers=[
    ],
)
