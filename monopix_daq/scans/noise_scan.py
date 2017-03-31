
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
    "column_enable": range(24,28),
    "start_threshold": 0.81,
    "stop_on_disabled": 6
}

class NoiseScan(ScanBase):
    scan_id = "noise_scan"

    def scan(self, start_threshold = 1.5, column_enable = [], stop_on_disabled = 1, **kwargs):

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
        
        for pix_col in column_enable:
            dcol = int(pix_col/2) 
            self.dut['CONF_SR']['ColRO_En'][35-pix_col] = 1
            
            self.dut.PIXEL_CONF['TRIM_EN'][pix_col,:] = 0
            self.dut.PIXEL_CONF['PREAMP_EN'][pix_col,:] = 1 
        
        self.dut.write_global_conf()
        self.dut.write_pixel_conf()
        
        TH = start_threshold 

        finished = False
        idx = 0
        dec_threshod = False
        dissabled_pixels = {}
        
        np.set_printoptions(linewidth=260)
        
        while not finished:
            
            self.dut['CONF']['RESET_GRAY'] = 1
            self.dut['CONF']['RESET'] = 1
            self.dut['CONF'].write()

            self.dut['CONF']['RESET'] = 0
            self.dut['CONF'].write()
            
            self.dut['CONF']['RESET_GRAY'] = 0
            self.dut['CONF'].write()

            self.dut['data_rx'].set_en(True)
            time.sleep(0.2)
            
            if dec_threshod:
                TH -= 0.001
            
            self.dut['TH'].set_voltage(TH, unit='V')  
            logging.info('Threshold: %f', TH)
            
            time.sleep(0.2)
                
            param_id = idx
            logging.info('Scan Pixel TH: %f (ID=%d)', TH, param_id)
            
            with self.readout(scan_param_id = param_id, fill_buffer=True, clear_buffer=True):
                
                self.dut['data_rx'].reset()
                self.dut['data_rx'].set_en(True)
                self.dut['fifo'].reset()
            
                self.dut['gate_tdc'].start()
                while not self.dut['gate_tdc'].is_done():
                    pass
                
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
            
            mage_hit = len(hit_pixels) > len(column_enable)*129*0.5 #50%
            
            
            msg = 'Correction: '
            if data_size and not mage_hit:    
                for pix in hit_pixels:
                    col = pix / 129
                    row = pix % 129
                    
                    if col > 35 or row > 129:
                        logging.warning('Something went very wrong! col=%d, row=%d, pix=%d', col, row, pix)
                    else:
                        if self.dut.PIXEL_CONF['TRIM_EN'][col,row] == 15:
                            self.dut.PIXEL_CONF['PREAMP_EN'][col,row] = 0
                            #dissabled_pixels_cnt += 1
                            pix_str = str([col, row])
                            if pix_str in dissabled_pixels:
                                dissabled_pixels[pix_str] += 1
                            else:
                                dissabled_pixels[pix_str] = 1
                            logging.info("DISABLE: %d, %d", col, row)
                            
                        else:
                            self.dut.PIXEL_CONF['TRIM_EN'][col,row] += 1
 
                        msg += '[%d, %d]=%d ' % (col, row , self.dut.PIXEL_CONF['TRIM_EN'][col,row])
                
                self.dut.write_pixel_conf()
                
                logging.info(msg)
                dec_threshod = False

            else:
                dec_threshod = True
            #dec_threshod = True
            
            msg = 'MEGA_HIT:'
            if mage_hit:
                for pix in hit_pixels:
                    col = pix / 129
                    row = pix % 129
                    msg += '[%d, %d] ' % (col, row)
                    
                logging.warning(msg)
                dec_threshod = False
            
            hist =  np.bincount(self.dut.PIXEL_CONF['TRIM_EN'][self.dut.PIXEL_CONF['PREAMP_EN'] == True])
            logging.info('Hist=%s', str(hist) )
            logging.info('Dissabled=%s', str(dissabled_pixels) )
            
            for col in column_enable:
                logging.info('Col[%d]=%s',col, str(self.dut.PIXEL_CONF['TRIM_EN'][col,:]))

            if data_size > 10000000 or idx > 1000 or len(dissabled_pixels) > stop_on_disabled:
                logging.warning('EXIT: stop_on_disabled=%d data_size=%d id=%d', len(dissabled_pixels), data_size, idx)
                finished = True
                
            idx += 1    
            
            self.dut['TH'].set_voltage(1.5, unit='V')

        scan_results = self.h5_file.create_group("/", 'scan_results', 'Scan Results')
        self.h5_file.create_carray(scan_results, 'TRIM_EN', obj=self.dut.PIXEL_CONF['TRIM_EN'])
        self.h5_file.create_carray(scan_results, 'PREAMP_EN', obj=self.dut.PIXEL_CONF['PREAMP_EN'] )
        logging.info('Final threshold value: %s', str(TH))
        self.meta_data_table.attrs.final_threshold = TH


    def analyze(self, h5_filename  = ''):
        pass
    
if __name__ == "__main__":

    scan = NoiseScan()
    scan.start(**local_configuration)
    scan.analyze()
