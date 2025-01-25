import os
import re

from setuptools import setup


def get_version():
    version_file = os.path.join("waanverse_mailer", "version.py")
    with open(version_file) as f:
        version_match = re.search(r"^__version__ = ['\"]([^'\"]*)['\"]", f.read(), re.M)
        if version_match:
            version = version_match.group(1)
            return version
        raise RuntimeError("Unable to find version string.")


if __name__ == "__main__":
    setup(version=get_version())
