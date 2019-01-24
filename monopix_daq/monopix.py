import time
import string
import os
import sys
import bitarray
import logging
import numpy as np

logger = logging.getLogger()
logger.setLevel(logging.INFO)

sys.path = [os.path.dirname(os.path.abspath(__file__))] + sys.path  #for data_rx module

from basil.dut import Dut
        
class monopix(Dut):

    def __init__(self,conf=None):
        
        if conf==None:
            conf = os.path.dirname(os.path.abspath(__file__)) + os.sep + "monopix.yaml"
        
        logging.info("Loading configuration file from %s" % conf)
        
        #conf = self._preprocess_conf(conf)
        super(monopix, self).__init__(conf)
        
        self.PIXEL_CONF = {'PREAMP_EN': np.full([36,129], True, dtype = np.bool),
                           'INJECT_EN'   : np.full([36,129], False, dtype = np.bool),
                           'MONITOR_EN'   : np.full([36,129], False, dtype = np.bool),
                           'TRIM_EN'  : np.full([36,129], 7, dtype = np.uint8),
                           }
        self.SET_VALUE={}
        
    def init(self):
        super(monopix, self).init()
        
        self['CONF']['RESET'] = 1
        self['CONF'].write()
        self['CONF']['RESET'] = 0
        self['CONF'].write()
        
        self['gate_tdc'].reset()
        self['inj'].reset()
        
        self['CONF_SR'].set_size(4841)
                
    def write_global_conf(self):
        
        self['CONF']['LDDAC'] = 1
        self['CONF'].write()
        
        self['CONF_SR'].write()
        while not self['CONF_SR'].is_ready:
            time.sleep(0.001)

        self['CONF']['LDDAC'] = 0
        self['CONF'].write()
        
    
    def _write_pixel_mask(self, mask):
                
        rev_mask = np.copy(mask)
        rev_mask[1::2,:] = np.fliplr(mask[1::2,:]) #reverse every 2nd column
        rev_mask = rev_mask[::-1,:] #reverse column
        
        mask_1d =  np.ravel(rev_mask)
        lmask = mask_1d.tolist()
        bv_mask = bitarray.bitarray(lmask)
                
        self['CONF']['LDPIX'] = 1
        self['CONF'].write()
        
        self['CONF_SR']['Pixels'][:] = bv_mask
        
        self['CONF_SR'].write()
        while not self['CONF_SR'].is_ready:
            time.sleep(0.001)
        
        self['CONF']['LDPIX'] = 0
        self['CONF'].write()
        
        
    def write_pixel_conf(self):

        for pix_bit in ['PREAMP_EN','INJECT_EN','MONITOR_EN']:
            self['CONF_SR'][pix_bit] = 1
            self._write_pixel_mask(self.PIXEL_CONF[pix_bit])
            self['CONF_SR'][pix_bit] = 0
        
        trim_bits = np.unpackbits(self.PIXEL_CONF['TRIM_EN'])
        trim_bits_array = np.reshape(trim_bits, (36,129,8)).astype(np.bool)
        
        for bit in range(4):
            trim_bits_sel_mask = trim_bits_array[:,:,7-bit]
            self['CONF_SR']['TRIM_EN'][bit] = 1
            self._write_pixel_mask(trim_bits_sel_mask)
            self['CONF_SR']['TRIM_EN'][bit] = 0
            
    def power_up(self):
    
        #DACS
        self['BL'].set_voltage(0.75, unit='V')
        self.SET_VALUE['BL']=0.75
        self['TH'].set_voltage(1.5, unit='V')
        self.SET_VALUE['TH']=1.5
        self['VCascC'].set_voltage(0.8, unit='V')
        self.SET_VALUE['VCascC']=0.8
        self['VCascN'].set_voltage(0.4, unit='V')
        self.SET_VALUE['VCascN']=0.4
        
        self['PBias'].set_current(0.5, unit='uA')
        self.SET_VALUE['PBias']=0.5
        
        self['INJ_HI'].set_voltage(0.5, unit='V')
        self.SET_VALUE['INJ_HI']=0.5
        self['INJ_LO'].set_voltage(0.1, unit='V')
        self.SET_VALUE['INJ_LO']=0.1
        
        #POWER
        self['VDDD'].set_current_limit(200, unit='mA')
        self['VDDD'].set_voltage(1.8, unit='V')
        self['VDDD'].set_enable(True)
        self.SET_VALUE['VDDD']=1.8

        self['VDDA'].set_voltage(1.8, unit='V')
        self['VDDA'].set_enable(True)
        self.SET_VALUE['VDDA']=1.8
        
        self['VDD_BCID_BUFF'].set_voltage(1.7, unit='V')
        self['VDD_BCID_BUFF'].set_enable(True)
        self.SET_VALUE['VDD_BCID_BUFF']=1.7
        
        self[
        self['VPC'].set_enable(True)
        self.SET_VALUE['VPC']=1.5

    def power_down(self):

        for pwr in ['VDDA', 'VDDD', 'VDD_BCID_BUFF', 'VPC']:
            self[pwr].set_enable(False)

    def power_status(self):
        staus = {}
       
        for pwr in ['VDDA', 'VDDD', 'VDD_BCID_BUFF', 'VPC']:
            staus[pwr+'[V]'] =  self[pwr].get_voltage(unit='V')
            staus[pwr+'[mA]'] = self[pwr].get_current(unit='mA')
            staus[pwr+"set"] = self.SET_VALUE[pwr]
        
        return staus
    
    def dac_status(self):
        staus = {}
        
        dac_names = ['BLRes', 'VAmp', 'VPFB', 'VPFoll', 'VPLoad', 'IComp', 'Vbias_CS', 'IBOTA', 'ILVDS', 'Vfs', 'LSBdacL', 'Vsf_dis1', 'Vsf_dis2','Vsf_dis3']
        for dac in  dac_names:
            staus[dac] = int(str(self['CONF_SR'][dac]), 2)
            
        for dac in ['BL', 'TH', 'VCascC', 'VCascN']:
            staus[dac] =  self[dac].get_voltage(unit='V')
            staus[dac+"set"] = self.SET_VALUE[dac]
        for dac in ['INJ_LO', 'INJ_HI']:
            staus[dac+"set"] = self.SET_VALUE[dac]
        return staus
        
    def interpret_tdc_data(self, raw_data, meta_data = []):
        data_type = {'names':['tdc','scan_param_id'], 'formats':['uint16','uint16']}
        ret = []
        if len(meta_data):
            param, index = np.unique(meta_data['scan_param_id'], return_index=True)
            index = index[1:]
            index = np.append(index, meta_data.shape[0])
            index = index - 1
            stops = meta_data['index_stop'][index]
            split = np.split(raw_data, stops)
            for i in range(len(split[:-1])):
                int_pix_data = self.interpret_tdc_data(split[i])
                int_pix_data['scan_param_id'][:] = param[i]
                if len(ret):
                    ret = np.hstack((ret, int_pix_data))
                else:
                    ret = int_pix_data
        else:
            ret = np.recarray((raw_data.shape[0]), dtype=data_type) 
            ret['tdc'][:] = np.bitwise_and(raw_data, 0xfff)     
            
        return ret
    
    def interpret_rx_data(self, raw_data, meta_data = []):
        raise(NotImplementedError)
        
        
if __name__=="__main__":
    
    dut = monopix.monopix()
    dut.init()
