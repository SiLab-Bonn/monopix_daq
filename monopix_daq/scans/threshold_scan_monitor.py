
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
    "repeat_command": 100,
    "mask_filename": '',
    "scan_range": [0.05, 0.25, 0.005],
    "scan_pixels": [[1,64]], #,[0,65],[0,66],[0,67]],
    "TH": 0.778
}

class ThresholdScanMonitor(ScanBase):
    scan_id = "threshold_scan_monitor"

    def scan(self,  repeat_command = 100, scan_range = [0, 0.2, 0.05], mask_filename = '', TH = 1.5, scan_pixels = [], **kwargs):

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
                
        
        self.dut["CONF_SR"]["PREAMP_EN"]=1
        self.dut["CONF_SR"]["INJECT_EN"]=1
        self.dut["CONF_SR"]["MONITOR_EN"]=1
        self.dut["CONF_SR"]["REGULATOR_EN"]=1
        self.dut["CONF_SR"]["BUFFER_EN"]=1
        self.dut.write_global_conf()

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
        
        scan_range = np.arange(scan_range[0], scan_range[1], scan_range[2])
        
        logging.info('Start Scan: pixels=%s scan_range=%s', str(scan_pixels), str(scan_range))
        
        for idx, pix in enumerate(scan_pixels):
            
            #SELECT_PIXEL
            pix_col = pix[0]
            pix_row = pix[1]
            
            self.dut['CONF_SR']['MON_EN'].setall(False)
            self.dut['CONF_SR']['MON_EN'][35-pix_col] = 1
            
            self.dut['CONF_SR']['INJ_EN'].setall(False)
            self.dut['CONF_SR']['INJ_EN'][17-int(pix_col/2)] = 1
            
            self.dut.write_global_conf()
            
            #CONFIGURE PIXELS
            #HACK
            self.dut.PIXEL_CONF['PREAMP_EN'][:] = 0 #???
            #self.dut.PIXEL_CONF['PREAMP_EN'][pix_col,:] = 1 #???
            self.dut.PIXEL_CONF['PREAMP_EN'][pix_col,pix_row] = 1 #???
            
            self.dut.PIXEL_CONF['TRIM_EN'][:] = 15
            self.dut.PIXEL_CONF['TRIM_EN'][pix_col, pix_row] = 0 #???
            
            self.dut.PIXEL_CONF['INJECT_EN'][:] = 0
            self.dut.PIXEL_CONF['INJECT_EN'][pix_col, pix_row] = 1
            self.dut.PIXEL_CONF['MONITOR_EN'][:] = 0
            self.dut.PIXEL_CONF['MONITOR_EN'][pix_col, pix_row] = 1
            self.dut.write_pixel_conf()

            self.dut['TH'].set_voltage(TH, unit='V')
            time.sleep(0.1)

            for vol_idx, vol in enumerate(scan_range):
                
                param_id = idx * len(scan_range) + vol_idx
                #logging.info('Scan Pixel Start: %s (V=%f ID=%d)', str(pix), vol, param_id)
                
                self.dut['INJ_HI'].set_voltage( float(INJ_LO + vol), unit='V')
                time.sleep(0.1)
                self.dut['inj'].set_en(True)
                
                with self.readout(scan_param_id = param_id, fill_buffer=True, clear_buffer=True):
                    
                    
                    self.dut['gate_tdc'].start()
                    while not self.dut['gate_tdc'].is_done():
                        pass
                    
                    while not self.dut['inj'].is_done():
                        pass
                    
                    time.sleep(0.01)
                    
                self.dut['inj'].set_en(False)
                dqdata = self.fifo_readout.data
                try:
                    data = np.concatenate([item[0] for item in dqdata])
                except ValueError:
                    data = []
                logging.info('Scan Pixel Finished: %s V=%f TDC_COUNT=%d', str(pix), vol, len(data))

            self.dut['TH'].set_voltage(1.5, unit='V')


        
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
            import monopix_daq.analysis as analysis
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
                A, mu, sigma = analysis.fit_scurve(hit_map[:,i], scan_range, repeat_command)
                logging.info('|%s :%s | mu=%s  sigma=%s', str(pix).rjust(10), "".join([str(hits).rjust(5) for hits in hit_map[:,i]]), str(mu), str(sigma),)
                
            logging.info('|------------%s |', "-----"*len(scan_range))
            
        return hit_map
        
if __name__ == "__main__":

    scan = ThresholdScanMonitor()
    scan.start(**local_configuration)
    scan.analyze()
