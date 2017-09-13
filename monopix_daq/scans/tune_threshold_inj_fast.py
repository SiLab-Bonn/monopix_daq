import time
import os
import sys
import logging
import numpy as np
import tables as tb
import yaml

from matplotlib import pyplot as plt
from simple_scan import SimpleScan
from monopix_daq.analysis.interpret_scan import interpret_rx_data,interpret_rx_data_scan
from monopix_daq.monopix_extension import MonopixExtensions
#from monopix_daq.scans.scan_threshold import ScanThreshold
#from monopix_daq.scan_base import ScanBase
from basil.dut import Dut

logging.basicConfig(level=logging.INFO, format="%(asctime)s - %(name)s - [%(levelname)-8s] (%(threadName)-10s) %(message)s")

show_info = False



class Tuning(SimpleScan):#, ScanThreshold):
    scan_id = "tune_threshold_inj"
    noisypixel_list=[]

    def get_filename(self):
        return self.output_filename

    def configure(self, repeat=1000, scan_range=[0, 0.2, 0.05], mask_filename='', TH=1.5, mask=16, columns=range(0, 36), threshold_overdrive=0.001, **kwargs):
        self.INJ_LO = 0.2
        try:
            self.pulser = Dut('../agilent33250a_pyserial.yaml')  # should be absolute path
            self.pulser.init()
            logging.info('Connected to ' + str(self.pulser['Pulser'].get_info()))
        except (RuntimeError, OSError):
            self.pulser = None
            logging.info('External injector not connected. Switch to internal one')

        self.dut['INJ_LO'].set_voltage(self.INJ_LO, unit='V')

        self.dut['TH'].set_voltage(1.5, unit='V')
        self.dut['VDDD'].set_voltage(1.7, unit='V')
        self.dut['VDD_BCID_BUFF'].set_voltage(1.7, unit='V')

        self.dut['inj'].set_delay(500 * 256 + 15)
        self.dut['inj'].set_width(500 * 256 - 15)
        self.dut['inj'].set_repeat(repeat)
        self.dut['inj'].set_en(True)
        self.dut['gate_tdc'].set_en(False)
        self.dut['gate_tdc'].set_delay(10)
        self.dut['gate_tdc'].set_width(2)
        self.dut['gate_tdc'].set_repeat(1)
        self.dut['CONF']['EN_GRAY_RESET_WITH_TDC_PULSE'] = 1

        self.dut["CONF_SR"]["PREAMP_EN"] = 1
        self.dut["CONF_SR"]["INJECT_EN"] = 1
        self.dut["CONF_SR"]["MONITOR_EN"] = 1
        self.dut["CONF_SR"]["REGULATOR_EN"] = 1
        self.dut["CONF_SR"]["BUFFER_EN"] = 1
        self.dut["CONF_SR"]["LSBdacL"] = 62
        self.dut["CONF_SR"]["VPFB"] = 32

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
        self.dut['CONF_SR']['INJ_EN'].setall(False)
        self.dut['CONF_SR']['ColRO_En'].setall(False)

        self.dut.PIXEL_CONF['PREAMP_EN'][:] = 0
        self.dut.PIXEL_CONF['INJECT_EN'][:] = 0
        self.dut.PIXEL_CONF['MONITOR_EN'][:] = 0
        self.dut.PIXEL_CONF['TRIM_EN'][:] = 15
        

    def scan(self, repeat=1000, scan_range=[0, 0.2, 0.05], mask_filename='', TH=1.5, mask=16, columns=range(0, 36), threshold_overdrive=0.001, TRIM_EN=None, inj_target=0.2,**kwargs):
        self.configure(repeat=repeat, columns=columns)
        self.mus = np.zeros(shape=(0))

        # LOAD PIXEL DAC
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
                logging.info('Loading threshold values (+mv): %f', TH)

                logging.info('Loading DAC values from: %s', str(dac_status))
                dac_names = ['BLRes', 'VAmp', 'VPFB', 'VPFoll', 'VPLoad', 'IComp', 'Vbias_CS', 'IBOTA', 'ILVDS', 'Vfs', 'LSBdacL', 'Vsf_dis1', 'Vsf_dis2', 'Vsf_dis3']
                for dac in dac_names:
                    self.dut['CONF_SR'][dac] = dac_status[dac]
                    print dac, self.dut['CONF_SR'][dac]

                scan_kwargs = yaml.load(in_file_h5.root.meta_data.attrs.kwargs)
                columns = scan_kwargs['column_enable']
                logging.info('Column Enable: %s', str(columns))

        else:
            # first time, get TRIM_EN from configuration
            if bit_index == 3:
                TRIM_EN = self.dut.PIXEL_CONF['TRIM_EN'].copy()
                for pix_col in columns:
                    TRIM_EN[pix_col, :] = 8
                    self.dut.PIXEL_CONF['PREAMP_EN'][pix_col, :] = 1
            else:
                # if TRIM_EN is given as parameter, do not change it
                for pix_col in columns:
                    self.dut.PIXEL_CONF['PREAMP_EN'][pix_col, :] = 1
        
        for pixel in self.noisypixel_list:
            print "MASKING noisy pixel" 
            print '[%d, %d]' % (pixel[0], pixel[1])
            #time.sleep(3)
            self.dut.PIXEL_CONF['PREAMP_EN'][pixel[0], pixel[1]] = 0
            self.dut.PIXEL_CONF['TRIM_EN'][pixel[0], pixel[1]] = 15

        for pix_col in columns:
            dcol = int(pix_col / 2)
            self.dut['CONF_SR']['ColRO_En'][35 - pix_col] = 1

        print '### Scanning with setting: ###'
        print TRIM_EN[configuration['columns'][:], :]

        self.dut.PIXEL_CONF['TRIM_EN'][:] = TRIM_EN[:]
    
        self.dut.write_pixel_conf()
        self.dut.write_global_conf()

        scan_range = np.arange(scan_range[0], scan_range[1], scan_range[2])

        logging.info('Threshold: %f', TH)
        self.dut['TH'].set_voltage(TH, unit='V')

        self.hits = None
        self.hits_data_type = {'names': ['inj', 'col', 'row', 'hist'], 'formats': [np.float64, 'uint16', 'uint16', 'uint16']}
        self.hits = np.recarray((0), dtype=self.hits_data_type)

        for pix_col_indx, pix_col in enumerate(columns):

            self.dut.PIXEL_CONF['TRIM_EN'][:] = TRIM_EN[:]
            self.dut['CONF_SR']['INJ_EN'].setall(False)

            mask_steps = []
            for m in range(mask):
                col_mask = np.copy(self.dut.PIXEL_CONF['INJECT_EN'][pix_col, :])
                col_mask[m::mask] = True
                mask_steps.append(np.copy(col_mask))

            # begin scan loop here
            self.scan_loop(pix_col_indx, pix_col, mask, mask_steps, TRIM_EN, TH, scan_range, repeat, inj_target)
        
        self.dut.PIXEL_CONF['TRIM_EN'][:]=self.TRIM_EN
        self.dut.PIXEL_CONF['INJECT_EN'][:]=0
        self.dut['TH'].set_voltage(TH, unit='V')
        print "This is the TRIM_EN apenas termina el ultimo loop", self.dut.PIXEL_CONF['TRIM_EN'][columns] 

    def get_hits(self):
        return self.hits

    def get_threshold_setting(self):
        return self.TRIM_EN

    def scan_loop(self, pix_col_indx, pix_col, mask, mask_steps, TRIM_EN, TH, scan_range, repeat, inj_target):

        # activate mask
        for idx, mask_step in enumerate(mask_steps):
            dcol = int(pix_col / 2)
            self.dut['CONF_SR']['INJ_EN'].setall(False)
            #self.dut['CONF_SR']['PREAMP_EN'].setall(False)
            self.dut.PIXEL_CONF['TRIM_EN'][:] = 15
            self.dut.PIXEL_CONF['INJECT_EN'][:] = 0

            self.dut.PIXEL_CONF['INJECT_EN'][pix_col, :] = mask_step
            self.dut.PIXEL_CONF['TRIM_EN'][pix_col, :][mask_step] = TRIM_EN[pix_col, :][mask_step]
            self.dut['CONF_SR']['INJ_EN'][17 - dcol] = 1

            self.dut.write_pixel_conf()
            self.dut.write_global_conf()

            self.dut['CONF']['RESET_GRAY'] = 1
            self.dut['CONF'].write()

            self.dut['CONF']['RESET_GRAY'] = 0
            self.dut['CONF'].write()

            time.sleep(0.1)
            
            # for given mask change injection value
            inj_value = inj_target
    
            param_id = pix_col_indx * len(scan_range) * mask + idx * len(scan_range)

            if show_info:
                logging.info('Scan : Column = %s MaskId=%d InjV=%f ID=%d)', pix_col, idx, inj_value, param_id)

            if self.pulser:
                self.pulser['Pulser'].set_voltage(self.INJ_LO, float(self.INJ_LO + inj_value), unit='V')
                if abs(inj_value) < 0.00001:
                    time.sleep(2)
            else:
                # Enabled before: (For GPAC injection)
                self.dut['INJ_LO'].set_voltage(self.INJ_LO, unit='V')
                self.dut['INJ_HI'].set_voltage(float(self.INJ_LO + inj_value), unit='V')
            
            time.sleep(0.1)
            
            self.dut['data_rx'].reset()
#                self.dut['data_rx'].CONF_START_FREEZE = 88
#                self.dut['data_rx'].CONF_START_READ = 92en
#                self.dut['data_rx'].CONF_STOP_FREEZE = 98
#                self.dut['data_rx'].CONF_STOP_READ = 94
#                self.dut['data_rx'].CONF_STOP = 110
#            self.dut['data_rx'].set_en(True)
#            time.sleep(0.2)
#            self.dut['fifo'].reset()

            self.dut_extensions.set_monoread(start_freeze=50,start_read=52,stop_read=54,stop_freeze=88,stop=98,gray_reset_by_tdc=1)
            self.dut['TH'].set_voltage(TH, unit='V')

            with self.readout(scan_param_id=param_id, fill_buffer=True, clear_buffer=True):

                # self.dut['inj'].start()
                self.dut['gate_tdc'].start()

                while not self.dut['inj'].is_done():
                    pass

                time.sleep(0.1)

                self.dut['data_rx'].set_en(False)

            dqdata = self.fifo_readout.data
            
            print "threshold"
            print tuning.dut['TH'].get_voltage(unit='V')

            #self.dut_extensions.stop_monoread()   ################
            self.dut['TH'].set_voltage(1.5, unit='V')
            
            try:
                data = np.concatenate([item[0] for item in dqdata])
            except ValueError:
                data = []

            data_size = len(data)
            
            
            logging.info('Scan Pixel Finished: V=%f DATA_COUNT=%d', inj_value, data_size)

            hit_data = interpret_rx_data(data, delete_noise=True)
            #before = len(hit_data)
            #print "len hit data before filtering:", 
            #hit_data = hit_data[np.array(hit_data['le'],dtype="int") < 25]
            #after = len(hit_data)
            #print "rejected data:", before, after, before - after, 

            pixel_data = np.array(hit_data['col'],dtype="int")*129+np.array(hit_data['row'],dtype="int")
            hit_pixels = np.unique(pixel_data)
            hist = np.bincount(pixel_data)

            # calculate threshold for pixels in this mask step here

            msg = ' '

            # Give id to pixels, starting from 0 at (col, row) = (0, 0)
            for activated_pixel_id in pix_col * 129 + np.where(mask_step)[0]:
                if activated_pixel_id in hit_pixels:
                    # There was a hit in this pixel
                    self.hits = np.append(self.hits, np.array([tuple([inj_value, activated_pixel_id / 129, activated_pixel_id % 129, hist[activated_pixel_id]])], dtype=self.hits_data_type))
                else:
                    # There was no hit in this pixel (although charge was injected). Set hist to 0
                    self.hits = np.append(self.hits, np.array([tuple([inj_value, activated_pixel_id / 129, activated_pixel_id % 129, 0])], dtype=self.hits_data_type))

            if data_size:
                for pix in hit_pixels:
                    col = pix / 129
                    row = pix % 129
                    #Noisy pixels to the noisy pixel list
                    if hist[pix] > 5*float(configuration['repeat']):
                        self.noisypixel_list.append([col,row])
                        print 'Added to the noisy list [%d, %d]' % (col, row)            
                        self.dut.PIXEL_CONF['PREAMP_EN'][col, row] = 0
                        self.dut.PIXEL_CONF['TRIM_EN'][col, row] = 15
                        
                    msg += '[%d, %d]=%d ' % (col, row, hist[pix])        
#                     self.hits = np.append(self.hits, np.array([tuple([inj_value, col, row, hist[pix]])], dtype=self.hits_data_type))
                logging.info(msg)

            if data_size > 1000000:
                logging.error('Too much data!')

                #return

            time.sleep(.5)

        # format hits
        self.TRIM_EN = TRIM_EN

    def search_global_TH(self, min_TH=0.760, max_TH=0.800, **kwargs):
        min_TH=configuration['TH_lowlim']
        max_TH=configuration['TH_highlim']
        n_inj=configuration['repeat']
        found=False
        TH_best=1.000
        precision=0.1
        while not found:
            TH_actual = round( (max_TH+min_TH)/2 , 3)
            configuration['TH']= TH_actual
            tuning.start(TRIM_EN=TRIM_EN.copy(), **configuration)
            hits = tuning.get_hits()
            counts=[]
            for i in np.arange(0,len(hits),1):
                counts.append(hits[i][3])
            #print counts
            median = np.median(counts)
            
            print "**************"
            print "Current median"
            print median
            print "**************"
            
            if median > abs(n_inj/2):
                min_TH=TH_actual
            elif median <= abs(n_inj/2):
                max_TH=TH_actual
            else:
                pass
            
            if abs( median - abs(n_inj/2) ) <= abs(precision*n_inj):
                TH_best=TH_actual 
                found=True       
            elif TH_best==TH_actual:
                if abs( median - abs(n_inj/2) ) <= abs(precision*n_inj):  
                    TH_best=TH_actual
                    found=True
                elif ( abs( median - abs(n_inj/2) ) > abs(precision*n_inj) ) and ( abs( median - abs(n_inj/2) ) <= abs(n_inj/2) ):
                    if median > abs(n_inj/2):
                        TH_best=TH_actual+0.001
                        found=True
                    else:
                        TH_best=TH_actual 
                        found=True  
                else:
                    print "A reliable value could not be found"
                    print TH_actual
                    print TH_best
                    print min_TH
                    print max_TH
                    print "The last attempted values were TH= %d, min_TH= %d and max_TH= %d, with a median of %d" % (TH_best, min_TH, max_TH, median)
                    sys.exit('Set different initial values')
            else:
                TH_best=TH_actual
                
        configuration['TH']= TH_best
                
                
        #for gthresh in TH_points:
            
        

    def analyze(self, h5_filename='',**kwargs):
        # Added analyze from source_scan to check if it saves le and te

        if h5_filename == '':
            h5_filename = self.output_filename + '.h5'

        logging.info('Analyzing: %s', h5_filename)
        np.set_printoptions(linewidth=240)

        with tb.open_file(h5_filename, 'r+') as in_file_h5:
            raw_data = in_file_h5.root.raw_data[:]
            meta_data = in_file_h5.root.meta_data[:]

            # print raw_data
            hit_data = interpret_rx_data_scan(raw_data, meta_data)
            lista = list(hit_data.dtype.descr)
            new_dtype = np.dtype(lista + [('InjV', 'float'), ('tot', 'uint8')])
            new_hit_data = np.zeros(shape=hit_data.shape, dtype=new_dtype)
            for field in hit_data.dtype.names:
                new_hit_data[field] = hit_data[field]
            # new_hit_data['InjV'] = local_configuration['scan_injection'][0] + hit_data['scan_param_id']*local_configuration['scan_injection'][2]

            tot = hit_data['te'] - hit_data['le']
            neg = hit_data['te'] < hit_data['le']
            print np.bincount(hit_data['le'])
            tot[neg] = hit_data['te'][neg] + (255 - hit_data['le'][neg])
            new_hit_data['tot'] = tot

            interpreted_filename = self.output_filename +'_interpreted.h5'
            h5_file_interpreted = tb.open_file(interpreted_filename, mode='w', title=self.scan_id)
            hit_data_table = h5_file_interpreted.create_table(h5_file_interpreted.root, 'hit_data', new_hit_data, filters=self.filter_tables)
            hit_data_table.attrs.kwargs = yaml.dump(kwargs)
            hit_data_table.attrs.power_status = in_file_h5.root.meta_data.attrs.power_status
            hit_data_table.attrs.dac_status = in_file_h5.root.meta_data.attrs.dac_status
            

def calculate_new_threshold_settings(bit_index, n_inj, hist_map, old_threshold):
    new_threshold = old_threshold

    # TODO can be omitted when saving closest distance
    # check if optimal threshold is already found

    # in any case, switch next bit (if bit is not least significant) to 1
    if bit_index > 0:
        new_threshold = new_threshold | (1 << bit_index - 1)

    # If needed raise threshold, otherwise keep 0
    new_threshold[hist_map < (n_inj / 2)] = ~(1 << bit_index) & new_threshold[hist_map < (n_inj / 2)]
    return new_threshold


def calculate_hist_map(hits, n_inj, old_threshold_setting):
    hist_map = np.zeros_like(old_threshold_setting, dtype=np.uint16)
    noisy = np.full_like(hist_map, True)

    # Iterate over all pixels
    for pixel in hits:
        hist_map[pixel["col"], pixel["row"]] = pixel["hist"]

    # exclude non-noisy pixels from mask
    noisy[hist_map < n_inj] = False

    return hist_map

# Initialize here

#scan = Tuning()
#m_ex = MonopixExtensions()





m_ex = MonopixExtensions("/home/idcs/git/monopix_daq_timestamp/monopix_daq/monopix_1_127_B18.yaml")
tuning = Tuning(dut_extentions=m_ex, sender_addr="tcp://127.0.0.1:4500")

#m_ex = MonopixExtensions("/home/idcs/git/monopix_daq_timestamp/monopix_daq/monopix_2_213_B19.yaml")
#tuning = Tuning(dut_extentions=m_ex, sender_addr="tcp://127.0.0.1:5500")





configuration = {
    "repeat": 200,
    "mask_filename": '',
    "scan_range": [0.01, 0.4, 0.025],
    "mask": 8,
    "TH": 0.766,
    "columns": range(0,36),
    "threshold_overdrive": 0.006,
    "inj_target":0.2,
    "TH_lowlim": 0.765,
    "TH_highlim": 0.800
}

run_threshold = True # TODO Set to True if a threshold scan should run after the tuning script, in order to check the tuning

# MAIN LOOP
tuning.configure(**configuration)
TRIM_EN = np.full((36, 129), 8, dtype=np.uint8)

best_threshold_setting = None  # best trim settings
hist_best = None  # hits for best trim setting

#for bit_index in [3]:    
#    print "LOOKING FOR GLOBAL THRESHOLD"
#    tuning.search_global_TH(**configuration)

print "This is the TH value before tuning the TRIM"
print configuration['TH']
print tuning.dut['TH'].get_voltage(unit='V')


timestr = time.strftime("%Y%m%d-%H%M%S")
TH_str= str(configuration["TH"])
TH_str=TH_str.replace('.',',')
inj_str= str(configuration["inj_target"])
inj_str=inj_str.replace('.',',')


file_path = '/home/idcs/STREAM/Devices/MONOPIX_01/Tests/20170908_TestBeamELSA_MONOPIXefficiency/InjTuning_B18/'+timestr+'_target'+inj_str+'_TH'+TH_str+'_VPFB32'

#file_path = '/home/idcs/STREAM/Devices/MONOPIX_01/Tests/20170908_TestBeamELSA_MONOPIXefficiency/InjTuning_B19/'+timestr+'_target'+inj_str+'_TH'+TH_str+'_VPFB32'


if not os.path.exists(file_path):
    os.makedirs(file_path)
    print "Created folder:"
    print file_path

#bit_index counts down from 3 to 0
#for bit_index in np.arange(3, -1, -1):
for bit_index in [3,3,2,1,0,-1]:    
    
    tuning.start(TRIM_EN=TRIM_EN.copy(), **configuration)
    threshold_setting = tuning.get_threshold_setting()

    trim_vals = threshold_setting
    hits = tuning.get_hits()

    if len(hits) != 129 * len(configuration['columns']):
        logging.error("Some hits were lost, information is missing!")
        raw_input("Proceed anyway?")

    # Calculate hsit_map
    hist_map = calculate_hist_map(hits, configuration["repeat"], threshold_setting)

    # Store best setting on the fly since search algo does not always
    # converge to best value
    if not np.any(best_threshold_setting):
        best_threshold_setting = TRIM_EN
        hist_best = hist_map
    else:
        selection = np.abs(hist_best - float(configuration["repeat"]) / 2) > np.abs(hist_map - float(configuration["repeat"]) / 2)
        logging.info("Updating %s values" % np.count_nonzero(selection))
        best_threshold_setting[selection] = TRIM_EN[selection]
        hist_best[selection] = hist_map[selection]

    np.save(file_path + "/trim_values_step" + str(3 - bit_index) + ".npy", best_threshold_setting)
#     print new_threshold_setting[columns[0]:columns[1], :].reshape(-1)
    plt.hist(best_threshold_setting[configuration['columns'][:], :].reshape(-1), bins=np.arange(-0.5, 16.5, 1))
    plt.title("TRIM tuning step "+str(3 - bit_index)+" in columns"+str(configuration['columns']))
    plt.savefig(file_path + '/trim_0' + str(3 - bit_index) + '.pdf')
#     plt.show()
    plt.clf()

    new_threshold_setting = calculate_new_threshold_settings(bit_index, configuration["repeat"], hist_map, TRIM_EN)

    TRIM_EN = new_threshold_setting
    

# scan with last bit 0

fixed_TRIM = np.copy(~(1 << 0) & TRIM_EN)
# Scan last bit with 0
tuning.start(TRIM_EN=fixed_TRIM.copy(), **configuration)
threshold_setting = tuning.get_threshold_setting()

trim_vals = threshold_setting
hits = tuning.get_hits()

#if len(hits) != 129 * (columns[1] - columns[0]):
if len(hits) != 129 * len(configuration['columns']):
    logging.error("Some hits were lost, information is missing!")
    raw_input("Proceed anyway?")

# Calculate hsit_map
hist_map = calculate_hist_map(hits, configuration["repeat"], threshold_setting)

# Store best setting on the fly since search algo does not always converge to best value
if not np.any(best_threshold_setting):
    best_threshold_setting = fixed_TRIM
    hist_best = hist_map
else:
    selection = np.abs(hist_best - float(configuration["repeat"]) / 2) > np.abs(hist_map - float(configuration["repeat"]) / 2)
    logging.info("Updating %s values" % np.count_nonzero(selection))
    best_threshold_setting[selection] = fixed_TRIM[selection]
    hist_best[selection] = hist_map[selection]

np.save(file_path + "/trim_values_step" + str(4) + ".npy", best_threshold_setting)
plt.hist(best_threshold_setting[configuration['columns'][:], :].reshape(-1), bins=np.arange(-0.5, 16.5, 1))
plt.savefig(file_path + '/trim_0' + str(4) + '.pdf')
plt.clf()

plt.hist(hist_best[configuration['columns'][:], :].reshape(-1), bins=np.arange(-0.5, float(configuration["repeat"])+0.5, 1))
plt.savefig(file_path + '/hist_0' + str(4) + '.pdf')
plt.clf()

print "hist"
print hist_best[configuration['columns'][:], :]
print "where"
print np.where(hist_best[:, :] > float(configuration["repeat"]) )
 

noisy_mask_high=np.where(hist_best[:, :] > float(configuration["repeat"]) )
#print noisy_mask_high[0]
#print noisy_mask_high[1]

for pos,i in enumerate(noisy_mask_high[0]):
    #print pos
    #print i
    j=noisy_mask_high[1][pos]
    #print j
    #print tuning.dut.PIXEL_CONF['PREAMP_EN'][i,j]
    tuning.dut.PIXEL_CONF['PREAMP_EN'][i,j]=0
    
noisy_mask_low=np.where(hist_best[:, :] < 2)
#print noisy_mask_low[0]
#print noisy_mask_low[1]

for pos,i in enumerate(noisy_mask_low[0]):
    #print pos
    #print i
    j=noisy_mask_low[1][pos]
    #print j
    #print tuning.dut.PIXEL_CONF['PREAMP_EN'][i,j]
    tuning.dut.PIXEL_CONF['PREAMP_EN'][i,j]=0
    
for pixel in tuning.noisypixel_list:
    tuning.dut.PIXEL_CONF['PREAMP_EN'][pixel[0],pixel[1]]=0

print "NOISY PIXELS with too many hits"
print tuning.noisypixel_list
    

for i in configuration['columns']:
#    print scan.TRIM_EN[i]
    print tuning.dut.PIXEL_CONF['TRIM_EN'][i]
    print tuning.dut.PIXEL_CONF['PREAMP_EN'][i]

tuning.analyze(**configuration)



#if run_threshold==True:
#    print "Analog scan starts with TH: %d" % (configuration['TH'])
#    time.sleep(10)
#    from matplotlib.backends.backend_pdf import PdfPages
#    scan_threshold= AnalogScan(dut=m_ex.dut)
#    with PdfPages(file_path + '/s_curve_tuned.pdf') as pdf:
#
#        scan.configure(**configuration)
#        scan.start(**configuration)
#        TRIM_EN = scan.TRIM_EN
#        
#        mus = scan.mus
#        sigmas = scan.sigmas
#        np.save(file_path + '/mu_values.npy', mus)
#        np.save(file_path + '/sigma_values.npy', sigmas)
#
#    print len(np.where(np.logical_or(mus[24:28, :] > 0.2, mus[24:28, :] < 0.1))[0])
#    plt.clf()