# MONOPIX_DAQ

[![Build Status](https://travis-ci.org/SiLab-Bonn/monopix_daq.svg?branch=master)](https://travis-ci.org/SiLab-Bonn/monopix_daq)

DAQ for MONOPIX prototype based on [Basil](https://github.com/SiLab-Bonn/basil) framework.

## Required packages

- Install [conda](http://conda.pydata.org) for python and needed packages :
```bash
curl https://repo.continuum.io/miniconda/Miniconda2-latest-Linux-x86_64.sh -o miniconda.sh
bash miniconda.sh -b -p $HOME/miniconda
export PATH=$HOME/miniconda/bin:$PATH
conda update --yes conda
conda install --yes numpy bitarray pytest pyyaml numba mock matplotlib scipy pytables progressbar
```

- Install [pySiLibUSB](https://github.com/SiLab-Bonn/pySiLibUSB) for USB support

- Download and install [Basil](https://github.com/SiLab-Bonn/basil) for data acquisition and generic firmware modules (tested with v2.4.4):
```bash
git clone -b v2.4.4 https://github.com/SiLab-Bonn/basil
cd basil
python setup.py develop 
cd ..
```

- Clone monopix_daq
```bash
git clone https://github.com/SiLab-Bonn/monopix_daq.git
cd monopix_daq
python setup.py develop
```

- Optional: Download and setup [cocotb](https://github.com/potentialventures/cocotb) for simulation:
```bash
git clone https://github.com/potentialventures/cocotb.git
export COCOTB=$(pwd)/cocotb
```

- Optional: Download and setup [online_monitor](https://github.com/SiLab-Bonn/online_monitor) to run the real-time monitors:
```bash
git clone https://github.com/SiLab-Bonn/online_monitor
cd online_monitor
python setup.py develop
```

## Firmware

- For MIO board:
    NOTE: A compiled bit file for the MIO board is provided in "/path-to-monopix_daq/firmware/bit/monopix_mio.bit"
    1. Use Xilinx ISE to open the "/path-to-monopix_daq/firmware/ise/monopix.xise" project.
    2. In the "Synthesis Options" of the project, add too the "Verilog Include Directories" the following basil paths:
        "/path-to-basil/basil/firmware/modules"
        "/path-to-basil/basil/firmware/modules/utils"
    3. Generate the "monopix_mio.bit" file through the "Generate Programming File" command.
    4. Check that the correct path to the bit file is set in the "/path-to-monopix_daq/monopix_daq/monopix.yaml" file.

- For MIO3 board:
    NOTE: There is not a compiled version of firmware for MIO3. In order to do generate, an additional working SiTCP library is also needed -It can be acquired [here](https://github.com/SiLab-Bonn/online_monitor)-.
    1. Use Vivado to open the "/path-to-monopix_daq/firmware/vivado/monopix_mio3.xpr" project.
    2. Add the SiTCP folder with libraries to "/path-to-monopix_daq/firmware/src/"
    3. In Vivado, select "Project Settings" and then clic on "Verilog Options". In the "Verilog Include Files Search Paths", add the following basil paths:
        "/path-to-basil/basil/firmware/modules"
        "/path-to-basil/basil/firmware/modules/utils"
    and "Apply"
    4. "Generate Bitstream" and flash the ".bit" file through JTAG to the FPGA, or flash a ".bin" file permanently if wanted.
    5. Ping to the corresponding IP address to check communication.

### Detailed instruction for pyBAR (similar software)

https://github.com/SiLab-Bonn/pyBAR/wiki/Step-by-step-Installation-Guide

## Usage

TBD
