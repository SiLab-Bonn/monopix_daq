
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
    "repeat": 100,
    "mask_filename": '',
    "scan_range": [0.0, 0.4, 0.01],
    "mask" : 16,
    "TH": 0.740,
    "columns": range(0, 4)
}

class ThresholdScan(ScanBase):
    scan_id = "threshold_scan"

    def scan(self,  repeat = 100, scan_range = [0, 0.2, 0.05], mask_filename = '', TH = 1.5, mask = 16, columns = range(0, 36), **kwargs):

        '''Scan loop
        Parameters
        ----------
        mask : int
            Number of mask steps.
        repeat : int
            Number of injections.
        '''

        #LSB
        self.dut["CONF_SR"]["LSBdacL"] = 60
        
        INJ_LO = 0.4
        self.dut['INJ_LO'].set_voltage(INJ_LO, unit='V')

        self.dut['TH'].set_voltage(1.5, unit='V')
        self.dut['VDDD'].set_voltage(1.6, unit='V')        
        self.dut['VDD_BCID_BUFF'].set_voltage(1.6, unit='V')

        self.dut['inj'].set_delay(20*64)
        self.dut['inj'].set_width(20*64)
        self.dut['inj'].set_repeat(repeat)
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

        self.dut['CONF_SR']['MON_EN'].setall(False)
        self.dut['CONF_SR']['INJ_EN'].setall(False)
        self.dut['CONF_SR']['ColRO_En'].setall(False)
        
        self.dut.PIXEL_CONF['PREAMP_EN'][:] = 0
        self.dut.PIXEL_CONF['INJECT_EN'][:] = 0
        self.dut.PIXEL_CONF['MONITOR_EN'][:] = 0
        self.dut.PIXEL_CONF['TRIM_EN'][:] = 15
    

        TRIM_EN = self.dut.PIXEL_CONF['PREAMP_EN'].copy()
                
        #LOAD PIXEL DAC
        if mask_filename:
            with tb.open_file(str(mask_filename), 'r') as in_file_h5:
                logging.info('Loading configuration from: %s', mask_filename)
                
                TRIM_EN = in_file_h5.root.scan_results.TRIM_EN[:]
                PREAMP_EN = in_file_h5.root.scan_results.PREAMP_EN[:]

                self.dut.PIXEL_CONF['TRIM_EN'][:] = TRIM_EN[:]
                self.dut.PIXEL_CONF['PREAMP_EN'][:] = PREAMP_EN[:]
                
                dac_status = yaml.load(in_file_h5.root.meta_data.attrs.dac_status)
                power_status = yaml.load(in_file_h5.root.meta_data.attrs.power_status)
                
                TH = in_file_h5.root.meta_data.attrs.final_threshold + 0.001
                
                scan_kwargs = yaml.load(in_file_h5.root.meta_data.attrs.kwargs)
                columns = scan_kwargs['column_enable']
                logging.info('Column Enable: %s', str(columns))
        
        else:
            for pix_col in columns:
                TRIM_EN[pix_col,:] = 7
                self.dut.PIXEL_CONF['PREAMP_EN'][pix_col,:] = 1
        
        for pix_col in columns:
            dcol = int(pix_col/2)  
            self.dut['CONF_SR']['ColRO_En'][35-pix_col] = 1
            
        self.dut.PIXEL_CONF['TRIM_EN'][:] = TRIM_EN[:]
        self.dut.write_global_conf()
        self.dut.write_pixel_conf()
        
        scan_range = np.arange(scan_range[0], scan_range[1], scan_range[2])
        
        logging.info('Threshold: %f', TH)
        self.dut['TH'].set_voltage(TH, unit='V')
        
        for pix_col_indx, pix_col in enumerate(columns):
            
            self.dut.PIXEL_CONF['TRIM_EN'][:] = TRIM_EN[:]
            self.dut['CONF_SR']['INJ_EN'].setall(False)
            
            mask_steps = []
            for m in range(mask):
                col_mask = np.copy(self.dut.PIXEL_CONF['INJECT_EN'][pix_col,:])
                col_mask[m::mask] = True
                mask_steps.append(np.copy(col_mask))

            for idx, mask_step in enumerate(mask_steps): #mask steps
                
                
                dcol = int(pix_col/2)  
                self.dut.PIXEL_CONF['INJECT_EN'][pix_col,:] = mask_step
                self.dut['CONF_SR']['INJ_EN'][17-dcol] = 1
                self.dut.PIXEL_CONF['PREAMP_EN'][pix_col,:]
                
                self.dut.write_global_conf()
                self.dut.write_pixel_conf()
                
                self.dut['CONF']['RESET_GRAY'] = 1
                self.dut['CONF']['RESET'] = 1
                self.dut['CONF'].write()

                self.dut['CONF']['RESET'] = 0
                self.dut['CONF'].write()
                
                self.dut['CONF']['RESET_GRAY'] = 0
                self.dut['CONF'].write()

                for vol_idx, vol in enumerate(scan_range):
                    
                    
                    param_id = pix_col_indx*len(scan_range)*mask + idx * len(scan_range) + vol_idx
                    
                    logging.info('Scan : Column = %s MaskId=%d InjV=%f ID=%d)', pix_col, idx, vol, param_id)
                    
                    self.dut['INJ_HI'].set_voltage( float(INJ_LO + vol), unit='V')
                    self.dut['TH'].set_voltage(TH, unit='V') 
                      
                    time.sleep(0.2)
                    self.dut['data_rx'].reset()
                    self.dut['data_rx'].set_en(True)
                    time.sleep(0.2)
                    self.dut['fifo'].reset()
                    self.dut['data_rx'].set_en(False)
                    
                    with self.readout(scan_param_id = param_id, fill_buffer=True, clear_buffer=True):
                        
                        self.dut['data_rx'].reset()
                        self.dut['fifo'].reset()
                        self.dut['data_rx'].set_en(True)
                        
                        self.dut['inj'].start()
                        while not self.dut['inj'].is_done():
                            pass
                        
                        time.sleep(0.1)
                        
                        self.dut['data_rx'].set_en(False)
                        self.dut['TH'].set_voltage(1.5, unit='V')
                
                    dqdata = self.fifo_readout.data
                    try:
                        data = np.concatenate([item[0] for item in dqdata])
                    except ValueError:
                        data = []
                        
                    data_size = len(data) 
                    logging.info('Scan Pixel Finished: V=%f DATA_COUNT=%d', vol, data_size)
                    
                    hit_data = self.dut.interpret_rx_data(data)
                    pixel_data = hit_data['col']*129+hit_data['row']
                    hit_pixels = np.unique(pixel_data)
                    hist =  np.bincount(pixel_data)
                    msg = ' '
                    
                    if data_size:   
                        for pix in hit_pixels:
                            col = pix / 129
                            row = pix % 129
                            msg += '[%d, %d]=%d ' % (col, row , hist[pix])
                        logging.info(msg)
            
                    if data_size > 100000:
                        logging.error('To much data!')
                        return


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
		    
            import yaml
            import monopix_daq.analysis as analysis
            scan_args = yaml.load(in_file_h5.root.meta_data.attrs.kwargs)
            
            columns = scan_args['columns']
            mask = scan_args['mask']
            scan_range = scan_args['scan_range']
            scan_range = np.arange(scan_range[0], scan_range[1], scan_range[2])
            
            repeat = scan_args['repeat']
            
            scan_params = (np.max(hit_data['scan_param_id'])+1)/len(scan_range)
            
            scan_range_size = len(scan_range)
            
            
            logging.info('|------------%s |', "-----"*len(scan_range))
            logging.info('|           :%s |', "".join([str(scan).rjust(4) for scan in scan_range]))
            logging.info('|------------%s |', "-----"*len(scan_range))
            
            for param in range(scan_params):
                hit_map = np.zeros((129*36, scan_range_size), dtype = np.int16)
                for i in range(scan_range_size):
                    wh = np.where(hit_data['scan_param_id'] == param*scan_range_size + i)
                    hd = hit_data[wh[0]]
                    
                    pix_hits = hd['col']*129+hd['row']
                    pix_uniq = np.unique(pix_hits)
                    hist =  np.bincount(pix_hits)
                    
                    pix_bc = np.bincount(pix_hits)
                    tot = hd['te']-hd['le']
                    #TODO: TOT=0 check why?
                    
                    for ph in pix_uniq:
                        hit_map[ph,i] = hist[ph]
                    
                where_hit = np.unique(np.where(hit_map > 0)[0])

                for i, pix in enumerate(where_hit):
                    A, mu, sigma = analysis.fit_scurve(hit_map[pix,:], scan_range, repeat)
                    logging.info('|%s :%s | mu=%s  sigma=%s', str([pix/129,pix%129]).rjust(10), "".join([str(hits).rjust(4) for hits in hit_map[pix,:]]), str(mu), str(sigma),)
                

            logging.info('|------------%s |', "-----"*len(scan_range))
            
            
        
if __name__ == "__main__":

    scan = ThresholdScan()
    scan.start(**local_configuration)
    scan.analyze()
