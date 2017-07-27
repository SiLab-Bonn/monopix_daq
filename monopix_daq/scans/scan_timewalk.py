import time
import logging
import numpy as np
import tables as tb
import yaml
import monopix_daq.analysis as analysis

from monopix_daq.scan_base import ScanBase
from progressbar import ProgressBar
from basil.dut import Dut

logging.basicConfig(level=logging.INFO, format="%(asctime)s - %(name)s - [%(levelname)-8s] (%(threadName)-10s) %(message)s")

local_configuration = {
    "how_long": 60,
    "repeat": 1000,
    #"scan_injection": [0.2, 1.8, 0.2],#Should be hard-coded
    "threshold_range": [0.8, 0.8, -0.001],#[1.035, 1.035, -0.001],#[0.7818, 0.7818, -0.001], #[0.793, 0.793, -0.002],[29,64]  #[0.780, 0.780, -0.002]  [1,64]  #[21,64] [0.770, 0.770, -0.001]
    "pixel":  [25,64],
    "VPFBvalue": 32,#56#48
    "scan_dac_id" : 0
}

class ScanTimeWalk(ScanBase):
    scan_id = "scan_timewalk"

    def scan(self, repeat = 10, threshold_range = [0.8, 0.7, -0.05], pixel = [1,64] , how_long = 1, VPFBvalue = 32, scan_dac_id =0, **kwargs):
        
        self.dut['fifo'].reset()
        
        is_pulser = False
        is_Oxford = True
        
        if is_pulser:
            if is_Oxford == False:
                try:
                    pulser = Dut('../agilent33250a_pyserial.yaml') #should be absolute path
                    pulser.init()
                    logging.info('Connected to '+str(pulser['Pulser'].get_info()))
                except RuntimeError:
                    logging.info('External injector not connected. Switch to internal one')
            else:
                from monopix_daq.agilent_8110a_visa import agilent_8110a_visa
                pulser = {}
                pulser['Pulser'] = agilent_8110a_visa(10)

        if is_pulser:
            INJ_LO = -0.2
        else:
            INJ_LO = 0.2

        if not is_pulser:
            self.dut['INJ_LO'].set_voltage(INJ_LO, unit='V')
        
        self.dut['inj'].set_delay(5*256)
        self.dut['inj'].set_width(5*256)
        if not is_pulser:
            self.dut['inj'].set_repeat(repeat)
        else:
            self.dut['inj'].set_repeat(repeat)
        self.dut['inj'].set_en(True)
        self.dut['gate_tdc'].set_en(False)
        self.dut['gate_tdc'].set_delay(10)
        self.dut['gate_tdc'].set_width(2)
        self.dut['gate_tdc'].set_repeat(1)
        
        self.dut['CONF']['EN_GRAY_RESET_WITH_TDC_PULSE'] = 1

        
        self.dut.write_global_conf()
        
        self.dut['TH'].set_voltage(1.5, unit='V')

        self.dut['VDDD'].set_voltage(1.7, unit='V')        
        self.dut['VDD_BCID_BUFF'].set_voltage(1.7, unit='V')
        #self.dut['VPC'].set_voltage(1.5, unit='V')

        self.dut["CONF_SR"]["PREAMP_EN"] = 1
        self.dut["CONF_SR"]["INJECT_EN"] = 1
        self.dut["CONF_SR"]["MONITOR_EN"] = 1
        self.dut["CONF_SR"]["REGULATOR_EN"] = 1
        self.dut["CONF_SR"]["BUFFER_EN"] = 1

        #LSB
        #self.dut["CONF_SR"]["LSBdacL"] = 60
        self.dut["CONF_SR"]["VPFB"] = VPFBvalue
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
        self.dut.PIXEL_CONF['INJECT_EN'][:] = 1
        self.dut.PIXEL_CONF['MONITOR_EN'][:] = 1
        self.dut.PIXEL_CONF['TRIM_EN'][:] = 15
            
        #LOAD PIXEL DAC
        pix_col = pixel[0]
        pix_row = pixel[1]
        dcol = int(pix_col/2)  

        self.dut.PIXEL_CONF['TRIM_EN'][pix_col,pix_row] = 0
        self.dut.PIXEL_CONF['PREAMP_EN'][pix_col,pix_row] = 1
        self.dut['CONF_SR']['ColRO_En'][35-pix_col] = 1
        
        np.set_printoptions(linewidth=260)
        
        #print "scan_injection"
        self.dut.PIXEL_CONF['INJECT_EN'][pix_col,pix_row] = 1
        self.dut['CONF_SR']['INJ_EN'][17-dcol] = 1
#        inj_scan_range = np.arange(scan_injection[0], scan_injection[1], scan_injection[2])#np.array([0.6, 0.8, 1, 1.2, 1.4])#np.arange(scan_injection[0], scan_injection[1], scan_injection[2])
        inj_scan_range = [0.2, 0.4, 0.6, 0.8, 1.0, 1.2 , 2] #hard-coded: many values at the beginning to check if there is any problem with extra overshoots
        self._inj_scan_range = inj_scan_range

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
            #dqdata = self.fifo_readout.data[1:-1]
            dqdata = self.fifo_readout.data
            try:
                data = np.concatenate([item[0] for item in dqdata])
            except ValueError:
                data = []

            hit_data = self.dut.interpret_rx_data(data)
            data_size = len(data) 
            
            pixel_data = hit_data['col']*129+hit_data['row']
            
            #tot = (hit_data['te'] - hit_data['le']) & 0xFF
            tot = hit_data['te'] - hit_data['le'] 
            neg = hit_data['te']<hit_data['le']
            tot[neg] = hit_data['te'][neg] + (255 - hit_data['le'][neg])
            
#            print "tot"
#            for i,d in enumerate(hit_data):
#                if d['te'] < d['le']:
#                    print d['te'], d['le'], tot[i], '*'
#                else:
#                    print d['te'], d['le'], tot[i]
#                     if i> 1000:
#                         break
            
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
            
            return tot_hist[1:-1]

        th_scan_range = np.arange(threshold_range[0], threshold_range[1], threshold_range[2])
        if len(th_scan_range) == 0:
            th_scan_range = [threshold_range[0]]

        #inj_scan_dict = {}
        
        for inx, vol in enumerate(inj_scan_range):
        
            self.dut['TH'].set_voltage(threshold_range[0], unit='V')  
            if is_pulser:
                pulser['Pulser'].set_voltage(INJ_LO, float(INJ_LO + vol), unit='V')
            else:
                #Enabled before: (For GPAC injection)
                self.dut['INJ_HI'].set_voltage( (INJ_LO+vol), unit='V')
            
            logging.info('Scan : TH=%f, InjV=%f ID=%d)',threshold_range[0], vol, inx)
            time.sleep(2)
            #time.sleep(0.2)
            
            with self.readout(scan_param_id = inx  + len(inj_scan_range) * scan_dac_id, fill_buffer=True, clear_buffer=True):
            
                self.dut['data_rx'].reset()
                self.dut['fifo'].reset()
                self.dut['data_rx'].set_en(True)
            
                self.dut['gate_tdc'].start()
                while not self.dut['inj'].is_done():
                    pass
                
                time.sleep(0.2)
               
                self.dut['data_rx'].set_en(False)
                self.dut['TH'].set_voltage(1.5, unit='V')
            
            #print_hist()
            #tot_hist = print_hist(all_hits = True)
            #inj_scan_dict[float(vol)] = tot_hist.tolist()                                

    def analyze(self, h5_filename=''):
        # Added analyze from source_scan to check if it saves le and te

        if h5_filename == '':
            h5_filename = self.output_filename +'.h5'
        else:
            self._inj_scan_range = [0.2, 0.4, 0.6, 0.8, 1.0, 1.2 , 2]

        logging.info('Analyzing: %s', h5_filename)
        np.set_printoptions(linewidth=240)

        with tb.open_file(h5_filename, 'r+') as in_file_h5:
            raw_data = in_file_h5.root.raw_data[:]
            meta_data = in_file_h5.root.meta_data[:]

            # print raw_data
            hit_data = self.dut.interpret_rx_data(raw_data, meta_data)
            lista = list(hit_data.dtype.descr)
            new_dtype = np.dtype(lista + [('InjV', 'float'), ('tot', 'uint8')])
            new_hit_data = np.zeros(shape=hit_data.shape, dtype=new_dtype)
            for field in hit_data.dtype.names:
                new_hit_data[field] = hit_data[field]

            find_injv = lambda x: self._inj_scan_range[x]
            find_injv_vec = np.vectorize(find_injv)
            new_hit_data['InjV'] = find_injv_vec(hit_data['scan_param_id'] % len(self._inj_scan_range))

            tot = hit_data['te'] - hit_data['le']
            neg = hit_data['te'] < hit_data['le']
            tot[neg] = hit_data['te'][neg] + (255 - hit_data['le'][neg])
            new_hit_data['tot'] = tot

            in_file_h5.create_table(in_file_h5.root, 'hit_data', new_hit_data, filters=self.filter_tables)

    def get_timewalk_distance(self, allow_overshoot=False, tot_min=5, scan_dac_id =0, h5_filename = ''):

        if h5_filename == '':
            h5_filename = self.output_filename +'.h5'
        else:
            self._inj_scan_range = [0.2, 0.4, 0.6, 0.8, 1.0, 1.2 , 2]

        with tb.open_file(h5_filename, 'r') as in_file_h5:
            new_hit_data = in_file_h5.root.hit_data[:]

            scan_dac_selection = np.logical_and(new_hit_data["scan_param_id"] > scan_dac_id*len(self._inj_scan_range), new_hit_data["scan_param_id"] < (scan_dac_id+1)*len(self._inj_scan_range))

            tot_vals = np.unique(new_hit_data[scan_dac_selection]['tot'])
            tot_vals = np.unique(filter(lambda x : x >= tot_min, tot_vals))
            has_overshoot = {}
            for val in tot_vals:
                if val < tot_min:
                    continue
                has_overshoot[val] = np.logical_and(new_hit_data[scan_dac_selection]['le'] > 10, new_hit_data[scan_dac_selection]['tot'] == val).any()

            if not allow_overshoot:
                mintot = new_hit_data[scan_dac_selection]['tot'] == np.amin(tot_vals)
                maxtot = new_hit_data[scan_dac_selection]['tot'] == np.amax(tot_vals)

            else:
                mintot = new_hit_data[scan_dac_selection]['tot'] == np.ma.min(np.ma.array(tot_vals, mask = np.array(has_overshoot.values())))
                maxtot = new_hit_data[scan_dac_selection]['tot'] == np.ma.max(np.ma.array(tot_vals, mask = np.array(has_overshoot.values())))

            self.le_mintot = np.mean(new_hit_data[scan_dac_selection][mintot]['le'])
            self.le_maxtot = np.mean(new_hit_data[scan_dac_selection][maxtot]['le'])

        return self.le_mintot - self.le_maxtot

    
if __name__ == "__main__":

    scan = ScanTimeWalk()
    scan.start(**local_configuration)
    scan.analyze()
    
    print 'Time walk     allowing overshoot:', scan.get_timewalk_distance(True)
    print 'Time walk not allowing overshoot:', scan.get_timewalk_distance(False)
    
        