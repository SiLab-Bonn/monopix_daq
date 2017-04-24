#
# ------------------------------------------------------------
# Copyright (c) All rights reserved
# SiLab, Institute of Physics, University of Bonn
# ------------------------------------------------------------
#

import unittest
import os, sys
from basil.utils.sim.utils import cocotb_compile_and_run, cocotb_compile_clean
import sys
import yaml
import time

from monopix_daq.monopix import monopix

class TestSim(unittest.TestCase):

    def setUp(self):
    
        #extra_defines = []
        #if os.environ['SIM']=='icarus':
        extra_defines = ['TEST_DC=1']
            
            
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
        
        self.dut = monopix(conf=cnfg)

    def test(self):
        self.dut.init()
        sys.stdout.write('.')
        
        self.dut['CONF_SR']['INJ_EN'].setall(True)
        self.dut['CONF_SR']['ColRO_En'].setall(True)
        
        self.dut.write_global_conf()
        sys.stdout.write('.')
        
        self.dut.PIXEL_CONF['INJECT_EN'][34,0] = 1
        self.dut.PIXEL_CONF['INJECT_EN'][35,0] = 1
        
        self.dut.PIXEL_CONF['PREAMP_EN'][:] = 1

        
        self.dut.write_pixel_conf()
        
        sys.stdout.write('.')
        
        #READBACK 
        self.dut['CONF']['SREN'] =1
        self.dut['CONF'].write()
        
        self.dut['inj'].set_delay(200)
        self.dut['inj'].set_width(1000)
        self.dut['inj'].set_repeat(1)
        self.dut['inj'].set_en(True)
        
        self.dut['CONF_SR']['Pixels'].setall(True)
        
        self.dut['CONF_SR'].set_repeat(10)
        self.dut['CONF_SR'].set_wait(1000)
        
        self.dut['CONF']['EN_OUT_CLK'] = 1
        self.dut['CONF']['EN_BX_CLK'] = 1
        self.dut['CONF']['EN_DRIVER'] = 1
        self.dut['CONF']['RESET_GRAY'] = 1
        self.dut['CONF']['EN_TEST_PATTERN'] = 0
        self.dut['CONF'].write()
        
        self.dut['CONF']['RESET_GRAY'] = 0
        self.dut['CONF'].write()
        
        sys.stdout.write('.')
        
        self.dut['data_rx'].set_en(True)
         
        self.dut['CONF_SR'].write()
        
        sys.stdout.write('.')
        
        while not self.dut['CONF_SR'].is_ready:
            sys.stdout.write('.')
        
        for _ in range(40):
            sys.stdout.write('.')
            self.dut['CONF_SR'].is_ready
        
        #print ''
        #print 'FifoSize:', self.dut['fifo']['FIFO_SIZE']
        data = self.dut['fifo'].get_data()
        self.assertEqual(len(data), 20)
        
        col = data & 0b111111
        row = (data >> 6) & 0xff
        te = (data >> 14 ) & 0xff
        le = (data >> 22) & 0xff
        tot = te - le

        self.assertEqual(col.tolist(), [0,1]*10)
        self.assertEqual(row.tolist(), [128,0]*10)
        self.assertEqual(tot.tolist(), [7]*20)
        
    def tearDown(self):
        self.dut.close()
        time.sleep(5)
        cocotb_compile_clean()

if __name__ == '__main__':
    unittest.main()
