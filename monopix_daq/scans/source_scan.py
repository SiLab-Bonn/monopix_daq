
from monopix_daq.scan_base import ScanBase
import time

import logging
logging.basicConfig(level=logging.INFO, format="%(asctime)s - %(name)s - [%(levelname)-8s] (%(threadName)-10s) %(message)s")

import numpy as np
import bitarray
import tables as tb
import yaml

from progressbar import ProgressBar
from basil.dut import Dut
import os



local_configuration = {
    "column_enable": [0,1,2,3],
    "threshold": 0.81,
    'mask_filename': ''
}

class SourceScan(ScanBase):
    scan_id = "source_scan"

    def scan(self, threshold = 1.5, column_enable = [], mask_filename = '',  **kwargs):

        '''Scan loop
        Parameters
        ----------
        mask : int
            Number of mask steps.
        repeat : int
            Number of injections.
        '''
        self.dut['fifo'].reset()

        
        INJ_LO = 0.2
        self.dut['INJ_LO'].set_voltage(INJ_LO, unit='V')
        
        self.dut.write_global_conf()
        
        self.dut['TH'].set_voltage(1.5, unit='V')

        self.dut['VDDD'].set_voltage(1.6, unit='V')        
        self.dut['VDD_BCID_BUFF'].set_voltage(1.6, unit='V')
        #self.dut['VPC'].set_voltage(1.5, unit='V')


        self.dut['inj'].set_en(False)
        
        #40M BX -> 10^7
        self.dut['gate_tdc'].set_delay(500)
        self.dut['gate_tdc'].set_width(500)
        self.dut['gate_tdc'].set_repeat(10000)
        self.dut['gate_tdc'].set_en(False)
        

        self.dut["CONF_SR"]["PREAMP_EN"] = 1
        self.dut["CONF_SR"]["INJECT_EN"] = 1
        self.dut["CONF_SR"]["MONITOR_EN"] = 0
        self.dut["CONF_SR"]["REGULATOR_EN"] = 1
        self.dut["CONF_SR"]["BUFFER_EN"] = 1

        #LSB
        self.dut["CONF_SR"]["LSBdacL"] = 60
        
        
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
            
        TH = threshold
        
        #LOAD PIXEL DAC
        with tb.open_file(str(mask_filename), 'r') as in_file_h5:
            logging.info('Loading configuration from: %s', mask_filename)
            
            TRIM_EN = in_file_h5.root.scan_results.TRIM_EN[:]
            PREAMP_EN = in_file_h5.root.scan_results.PREAMP_EN[:]

            self.dut.PIXEL_CONF['TRIM_EN'][:] = TRIM_EN[:]
            self.dut.PIXEL_CONF['PREAMP_EN'][:] = PREAMP_EN[:]
            
            dac_status = yaml.load(in_file_h5.root.meta_data.attrs.dac_status)
            power_status = yaml.load(in_file_h5.root.meta_data.attrs.power_status)
            
            TH = in_file_h5.root.meta_data.attrs.final_threshold + 0.002
            
            scan_kwargs = yaml.load(in_file_h5.root.meta_data.attrs.kwargs)
            column_enable = scan_kwargs['column_enable']
            logging.info('Column Enable: %s', str(column_enable))
            
          
        for pix_col in column_enable:
            dcol = int(pix_col/2)  
            self.dut['CONF_SR']['ColRO_En'][35-pix_col] = 1
            
        
        self.dut.write_global_conf()
        self.dut.write_pixel_conf()
        
        self.dut['CONF']['RESET_GRAY'] = 1
        self.dut['CONF']['RESET'] = 1
        self.dut['CONF'].write()

        self.dut['CONF']['RESET'] = 0
        self.dut['CONF'].write()
        
        self.dut['CONF']['RESET_GRAY'] = 0
        self.dut['CONF'].write()

        self.dut['data_rx'].set_en(True)
        time.sleep(0.2)
        
        self.dut['TH'].set_voltage(TH, unit='V')  
        logging.info('Threshold: %f', TH)
        
        time.sleep(0.2)
            
        logging.info('Scan Pixel TH: %f', TH)
        
        with self.readout(scan_param_id = 0, fill_buffer=True, clear_buffer=True):
            
            self.dut['data_rx'].reset()
            self.dut['fifo'].reset()
            self.dut['data_rx'].set_en(True)
                    
            time.sleep(10)
            
            self.dut['data_rx'].set_en(False)
            self.dut['TH'].set_voltage(1.5, unit='V')
            
        dqdata = self.fifo_readout.data
        try:
            data = np.concatenate([item[0] for item in dqdata])
        except ValueError:
            data = []

        hit_data = self.dut.interpret_rx_data(data)

        data_size = len(data) 
        
        pixel_data = hit_data['col']*129+hit_data['row']
        hit_pixels = np.unique(pixel_data)
        hist =  np.bincount(pixel_data)
        print hist
        
        msg = ' '
        if data_size:   
            for pix in hit_pixels:
                col = pix / 129
                row = pix % 129
                                   
                msg += '[%d, %d]=%d ' % (col, row , hist[pix])
            
            logging.info(msg)


    def analyze(self, h5_filename  = ''):
        pass
    
if __name__ == "__main__":

    scan = SourceScan()
    scan.start(**local_configuration)
    scan.analyze()
