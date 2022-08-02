#!/usr/bin/env python

from setuptools import setup, find_packages

with open("README.md", "rt") as fh:
    long_description = fh.read()

dependencies = [
    "chia-blockchain==1.3.5",
]

dev_dependencies = [
    "flake8",
    "mypy",
    "black==21.12b0",
    "pytest",
    "pytest-asyncio",
]

setup(
    name="contract_patterns",
    packages=find_packages(exclude=("tests",)),
    author="Quexington",
    entry_points={},
    package_data={
        "": ["*.clsp.hex"],
    },
    author_email="m.hauff@chia.net",
    setup_requires=["setuptools_scm"],
    install_requires=dependencies,
    url="https://github.com/Chia-Network/contract_patterns",
    license="https://opensource.org/licenses/Apache-2.0",
    description="Contract patterns",
    long_description=long_description,
    long_description_content_type="text/markdown",
    classifiers=[
        "Programming Language :: Python :: 3",
        "Programming Language :: Python :: 3.6",
        "Programming Language :: Python :: 3.7",
        "Programming Language :: Python :: 3.8",
        "Programming Language :: Python :: 3.9",
        "License :: OSI Approved :: Apache Software License",
        "Topic :: Security :: Cryptography",
    ],
    extras_require=dict(
        dev=dev_dependencies,
    ),
    project_urls={
        "Bug Reports": "https://github.com/Chia-Network/contract_patterns",
        "Source": "https://github.com/Chia-Network/contract_patterns",
    },
)
