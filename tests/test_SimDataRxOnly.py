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

from basil.dut import Dut
sys.path.append("/home/user/workspace/monopix/monopix_daq_20160609_localcopyofgraysrt/monopix_daq")

cnfg_yaml = """
transfer_layer:
  - name  : intf
    type  : SiSim
    init:
        host : localhost
        port  : 12345

hw_drivers:
  - name      : gpio
    type      : gpio
    interface : intf
    base_addr : 0x0000
    size      : 64

  - name      : mono_data_rx
    type      : mono_data_rx
    interface : intf
    base_addr : 0x1000


  - name      : PULSE_GEN
    type      : pulse_gen
    interface : intf
    base_addr : 0x3000
    
  - name      : PULSE_READ
    type      : pulse_gen
    interface : intf
    base_addr : 0x4000

  - name      : fifo
    type      : sram_fifo
    interface : intf
    base_addr : 0x8000
    base_data_addr: 0x80000000

registers:
  - name        : value
    type        : StdRegister
    hw_driver   : gpio
    size        : 64
    fields:
      - name    : OUT3
        size    : 16
        offset  : 63
      - name    : OUT2
        size    : 24
        offset  : 47
      - name    : IO
        size    : 4
        offset  : 3
"""

class TestSimTimestamp(unittest.TestCase):
    def setUp(self):
        cocotb_compile_and_run([os.path.join(os.path.dirname(__file__), 'hdl/test_SimDataRxOnly.v')])

        self.chip = Dut(cnfg_yaml)
        self.chip.init()
        self.debug=1

    def test_io(self):
        self.chip['mono_data_rx'].reset()
        self.chip['mono_data_rx'].CONF_START_FREEZE = 88
        self.chip['mono_data_rx'].CONF_START_READ = 92
        self.chip['mono_data_rx'].CONF_STOP_FREEZE = 127
        self.chip['mono_data_rx'].CONF_STOP_READ = 94
        self.chip['mono_data_rx'].CONF_STOP = 128
        self.chip['mono_data_rx'].set_en(True)
        ret = self.chip["mono_data_rx"].get_configuration()
        
        self.assertEqual(ret['CONF_START_FREEZE'],88)
        self.assertEqual(ret['CONF_STOP_FREEZE'],127)
        self.assertEqual(ret['CONF_START_READ'],92)
        self.assertEqual(ret['CONF_STOP_READ'],94)
        self.assertEqual(ret['CONF_STOP'],128)

        self.chip['gpio'].reset()

        self.chip['fifo'].reset()
        ret = self.chip['fifo'].get_fifo_size()
        self.assertEqual(ret, 0)

        # trigger mono_data_rx
        self.chip['PULSE_GEN'].set_delay(50)
        self.chip['PULSE_GEN'].set_width(94)
        self.chip['PULSE_GEN'].set_repeat(10)
        #self.chip['PULSE_GEN']["EN"]=True
        
        #self.chip['value']["IO"]=15
        #self.chip['value'].write()
        self.chip['PULSE_GEN'].start()
        while(not self.chip['PULSE_GEN'].is_done()):
            pass
        
        ## get data from fifo
        #ret = self.chip['fifo'].get_fifo_size()
        #self.assertEqual(ret, 3*4)

        #ret = self.chip['fifo'].get_data()
        #self.assertEqual(len(ret), 3)

        ## check with gpio
        #ret2 = self.chip['gpio'].get_data()
        #self.assertEqual(len(ret2), 8)

        #for i,r in enumerate(ret):
        #    self.assertEqual(r&0xF0000000, 0x50000000)
        #    self.assertEqual(r&0xF000000, 0x1000000*(3-i))

        #if self.debug:
            #print hex(ret[0]&0xFFFFFF) ,hex(0x10000*ret2[5]+0x100*ret2[6]+ret2[7])
            #print hex(ret[1]&0xFFFFFF) ,hex(0x10000*ret2[2]+0x100*ret2[3]+ret2[4])
            #print hex(ret[2]&0xFFFFFF) ,hex(0x100*ret2[0]+ret2[1])
        #else:
        #    self.assertEqual(ret[2]&0xFFFFFF,0x10000*ret2[5]+0x100*ret2[6]+ret2[7])
        #    self.assertEqual(ret[1]&0xFFFFFF,0x10000*ret2[2]+0x100*ret2[3]+ret2[4])
        #    self.assertEqual(ret[1]&0xFFFFFF,0x100*ret2[0]+ret2[1])

    def test_dut_iter(self):
        conf = yaml.safe_load(cnfg_yaml)

        def iter_conf():
            for item in conf['registers']:
                yield item
            for item in conf['hw_drivers']:
                yield item
            for item in conf['transfer_layer']:
                yield item

        for mod, mcnf in zip(self.chip, iter_conf()):
            self.assertEqual(mod.name, mcnf['name'])
            self.assertEqual(mod.__class__.__name__, mcnf['type'])

    def tearDown(self):
        self.chip.close()  # let it close connection and stop simulator
        cocotb_compile_clean()

if __name__ == '__main__':
    unittest.main()
