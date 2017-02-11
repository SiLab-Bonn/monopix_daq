#
# ------------------------------------------------------------
# Copyright (c) All rights reserved
# SiLab, Institute of Physics, University of Bonn
# ------------------------------------------------------------
#

import unittest
import os
from basil.utils.sim.utils import cocotb_compile_and_run, cocotb_compile_clean
import sys
import yaml
import time

from monopix_daq.monopix import monopix
from monopix_daq.scans.threshold_scan_monitor import ThresholdScanMonitor

class TestSim(unittest.TestCase):

    def setUp(self):
        
        root_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__))) #../
        print root_dir
        cocotb_compile_and_run(
            sim_files = [root_dir + '/tests/hdl/monopix_tb.sv'], 
            sim_bus = 'basil.utils.sim.SiLibUsbBusDriver',
            include_dirs = (root_dir, root_dir + "/firmware/src"),
            extra = '\nVSIM_ARGS += -wlf /tmp/monopix.wlf  \n'
        
        )
       
        with open(root_dir + '/monopix_daq/monopix.yaml', 'r') as f:
            self.cnfg = yaml.load(f)

        self.cnfg['transfer_layer'][0]['type'] = 'SiSim'

        
    def test(self):
        self.scan = ThresholdScanMonitor(self.cnfg)
        self.scan.start(scan_pixels = [[0,0],[0,1]], repeat_command = 10)
        
    def tearDown(self):
        self.scan.dut.close()
        time.sleep(5)
        cocotb_compile_clean()

if __name__ == '__main__':
    unittest.main()
