import time
import os
import sys
import logging
import numpy as np
import tables as tb
import yaml

import matplotlib
matplotlib.use('Agg')
from matplotlib import pyplot as plt
from monopix_daq.scans.simple_scan import SimpleScan
from monopix_daq.analysis.interpret_scan import interpret_rx_data,interpret_rx_data_scan
from basil.dut import Dut

logging.basicConfig(level=logging.INFO, format="%(asctime)s - %(name)s - [%(levelname)-8s] (%(threadName)-10s) %(message)s")

show_info = False

class Tuning(SimpleScan):#, ScanThreshold):
    scan_id = "tune_threshold_inj"
    noisypixel_list=[]

    def get_filename(self):
        return self.output_filename

    def scan(self, repeat=1000, mask_filename='', scan_range=[0, 0.2, 0.05], mask=16, TH=1.5, search_globalTH=True ,columns=range(0, 36), 
                     threshold_overdrive=0.001, inj_target=0.2, TH_lowlim=0.760, TH_highlim=0.840, LSB_value=45, VPFB_value=32, out_folder="", **kwargs):
        
        self.TRIM_EN = np.full((36, 129), 8, dtype=np.uint8)
        self.TH = TH
        self.columns = columns 
        self.inj_target= inj_target
        self.LSB_value=LSB_value
        self.VPFB_value=VPFB_value
                
        self.best_threshold_setting = None  # best trim settings
        self.hist_best = None  # hist for best trim setting
        self.lastbitshift_TRIM = None

        if search_globalTH==True:
            self.TH = self.search_global_TH(repeat=repeat, mask_filename=mask_filename, scan_range=scan_range, mask=mask, TH=self.TH, columns=columns, 
                                            threshold_overdrive=threshold_overdrive, inj_target=inj_target, TH_lowlim=TH_lowlim, TH_highlim=TH_highlim, 
                                            LSB_value=LSB_value, VPFB_value=VPFB_value, TRIM_EN=self.TRIM_EN)
        else:
            pass
        
        self.dut['TH'].set_voltage(self.TH, unit='V')
        
        logging.info( "This is the TH value before tuning the TRIM: %3f", self.TH) 
        logging.info("TH measured: %3f", self.dut['TH'].get_voltage(unit='V'))
        #time.sleep(10)
        
        timestr = time.strftime("%Y%m%d-%H%M%S")
        TH_str= str(self.TH)
        TH_str=TH_str.replace('.',',')
        inj_str= str(self.inj_target)
        inj_str=inj_str.replace('.',',')
        LSB_str= str(self.LSB_value)
        VPFB_str= str(self.VPFB_value)

        if out_folder=="":
            out_folder = os.path.join(os.getcwd(),"output_data/")
        else:    
            pass
        self.file_path = out_folder+timestr+"_tune_th"+'_target'+inj_str+'_TH'+TH_str+'_LSB'+LSB_str+'_VPFB'+VPFB_str

        if not os.path.exists(self.file_path):
            os.makedirs(self.file_path)
            logging.info("Created folder: %s", self.file_path)
        

        for bit_index in np.arange(3, -1, -1):
        #for bit_index in [3,3,2,1,0,-1]:
            logging.info('This is the TRIM at the start of the step %i in the TRIM binary search :' , 3-bit_index )
            for i in self.columns:    
                logging.info('For column %i: %s', i, str( self.TRIM_EN[i] ) )
    
            
            self.scan_trim(repeat=repeat, mask_filename=mask_filename, scan_range=scan_range, mask=mask, TH=self.TH, columns=columns, 
                            threshold_overdrive=threshold_overdrive, inj_target=inj_target, TH_lowlim=TH_lowlim, TH_highlim=TH_highlim, 
                            LSB_value=LSB_value, VPFB_value=VPFB_value, TRIM_EN=self.TRIM_EN.copy(), bit_index=bit_index)
            self.check_best_th(repeat=repeat, TRIM=None, bit_index=bit_index)
        
        #Cross-check the last bit
        self.scan_trim(repeat=repeat, mask_filename=mask_filename, scan_range=scan_range, mask=mask, TH=self.TH, columns=columns, 
                        threshold_overdrive=threshold_overdrive, inj_target=inj_target, TH_lowlim=TH_lowlim, TH_highlim=TH_highlim, 
                        LSB_value=LSB_value, VPFB_value=VPFB_value, TRIM_EN=self.lastbitshift_TRIM.copy(), bit_index=-1)
        self.check_best_th(repeat=repeat, TRIM=None, bit_index=-1)
        
        logging.info('This is the best TRIM after cross-checking the last bit:')
        for i in self.columns:
            logging.info('For column %i: %s', i, str( self.best_threshold_setting[i] ) )
        
        self.TRIM_EN = self.best_threshold_setting.copy()
        self.dut.PIXEL_CONF['TRIM_EN'] = self.best_threshold_setting.copy()
        
        self.finalMaskNoisyPixels(repeat=repeat)
        
        self.dut.write_pixel_conf()
        self.dut.write_global_conf()
        
        for i in self.columns:
            logging.info('Final TRIM for column %i: %s', i, str(self.dut.PIXEL_CONF['TRIM_EN'][i]))
            logging.info('Final PREAMP for column %i: %s', i, str(self.dut.PIXEL_CONF['PREAMP_EN'][i]))

        logging.info("Results from tuning saved to: %s", self.file_path)
       
    def scan_trim(self, repeat=1000, mask_filename='', scan_range=[0, 0.2, 0.05], mask=16, TH=1.5, columns=range(0, 36), 
                     threshold_overdrive=0.001, inj_target=0.2, TH_lowlim=0.760, TH_highlim=0.840, LSB_value=45, VPFB_value=32, TRIM_EN=None, bit_index=3):
        
        #self.configure(repeat=repeat, columns=columns)
        self.mus = np.zeros(shape=(0))
        
        logging.info("THIS IS THE TRIM THAT COMES IN") 
        for i in columns:
            logging.info('TRIM FROM COLUMN: %i --- %s', i, str( TRIM_EN[i] ) )
             
        # LOAD PIXEL DAC
        if mask_filename:
            with tb.open_file(str(mask_filename), 'r') as in_file_h5:
                sys.exit('Loading mask_filename is not implemented yet in this script')
                #logging.info('Loading configuration from: %s', mask_filename)

                #TRIM_EN = in_file_h5.root.scan_results.TRIM_EN[:]
                #PREAMP_EN = in_file_h5.root.scan_results.PREAMP_EN[:]

                #self.dut.PIXEL_CONF['TRIM_EN'][:] = TRIM_EN[:]
                #self.dut.PIXEL_CONF['PREAMP_EN'][:] = PREAMP_EN[:]

                #dac_status = yaml.load(in_file_h5.root.meta_data.attrs.dac_status)
                #power_status = yaml.load(in_file_h5.root.meta_data.attrs.power_status)

                #TH = in_file_h5.root.meta_data.attrs.final_threshold + threshold_overdrive
                #logging.info('Loading threshold values (+mv): %f', TH)

                #logging.info('Loading DAC values from: %s', str(dac_status))
                #dac_names = ['BLRes', 'VAmp', 'VPFB', 'VPFoll', 'VPLoad', 'IComp', 'Vbias_CS', 'IBOTA', 'ILVDS', 'Vfs', 'LSBdacL', 'Vsf_dis1', 'Vsf_dis2', 'Vsf_dis3']
                #for dac in dac_names:
                #    self.dut['CONF_SR'][dac] = dac_status[dac]
                #    logging.info("DAC %s: %f", dac, self.dut['CONF_SR'][dac])
                    #print dac, self.dut['CONF_SR'][dac]

                #scan_kwargs = yaml.load(in_file_h5.root.meta_data.attrs.kwargs)
                #columns = scan_kwargs['column_enable']
                #logging.info('Column Enable: %s', str(columns))

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
            logging.info("MASKING noisy pixel: [%d, %d]", pixel[0], pixel[1] )
            self.dut.PIXEL_CONF['PREAMP_EN'][pixel[0], pixel[1]] = 0
            self.dut.PIXEL_CONF['TRIM_EN'][pixel[0], pixel[1]] = 15

        for pix_col in columns:
            dcol = int(pix_col / 2)
            #self.dut['CONF_SR']['ColRO_En'][35 - pix_col] = 1

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
        
        self.dut.PIXEL_CONF['TRIM_EN'][:]=TRIM_EN[:]
        self.dut.PIXEL_CONF['INJECT_EN'][:]=0
        self.dut['TH'].set_voltage(TH, unit='V')
        self.dut.write_pixel_conf()
        self.dut.write_global_conf()
        logging.info("This is the TRIM_EN after the last loop: %s", str(self.dut.PIXEL_CONF['TRIM_EN'][columns]) ) 

    def get_hits(self):
        return self.hits

    def get_threshold_setting(self):
        return self.TRIM_EN

    def scan_loop(self, pix_col_indx, pix_col, mask, mask_steps, TRIM_EN, TH, scan_range, repeat, inj_target):

        # activate mask
        for idx, mask_step in enumerate(mask_steps):
            
            dcol = int(pix_col / 2)
            self.dut['CONF_SR']['INJ_EN'][:] = 0 
            self.dut['CONF_SR']['PREAMP_EN'][:] = 0 
            self.dut.PIXEL_CONF['TRIM_EN'][:] = 15
            self.dut.PIXEL_CONF['PREAMP_EN'][:] = 0

            self.dut.PIXEL_CONF['INJECT_EN'][:] = 0
            
            
            self.dut.PIXEL_CONF['PREAMP_EN'][pix_col, :][mask_step] = 1
            self.dut.PIXEL_CONF['INJECT_EN'][pix_col, :][mask_step] = 1 
            self.dut.PIXEL_CONF['TRIM_EN'][pix_col, :][mask_step] = TRIM_EN[pix_col, :][mask_step]
            self.dut.PIXEL_CONF['MONITOR_EN'][pix_col, :][mask_step] = 0
            
            self.dut['CONF_SR']['ColRO_En'][35 - pix_col] = 1
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
            self.dut_extensions.set_monoread(start_freeze=90,start_read=92,stop_read=94,stop_freeze=128,stop=138,gray_reset_by_tdc=1)
            self.dut['TH'].set_voltage(TH, unit='V')
            logging.info("Threshold before injecting: %s", str(self.dut['TH'].get_voltage(unit='V')))
            time.sleep(0.2)
            
            with self.readout(scan_param_id=param_id, fill_buffer=True, clear_buffer=True):

                #self.dut['gate_tdc'].start()
                self.dut['inj'].start()

                while not self.dut['inj'].is_done():
                    time.sleep(0.01)
                    pass

                time.sleep(0.2)

                self.dut['data_rx'].set_en(False)

            logging.info("Threshold after readout: %f", self.dut['TH'].get_voltage(unit='V') )
            #self.dut_extensions.stop_monoread()   ################
            self.dut['TH'].set_voltage(1.5, unit='V')
            dqdata = self.fifo_readout.data

            try:
                data = np.concatenate([item[0] for item in dqdata])
            except ValueError:
                data = []

            data_size = len(data)
            
            
            logging.info('Scan Pixel Finished: V=%f DATA_COUNT=%d', inj_value, data_size)

            hit_data = interpret_rx_data(data, delete_noise=True)

            pixel_data = np.array(hit_data['col'],dtype="int") * 129 + np.array(hit_data['row'],dtype="int")
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
                    if hist[pix] > 5*float(repeat):
                        self.noisypixel_list.append([col,row])
                        logging.info("Added to the noisy list: [%d, %d] ", col, row )
                        self.dut.PIXEL_CONF['PREAMP_EN'][col, row] = 0
                        self.dut.PIXEL_CONF['TRIM_EN'][col, row] = 15
                        
                    msg += '[%d, %d]=%d ' % (col, row, hist[pix])        
#                     self.hits = np.append(self.hits, np.array([tuple([inj_value, col, row, hist[pix]])], dtype=self.hits_data_type))
                logging.info(msg)

            if data_size > 10000000:
                logging.error('Too much data!')

                #return
            time.sleep(.5)

        # format hits
        self.TRIM_EN = TRIM_EN

    def search_global_TH(self, repeat=1000, mask_filename='', scan_range=[0, 0.2, 0.05], mask=16, TH=1.5, columns=range(0, 36), 
                     threshold_overdrive=0.001, inj_target=0.2, TH_lowlim=0.760, TH_highlim=0.840, LSB_value=45, VPFB_value=32, TRIM_EN=None):
        #This method looks for and returns a global threshold -within a given range- as close as possible to the target charge. 
        
        min_TH = TH_lowlim
        max_TH = TH_highlim
        repeat_val = repeat
        
        logging.info( "LOOKING FOR GLOBAL THRESHOLD" )
        logging.info("Searching for an optimal global threshold between %3f V and %3f V, with %d injections.", min_TH, max_TH, repeat_val )
        
        n_inj=repeat_val    # Number of injections
        found=False         # A flag for the proper global threshold
        TH_best=1.000 
        precision=0.1       # Percentage of total number of injections still reliable to set the Global Threshold
        while not found:
            TH_actual = round( (max_TH+min_TH)/2 , 3)
            #configuration['TH']= TH_actual
            self.TH = TH_actual
            self.scan_trim(repeat=repeat, mask_filename=mask_filename, scan_range=scan_range, mask=mask, TH=TH_actual, columns=columns, 
                           threshold_overdrive=threshold_overdrive, inj_target=inj_target, TH_lowlim=TH_lowlim, TH_highlim=TH_highlim, 
                           LSB_value=LSB_value, VPFB_value=VPFB_value, TRIM_EN=TRIM_EN.copy(), bit_index=3)
            hits = self.get_hits()
            counts=[]
            print hits
            for i in np.arange(0,len(hits),1):
                counts.append(hits[i][3])
            counts.sort()
            print counts
            median = np.median(counts)
            print median
            
            logging.info("----- Current median of total counts: %f -----", median)
            
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
                    logging.info("A reliable value could not be found. The last attempted values were TH= %d, min_TH= %d and max_TH= %d, with a median of %d", TH_best, min_TH, max_TH, median)
                    sys.exit('Set different initial values')
            else:
                TH_best=TH_actual
                
        return TH_best

    def check_best_th(self, repeat, TRIM=None, bit_index=3):
        
        threshold_setting = self.get_threshold_setting()
        trim_vals = threshold_setting
        
        hits = self.get_hits()

        if len(hits) != 129 * len(self.columns):
            logging.error("Some hits were lost, information is missing!")
            raw_input("Proceed anyway?")
        
        hist_map = calculate_hist_map(hits, repeat, threshold_setting)
        
        # Store best setting on the fly since search algo does not always converge to best value
        if not np.any(self.best_threshold_setting):
            self.best_threshold_setting = self.TRIM_EN
            self.hist_best = hist_map
        else:
            selection = np.abs(self.hist_best - float(repeat) / 2) > np.abs(hist_map - float(repeat) / 2)
            logging.info("Updating %s values" % np.count_nonzero(selection))
            self.best_threshold_setting[selection] = self.TRIM_EN[selection]
            self.hist_best[selection] = hist_map[selection]
            
        np.save(self.file_path + "/trim_values_step" + str(3 - bit_index) + ".npy", self.best_threshold_setting)
        plt.hist(self.best_threshold_setting[self.columns[:], :].reshape(-1), bins=np.arange(-0.5, 16.5, 1))
        plt.title("TRIM tuning step "+str(3 - bit_index)+" in columns "+str(self.columns))
        plt.savefig(self.file_path + '/trim_0' + str(3 - bit_index) + '.pdf')
        plt.clf()
        
        if(3-bit_index <= 3):
            
                new_threshold_setting = calculate_new_threshold_settings(bit_index, configuration["repeat"], hist_map, self.TRIM_EN)
                self.TRIM_EN = new_threshold_setting
                logging.info( "At the end of bit: %s ", str(bit_index) ) 
                for i in self.columns:
                    logging.info( "Best threshold for column %i: %s", i, str(self.best_threshold_setting[i]) )
        else:
            pass

        if (3-bit_index == 3): 
            logging.info( "Before the fix:")
            for i in configuration['columns']:
                #print TRIM_EN[i]
                logging.info( "Best threshold for column %i: %s", i, str(self.TRIM_EN[i]) )
                self.lastbitshift_TRIM = np.copy((1 << 0) ^ self.TRIM_EN)


            logging.info( "After the fix:")
            for i in configuration['columns']:
                #print fixed_TRIM[i]
                logging.info( "Best threshold for column %i: %s", i, str(self.lastbitshift_TRIM[i]) )                   
        elif (3-bit_index == 4):
            plt.hist(self.hist_best[self.columns[:], :].reshape(-1), bins=np.arange(-0.5, float(repeat)+0.5, 1))
            plt.title("TRIM tuning step "+str(3 - bit_index)+" in columns "+str(self.columns))
            plt.savefig(self.file_path + '/hist_0' + str(3-bit_index) + '.pdf')
            plt.clf()
        else:
            pass
            
    def finalMaskNoisyPixels(self, repeat):
        
        noisy_mask_high=np.where(self.hist_best[:, :] > float(repeat) )
        for pos,i in enumerate(noisy_mask_high[0]):
            j=noisy_mask_high[1][pos]
            tuning.dut.PIXEL_CONF['PREAMP_EN'][i,j]=0
    
        noisy_mask_low=np.where(self.hist_best[:, :] < 2)
        for pos,i in enumerate(noisy_mask_low[0]):
            j=noisy_mask_low[1][pos]
            self.dut.PIXEL_CONF['PREAMP_EN'][i,j]=0
    
        for pixel in self.noisypixel_list:
            self.dut.PIXEL_CONF['PREAMP_EN'][pixel[0],pixel[1]]=0

        logging.info( "NOISY PIXELS: %s",  str(self.noisypixel_list) )       
            
    def analyze(self, h5_filename='',**kwargs):
        # Analyzes 

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
            #print np.bincount(hit_data['le'])
            tot[neg] = hit_data['te'][neg] + (255 - hit_data['le'][neg])
            new_hit_data['tot'] = tot

            interpreted_filename = self.output_filename +'_interpreted.h5'
            h5_file_interpreted = tb.open_file(interpreted_filename, mode='w', title=self.scan_id)
            hit_data_table = h5_file_interpreted.create_table(h5_file_interpreted.root, 'hit_data', new_hit_data, filters=self.filter_tables)
            hit_data_table.attrs.kwargs = yaml.dump(kwargs)
            hit_data_table.attrs.power_status = in_file_h5.root.meta_data.attrs.power_status
            hit_data_table.attrs.dac_status = in_file_h5.root.meta_data.attrs.dac_status
            hit_data_table.attrs.rx_status = in_file_h5.root.meta_data.attrs.rx_status
            hit_data_table.attrs.pixel_conf = in_file_h5.root.meta_data.attrs.pixel_conf

configuration = {
    "repeat": 200,
    "mask_filename": '',
    "scan_range": [0.05, 0.7, 0.025],
    "mask": 6,
    "TH": 0.800,
    "search_globalTH": True, 
    "columns": range(24,28),
    "threshold_overdrive": 0.006,
    "inj_target":0.15,
    "TH_lowlim": 0.760,
    "TH_highlim": 0.790,
    "LSB_value":45,
    "VPFB_value":32,
    "out_folder": '/home/idcs/STREAM/Devices/MONOPIX_01/Tests/20180730_Test_thinMONOPIX/InjTuning_200/'
}

if __name__ == "__main__": 
    from monopix_daq.monopix_extension import MonopixExtensions
    
    def calculate_new_threshold_settings(bit_index, n_inj, hist_map, old_threshold):
        new_threshold = old_threshold

        # TODO can be omitted when saving closest distance
        # check if optimal threshold is already found

        # In any case, switch next bit (if bit is not least significant) to 1
        if bit_index > 0:
            new_threshold = new_threshold | (1 << bit_index - 1)

        #  If needed raise threshold, otherwise keep 0
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
    
    
    run_threshold = True # TODO Set to True if a threshold scan should run after the tuning script, in order to check the tuning
    
    m_ex = MonopixExtensions("../monopix_mio3.yaml")
    tuning = Tuning(dut_extentions=m_ex, sender_addr="tcp://127.0.0.1:5500")
    tuning.configure(**configuration)
    tuning.start(**configuration)
    tuning.analyze(**configuration)
