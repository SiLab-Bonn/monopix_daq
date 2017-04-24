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
import numpy as np

from monopix_daq.monopix import monopix

class TestSim(unittest.TestCase):

    def setUp(self):
        
        extra_defines = []
        if os.environ['SIM']=='icarus':
            extra_defines = ['TEST_DC=1']
            
        root_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__))) #../
        print root_dir
        cocotb_compile_and_run(
            sim_files = [root_dir + '/tests/hdl/monopix_tb.sv'], 
            extra_defines = extra_defines,
            sim_bus = 'basil.utils.sim.SiLibUsbBusDriver',
            include_dirs = (root_dir, root_dir + "/firmware/src"),
            extra = '\nVSIM_ARGS += -wlf /tmp/monopix.wlf \n'
        )
       
        with open(root_dir + '/monopix_daq/monopix.yaml', 'r') as f:
            self.cnfg = yaml.load(f)

        self.cnfg['transfer_layer'][0]['type'] = 'SiSim'
        self.cnfg['hw_drivers'][0]['init']['no_calibration'] = True
        
    @unittest.skip("testing skipping")
    def test_threshold_scan(self):
        import monopix_daq.scans.threshold_scan
  
        params = monopix_daq.scans.threshold_scan.local_configuration 
  
        self.scan = monopix_daq.scans.threshold_scan.ThresholdScan(self.cnfg)
        params['repeat_command'] = 2
        params['scan_pixels'] =  [[0,0],[0,4]]        
        params['scan_range'] =  [0, 0.2, 0.04]  
        scan_range = np.arange(params['scan_range'][0], params['scan_range'][1], params['scan_range'][2])
 
        self.scan.start(**params)
        H = self.scan.analyze()
        exp = np.full((len(scan_range), len(params['scan_pixels'])), params['repeat_command'])

        comp = (H == exp)
        self.assertTrue(comp.all())
        
    def tearDown(self):
        self.scan.dut.close()
        time.sleep(5)
        cocotb_compile_clean()

if __name__ == '__main__':
    unittest.main()
