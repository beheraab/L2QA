"""This file specifies the required version of setuptools for package distribution."""

# from setuptools import setup, find_packages

# setup(
#     name="extraction",
#     version="0.2",
#     package_dir={'': 'src'},
#     packages=find_packages('src'),
#     include_package_data=True,
# )

import setuptools
import pkg_resources

REQUIRED_VERSION = '40.8.0'
if pkg_resources.parse_version(setuptools.__version__) < pkg_resources.parse_version(REQUIRED_VERSION):
    raise SystemExit("You are using setuptools version {}, "
                     "however version {} is atleast required".format(setuptools.__version__,
                                                                     REQUIRED_VERSION,))

setuptools.setup()
