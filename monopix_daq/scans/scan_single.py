
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
import monopix_daq.analysis as analysis

local_configuration = {
    "how_long": 60,
    "repeat": 1000,
    "scan_injection": [0.0, 1.0, 0.02],
    "threshold_range": [0.779, 0.779, -0.002],
    "pixel": [1,64] 
}

class ScanSingle(ScanBase):
    scan_id = "scan_single"

    def scan(self, repeat = 100, threshold_range = [0.8, 0.7, -0.05], pixel = [1,64] , how_long = 1, scan_injection = 0, **kwargs):
        
        self.dut['fifo'].reset()
        
        INJ_LO = 0.2
        try:
            pulser = Dut('../agilent33250a_pyserial.yaml') #should be absolute path
            pulser.init()
            logging.info('Connected to '+str(pulser['Pulser'].get_info()))
        except RuntimeError:
            logging.info('External injector not connected. Switch to internal one')

        self.dut['INJ_LO'].set_voltage(INJ_LO, unit='V')


        #self.dut['INJ_LO'].set_voltage(INJ_LO, unit='V')
        
        self.dut['inj'].set_delay(20*64)
        self.dut['inj'].set_width(20*64)
        self.dut['inj'].set_repeat(repeat)
        self.dut['inj'].set_en(False)
        self.dut['gate_tdc'].set_en(False)
        
        
        self.dut.write_global_conf()
        
        self.dut['TH'].set_voltage(1.5, unit='V')

        self.dut['VDDD'].set_voltage(1.6, unit='V')        
        self.dut['VDD_BCID_BUFF'].set_voltage(1.6, unit='V')
        #self.dut['VPC'].set_voltage(1.5, unit='V')
        

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
        self.dut['CONF_SR']['ColRO_En'].setall(True)
        
        self.dut.PIXEL_CONF['PREAMP_EN'][:] = 0
        self.dut.PIXEL_CONF['INJECT_EN'][:] = 0
        self.dut.PIXEL_CONF['MONITOR_EN'][:] = 0
        self.dut.PIXEL_CONF['TRIM_EN'][:] = 15
            
        #LOAD PIXEL DAC
        pix_col = pixel[0]
        pix_row = pixel[1]
        dcol = int(pix_col/2)  

        self.dut.PIXEL_CONF['TRIM_EN'][pix_col,pix_row] = 0
        self.dut.PIXEL_CONF['PREAMP_EN'][pix_col,pix_row] = 1
        self.dut['CONF_SR']['ColRO_En'][35-pix_col] = 1
        
        np.set_printoptions(linewidth=260)
        
        if scan_injection:
            print "scan_injection"
            self.dut.PIXEL_CONF['INJECT_EN'][pix_col,pix_row] = 1
            self.dut['CONF_SR']['INJ_EN'][17-dcol] = 1
            inj_scan_range = np.arange(scan_injection[0], scan_injection[1], scan_injection[2])

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
    
        def print_hist(all_hits = False):    
            dqdata = self.fifo_readout.data
            try:
                data = np.concatenate([item[0] for item in dqdata])
            except ValueError:
                data = []

            hit_data = self.dut.interpret_rx_data(data)
            data_size = len(data) 
            
            pixel_data = hit_data['col']*129+hit_data['row']
            tot = hit_data['te']-hit_data['le']
            scan_pixel = pix_col * 129 + pix_row                    
            scan_pixel_hits = np.where(pixel_data == scan_pixel)[0]
            tot_hist = np.bincount(tot[scan_pixel_hits])
            
            argmax = -1
            if len(tot_hist):
                argmax = np.argmax(tot_hist)
            
            logging.info('Data Count: %d ToT Histogram: %s (argmax=%d)', data_size, str(tot_hist), argmax)
            
        
            if all_hits:
                hit_pixels = np.unique(pixel_data)
                hist =  np.bincount(pixel_data)
                msg = ' '
                for pix in hit_pixels:
                    col = pix / 129
                    row = pix % 129
                                       
                    msg += '[%d, %d]=%d %f' % (col, row , hist[pix], np.mean(tot))
                    
                logging.info(msg)

        th_scan_range = np.arange(threshold_range[0], threshold_range[1], threshold_range[2])
        if len(th_scan_range) == 0:
            th_scan_range = [threshold_range[0]]

        if scan_injection:
            for inx, vol in enumerate(inj_scan_range):
                
                self.dut['TH'].set_voltage(threshold_range[0], unit='V')  
                pulser['Pulser'].set_voltage(INJ_LO, float(INJ_LO + vol), unit='V')
                self.dut['INJ_HI'].set_voltage( float(INJ_LO + vol), unit='V')
                
                logging.info('Scan : TH=%f, InjV=%f ID=%d)',threshold_range[0], vol, inx)
                time.sleep(0.2)
                
                with self.readout(scan_param_id = inx, fill_buffer=True, clear_buffer=True):
  
                    self.dut['data_rx'].reset()
                    self.dut['fifo'].reset()
                    self.dut['data_rx'].set_en(True)

                    self.dut['inj'].start()
                    while not self.dut['inj'].is_done():
                        pass
                    
                    time.sleep(0.2)
                   
                    self.dut['data_rx'].set_en(False)
                    self.dut['TH'].set_voltage(1.5, unit='V')
                    
                #print_hist()
                print_hist(all_hits = True)
                    
        else:
            for inx, TH in enumerate(th_scan_range):
                with self.readout(scan_param_id = inx, fill_buffer=True, clear_buffer=True):
                
                    logging.info('Scan : Threshold=%f ID=%d)', TH, inx)
                    
                    self.dut['TH'].set_voltage(TH, unit='V')
                    time.sleep(0.2)
                    
                    logging.info('Threshold: %f', TH)
                    self.dut['data_rx'].reset()
                    self.dut['fifo'].reset()
                    self.dut['data_rx'].set_en(True)
                    
                    for _ in range(how_long/10):        
                        time.sleep(10)
                        print_hist()
                                    
                    self.dut['data_rx'].set_en(False)
                    self.dut['TH'].set_voltage(1.5, unit='V')
                    
                print_hist(all_hits = True)

    def analyze(self, h5_filename  = ''):
        pass
    
if __name__ == "__main__":

    scan = ScanSingle()
    scan.start(**local_configuration)
    scan.analyze()
