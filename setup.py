#!/usr/bin/env python

from setuptools import setup
from setuptools import find_packages
from platform import system

import numpy as np
import os

version = '0.0.1'


author = 'Tomasz Hemperek'
author_email = 'hemperek@physik.uni-bonn.de'

# requirements for core functionality
install_requires = ['basil-daq==2.5.dev0', 'bitarray>=0.8.1', 'matplotlib', 'numpy', 'pyyaml', 'scipy']

setup(
    name='monopix_daq',
    version=version,
    description='DAQ for MONOPIX',
    url='https://github.com/SiLab-Bonn/monopix_daq',
    license='',
    long_description='',
    author=author,
    maintainer=author,
    author_email=author_email,
    maintainer_email=author_email,
    install_requires=install_requires,
    packages=find_packages(),  
    include_package_data=True,  
    package_data={'': ['README.*', 'VERSION'], 'docs': ['*'], 'monopix_daq': ['*.yaml', '*.bit']},
    platforms='any'
)
