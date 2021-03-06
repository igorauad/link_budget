import re
import sys
from setuptools import setup, find_packages


if sys.version_info[0] < 3:
    raise SystemExit("Error: the link-budget tool requires Python 3")

version = re.search(
    r'^__version__\s*=\s*"(.*)"',
    open('linkbudget/main.py').read(),
    re.M
).group(1)

long_description = """## link-budget

A link budget calculator for satellite communications and radar systems.

"""

setup(
    name="link-budget",
    packages=find_packages(),
    entry_points={
        "console_scripts": ['link-budget = linkbudget.main:main']
    },
    version=version,
    description="Link budget analysis for telecommunications systems",
    long_description=long_description,
    long_description_content_type='text/markdown',
    author="Igor Freire",
    author_email="igor@blockstream.com",
    url="https://github.com/igorauad/link_budget",
    classifiers=[
        'Programming Language :: Python :: 3',
        "Programming Language :: Python :: 3 :: Only",
        "License :: OSI Approved :: GNU General Public License v3 (GPLv3)"
    ],
    python_requires='>=3'
)
