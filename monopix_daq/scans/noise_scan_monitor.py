
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
    "scan_range": [0.8, 0.7, -0.03],
    "scan_pixels": [[0,0],[0,1]]
}

class ThresholdScanMonitor(ScanBase):
    scan_id = "noise_scan_monitor"

    def scan(self,  repeat_command = 100, scan_range = [0.8, 0.7, -0.05], mask_filename = '', scan_pixels = [], **kwargs):
        
        self.dut.write_global_conf()
        
        #if mask_filename:
        #    logging.info('Using pixel mask from file: %s', mask_filename)
        #
        #    with tb.open_file(mask_filename, 'r') as in_file_h5:
        #        mask_tdac = in_file_h5.root.scan_results.tdac_mask[:]
        #        mask_en = in_file_h5.root.scan_results.en_mask[:]
        #SCAN
        
        self.dut['gate_tdc'].set_delay(10)
        self.dut['gate_tdc'].set_width(5000)
        self.dut['gate_tdc'].set_repeat(repeat_command)
        self.dut['gate_tdc'].set_en(False)
                
        self.dut['tdc'].EN_INVERT_TDC = 1
        self.dut['tdc'].ENABLE_EXTERN = 1
        
        scan_range = np.arange(scan_range[0], scan_range[1], scan_range[2])
        
        logging.info('Start Scan: pixels=%s scan_range=%s', str(scan_pixels), str(scan_range))
        
        for idx, pix in enumerate(scan_pixels):
            
            #SELECT_PIXEL
            pix_col = pix[0]
            pix_row = pix[1]
            
            self.dut['CONF_SR']['MON_EN'].setall(False)
            self.dut['CONF_SR']['MON_EN'][pix_col] = 1
            
            self.dut['CONF_SR']['INJ_EN'].setall(False)
            
            self.dut.write_global_conf()
            
            #CONFIGURE PIXELS
            self.dut.PIXEL_CONF['PREAMP_EN'][:] = 1 #???
            
            self.dut.PIXEL_CONF['TRIM_EN'][:] = 7
            self.dut.PIXEL_CONF['TRIM_EN'][pix_col, pix_row] = 7 #???
            
            self.dut.PIXEL_CONF['INJECT_EN'][:] = 0
            self.dut.PIXEL_CONF['MONITOR_EN'][:] = 0
            self.dut.PIXEL_CONF['MONITOR_EN'][pix_col, pix_row] = 1
            self.dut.write_pixel_conf()
            
            for vol_idx, vol in enumerate(scan_range):
                
                param_id = idx * len(scan_range) + vol_idx
                #logging.info('Scan Pixel Start: %s (TH=%f ID=%d)', str(pix), vol, param_id)
                                
                with self.readout(scan_param_id = param_id, fill_buffer=True, clear_buffer=True):
                    
                    self.dut['gate_tdc'].start()
                    while not self.dut['gate_tdc'].is_done():
                        pass
                    
                    time.sleep(0.01)
                    
                dqdata = self.fifo_readout.data
                try:
                    data = np.concatenate([item[0] for item in dqdata])
                except ValueError:
                    data = []
                logging.info('Scan Pixel Finished: %s TH=%f TDC_COUNT=%d', str(pix), vol, len(data))
        
    def analyze(self, h5_filename  = ''):
        if h5_filename == '':
            h5_filename = self.output_filename +'.h5'
        
        logging.info('Anallyzing: %s', h5_filename)
        
        
        
        with tb.open_file(h5_filename, 'r+') as in_file_h5:
            raw_data = in_file_h5.root.raw_data[:]
            meta_data = in_file_h5.root.meta_data[:]
            
            tdc_data = self.dut.interpret_tdc_data(raw_data, meta_data)
            #in_file_h5.create_table(in_file_h5.root, 'tdc_data', tdc_data, filters=self.filter_tables)

            import yaml
            scan_args = yaml.load(in_file_h5.root.meta_data.attrs.kwargs)
            
            scan_range = scan_args['scan_range']
            scan_range = np.arange(scan_range[0], scan_range[1], scan_range[2])
            
            scan_pixels = scan_args['scan_pixels']
            repeat_command = scan_args['repeat_command']
            
            hit_map = np.full((len(scan_range), len(scan_pixels)), -1, dtype = np.int16)
            noise_fit = []
            mean_fit = []
            
            for i in range(len(scan_range)*len(scan_pixels)):
                wh = np.where(tdc_data['scan_param_id'] == i)  # this can be faster
                hd = tdc_data[wh[0]]
                
                pix = int(i / len(scan_range))
                scan = i %  len(scan_range)

                hit_map[scan,pix] = len(hd)

            logging.info('|------------%s |', "-----"*len(scan_range))
            logging.info('|           :%s |', "".join([str(scan).rjust(5) for scan in scan_range]))
            logging.info('|------------%s |', "-----"*len(scan_range))

            for i,pix in enumerate(scan_pixels):
                
                logging.info('|%s :%s |', str(pix).rjust(10), "".join([str(hits).rjust(5) for hits in hit_map[:,i]]))
                
            logging.info('|------------%s |', "-----"*len(scan_range))
        
        return hit_map
        
if __name__ == "__main__":

    scan = ThresholdScanMonitor()
    scan.start(**local_configuration)
    scan.analyze()
