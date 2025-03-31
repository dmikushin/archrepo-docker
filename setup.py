from setuptools import setup, find_packages

with open("README.md", "r", encoding="utf-8") as fh:
    long_description = fh.read()

setup(
    name="archrepo",
    version="0.1.0",
    author="Dmitry Mikushin",
    author_email="dmitry@kernelgen.org",
    description="Setup your custom ArchLinux package repository and manage it using a Python API",
    long_description=long_description,
    long_description_content_type="text/markdown",
    url="https://github.com/dmikushin/archrepo-docker",
    packages=find_packages(),
    classifiers=[
        "Programming Language :: Python :: 3",
        "License :: OSI Approved :: MIT License",
        "Operating System :: OS Independent",
    ],
    python_requires=">=3.6",
    entry_points={
        "console_scripts": [
            "archrepo=archrepo.api:main",
        ],
    },
)
