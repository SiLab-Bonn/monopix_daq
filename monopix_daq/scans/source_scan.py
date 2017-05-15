import time
import logging
import numpy as np
import bitarray
import tables as tb
import yaml
import os

from monopix_daq.scan_base import ScanBase
from progressbar import ProgressBar
from basil.dut import Dut

logging.basicConfig(level=logging.INFO, format="%(asctime)s - %(name)s - [%(levelname)-8s] (%(threadName)-10s) %(message)s")




local_configuration = {
    #'mask_filename': '/home/idcs/STREAM/Devices/MONOPIX_01/Tests/20170424_TestBeam_MIPs+Bias/noise_tune/20170424_094650_noise_scan.h5',
    "TH": 0.855,
    "columns": range(24, 28),
    "threshold_overdrive" : 0.007
}

class SourceScan(ScanBase):
    scan_id = "source_scan"

    def scan(self, TH = 1.5, column_enable = [], mask_filename = '', threshold_overdrive = 0.001, columns = range(36), **kwargs):

#        self.dut['fifo'].reset()
#        self.dut.write_global_conf()
        self.dut['TH'].set_voltage(1.5, unit='V')
        
        self.dut['VDDD'].set_voltage(1.7, unit='V')        
        self.dut['VDD_BCID_BUFF'].set_voltage(1.7, unit='V')
           

        self.dut["CONF_SR"]["PREAMP_EN"] = 1
        self.dut["CONF_SR"]["INJECT_EN"] = 1
        self.dut["CONF_SR"]["MONITOR_EN"] = 0
        self.dut["CONF_SR"]["REGULATOR_EN"] = 1
        self.dut["CONF_SR"]["BUFFER_EN"] = 1
        
        #VPFB Feedback
        self.dut["CONF_SR"]["VPFB"] = 4

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

        self.dut['CONF_SR']['MON_EN'].setall(True)
        self.dut['CONF_SR']['INJ_EN'].setall(True)
        self.dut['CONF_SR']['ColRO_En'].setall(False)
        
        self.dut.PIXEL_CONF['PREAMP_EN'][:] = 0
        self.dut.PIXEL_CONF['INJECT_EN'][:] = 0
        self.dut.PIXEL_CONF['MONITOR_EN'][:] = 0
        self.dut.PIXEL_CONF['TRIM_EN'][:] = 15

        TRIM_EN = self.dut.PIXEL_CONF['TRIM_EN'].copy()
                
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
                
                TH = in_file_h5.root.meta_data.attrs.final_threshold + threshold_overdrive
                logging.info('Loading threshold values (+%f): %f', threshold_overdrive, TH)
                
                logging.info('Loading DAC values from: %s', str(dac_status))
                dac_names = ['BLRes', 'VAmp', 'VPFB', 'VPFoll', 'VPLoad', 'IComp', 'Vbias_CS', 'IBOTA', 'ILVDS', 'Vfs', 'LSBdacL', 'Vsf_dis1', 'Vsf_dis2','Vsf_dis3']
                for dac in  dac_names:
                   self.dut['CONF_SR'][dac] = dac_status[dac]
                   #print dac, self.dut['CONF_SR'][dac]
                    
                scan_kwargs = yaml.load(in_file_h5.root.meta_data.attrs.kwargs)
                columns = scan_kwargs['column_enable']
                logging.info('Column Enable: %s', str(columns))
        
        else:
            for pix_col in columns:
                TRIM_EN[pix_col,:] = 7
                self.dut.PIXEL_CONF['PREAMP_EN'][pix_col,:] = 1
        
        for pix_col in columns: 
            self.dut['CONF_SR']['ColRO_En'][35-pix_col] = 1
            
        self.dut.PIXEL_CONF['TRIM_EN'][:] = TRIM_EN[:]
        
        self.dut.write_global_conf()
        self.dut.write_pixel_conf()
        
        self.dut['CONF']['RESET_GRAY'] = 1
        self.dut['CONF'].write()
        
        self.dut['CONF']['RESET_GRAY'] = 0
        self.dut['CONF'].write()
        
        logging.info('Threshold: %f', TH)
        self.dut['TH'].set_voltage(TH, unit='V')
        
        time.sleep(0.1)
        self.dut['data_rx'].reset()
        self.dut['data_rx'].set_en(True)
        time.sleep(0.2)
        self.dut['data_rx'].set_en(False)
        self.dut['fifo'].reset()
        
        with self.readout(scan_param_id = 0, fill_buffer=True, clear_buffer=True):
            
            self.dut['data_rx'].reset()
            self.dut['data_rx'].set_en(True)
             
            for i in range(2000):
                time.sleep(10)
                logging.info("Time = " + str(i) + '-'*20)
                
                dqdata = self.fifo_readout.data
                try:
                    data = np.concatenate([item[0] for item in dqdata])
                except :
                    data = []

                hit_data = self.dut.interpret_rx_data(data)

                data_size = len(data) 
                
                pixel_data = hit_data['col']*129+hit_data['row']
                hit_pixels = np.unique(pixel_data)
                hist =  np.bincount(pixel_data)
                
                hist = np.pad(hist, (0, 36 * 129 - hist.shape[0]), 'constant')
                hist_array = np.reshape(hist, [36,129])

                np.set_printoptions(linewidth=260)
                
                for pix_col in columns:
                    logging.info('Col[%d]=%s',pix_col, str(hist_array[pix_col,:]))
                
                np.save(self.output_filename +'.npy', hist_array)
                        
                msg = ' '
                if data_size:   
                    for pix in hit_pixels:
                        col = pix / 129
                        row = pix % 129
                                           
                        msg += '[%d, %d]=%d ' % (col, row , hist[pix])
                    
                    logging.info(msg)

            self.dut['data_rx'].set_en(False)
            self.dut['TH'].set_voltage(1.5, unit='V')
            
    def analyze(self, h5_filename  = ''):
    
        if h5_filename == '':
            h5_filename = self.output_filename +'.h5'
        
        logging.info('Anallyzing: %s', h5_filename)
        np.set_printoptions(linewidth=240)
         
        with tb.open_file(h5_filename, 'r+') as in_file_h5:
            raw_data = in_file_h5.root.raw_data[:]
            meta_data = in_file_h5.root.meta_data[:]
            
            #print raw_data
            hit_data = self.dut.interpret_rx_data(raw_data, meta_data)
            in_file_h5.create_table(in_file_h5.root, 'hit_data', hit_data, filters=self.filter_tables)
            
    
if __name__ == "__main__":

    scan = SourceScan()
    scan.start(**local_configuration)
    scan.analyze()
