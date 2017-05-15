import time
import logging
import numpy as np
import tables as tb

from monopix_daq.scan_base import ScanBase
from progressbar import ProgressBar
from basil.dut import Dut

logging.basicConfig(level=logging.INFO, format="%(asctime)s - %(name)s - [%(levelname)-8s] (%(threadName)-10s) %(message)s")

local_configuration = {
    "column_enable": range(12,16),              #Range of columns to be considered
    "start_threshold": 0.79,                   #Initial global Threshold value (in Volts)
    "stop_on_disabled": 6                       #Maximum number of pixels 
}

class NoiseScan(ScanBase):
    scan_id = "noise_scan"

    def scan(self, start_threshold = 1.5, column_enable = [], stop_on_disabled = 1, **kwargs):

       
        self.dut['fifo'].reset()
        self.dut.write_global_conf()
        self.dut['TH'].set_voltage(1.5, unit='V')

        self.dut['VDDD'].set_voltage(1.7, unit='V')        
        self.dut['VDD_BCID_BUFF'].set_voltage(1.7, unit='V')
        #self.dut['VPC'].set_voltage(1.5, unit='V')
        
        self.dut['inj'].set_en(False)

        #40M BX -> 10^7, the gate_tdc counter determines the total time pixels are measuring, BX Units
        self.dut['gate_tdc'].set_delay(500)
        self.dut['gate_tdc'].set_width(500)
        self.dut['gate_tdc'].set_repeat(10000)
        self.dut['gate_tdc'].set_en(False)              #disabling external start
        

        self.dut["CONF_SR"]["PREAMP_EN"] = 1
        self.dut["CONF_SR"]["INJECT_EN"] = 1
        self.dut["CONF_SR"]["MONITOR_EN"] = 0
        self.dut["CONF_SR"]["REGULATOR_EN"] = 1
        self.dut["CONF_SR"]["BUFFER_EN"] = 1

        #LSB
        self.dut["CONF_SR"]["LSBdacL"] = 42
        
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
        
        self.dut['CONF']['RESET_GRAY'] = 0          #Why do we enable and disable RESETs? (IDCS) ---Time while you write in between. 
        self.dut['CONF'].write()

        self.dut['CONF_SR']['MON_EN'].setall(False)
        self.dut['CONF_SR']['INJ_EN'].setall(False)
        self.dut['CONF_SR']['ColRO_En'].setall(False)
        
        self.dut.PIXEL_CONF['PREAMP_EN'][:] = 0
        self.dut.PIXEL_CONF['INJECT_EN'][:] = 0
        self.dut.PIXEL_CONF['MONITOR_EN'][:] = 1    #Why monitor enabled in noise scan and not in threshold scan? (Check if when enable it makes a difference)
        self.dut.PIXEL_CONF['TRIM_EN'][:] = 15
     
        PREAMP_EN = self.dut.PIXEL_CONF['PREAMP_EN'].copy() #Making an independent copy (IDCS)
     
        mask = 32                                           #Mask step (IDCS)
        for pix_col in column_enable:
            self.dut['CONF_SR']['ColRO_En'][35-pix_col] = 1
            
        #    #self.dut.PIXEL_CONF['TRIM_EN'][pix_col,:] = 0
        #    #self.dut.PIXEL_CONF['PREAMP_EN'][pix_col,:] = 1 
        #
        #    self.dut.PIXEL_CONF['TRIM_EN'][pix_col,::mask] = 0
            self.dut.PIXEL_CONF['PREAMP_EN'][pix_col,:] = 1         
            
            print  self.dut.PIXEL_CONF['PREAMP_EN'][pix_col,:]          #Check if this is printing the right thing (IDCS)
        
        TRIM_EN = self.dut.PIXEL_CONF['TRIM_EN'].copy()
        TRIM_EN[:] = 0
        
        PREAMP_EN[:] = self.dut.PIXEL_CONF['PREAMP_EN'][:]
            
        self.dut.write_global_conf()
        self.dut.write_pixel_conf()
        
        TH = start_threshold 
        finished = False
        idx = 0
        dec_threshod = False
        disabled_pixels = {}
        
        np.set_printoptions(linewidth=260)
                
        while not finished:
           
            if dec_threshod:
                #TH -= 0.0002
                TH -= 0.0005
            
            mask_steps = []
            for m in range(mask):
                noise_mask = np.full([36,129], False, dtype = np.bool)
                noise_mask[column_enable[0]:column_enable[-1]+1,m::mask] = True
                #print column_enable[0], noise_mask[column_enable[0],:]
                #print column_enable[-1], noise_mask[column_enable[-1],:]
                mask_steps.append(np.copy(noise_mask))
                
            logging.info('Scan Pixel TH: %f (ID=%d)', TH, idx)
            
            clear_buffer = True

            for m_index, mask_step in enumerate(mask_steps): #mask steps
                
                #only trim masked
                self.dut.PIXEL_CONF['TRIM_EN'][:] = 15
                self.dut.PIXEL_CONF['TRIM_EN'][mask_step] = TRIM_EN[mask_step] 
                
                #self.dut.write_global_conf()
                self.dut.write_pixel_conf()
                                
                #time.sleep(0.1)
                
                self.dut['TH'].set_voltage(TH, unit='V')  
                #print self.dut['TH'].get_voltage(unit='V')  
                
                logging.info('m_index TH: %f (ID=%d)', TH, m_index)
                
                time.sleep(0.1)
                
                self.dut['data_rx'].set_en(True)
                
                time.sleep(0.1)
                    
                param_id = idx
                
                self.dut['data_rx'].reset()
                self.dut['data_rx'].set_en(False)       #Giving time to clean up the chip on every step (IDCS)
                self.dut['fifo'].reset()
                    
                with self.readout(scan_param_id = param_id, fill_buffer=True, clear_buffer=clear_buffer):
                
                    self.dut['data_rx'].set_en(True)    
                    self.dut['gate_tdc'].start()
                    while not self.dut['gate_tdc'].is_done():
                        pass
                    
                    self.dut['data_rx'].set_en(False)
                    self.dut['TH'].set_voltage(1.5, unit='V')       #It makes the chip quiet while other things are done
                    
                clear_buffer = False
                
            dqdata = self.fifo_readout.data
            try:
                data = np.concatenate([item[0] for item in dqdata])     #Getting the data out of the memory
            except ValueError:
                data = []

            hit_data = self.dut.interpret_rx_data(data)

            data_size = len(data) 
            
            pixel_data = hit_data['col']*129+hit_data['row']        #pixel_data: Universal pixel numbers for all pixels in hit_data
            hit_pixels = np.unique(pixel_data)                      #hit_pixels: List of non-repeated hit pixels
            hit_hist =  np.bincount(pixel_data)                     #calculates the number of occurencies of every value

            mega_hit = 0 #len(hit_pixels) > len(column_enable)*129*0.5 #50%
            
            dec_threshod = True
            msg = 'Correction: '
            if data_size and not mega_hit:    
                for pix in hit_pixels:
                    col = pix / 129
                    row = pix % 129
                        
                    if hit_hist[pix] > 1:              
                      
                        
                        if col > 35 or row > 129 or col < 0 or row < 0:
                            logging.warning('Something went very wrong! col=%d, row=%d, pix=%d', col, row, pix)
                        else:
                            if TRIM_EN[col,row] == 15 :
                                self.dut.PIXEL_CONF['PREAMP_EN'][col,row] = 0
                                #disabled_pixels_cnt += 1
                                pix_str = str([col, row])
                                if PREAMP_EN[col,row]:                                      
                                    if pix_str in disabled_pixels:                          
                                        disabled_pixels[pix_str] += 1
                                    else:
                                        disabled_pixels[pix_str] = 1                        
                                    logging.info("DISABLE: %d, %d", col, row)
                                logging.warning("DISABLE OUT OF RANGE: %d, %d", col, row)
                                
                            else:
                                #self.dut.PIXEL_CONF['TRIM_EN'][col,row] += 1
                                TRIM_EN[col,row] += 1
                                dec_threshod = False
     
                    if col <= 35 and row <= 129:
                        msg += '[%d, %d]=%d(%d) ' % (col, row , TRIM_EN[col,row], hit_hist[pix])
                
                self.dut.write_pixel_conf()
                
                logging.info(msg)
                
            #dec_threshod = True
            
            msg = 'MEGA_HIT:'
            if mega_hit:
                for pix in hit_pixels:
                    col = pix / 129
                    row = pix % 129
                    msg += '[%d, %d] ' % (col, row)
                    
                logging.warning(msg)
                dec_threshod = False
            
            hist =  np.bincount(TRIM_EN[self.dut.PIXEL_CONF['PREAMP_EN'] == True])
            logging.info('Hist=%s', str(hist) )
            logging.info('Disabled=%s', str(disabled_pixels) )
            
            for col in column_enable:
                logging.info('Col[%d]=%s',col, str(TRIM_EN[col,:]))

            if data_size > 10000000 or idx > 1000 or len(disabled_pixels) > stop_on_disabled:
                logging.warning('EXIT: stop_on_disabled=%d data_size=%d id=%d', len(disabled_pixels), data_size, idx)
                finished = True
                
            idx += 1    
            
            self.dut['TH'].set_voltage(1.5, unit='V')

        scan_results = self.h5_file.create_group("/", 'scan_results', 'Scan Results')
        self.h5_file.create_carray(scan_results, 'TRIM_EN', obj=TRIM_EN)
        self.h5_file.create_carray(scan_results, 'PREAMP_EN', obj=self.dut.PIXEL_CONF['PREAMP_EN'] )
        logging.info('Final threshold value: %s', str(TH))
        self.meta_data_table.attrs.final_threshold = TH


    def analyze(self, h5_filename  = ''):
        pass
    
if __name__ == "__main__":

    scan = NoiseScan()
    scan.start(**local_configuration)
    scan.analyze()
