import time
import numpy as np
import tables as tb
import yaml
import logging
import os

import matplotlib
matplotlib.use('Agg')
from monopix_daq.analysis import analysis
from simple_scan import SimpleScan
from matplotlib import pyplot as plt
from matplotlib.backends.backend_pdf import PdfPages
from monopix_daq.analysis.interpret_scan import interpret_rx_data,interpret_rx_data_scan
from monopix_daq.analysis.plotting import plot_THscan
from monopix_daq.scan_base import ScanBase
from basil.dut import Dut
from monopix_daq.monopix_extension import MonopixExtensions


logging.basicConfig(level=logging.INFO, format="%(asctime)s - %(name)s - [%(levelname)-8s] (%(threadName)-10s) %(message)s")

show_info = False

class ScanThreshold(SimpleScan):
    
    scan_id = "scan_threshold"
    noisypixel_list=[]

    def get_filename(self):
        return self.output_filename
    
    def scan(self, repeat=100, scan_range=[0.0, 0.35, 0.025], mask_filename='', TH=1.5, mask=16, columns=range(0, 36), threshold_overdrive=0.001, 
             LSB_value=32, VPFB_value=32, TRIM_EN=None, **kwargs):
        #self.configure()
        self.mus = np.zeros(shape=(36, 129), dtype='f')
        self.sigmas = np.zeros(shape=(36, 129), dtype='f')

        # LOAD PIXEL DAC
        if mask_filename[-3:] ==".h5":
#            with tb.open_file(str(mask_filename), 'r') as in_file_h5:
#                logging.info('Loading configuration from: %s', mask_filename)
#
#                TRIM_EN = in_file_h5.root.scan_results.TRIM_EN[:]
#                PREAMP_EN = in_file_h5.root.scan_results.PREAMP_EN[:]
#
#                self.dut.PIXEL_CONF['TRIM_EN'][:] = TRIM_EN[:]
#                self.dut.PIXEL_CONF['PREAMP_EN'][:] = PREAMP_EN[:]
#
#                dac_status = yaml.load(in_file_h5.root.meta_data.attrs.dac_status)
#                power_status = yaml.load(in_file_h5.root.meta_data.attrs.power_status)
#
#                TH = in_file_h5.root.meta_data.attrs.final_threshold + threshold_overdrive
#                logging.info('Loading threshold values (+mv): %f', TH)
#
#                logging.info('Loading DAC values from: %s', str(dac_status))
#                dac_names = ['BLRes', 'VAmp', 'VPFB', 'VPFoll', 'VPLoad', 'IComp', 'Vbias_CS', 'IBOTA', 'ILVDS', 'Vfs', 'LSBdacL', 'Vsf_dis1', 'Vsf_dis2', 'Vsf_dis3']
#                for dac in dac_names:
#                    self.dut['CONF_SR'][dac] = dac_status[dac]
#                    print dac, self.dut['CONF_SR'][dac]
#
#                scan_kwargs = yaml.load(in_file_h5.root.meta_data.attrs.kwargs)
#                columns = scan_kwargs['column_enable']
#                logging.info('Column Enable: %s', str(columns))

            self.dut_extensions.load_config(mask_filename)
            
            if configuration["TH_from_mask"]==False:
                TH = configuration["TH"]
                logging.info("Threshold set from local configuration: %s", str(TH))
                              
            else:
                TH = self.dut['TH'].get_voltage(unit='V')
                logging.info("Threshold modified from loaded file: %s", str(TH))
                
            
            #time.sleep(10)
                
            with tb.open_file(str(mask_filename), 'r') as in_file_h5:
                loaded_kwargs = yaml.load(in_file_h5.root.meta_data.attrs.kwargs)
                ret = yaml.load(in_file_h5.root.meta_data.attrs.pixel_conf)
                columns=loaded_kwargs['columns']
                logging.info('Column Enable: %s', str(columns))
                #THE_TRIM = np.load('/home/idcs/STREAM/Devices/MONOPIX_01/Tests/20180705_Test_thinMONOPIX/InjTuning_200/20180724-173423_target0,18_TH0,772_VPFB32/trim_values_step4.npy')
                #self.dut.PIXEL_CONF['TRIM_EN'][:] = THE_TRIM
                self.dut_extensions.set_preamp_en(ret["pix_PREAMP_EN"])
                
#                
#                try:
#                    inj_target_v=loaded_kwargs['inj_target']
#                    logging.info('Injection target from tuning: %s', str(inj_target_v))
#                except:
#                    pass
#                
#                try:
#                    TH=loaded_kwargs['TH']
#                    logging.info('Loaded TH: %s', str(TH))
#                except:
#                    pass
            
#            for pix_col in columns:
#                self.dut.PIXEL_CONF['PREAMP_EN'][pix_col, :] = 1
        elif mask_filename[-4:] ==".npy":
            THE_TRIM = np.load(mask_filename)
            self.dut.PIXEL_CONF['TRIM_EN'][:] = THE_TRIM

        else:
            # first time, get TRIM_EN from configuration
            if np.any(TRIM_EN is None):
                for pix_col in columns:
                    self.dut.PIXEL_CONF['PREAMP_EN'][pix_col, :] = 1

            else:
                # if TRIM_EN is given as parameter, do not change it
                for pix_col in columns:
                    self.dut.PIXEL_CONF['PREAMP_EN'][pix_col, :] = 1

#        self.dut.PIXEL_CONF['TRIM_EN'][:] = np.load(file_path + '/trim_values_step4.npy')

        for pix_col in columns:
            dcol = int(pix_col / 2)
#            self.dut['CONF_SR']['ColRO_En'][35 - pix_col] = 1

#         self.dut.PIXEL_CONF['TRIM_EN'][:] = 8
        if file_path!='' and mask_filename=='':    
            self.dut.PIXEL_CONF['TRIM_EN'][:] = 0
        elif file_path=='' and mask_filename!='':
            pass
            #self.dut.PIXEL_CONF['TRIM_EN'][:] = np.load(file_path + '/trim_values_step4.npy')
        else:
            pass
        
        ##print self.dut.PIXEL_CONF['TRIM_EN'][configuration['columns'][:], :]
        ##print self.dut.PIXEL_CONF['PREAMP_EN'][configuration['columns'][:], :]
        
        self.dut.write_pixel_conf()
        self.dut.write_global_conf()

        scan_range = np.arange(scan_range[0], scan_range[1], scan_range[2])

        logging.info('Threshold from configuration: %f', TH)
        #print "THs"
        #print TH
        #print self.dut['TH'].get_voltage(unit='V')

        self.dut['TH'].set_voltage(TH-0.001, unit='V')
        #self.logger.info('Power Status: %s', str(self.dut.power_status()))
        logging.info('Measured threshold: %f', str(self.dut['TH'].get_voltage(unit='V')))
        

        for pix_col_indx, pix_col in enumerate(columns):
            
	    #self.dut.PIXEL_CONF['TRIM_EN'][:] = TRIM_EN[:]
        #ojojo    self.dut['CONF_SR']['INJ_EN'].setall(False)

            mask_steps = []
            for m in range(mask):
                col_mask = np.copy(self.dut.PIXEL_CONF['INJECT_EN'][pix_col, :])
                col_mask[m::mask] = True
                mask_steps.append(np.copy(col_mask))
             
            # begin scan loop here
            logging.info('Scanning column: %i'pix_col
            self.scan_loop(pix_col_indx, pix_col, mask, mask_steps, TRIM_EN, TH, scan_range, repeat)
            #pdf.savefig(fig)
            #plt.close()

#         plt.clf()
        #plt.savefig(file_path + '/s_curve_tuned.pdf')
        
        mus = self.mus
        sigmas = self.sigmas
        np.save(file_path + '/mu_values.npy', mus)
        np.save(file_path + '/sigma_values.npy', sigmas)
        
        plot_THscan.plot_thresholdscanresults(file_path, Cinj=2.75e4, columns=columns)
#        plt.clf()

    def scan_loop(self, pix_col_indx, pix_col, mask, mask_steps, TRIM_EN, TH, scan_range, repeat):

        # activate mask
        for idx, mask_step in enumerate(mask_steps):

            dcol = int(pix_col / 2)
            self.dut['CONF_SR']['INJ_EN'][:] = 0 
            self.dut['CONF_SR']['PREAMP_EN'][:] = 0 
            #self.dut.PIXEL_CONF['TRIM_EN'][:] = 15
            self.dut.PIXEL_CONF['PREAMP_EN'][:] = 0 
            
            self.dut.PIXEL_CONF['INJECT_EN'][:] = 0

            self.dut.PIXEL_CONF['PREAMP_EN'][pix_col, :][mask_step] = 1
            self.dut.PIXEL_CONF['INJECT_EN'][pix_col, :][mask_step] = 1 
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

            data_type = {'names': ['inj', 'col', 'row', 'hist'], 'formats': [np.float64, 'uint16', 'uint16', 'uint16']}
            hits = np.recarray((0), dtype=data_type)

            ##print "Before injecting:"
            ##print self.dut.PIXEL_CONF['TRIM_EN'][configuration['columns'][:], :]
            ##print self.dut.PIXEL_CONF['PREAMP_EN'][configuration['columns'][:], :]
            # for given mask change injection value
            for vol_idx, inj_value in enumerate(scan_range):
            
                self.dut['data_rx'].reset()
                self.dut['fifo'].reset()             
            
                for pixel in self.noisypixel_list:
                    self.dut.PIXEL_CONF['PREAMP_EN'][pixel[0],pixel[1]]=0
                    self.dut.PIXEL_CONF['INJECT_EN'][pixel[0],pixel[1]]=0
                    self.dut.write_pixel_conf()
                    self.dut.write_global_conf()

                
                param_id = pix_col_indx * len(scan_range) * mask + idx * len(scan_range) + vol_idx

                if show_info:
                    logging.info('Scan : Column = %s MaskId=%d InjV=%f ID=%d', pix_col, idx, inj_value, param_id)

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
                    
                    self.dut['inj'].start()

                    while not self.dut['inj'].is_done():
                        pass

                    time.sleep(0.2)

                    self.dut['data_rx'].set_en(False)

                
                self.dut['TH'].set_voltage(1.5, unit='V')    
                dqdata = self.fifo_readout.data
                
                try:
                    data = np.concatenate([item[0] for item in dqdata])
                except ValueError:
                    data = []

                data_size = len(data)

                logging.info('Scan Pixel Finished: V=%f DATA_COUNT=%d', inj_value, data_size)

                hit_data = interpret_rx_data(data, delete_noise=True)
                print "raw_data",len(data),"hit_data",len(hit_data)
                pixel_data = np.array(hit_data['col'],dtype="int")*129+np.array(hit_data['row'],dtype="int")
                hit_pixels = np.unique(pixel_data)
                hist = np.bincount(pixel_data)

                # calculate threshold for pixels in this mask step here

                msg = ' '
               
                if data_size:
                    for pix in hit_pixels:
                        col = pix / 129
                        row = pix % 129
                    	#Noisy pixels to the noisy pixel list
                        if hist[pix] > 1.2* float(repeat):
                            self.noisypixel_list.append([col,row])
                            logging.info("Added to the noisy list: [%d, %d] ", col, row ) 
                            self.dut.PIXEL_CONF['PREAMP_EN'][col, row] = 0
                        msg += '[%d, %d]=%d ' % (col, row, hist[pix])
                        hits = np.append(hits, np.array([tuple([inj_value, col, row, hist[pix]])], dtype=data_type))
                    logging.info(msg)

                if data_size > 10000000:
                    logging.error('Too much data!')

                    return

            time.sleep(.5)

            logging.info("Analyze data of column %d" % pix_col)
            TRIM_EN = self.calculate_pixel_threshold(hits, scan_range, TRIM_EN, repeat)

        self.TRIM_EN = TRIM_EN

    def calculate_pixel_threshold(self, hits, scan_range, TRIM_EN, repeat):
        hits['col'] = hits['col'] * 129 + hits['row']

        # TODO: ignore pixels that are not in mask
        for pixel in np.unique(hits['col']):
            pixel_data = hits[np.where(hits['col'] == pixel)[0]]

            hist = np.zeros(shape=(len(scan_range)))

            # pad all other injection values where no hits are with 0
            for index, inj_value in enumerate(pixel_data['inj']):
                hist[scan_range == inj_value] = pixel_data['hist'][index]

            # fit s curve
            A, mu, sigma = analysis.fit_scurve(hist, scan_range, repeat)
            pixel_col= pixel / 129
            pixel_row= pixel % 129
            self.mus[pixel / 129, pixel % 129] = mu
            self.sigmas[pixel / 129, pixel % 129] = sigma
            
            fig=plt.figure()
            plt.ylim(0, repeat + 0.12*repeat)
            plt.title('S-curve for pixel [%d,%d]' %(pixel_col,pixel_row) )
            plt.plot(scan_range, hist, marker= "o", linestyle='--')
            plt.plot(np.arange(scan_range[0], scan_range[-1], 0.001), analysis.scurve(np.arange(scan_range[0], scan_range[-1], 0.001), A, mu, sigma))
            pdf.savefig(fig)
            plt.close()



configuration = {
    "repeat": 200,
    "mask_filename": '/home/idcs/git/monopix_cleanup201807/monopix_master/monopix_daq/scans/output_data/20180726_232538_tune_threshold_inj.h5',
    "scan_range": [0.05, 0.4, 0.025],
    "mask": 4,
    "TH": 0.765,
    "TH_from_mask":False,
    "columns": range(24,26),
    "threshold_overdrive": 0.006,
    "LSB_value":45,
    "VPFB_value":32,
    "out_folder":""
    }

if __name__ == '__main__':
    from monopix_daq.monopix_extension import MonopixExtensions        
        
    timestr = time.strftime("%Y%m%d-%H%M%S")
    if str(configuration["mask_filename"])!='':
        TH_str= "X"
        LSB_str= "X"
        VPFB_str= "X"
    else:
        TH_str= str(configuration["TH"])
        TH_str=TH_str.replace('.',',')
        LSB_str= str(configuration["LSB_value"])
        VPFB_str= str(configuration["VPFB_value"])
    
    if configuration["out_folder"]=="":
        out_folder = os.path.join(os.getcwd(),"output_data/")
    else:    
        pass
    file_path = out_folder+timestr+"_scan_th"+'_TH'+TH_str+'_LSB'+LSB_str+'_VPFB'+VPFB_str+'/'
    
    #file_path = out_folder+timestr+"_tune_th"+'_target'+inj_str+'_TH'+TH_str+'_LSB'+LSB_str+'_VPFB'+VPFB_str
    #file_path = '../scans/output_data/scanTH_'+timestr+'_TH'+TH_str+'_LSB'+LSB_str+'_VPFB'+VPFB_str+'/'

    if not os.path.exists(file_path):
        os.makedirs(file_path)
        logging.info( "Created folder: %s", file_path)
    
    m_ex = MonopixExtensions("../monopix_mio3.yaml")
    scan = ScanThreshold(dut_extentions=m_ex, fname=file_path, sender_addr="tcp://127.0.0.1:5500")
    
    with PdfPages(file_path + '/s_curve_tuned.pdf') as pdf:
        scan.configure(**configuration)
        scan.start(**configuration)
        logging.info( "Threshold: %s", str(scan.dut['TH'].get_voltage(unit='V')))
        TRIM_EN = scan.TRIM_EN
    plt.clf()
