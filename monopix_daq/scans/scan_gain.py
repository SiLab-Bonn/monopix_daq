import time
import logging
import numpy as np
import tables as tb
import yaml
import monopix_daq.analysis.analysis as analysis
import monopix_daq.scans.scan_single as scan_single

from monopix_daq.scan_base import ScanBase
from progressbar import ProgressBar
from basil.dut import Dut

logging.basicConfig(level=logging.INFO, format="%(asctime)s - %(name)s - [%(levelname)-8s] (%(threadName)-10s) %(message)s")

local_configuration = {
    "how_long": 60,
    "repeat": 1000,
    "scan_injection": [0.12, 0.121, 0.1],
    "threshold_range": [0.783, 0.783, -0.001],
    "pixel":  [2,64],
    "VPFBvalue":4
}

class ScanGain(ScanBase):
    scan_id = "scan_gain"
    def scan(self, repeat = 1, threshold_range = [0.8, 0.8, -0.05], pixel = [1,64] , how_long = 60, scan_injection = 0, VPFBvalue = 32, **kwargs):
        
        self.dut['fifo'].reset()
        INJ_LO = -0.2
        
        try:
            pulser = Dut('../agilent33250a_pyserial.yaml') #should be absolute path
            pulser.init()
            logging.info('Connected to '+str(pulser['Pulser'].get_info()))
        except RuntimeError:
            logging.info('External injector not connected. Switch to internal one')
    
        self.dut['inj'].set_delay(5*256)
        self.dut['inj'].set_width(5*256)
        self.dut['inj'].set_repeat(repeat)
        self.dut['inj'].set_en(True)
        self.dut['gate_tdc'].set_en(False)
        self.dut['gate_tdc'].set_delay(10)
        self.dut['gate_tdc'].set_width(2)
        self.dut['gate_tdc'].set_repeat(1)
        
        self.dut['CONF']['EN_GRAY_RESET_WITH_TDC_PULSE'] = 1
        
        self.dut.write_global_conf()
        
        self.dut['TH'].set_voltage(1.5, unit='V')
        self.dut['VDDD'].set_voltage(1.7, unit='V')        
        self.dut['VDD_BCID_BUFF'].set_voltage(1.7, unit='V')
        #self.dut['VPC'].set_voltage(1.5, unit='V')

        self.dut["CONF_SR"]["PREAMP_EN"] = 1
        self.dut["CONF_SR"]["INJECT_EN"] = 1
        self.dut["CONF_SR"]["MONITOR_EN"] = 1
        self.dut["CONF_SR"]["REGULATOR_EN"] = 1
        self.dut["CONF_SR"]["BUFFER_EN"] = 1
        #self.dut["CONF_SR"]["LSBdacL"] = 60 #LSB
        self.dut["CONF_SR"]["VPFB"] = VPFBvalue
        #self.dut["CONF_SR"]["IComp"] = 16
        self.dut.write_global_conf()
        
        self.dut['CONF']['EN_OUT_CLK'] = 1
        self.dut['CONF']['EN_BX_CLK'] = 1
        self.dut['CONF']['EN_DRIVER'] = 1
        self.dut['CONF']['EN_DATA_CMOS'] = 0

        self.dut['CONF']['RESET_GRAY'] = 1
        self.dut['CONF']['EN_TEST_PATTERN'] = 0
        self.dut['CONF']['RESET'] = 1
        self.dut['CONF'].write()

        self.dut['CONF']['RESET'] = 0
        self.dut['CONF'].write()  
        self.dut['CONF']['RESET_GRAY'] = 0
        self.dut['CONF'].write()
        
        self.dut['CONF_SR']['MON_EN'].setall(False)
        self.dut['CONF_SR']['INJ_EN'].setall(False)
        self.dut['CONF_SR']['ColRO_En'].setall(False)
        
        self.dut.PIXEL_CONF['PREAMP_EN'][:] = 0
        self.dut.PIXEL_CONF['INJECT_EN'][:] = 0
        self.dut.PIXEL_CONF['MONITOR_EN'][:] = 0
        self.dut.PIXEL_CONF['TRIM_EN'][:] = 15
        self.dut['CONF_SR']['MON_EN'][35-pix_col] = 1

        self.dut.PIXEL_CONF['TRIM_EN'][pix_col,pix_row] = 0
        self.dut.PIXEL_CONF['PREAMP_EN'][pix_col,:] = 1
        self.dut.PIXEL_CONF['MONITOR_EN'][pix_col,pix_row] = 1
        self.dut['CONF_SR']['ColRO_En'][35-pix_col] = 1

    
    def analyze(self, h5_filename  = ''):