# MONOPIX

DAQ for MONOPIX prototype based on [Basil](https://github.com/SiLab-Bonn/basil) framwork.

## Instalation

- Install [conda](http://conda.pydata.org) for python and needed packages :
```bash
curl https://repo.continuum.io/miniconda/Miniconda2-latest-Linux-x86_64.sh -o miniconda.sh
bash miniconda.sh -b -p $HOME/miniconda
export PATH=$HOME/miniconda/bin:$PATH
conda update --yes conda
conda install --yes numpy bitarray pytest pyyaml numba mock matplotlib scipy pytables progressbar
```

- Install [pySiLibUSB](https://github.com/SiLab-Bonn/pySiLibUSB) for USB support

- Clone monopix_daq
```bash
git clone https://github.com/SiLab-Bonn/monopix_daq.git
cd monopix_daq
python setup.py develop
```

- (For firmware development) Download and install [Basil](https://github.com/SiLab-Bonn/basil):
```bash
git clone -b v2.4.4 https://github.com/SiLab-Bonn/basil
cd basil
python setup.py develop 
cd ..
```

- (For simulation) Download and setup [cocotb](https://github.com/potentialventures/cocotb):
```bash
git clone https://github.com/potentialventures/cocotb.git
export COCOTB=$(pwd)/cocotb
```

###Detailed instruction for pyBAR (similar software)

https://github.com/SiLab-Bonn/pyBAR/wiki/Step-by-step-Installation-Guide

## Usage

TBD
