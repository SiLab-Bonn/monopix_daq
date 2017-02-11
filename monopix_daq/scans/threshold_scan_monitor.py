
from monopix_daq.scan_base import ScanBase
import time

import logging
logging.basicConfig(level=logging.INFO, format="%(asctime)s - %(name)s - [%(levelname)-8s] (%(threadName)-10s) %(message)s")

import numpy as np
import bitarray
import tables as tb

from progressbar import ProgressBar
from basil.dut import Dut
import os

local_configuration = {
    "repeat_command": 10,
    "mask_filename": '',
    "scan_range": [0, 0.2, 0.05],
    "scan_pixels": [[0,0],[0,1]]
}

class ThresholdScanMonitor(ScanBase):
    scan_id = "threshold_scan_monitor"

    def scan(self,  repeat_command = 100, scan_range = [0, 0.2, 0.05], mask_filename = '', scan_pixels = [], **kwargs):

        '''Scan loop
        Parameters
        ----------
        mask : int
            Number of mask steps.
        repeat : int
            Number of injections.
        '''
        
        INJ_LO = 0.2
        self.dut['INJ_LO'].set_voltage(INJ_LO, unit='V')
        
        self.dut.write_global_conf()
        
        #if mask_filename:
        #    logging.info('Using pixel mask from file: %s', mask_filename)
        #
        #    with tb.open_file(mask_filename, 'r') as in_file_h5:
        #        mask_tdac = in_file_h5.root.scan_results.tdac_mask[:]
        #        mask_en = in_file_h5.root.scan_results.en_mask[:]
        #SCAN
        
        self.dut['gate_tdc'].set_delay(1000)
        self.dut['gate_tdc'].set_width(500)
        self.dut['gate_tdc'].set_repeat(repeat_command)
        self.dut['gate_tdc'].set_en(False)
        
        self.dut['inj'].set_delay(250)
        self.dut['inj'].set_width(1000)
        self.dut['inj'].set_repeat(1)
        self.dut['inj'].set_en(False)
        
        self.dut['tdc'].EN_INVERT_TDC = 1
        self.dut['tdc'].ENABLE_EXTERN = 1
        
        pixels_cnt = len(scan_pixels)
        scan_range = np.arange(scan_range[0], scan_range[1], scan_range[2])
        
        logging.info('Start Scan: pixels=%s scan_range=%s', str(scan_pixels),str(scan_pixels))
        
        for idx, pix in enumerate(scan_pixels):
            
            #SELECT_PIXEL
            pix_col = pix[0]
            pix_row = pix[1]
            
            self.dut['CONF_SR']['MON_EN'].setall(False)
            self.dut['CONF_SR']['MON_EN'][pix_col] = 1
            
            self.dut['CONF_SR']['INJ_EN'].setall(False)
            self.dut['CONF_SR']['INJ_EN'][int(pix_col/2)] = 1
            
            self.dut.write_global_conf()
            
            #CONFIGURE PIXELS
            self.dut.PIXEL_CONF['PREAMP_EN'][:] = 1 #???
            
            self.dut.PIXEL_CONF['TRIM_EN'][:] = 7
            self.dut.PIXEL_CONF['TRIM_EN'][pix_col, pix_row] = 7 #???
            
            self.dut.PIXEL_CONF['INJECT_EN'][:] = 0
            self.dut.PIXEL_CONF['INJECT_EN'][pix_col, pix_row] = 1
            self.dut.PIXEL_CONF['MONITOR_EN'][:] = 0
            self.dut.PIXEL_CONF['MONITOR_EN'][pix_col, pix_row] = 1
            self.dut.write_pixel_conf()

            
            for vol_idx, vol in enumerate(scan_range):
                
                param_id = idx * pixels_cnt + vol_idx
                logging.info('Scan Pixel: %s (V=%f ID=%d)', str(pix), vol, param_id)
                
                self.dut['INJ_HI'].set_voltage( float(INJ_LO + vol), unit='V')
                time.sleep(0.1)
                self.dut['inj'].set_en(True)
                
                with self.readout(scan_param_id = param_id, fill_buffer=True, clear_buffer=True):
                    
                    
                    self.dut['gate_tdc'].start()
                    while not self.dut['gate_tdc'].is_done():
                        pass
                    
                    while not self.dut['inj'].is_done():
                        pass
                    
                    time.sleep(0.1)
                    
                self.dut['inj'].set_en(False)
                dqdata = self.fifo_readout.data
                try:
                    data = np.concatenate([item[0] for item in dqdata])
                except ValueError:
                    data = []
                logging.info('Scan Pixel: %s V=%f TDC_COUNT=%d', str(pix), vol, len(data))

        #scan_results = self.h5_file.create_group("/", 'scan_results', 'Scan Masks')
        #self.h5_file.create_carray(scan_results, 'tdac_mask', obj=mask_tdac)
        #self.h5_file.create_carray(scan_results, 'en_mask', obj=mask_en)
        
    def analyze(self):
        pass
                
if __name__ == "__main__":

    scan = ThresholdScanMonitor()
    scan.start(**local_configuration)
    scan.analyze()
