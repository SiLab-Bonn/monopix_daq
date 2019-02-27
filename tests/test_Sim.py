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

import monopix_daq.monopix as monopix

class TestSim(unittest.TestCase):

    def setUp(self):
    
        extra_defines = []
        #os.environ['SIM'] = 'questa'
        os.environ['SIM'] = 'icarus'
        if os.environ['SIM']=='icarus':
            extra_defines = ['TEST_DC=1']
        elif os.environ['SIM'] == 'questa':
            extra_defines = ['TEST_DC=8']
            
            
        root_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__))) #../
        print root_dir
        cocotb_compile_and_run(
            sim_files = [root_dir + '/tests/hdl/monopix_tb.sv'],
            extra_defines = extra_defines,
            sim_bus = 'basil.utils.sim.SiLibUsbBusDriver',
            include_dirs = (root_dir, root_dir + "/firmware/src"),
            extra = '\nVSIM_ARGS += -wlf /tmp/monopix.wlf  \n'
        
        )
       
        with open(root_dir + '/monopix_daq/monopix.yaml', 'r') as f:
            cnfg = yaml.load(f)

        cnfg['transfer_layer'][0]['type'] = 'SiSim'
        cnfg['hw_drivers'][0]['init']['no_calibration'] = True

        self.monopix = monopix.Monopix(conf=cnfg)
        self.dut = self.monopix.dut


    def test(self):
        self.dut.init()
        
        self.dut['CONF_SR']['MON_EN'].setall(True)
        self.dut['CONF_SR']['INJ_EN'].setall(True)
        
        self.dut.write_global_conf()
        
        #self.dut.PIXEL_CONF['INJECT_EN'][0,0] = 1
        #self.dut.PIXEL_CONF['MONITOR_EN'][0,0] = 1
        self.dut.PIXEL_CONF['MONITOR_EN'][1,0] = 1
        self.dut.PIXEL_CONF['MONITOR_EN'][2,0] = 1
        
        self.dut.write_pixel_conf()
        
        sys.stdout.write('.')
        
        #READBACK 
        self.dut['CONF']['SREN'] =1
        self.dut['CONF'].write()
        
        self.dut['inj'].set_delay(200)
        self.dut['inj'].set_width(1000)
        self.dut['inj'].set_repeat(1)
        self.dut['inj'].set_en(True)
        
        sys.stdout.write('.')
        
        self.dut['CONF_SR']['Pixels'].setall(True)
        
        self.dut['CONF_SR'].set_repeat(10)
        self.dut['CONF_SR'].set_wait(1000)
        self.dut['CONF_SR'].write()
        
        sys.stdout.write('.')
        
        while not self.dut['CONF_SR'].is_ready:
            sys.stdout.write('.')
        
        for _ in range(40):
            sys.stdout.write('.')
            self.dut['CONF_SR'].is_ready
        
    def tearDown(self):
        self.dut.close()
        time.sleep(5)
        cocotb_compile_clean()

if __name__ == '__main__':
    unittest.main()
