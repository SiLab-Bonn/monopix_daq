
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
    "scan_range": [0.0, 0.8, 0.025],
    "scan_pixels": [[0,62], [1,62]],
    "TH": 0.790
}

class ThresholdScan(ScanBase):
    scan_id = "threshold_scan"

    def scan(self,  repeat_command = 100, scan_range = [0, 0.2, 0.05], mask_filename = '', TH = 1.5, scan_pixels = [], **kwargs):

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
        
        #if mask_filename:
        #    logging.info('Using pixel mask from file: %s', mask_filename)
        #
        #    with tb.open_file(mask_filename, 'r') as in_file_h5:
        #        mask_tdac = in_file_h5.root.scan_results.tdac_mask[:]
        #        mask_en = in_file_h5.root.scan_results.en_mask[:]
        #SCAN
        self.dut['TH'].set_voltage(1.5, unit='V')

        self.dut['VDDD'].set_voltage(1.7, unit='V')        
        self.dut['VDD_BCID_BUFF'].set_voltage(1.7, unit='V')
        #self.dut['VPC'].set_voltage(1.5, unit='V')

        self.dut['inj'].set_delay(20*64)
        self.dut['inj'].set_width(20*64)
        self.dut['inj'].set_repeat(repeat_command)
        self.dut['inj'].set_en(False)
            

        self.dut["CONF_SR"]["PREAMP_EN"] = 1
        self.dut["CONF_SR"]["INJECT_EN"] = 1
        self.dut["CONF_SR"]["MONITOR_EN"] = 0
        self.dut["CONF_SR"]["REGULATOR_EN"] = 1
        self.dut["CONF_SR"]["BUFFER_EN"] = 1

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

        scan_range = np.arange(scan_range[0], scan_range[1], scan_range[2])
        
        logging.info('Start Scan: pixels=%s scan_range=%s', str(scan_pixels), str(scan_range))
        logging.info('Threshold: %f', TH)

        for idx, pix in enumerate(scan_pixels):
            
            #SELECT_PIXEL
            pix_col = pix[0]
            pix_row = pix[1]
            print pix_col
            
            dcol = int(pix_col/2)
            
            self.dut['CONF_SR']['MON_EN'].setall(False)
            self.dut['CONF_SR']['MON_EN'][pix_col] = 1

            self.dut['CONF_SR']['INJ_EN'].setall(False)
            self.dut['CONF_SR']['INJ_EN'][17-dcol] = 1
            
            self.dut['CONF_SR']['ColRO_En'].setall(False)
            self.dut['CONF_SR']['ColRO_En'][35-pix_col] = 1
            
            self.dut.write_global_conf()
            
            #CONFIGURE PIXELS
            self.dut.PIXEL_CONF['PREAMP_EN'][:] = 0
            self.dut.PIXEL_CONF['PREAMP_EN'][pix_col,:] = 1 
            
            self.dut.PIXEL_CONF['TRIM_EN'][:] = 15
            self.dut.PIXEL_CONF['TRIM_EN'][pix_col, pix_row] = 0 
            
            self.dut.PIXEL_CONF['INJECT_EN'][:] = 0
            self.dut.PIXEL_CONF['INJECT_EN'][pix_col, pix_row] = 1
            
            self.dut.PIXEL_CONF['MONITOR_EN'][:] = 0
            #self.dut.PIXEL_CONF['MONITOR_EN'][pix_col, pix_row] = 1

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
            time.sleep(0.2)
            self.dut['data_rx'].reset()
            self.dut['data_rx'].set_en(True)
            self.dut['fifo'].reset()

            for vol_idx, vol in enumerate(scan_range):
                
                param_id = idx * len(scan_range) + vol_idx
                logging.info('Scan Pixel Start: %s (V=%f ID=%d)', str(pix), vol, param_id)
                
                self.dut['INJ_HI'].set_voltage( float(INJ_LO + vol), unit='V')
                #self.dut['INJ_HI'].set_voltage( float(INJ_LO + 0), unit='V')

                time.sleep(0.1)
                
                with self.readout(scan_param_id = param_id, fill_buffer=True, clear_buffer=True):
                    
                    self.dut['inj'].start()
                    while not self.dut['inj'].is_done():
                        pass
                    
                    time.sleep(0.2)
                    
                dqdata = self.fifo_readout.data
                try:
                    data = np.concatenate([item[0] for item in dqdata])
                except ValueError:
                    data = []
                logging.info('Scan Pixel Finished: %s V=%f DATA_COUNT=%d', str(pix), vol, len(data))
                if len(data) > 10000:
                    return

            self.dut['data_rx'].set_en(False)
            self.dut['TH'].set_voltage(1.5, unit='V')

        print self.dut.power_status()


    def analyze(self, h5_filename  = ''):
        if h5_filename == '':
            h5_filename = self.output_filename +'.h5'
        
        logging.info('Anallyzing: %s', h5_filename)
        
        with tb.open_file(h5_filename, 'r+') as in_file_h5:
            raw_data = in_file_h5.root.raw_data[:]
            meta_data = in_file_h5.root.meta_data[:]
            
            #print raw_data
            hit_data = self.dut.interpret_rx_data(raw_data, meta_data)
            #in_file_h5.create_table(in_file_h5.root, 'hit_data', hit_data, filters=self.filter_tables)
		
            pix = hit_data['col']*129+hit_data['row']
            
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
                wh = np.where(hit_data['scan_param_id'] == i)  # this can be faster
                hd = hit_data[wh[0]]
                
                pix = int(i / len(scan_range))
                scan = i %  len(scan_range)
                
                pix_hits = hd['col']*129+hd['row']
                pix_uniq = np.unique(pix_hits)
                pix_bc = np.bincount(pix_hits)
                tot = hd['te']-hd['le']
                
                hit_list = ''
                
                righ_hits =  len(np.where( tot > 0 )[0])
                righ_tot  = np.mean(tot[np.where( tot > 0 )[0]])
                
                for i in pix_uniq:
                    hit_list +=' [%d,%d]=%d (%d) {tot=%f (%f)}' % ( i/129, i%129, pix_bc[i], righ_hits, np.mean(tot), righ_tot)
                    
                
                logging.info( str(scan_pixels[pix]) + ': ' + str(pix) + ' ' + str(pix) + ' '+ str(hit_list)) # + ' le:'+ str(hd['le']) +' te:'+ str(hd['te']) + ' '+ str(tot))
                
                hit_map[scan,pix] = len(hd)
            
            logging.info('|------------%s |', "-----"*len(scan_range))
            logging.info('|           :%s |', "".join([str(scan).rjust(4) for scan in scan_range]))
            logging.info('|------------%s |', "-----"*len(scan_range))

            for i,pix in enumerate(scan_pixels):
                A, mu, sigma = analysis.fit_scurve(hit_map[:,i], scan_range, repeat_command)
                logging.info('|%s :%s | mu=%s  sigma=%s', str(pix).rjust(10), "".join([str(hits).rjust(4) for hits in hit_map[:,i]]), str(mu), str(sigma),)
                
            logging.info('|------------%s |', "-----"*len(scan_range))
            
        return hit_map
        
if __name__ == "__main__":

    scan = ThresholdScan()
    scan.start(**local_configuration)
    scan.analyze()
