import time
import logging
import numpy as np
import tables as tb
import yaml

import matplotlib
matplotlib.use('Agg')
from monopix_daq.analysis.interpret_scan import interpret_rx_data,interpret_rx_data_scan
from monopix_daq.scan_base import ScanBase
from progressbar import ProgressBar
from basil.dut import Dut
from simple_scan import SimpleScan


logging.basicConfig(level=logging.INFO, format="%(asctime)s - %(name)s - [%(levelname)-8s] (%(threadName)-10s) %(message)s")

local_configuration = {
    "how_long": 60,
    "repeat": 1000,
    #"scan_injection": [0.125, 1.526, 0.025],
    "scan_injection": [0.3, 1.01, 0.025],
    #"threshold_range": [0.780, 0.780, -0.001],#[0.855, 0.855, -0.001],#[1.035, 1.035, -0.001],#[0.7818, 0.7818, -0.001], #[0.793, 0.793, -0.002],[29,64]  #[0.780, 0.780, -0.002]  [1,64]  #[21,64] [0.770, 0.770, -0.001]
    "threshold_range": [0.770, 0.770, -0.001],
    "pixel": [25, 64],
    "LSB_value":45,
    "VPFB_value":32
}

class ScanSingle(SimpleScan):
    scan_id = "scan_single"

    def scan(self, repeat = 10, threshold_range = [0.8, 0.7, -0.05], pixel = [1,64] , how_long = 1, scan_injection = 0, LSB_value=45, VPFB_value = 32, **kwargs):
        
        self.dut['data_rx'].reset()
        self.dut['fifo'].reset()      
        
         #LOAD PIXEL DAC
        pix_col = pixel[0]
        pix_row = pixel[1]
        dcol = int(pix_col / 2)
        
        self.dut['CONF_SR']['MON_EN'][35 - pix_col] = 1

        self.dut.PIXEL_CONF['TRIM_EN'][pix_col, pix_row] = 8
        
        self.dut.PIXEL_CONF['PREAMP_EN'][pix_col, pix_row] = 1
        
        self.dut.PIXEL_CONF['MONITOR_EN'][pix_col, pix_row] = 1
        
        self.dut['CONF_SR']['ColRO_En'][35 - pix_col] = 1
        
        np.set_printoptions(linewidth=260)
        
        if scan_injection:
            logging.info("Starting a scan over injection values between %3f V and %3f V, with %d injections.", scan_injection[0], scan_injection[1], repeat)
            self.dut.PIXEL_CONF['INJECT_EN'][pix_col,pix_row] = 1
            self.dut['CONF_SR']['INJ_EN'][17-dcol] = 1
            inj_scan_range = np.arange(scan_injection[0], scan_injection[1], scan_injection[2])#np.array([0.6, 0.8, 1, 1.2, 1.4])#np.arange(scan_injection[0], scan_injection[1], scan_injection[2])

        self.dut.write_pixel_conf()
        self.dut.write_global_conf()
        
        
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
            #dqdata = self.fifo_readout.data[1:-1]
            dqdata = self.fifo_readout.data
            try:
                data = np.concatenate([item[0] for item in dqdata])
            except ValueError:
                data = []

            hit_data = interpret_rx_data(data)
            data_size = len(data) 

            pixel_data = np.array(hit_data['col'],dtype="int")*129+np.array(hit_data['row'],dtype="int")

            # tot = (hit_data['te'] - hit_data['le']) & 0xFF
            tot = hit_data['te'] - hit_data['le']
            neg = hit_data['te'] < hit_data['le']
            tot[neg] = hit_data['te'][neg] + (255 - hit_data['le'][neg])

            scan_pixel = pix_col * 129 + (pix_row)
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

                    msg += '[%d, %d]=%d %f' % (col, row, hist[pix], np.mean(tot))

                logging.info(msg)
            return tot_hist[0:]

        th_scan_range = np.arange(threshold_range[0], threshold_range[1], threshold_range[2])
        if len(th_scan_range) == 0:
            th_scan_range = [threshold_range[0]]

        inj_scan_dict = {}

        if scan_injection:
            for inx, vol in enumerate(inj_scan_range):
                
                self.dut['TH'].set_voltage(threshold_range[0], unit='V')
                if self.pulser:
                    self.INJ_LO = -0.2
                    self.pulser['Pulser'].set_voltage(self.INJ_LO, float(self.INJ_LO + vol), unit='V')
                else:
                    # Enabled before: (For GPAC injection)
                    self.dut['INJ_LO'].set_voltage(self.INJ_LO, unit='V')
                    self.dut['INJ_HI'].set_voltage(float(self.INJ_LO + vol), unit='V')

                logging.info('Scan : TH=%f, InjV=%f ID=%d)', threshold_range[0], vol, inx)
                
                time.sleep(0.1)                
                self.dut['data_rx'].reset()
                self.dut['fifo'].reset()
                self.dut_extensions.set_monoread(start_freeze=90,start_read=92,stop_read=94,stop_freeze=128,stop=138,gray_reset_by_tdc=1)
                self.dut['TH'].set_voltage(threshold_range[0], unit='V')
                time.sleep(0.2)

                with self.readout(scan_param_id=inx, fill_buffer=True, clear_buffer=True):
                #with self.readout(scan_param_id=inx, fill_buffer=False, clear_buffer=True, reset_sram_fifo=True):
                    
                    #self.dut['data_rx'].CONF_START_FREEZE = 90 #50
                    #self.dut['data_rx'].CONF_START_READ = 92 #52
                    #self.dut['data_rx'].CONF_STOP_FREEZE = 128 #88
                    #self.dut['data_rx'].CONF_STOP_READ = 94 #54
                    #self.dut['data_rx'].CONF_STOP = 138 #100
                    #self.dut['data_rx'].set_en(True)

                    #self.dut['gate_tdc'].start()
                    self.dut['inj'].start()
                    
                    while not self.dut['inj'].is_done():
                        pass

                    time.sleep(0.2)
                    
                    self.dut['data_rx'].set_en(False)
                    
                    self.dut['TH'].set_voltage(1.5, unit='V')

                tot_hist = print_hist(all_hits=True)

                inj_scan_dict[float(vol)] = tot_hist.tolist()

            print inj_scan_dict
#            with open('calib.yml', 'w') as outfile:
#                yaml.dump(inj_scan_dict, outfile, default_flow_style=False)

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

                    for _ in range(how_long / 10):
                        time.sleep(10)
                        print_hist()

                    self.dut['data_rx'].set_en(False)
                    self.dut['TH'].set_voltage(1.5, unit='V')

                tot_hist = print_hist(all_hits=True)
#                with open('source_noise.yml', 'w') as outfile:
#                    yaml.dump(tot_hist.tolist(), outfile, default_flow_style=False)
                

    def analyze(self, h5_filename='',**kwargs):

        # Added analyze from source_scan to check if it saves le and te

        if h5_filename == '':
            h5_filename = self.output_filename +'.h5'
        
        logging.info('Analyzing: %s', h5_filename)
        np.set_printoptions(linewidth=240)

        with tb.open_file(h5_filename, 'r+') as in_file_h5:
            raw_data = in_file_h5.root.raw_data[:]
            meta_data = in_file_h5.root.meta_data[:]
            
            #print raw_data
            hit_data = interpret_rx_data_scan(raw_data, meta_data)
            lista = list(hit_data.dtype.descr)
            new_dtype = np.dtype(lista + [('InjV', 'float'), ('tot', 'uint8')])
            new_hit_data = np.zeros(shape=hit_data.shape, dtype=new_dtype)
            for field in hit_data.dtype.names:
                new_hit_data[field] = hit_data[field]
            new_hit_data['InjV'] = local_configuration['scan_injection'][0] + hit_data['scan_param_id'] * local_configuration['scan_injection'][2]

            tot = hit_data['te'] - hit_data['le']
            neg = hit_data['te'] < hit_data['le']
            tot[neg] = hit_data['te'][neg] + (255 - hit_data['le'][neg])
            new_hit_data['tot'] = tot

            in_file_h5.create_table(in_file_h5.root, 'hit_data', new_hit_data, filters=self.filter_tables)

if __name__ == "__main__":
    from monopix_daq.monopix_extension import MonopixExtensions

    m_ex = MonopixExtensions("../monopix_mio3.yaml")
    scan = ScanSingle(dut_extentions=m_ex, sender_addr="tcp://127.0.0.1:5500")
    scan.configure(**local_configuration)
    scan.start(**local_configuration)
    scan.analyze(**local_configuration)
