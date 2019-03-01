import sys,time,os
import numpy as np
import logging
import warnings
import yaml
import bitarray
import tables
import yaml
import socket

sys.path = [os.path.dirname(os.path.abspath(__file__))] + sys.path 
COL_SIZE = 36 ##TODO change hard coded values
ROW_SIZE = 129
OUTPUT_DIR=os.path.join(os.path.dirname(os.path.abspath(__file__)),"output_data")

import basil.dut

def format_power(dat): ### TODO improve more...
    s="power:"
    for pwr in ['VDDA', 'VDDD', 'VDD_BCID_BUFF', 'VPC', "PBias", "NTC",
                'BL', 'TH', 'VCascC', 'VCascN']:
        s=s+" %s=%.4fV(%fmA)"%(pwr,dat[pwr+'[V]'] ,dat[pwr+'[mA]']) 
    return s
def format_dac(dat): ### TODO improve more...
    s="DAC:"
    for dac in ['BLRes', 'VAmp', 'VPFB', 'VPFoll', 'VPLoad', 'IComp', 'Vbias_CS', 'IBOTA', 'ILVDS', 'Vfs', 'LSBdacL', 'Vsf_dis1', 'Vsf_dis2','Vsf_dis3']:
        s=s+" %s=%d"%(dac,dat[dac]) 
    return s
def format_pix(dat): ### TODO improve more...
    s="Pixels:"
    return s
    
def mk_fname(ext="data.npy",dirname=None):
    if dirname==None:
        prefix=ext.split(".")[0]
        dirname=os.path.join(OUTPUT_DIR,prefix)
    if not os.path.exists(dirname):
        os.system("mkdir -p %s"%dirname)
    return os.path.join(dirname,time.strftime("%Y%m%d_%H%M%S0_")+ext)

class Monopix():
    default_yaml=os.path.dirname(os.path.abspath(__file__)) + os.sep + "monopix_mio3.yaml"
    def __init__(self,dut=None,no_power_reset=True):
        ## set logger
        self.logger = logging.getLogger()
        logFormatter = logging.Formatter("%(asctime)s [%(levelname)-5.5s] (%(threadName)-10s) %(message)s")
        fname=mk_fname(ext="log.log")
        fileHandler = logging.FileHandler(fname)
        fileHandler.setFormatter(logFormatter) 
        self.logger.addHandler(fileHandler)

        self.debug=0
        self.inj_device="gpac"
        self.COL_SIZE = 36  ##TODO this will be used in scans... maybe not here
        self.ROW_SIZE = 129

        if dut is None:
            dut = self.default_yaml
        if isinstance(dut,str):
            with open(dut) as f:
                conf=yaml.load(f)
            for i,e in enumerate(conf["hw_drivers"]):
                if e["type"]=="GPAC":
                    conf["hw_drivers"][i]["init"]["no_power_reset"]=no_power_reset
                    break
            self.dut=basil.dut.Dut(conf=conf)
        elif isinstance(dut,monopix.Monopix):
            self.dut=dut

        self.dut.PIXEL_CONF = {'PREAMP_EN': np.full([36,129], True, dtype = np.bool),
                       'INJECT_EN'   : np.full([36,129], False, dtype = np.bool),
                       'MONITOR_EN'   : np.full([36,129], False, dtype = np.bool),
                       'TRIM_EN'  : np.full([36,129], 7, dtype = np.uint8),
                       }
         
        self.dut.SET_VALUE={}
        self.dut.init()
        fw_version = self.dut['intf'].read(0x0,1)[0]
        logging.info("Firmware version: %s" % (fw_version))
        
        for reg in self.dut._conf["registers"]:
            if reg["name"] in ["INJ_HI", "INJ_LO"] and "init" in reg:
                self.logger.info("modify %s: %s"%(reg["name"],str(reg["init"])))
                self.dut[reg["name"]]._ch_cal[reg['arg_add']['channel']].update(reg["init"])

        self.dut['CONF']['RESET'] = 1
        self.dut['CONF'].write()
        self.dut['CONF']['RESET'] = 0
        self.dut['CONF'].write()
        self.dut['inj'].reset()
        self.dut['CONF_SR'].set_size(4841)

        self.power_up()

        status=self.power_status()
        s=format_power(status)
        self.logger.info(s)
        self._write_global_conf()
        self.set_preamp_en("all")
        self.set_inj_en([18,25])
        self.set_mon_en([18,25])
        self.set_tdac(0)
        
        self.dut["gate_tdc"].reset()
        self.set_inj_all()
        
    def reconnect_fifo(self):
        try:
            self.dut['intf']._sock_tcp.close()
        except:
            pass
        self.dut['intf']._sock_tcp = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        connect_timeout = float(self.dut['intf']._init.get('connect_timeout', 5.0))
        self.dut['intf']._sock_tcp.settimeout(connect_timeout)
        self.dut['intf']._sock_tcp.connect((self.dut['intf']._init['ip'], self.dut['intf']._init['tcp_port']))
        self.dut['intf']._sock_tcp.settimeout(None) 
        self.dut['intf']._sock_tcp.setblocking(0)

    def _write_global_conf(self):        
        self.dut['CONF']['LDDAC'] = 1
        self.dut['CONF'].write()
        
        self.dut['CONF_SR'].write()
        while not self.dut['CONF_SR'].is_ready:
            time.sleep(0.001)

        self.dut['CONF']['LDDAC'] = 0
        self.dut['CONF'].write()
        
    def _write_pixel_mask(self, mask):                
        rev_mask = np.copy(mask)
        rev_mask[1::2,:] = np.fliplr(mask[1::2,:]) #reverse every 2nd column
        rev_mask = rev_mask[::-1,:] #reverse column
        
        mask_1d =  np.ravel(rev_mask)
        lmask = mask_1d.tolist()
        bv_mask = bitarray.bitarray(lmask)
                
        self.dut['CONF']['LDPIX'] = 1
        self.dut['CONF'].write()
        
        self.dut['CONF_SR']['Pixels'][:] = bv_mask
        
        self.dut['CONF_SR'].write()
        while not self.dut['CONF_SR'].is_ready:
            time.sleep(0.001)
        
        self.dut['CONF']['LDPIX'] = 0
        self.dut['CONF'].write()
    
    def _cal_pix(self,pix_bit,pix):
        if isinstance(pix,str):
            if pix=="all":
                self.dut.PIXEL_CONF[pix_bit][:,:]=1
            elif pix=="none":
                self.dut.PIXEL_CONF[pix_bit][:,:]=0
        elif isinstance(pix[0],int):
            self.dut.PIXEL_CONF[pix_bit][:,:]=0
            self.dut.PIXEL_CONF[pix_bit][pix[0],pix[1]]=1
        elif len(pix)==COL_SIZE and len(pix[0])==ROW_SIZE:
            self.dut.PIXEL_CONF[pix_bit][:,:]=np.array(pix,np.bool)
        else:
            self.dut.PIXEL_CONF[pix_bit][:,:]=0
            for p in pix:
               self.dut.PIXEL_CONF[pix_bit][p[0],p[1]]=1
               
###### power ##### 
    def power_up(self,VDDD=1.8,VDDA=1.8,VDD_BCID_BUFF=1.8,VPC=1.5,BL=0.75,TH=1.5,VCascC=0.8,VCascN=0.4,
                PBias=0.5,NTC=5,INJ_HI=0.6,INJ_LO=0.2):
    
        #DACS
        self.dut['BL'].set_voltage(BL, unit='V')
        self.dut.SET_VALUE['BL']=BL
        self.dut['TH'].set_voltage(TH, unit='V')
        self.dut.SET_VALUE['TH']=TH
        self.dut['VCascC'].set_voltage(VCascC, unit='V')
        self.dut.SET_VALUE['VCascC']=VCascC
        self.dut['VCascN'].set_voltage(VCascN, unit='V')
        self.dut.SET_VALUE['VCascN']=VCascN
        
        self.dut['PBias'].set_current(PBias, unit='uA')
        self.dut.SET_VALUE['PBias']=PBias
        self.dut["NTC"].set_current(NTC,unit="uA")
        self.dut.SET_VALUE['NTC']=NTC
        
        self.dut['INJ_HI'].set_voltage(INJ_HI, unit='V')
        self.dut.SET_VALUE['INJ_HI']=INJ_HI
        self.dut['INJ_LO'].set_voltage(INJ_LO, unit='V')
        self.dut.SET_VALUE['INJ_LO']=INJ_LO
        
        #POWER
        self.dut['VDDD'].set_current_limit(200, unit='mA')
        self.dut['VDDD'].set_voltage(VDDD, unit='V')
        self.dut['VDDD'].set_enable(True)
        self.dut.SET_VALUE['VDDD']=VDDD

        self.dut['VDDA'].set_voltage(VDDA, unit='V')
        self.dut['VDDA'].set_enable(True)
        self.dut.SET_VALUE['VDDA']=VDDA
        
        self.dut['VDD_BCID_BUFF'].set_voltage(VDD_BCID_BUFF, unit='V')
        self.dut['VDD_BCID_BUFF'].set_enable(True)
        self.dut.SET_VALUE['VDD_BCID_BUFF']=VDD_BCID_BUFF
        
        self.dut['VPC'].set_voltage(VPC, unit='V')
        self.dut['VPC'].set_enable(True)
        self.dut.SET_VALUE['VPC']=VPC 
                    
    def power_down(self):
        for pwr in ['VDDA', 'VDDD', 'VDD_BCID_BUFF', 'VPC']:
            self.dut[pwr].set_enable(False)
            
    def power_status(self):
        staus = {}       
        for pwr in ['VDDA', 'VDDD', 'VDD_BCID_BUFF', 'VPC', "PBias", "NTC",
                    'BL', 'TH', 'VCascC', 'VCascN']:
            staus[pwr+'[V]'] =  self.dut[pwr].get_voltage(unit='V')
            staus[pwr+'[mA]'] = self.dut[pwr].get_current(unit='mA')
            staus[pwr+"set"] = self.dut.SET_VALUE[pwr]
        for dac in ['INJ_LO', 'INJ_HI']:
            staus[dac+"set"] = self.dut.SET_VALUE[dac]
        return staus
    
    def dac_status(self):
        staus = {}       
        dac_names = ['BLRes', 'VAmp', 'VPFB', 'VPFoll', 'VPLoad', 'IComp', 'Vbias_CS', 'IBOTA', 'ILVDS', 'Vfs', 'LSBdacL', 'Vsf_dis1', 'Vsf_dis2','Vsf_dis3']
        for dac in  dac_names:
            staus[dac] = int(str(self.dut['CONF_SR'][dac]), 2)
        return staus   
               
###### pixel dac ##### 
    def set_preamp_en(self,pix="all",ColRO_En="auto"):
        self._cal_pix("PREAMP_EN",pix)       
        self.dut["CONF_SR"]["REGULATOR_EN"] = bool(np.any(self.dut.PIXEL_CONF["PREAMP_EN"][:,:]))
        self.dut['CONF_SR']['ColRO_En'].setall(False)

        if ColRO_En=="auto":
            for i in range(36):
                self.dut['CONF_SR']['ColRO_En'][35-i] = bool(np.any(self.dut.PIXEL_CONF["PREAMP_EN"][i,:]))
        elif ColRO_En=="all":
            self.dut['CONF_SR']['ColRO_En'].setall(True)
        elif ColRO_En=="none":
            self.dut['CONF_SR']['ColRO_En'].setall(False)
        elif ":" in ColRO_En:
            cols=np.zeros(COL_SIZE,int)
            tmp=ColRO_En.split(":")
            cols[int(tmp[0]):int(tmp[1])]=1
            for i in range(36):
                self.dut['CONF_SR']['ColRO_En'][35-i] = bool(cols[i])
        elif len(ColRO_En)==36:
            self.dut['CONF_SR']['ColRO_En'] = ColRO_En

        self.dut['CONF_SR']["PREAMP_EN"] = 1 
        self._write_pixel_mask(self.dut.PIXEL_CONF["PREAMP_EN"])
        self.dut['CONF_SR']["PREAMP_EN"] = 0
        
        self._write_global_conf()
        
        arg=np.argwhere(self.dut.PIXEL_CONF["PREAMP_EN"][:,:])
        self.logger.info("set_preamp_en pix=%d%s ColRO_En=%s"%(
                         len(arg),str(arg).replace("\n"," "),
                         str(self.dut['CONF_SR']['ColRO_En'])))

    def set_mon_en(self,pix="none"):
        pixlist=self._cal_pix("MONITOR_EN",pix)
        self.dut["CONF_SR"]["BUFFER_EN"] = bool(np.any(self.dut.PIXEL_CONF["MONITOR_EN"][:,:]))
        self.dut['CONF_SR']['MON_EN'].setall(False)
        for i in range(36):
            self.dut['CONF_SR']['MON_EN'][35-i] = bool(np.any(self.dut.PIXEL_CONF["MONITOR_EN"][i,:]))
        self.dut['CONF_SR']["MONITOR_EN"] = 1 
        self._write_pixel_mask(self.dut.PIXEL_CONF["MONITOR_EN"])
        self.dut['CONF_SR']["MONITOR_EN"] = 0

        self._write_global_conf()
      
        arg=np.argwhere(self.dut.PIXEL_CONF["MONITOR_EN"][:,:])
        self.logger.info("set_mon_en pix: %d%s"%(len(arg),str(arg).replace("\n"," ")))

    def set_inj_en(self,pix="none"):
        pixlist=self._cal_pix("INJECT_EN",pix)
        self.dut['CONF_SR']['INJ_EN'].setall(False)
        for i in range(18):
            self.dut['CONF_SR']['INJ_EN'][17-i] = bool(np.any(self.dut.PIXEL_CONF["INJECT_EN"][2*i:2*(i+1),:]))
        self.dut['CONF_SR']["INJECT_EN"] = 1
        self._write_pixel_mask(self.dut.PIXEL_CONF["INJECT_EN"])
        self.dut['CONF_SR']["INJECT_EN"] = 0
        
        self._write_global_conf()

        arg=np.argwhere(self.dut.PIXEL_CONF["INJECT_EN"][:,:])
        self.logger.info("set_inj_en pix: %d %s"%(len(arg),str(arg).replace("\n"," ")))
        
    def set_tdac(self,tdac):
        if isinstance(tdac,int):
            self.dut.PIXEL_CONF["TRIM_EN"][:,:]=tdac
            self.logger.info("set_tdac all: %d"%tdac)
        elif len(tdac)==len(self.dut.PIXEL_CONF["TRIM_EN"]) and \
             len(tdac[0])== len(self.dut.PIXEL_CONF["TRIM_EN"][0]):
            self.logger.info("set_tdac")
            self.dut.PIXEL_CONF["TRIM_EN"]=np.array(tdac,dtype = np.uint8)
        else:
            self.logger.info("ERROR: wrong instance. tdac must be int or [36,129]")
            return 

        trim_bits = np.unpackbits(self.dut.PIXEL_CONF['TRIM_EN'])
        trim_bits_array = np.reshape(trim_bits, (36,129,8)).astype(np.bool)
        for bit in range(4):
            trim_bits_sel_mask = trim_bits_array[:,:,7-bit]
            self.dut['CONF_SR']['TRIM_EN'][bit] = 1
            self._write_pixel_mask(trim_bits_sel_mask)
            self.dut['CONF_SR']['TRIM_EN'][bit] = 0
        self._write_global_conf()
        
    def get_tdac_memory(self):
        return np.copy(self.dut.PIXEL_CONF["TRIM_EN"])
    
    def pix_status(self):
        for k in ["ColRO_En","MON_EN","INJ_EN","BUFFER_EN","REGULATOR_EN","Pixels"]:
            ret[k]=self.dut["CONF_SR"][k].to01()
        return ret
        
##### global dac ####
    def set_global(self,**kwarg):
        for k in kwarg.keys():
            self.dut["CONF_SR"][k]=kwarg[k]
        self._write_global_conf()
        s="set_global:"
        for k in kwarg.keys():
            s=s+"%s=%d "%(k,kwarg[k])
        self.logger.info(s)
            
    def set_th(self,th):
        self.dut['TH'].set_voltage(th, unit='V')
        self.dut.SET_VALUE["TH"]=th
        th_meas=self.dut['TH'].get_voltage(unit='V')
        self.logger.info("set_th: TH=%f th_meas=%f"%(th,th_meas)) 
        
    def get_th(self):
        th_meas=self.dut['TH'].get_voltage(unit='V')
        self.logger.info("get_th:th_set=%f th_meas=%f"%(self.dut.SET_VALUE["TH"],th_meas))
        return th_meas
        
##### temp and inj ####
    def get_temperature(self):
        vol=self.dut["NTC"].get_voltage()
        if not (vol>0.5 and vol<1.5):
          for i in np.arange(200,-200,-2):
            self.dut["NTC"].set_current(i,unit="uA")
            self.dut.SET_VALUE["NTC"]=i
            time.sleep(0.1)
            vol=self.dut["NTC"].get_voltage()
            if vol>0.7 and vol<1.3:
                break
          if abs(i)>190:
            self.logger.info("temperature() NTC error")
        temp=np.empty(10)
        for i in range(len(temp)):
            temp[i]=self.dut["NTC"].get_temperature("C")
        return np.average(temp[temp!=float("nan")])
        
    def set_inj_high(self,inj_high):
        if isinstance(self.inj_device,str) and self.inj_device=="gpac":
            self.dut["INJ_HI"].set_voltage(inj_high,unit="V")
        else:
            self.inj_device.set_voltage(inj_high,high=True)
            time.sleep(0.1)
        self.dut.SET_VALUE["INJ_HI"]=inj_high
            
    def set_inj_low(self,inj_low):
        if isinstance(self.inj_device,str) and self.inj_device=="gpac":
            self.dut["INJ_LO"].set_voltage(inj_low,unit="V")
        else:
            self.inj_device.set_voltage(inj_low,high=False)
            time.sleep(0.1)
        self.dut.SET_VALUE["INJ_LO"]=inj_low
       
    def set_inj_all(self,inj_high=0.6,inj_low=0.2,inj_n=100,inj_width=5000,delay=700,ext=False,inj_phase=0):
        self.set_inj_high(inj_high)
        self.set_inj_low(inj_low)

        self.dut["inj"].reset()
        self.dut["inj"]["REPEAT"]=inj_n
        self.dut["inj"]["DELAY"]=inj_width
        self.dut["inj"]["WIDTH"]=inj_width
        self.dut["inj"].set_phase(int(inj_phase))
        self.dut["inj"]["EN"]=0
        
        if self.dut["inj"].get_phase()!=inj_phase:
            self.logger.error("inj:set_inj_phase=%d PHASE_DES=%x"%(inj_phase,self.dut["inj"]["PHASE_DES"]))

        self.logger.info("inj:%.4f,%.4f inj_width:%d inj_phase:%x inj_n:%d delay:%d ext:%d"%(
            inj_high,inj_low,inj_width,
            self.dut["inj"]["PHASE_DES"],
            self.dut["inj"]["REPEAT"],delay,
            int(ext)))
            
    def start_inj(self,inj_high=None,wait=False):
        if inj_high is not None:
            self.set_inj_high(inj_high)
        self.dut["inj"].start()
        self.logger.info("start_inj:%.4f,%.4f phase=%d"%(
                self.dut.SET_VALUE["INJ_HI"],self.dut.SET_VALUE["INJ_LO"],
                self.dut["inj"].get_phase()))
        while self.dut["inj"].is_done()!=1 and wait==True:
             time.sleep(0.001)
            
###### data fifo ####
    def get_data_now(self):
        return self.dut['fifo'].get_data()

    def get_data(self,wait=0.2):
        self.dut["inj"].start()
        i=0
        raw=np.empty(0,dtype='uint32')
        while self.dut["inj"].is_done()!=1:
            time.sleep(0.001)
            raw=np.append(raw,self.dut['fifo'].get_data())
            i=i+1
            if i>10000:
                break
        time.sleep(wait)
        raw=np.append(raw,self.dut['fifo'].get_data())
        if i>10000:
            self.logger.info("get_data: error timeout len=%d"%len(raw))
        lost_cnt=self.dut["data_rx"]["LOST_COUNT"]
        if self.dut["data_rx"]["LOST_COUNT"]!=0:
            self.logger.warn("get_data: error cnt=%d"%lost_cnt)      
        return raw
        
    def reset_monoread(self,wait=0.001,sync_timestamp=1):
        self.dut['CONF']['EN_GRAY_RESET_WITH_TIMESTAMP'] = sync_timestamp
        self.dut['CONF']['RESET_GRAY'] = 1
        self.dut['CONF']['RESET'] = 1
        self.dut['CONF'].write()
        time.sleep(wait)
        self.dut['CONF']['RESET'] = 0
        self.dut['CONF'].write()
        time.sleep(wait)
        self.dut['CONF']['RESET_GRAY'] = 0
        self.dut['CONF'].write()
        
    def set_monoread(self,start_freeze=90,start_read=90+2,stop_read=90+2+2,
                     stop_freeze=90+37,stop=90+37+10,
                     sync_timestamp=1,read_shift=59):
        # start_freeze=50,start_read=52,stop_read=52+2,stop_freeze=52+36,stop=52+36+10
        th=self.dut.SET_VALUE["TH"]
        self.dut["TH"].set_voltage(1.5,unit="V")
        self.dut.SET_VALUE["TH"]=1.5
        ## reaset readout module of FPGA
        self.dut['data_rx'].reset()
        self.dut['data_rx'].READ_SHIFT = read_shift
        self.dut['data_rx'].CONF_START_FREEZE = start_freeze
        self.dut['data_rx'].CONF_START_READ = start_read
        self.dut['data_rx'].CONF_STOP_FREEZE = stop_freeze
        self.dut['data_rx'].CONF_STOP_READ = stop_read
        self.dut['data_rx'].CONF_STOP = stop
        
        ## set switches
        self.dut['CONF']['EN_GRAY_RESET_WITH_TIMESTAMP'] = sync_timestamp
        self.dut['CONF']['RESET_GRAY'] = 1
        self.dut['CONF']['RESET'] = 1
        self.dut['CONF']['EN_DATA_CMOS'] = 0
        self.dut['CONF']['EN_TEST_PATTERN'] = 0
        self.dut['CONF']['EN_OUT_CLK'] = 1
        self.dut['CONF']['EN_BX_CLK'] = 1
        self.dut['CONF']['EN_DRIVER'] = 1
        self.dut['CONF'].write()
        ## reset readout of the chip
        self.dut['CONF']['RESET_GRAY'] = 1
        self.dut['CONF']['RESET'] = 1
        self.dut['CONF'].write()
        time.sleep(0.001)
        self.dut['CONF']['RESET'] = 0
        self.dut['CONF'].write()
        time.sleep(0.001)
        self.dut['CONF']['RESET_GRAY'] = 0
        self.dut['CONF'].write()
        # set th low, reset fifo, set rx on,wait for th, reset fifo to delete trash data
        self.dut["TH"].set_voltage(th,unit="V")
        self.dut.SET_VALUE["TH"]=th
        self.dut['fifo'].reset()
        self.dut['data_rx'].set_en(True) ##readout trash data from chip
        time.sleep(0.3)
        self.logger.info('set_monoread: start_freeze=%d start_read=%d stop_read=%d stop_freeze=%d stop=%d reset fifo=%d'%(
                     start_freeze,start_read,stop_read,stop_freeze,stop, self.dut['fifo'].get_FIFO_SIZE()))
        self.dut['fifo'].reset() ## discard trash
    
    def stop_monoread(self):
        self.dut['data_rx'].set_en(False)
        lost_cnt=self.dut["data_rx"]["LOST_COUNT"]
        if lost_cnt!=0:
            self.logger.warn("stop_monoread: error cnt=%d"%lost_cnt)
        #exp=self.dut["data_rx"]["EXPOSURE_TIME"]
        self.logger.info("stop_monoread:lost_cnt=%d"%lost_cnt)
        self.dut['CONF']['RESET_GRAY'] = 1
        self.dut['CONF']['RESET'] = 1
        self.dut['CONF']['EN_DATA_CMOS'] = 0
        self.dut['CONF']['EN_TEST_PATTERN'] = 0
        self.dut['CONF']['EN_OUT_CLK'] = 0
        self.dut['CONF']['EN_BX_CLK'] = 0
        self.dut['CONF']['EN_DRIVER'] = 0
        self.dut['CONF'].write()
        return lost_cnt
    def set_tlu(self,tlu_delay=8,ts=True):
        self.dut["tlu"]["RESET"]=1
        self.dut["tlu"]["TRIGGER_MODE"]=3
        self.dut["tlu"]["EN_TLU_VETO"]=0
        self.dut["tlu"]["MAX_TRIGGERS"]=0
        self.dut["tlu"]["TRIGGER_COUNTER"]=0
        self.dut["tlu"]["TRIGGER_LOW_TIMEOUT"]=0
        self.dut["tlu"]["TRIGGER_VETO_SELECT"]=0
        self.dut["tlu"]["TRIGGER_THRESHOLD"]=0
        self.dut["tlu"]["DATA_FORMAT"]=2
        self.dut["tlu"]["TRIGGER_HANDSHAKE_ACCEPT_WAIT_CYCLES"]=20
        self.dut["tlu"]["TRIGGER_DATA_DELAY"]=tlu_delay
        self.dut["tlu"]["TRIGGER_SELECT"]=0
        self.logger.info("set_tlu: tlu_delay=%d"%tlu_delay)
        self.dut["tlu"]["TRIGGER_ENABLE"]=1    
        
    def stop_tlu(self):
        self.dut["tlu"]["TRIGGER_ENABLE"]=0
        
    def set_timestamp640(self,src="tlu"):
       self.dut["timestamp_%s"%src].reset()
       self.dut["timestamp_%s"%src]["EXT_TIMESTAMP"]=True
       if src=="tlu":
            self.dut["timestamp_tlu"]["INVERT"]=0
            self.dut["timestamp_tlu"]["ENABLE_TRAILING"]=0
            self.dut["timestamp_tlu"]["ENABLE"]=0
            self.dut["timestamp_tlu"]["ENABLE_EXTERN"]=1
       elif src=="inj":
            self.dut["timestamp_inj"]["ENABLE_EXTERN"]=0 ##although this is connected to gate
            self.dut["timestamp_inj"]["INVERT"]=0
            self.dut["timestamp_inj"]["ENABLE_TRAILING"]=0
            self.dut["timestamp_inj"]["ENABLE"]=1
       elif src=="rx1":
            self.dut["timestamp_tlu"]["INVERT"]=0
            self.dut["timestamp_inj"]["ENABLE_EXTERN"]=0 ## connected to 1'b1
            self.dut["timestamp_inj"]["ENABLE_TRAILING"]=0
            self.dut["timestamp_inj"]["ENABLE"]=1
       else: #"mon"
            self.dut["timestamp_mon"]["INVERT"]=1
            self.dut["timestamp_mon"]["ENABLE_TRAILING"]=1
            self.dut["timestamp_mon"]["ENABLE_EXTERN"]=0
            self.dut["timestamp_mon"]["ENABLE"]=1
       self.logger.info("set_timestamp640:src=%s"%src)
        
    def stop_timestamp640(self,src="tlu"):
        self.dut["timestamp_%s"%src]["ENABLE_EXTERN"]=0
        self.dut["timestamp_%s"%src]["ENABLE"]=0
        lost_cnt=self.dut["timestamp_%s"%src]["LOST_COUNT"]
        self.logger.info("stop_timestamp640:src=%s lost_cnt=%d"%(src,lost_cnt))
        
    def stop_all_data(self):
        self.stop_tlu()
        self.stop_monoread()
        self.stop_timestamp640("tlu")
        self.stop_timestamp640("inj")
        self.stop_timestamp640("rx1")
        self.stop_timestamp640("mon")

#### load and save config
    def save_config(self,fname=None):
        if fname==None:
            fname=mk_fname(ext="config.yaml")
        conf=self.dut.get_configuration()
        conf.update(self.power_status())
        conf.update(self.dac_status())
        for k in self.dut.PIXEL_CONF.keys():
            conf["pix_"+k]=np.array(self.dut.PIXEL_CONF[k],int).tolist()
        #for k in ["ColRO_En","MON_EN","INJ_EN","BUFFER_EN","REGULATOR_EN"]:
        #    conf[k]=self.dut["CONF_SR"][k].to01()
        with open(fname,"w") as f:
            yaml.dump(conf,f)
        self.logger.info("save_config: %s"%fname)
          
    def load_config(self,fname):
        if fname[-4:] ==".npy":
            with open(fname,"rb") as f:
                while True:
                    try:
                        ret=np.load(f).all()
                    except:
                        break
            self.set_preamp_en(ret["pixlist"])
            self.set_th(ret["th"])
            self.set_tdac(ret["tdac"])
            self.set_global(LSBdacL=ret["LSBdacL"])
        if fname[-3:] ==".h5":
            with tables.open_file(fname) as f:
                    ret=yaml.load(f.root.meta_data.attrs.power_status)
                    power={}
                    for k in ['VDDA', 'VDDD', 'VDD_BCID_BUFF', 'VPC']:
                            power[k]=ret[k+"set"]
                    for k in  ['BL', 'TH', 'VCascC', 'VCascN',"INJ_HI","INJ_LO","PBias","NTC"]:
                            power[k]=ret[k+"set"]
                    self.power_up(**power)
                    dac=yaml.load(f.root.meta_data.attrs.dac_status)
                    self.set_global(**dac)
                    ret=yaml.load(f.root.meta_data.attrs.firmware)
                    tmp=yaml.load(f.root.meta_data.attrs.pixel_conf)
            self.set_mon_en(np.array(tmp["MONITOR_EN"],int).tolist())
            self.set_inj_en(np.array(tmp["INJECT_EN"],int).tolist())
            self.set_tdac(np.array(tmp["TRIM_EN"],int).tolist())
            self.set_preamp_en(np.array(tmp["PREAMP_EN"],int).tolist(),
                               ColRO_En=ret["CONF_SR"]["ColRO_En"][:])
            for module in ["inj","gate_tdc","tlu","timestamp_inj","timestamp_tlu","timestamp_mon","data_rx"]:
                        s="load_config: %s "%module
                        for reg in ret[module]:
                            self.dut[module][reg]=ret[module][reg]
                            s=s+" %s=%d"%(reg,ret[module][reg])
                        self.logger.info(s)
            return tmp
        else:
            with open(fname) as f:
                    ret=yaml.load(f)
                    ret["CONF_SR"]["ColRO_En"]=ret["CONF_SR"]["ColRO_En"][:] ##TODO check
            dac={}
            for k in ['BLRes', 'VAmp', 'VPFB', 'VPFoll', 'VPLoad', 'IComp', 'Vbias_CS', 'IBOTA', 'ILVDS', 'Vfs', 'LSBdacL', 'Vsf_dis1', 'Vsf_dis2','Vsf_dis3']:
                    dac[k]=ret[k]
            self.set_global(**dac)
            
            power={}
            for k in ['VDDA', 'VDDD', 'VDD_BCID_BUFF', 'VPC']:
                    power[k]=ret[k+"set"]
            for k in  ['BL', 'TH', 'VCascC', 'VCascN',"INJ_HI","INJ_LO","PBias","NTC"]:
                    power[k]=ret[k+"set"]
            self.power_up(**power)     
            self.set_mon_en(ret["pix_MONITOR_EN"])
            self.set_preamp_en(ret["pix_PREAMP_EN"],ColRO_En=ret["CONF_SR"]["ColRO_En"][:])
            self.set_inj_en(ret["pix_INJECT_EN"])
            self.set_tdac(ret["pix_TRIM_EN"])
            self.logger.info("===================loading===========================")
            for module in ["inj","gate_tdc","tlu","timestamp_inj","timestamp_tlu","timestamp_mon","data_rx"]:
                s="load_config: %s "%module
                for reg in ret[module]:
                    self.dut[module][reg]=ret[module][reg]
                    s=s+" %s=%d"%(reg,ret[module][reg])
                self.logger.info(s)
            ## TODO check Col_RO_En etc
        return ret
        
    def show(self,all="all"): ##TODO !!
        if all=="pix":
            ret=self.pix_status()
            s=format_pix(ret)
            self.logger.info(s)
        if all=="all" or all=="tdac":
            pass
        if all=="all" or all=="preamp":
            pass
        if all=="all" or all=="inj":
            pass
        if all=="all" or all=="mon":
            pass
        if all=="all" or all=="power":
            ret=self.power_status()
            s=format_power(ret)
            self.logger.info(s)
        if all=="all" or all=="dac":
            ret=self.dac_status()
            s=format_dac(ret)
            self.logger.info(s)

class MonopixMio(Monopix):
    default_yaml=os.path.dirname(os.path.abspath(__file__)) + os.sep + "monopix.yaml"
    def set_inj_all(self,inj_high=0.5,inj_low=0.1,inj_n=100,inj_width=5000,delay=700,ext=False,inj_phase=None):
        if inj_phase!=None and inj_phase!=0:
            self.logger.error("injection phase cannot be changed with MIO")
            return
        self.set_inj_high(inj_high)
        self.set_inj_low(inj_low)

        self.dut["inj"].reset()
        self.dut["inj"]["REPEAT"]=inj_n
        self.dut["inj"]["DELAY"]=inj_width
        self.dut["inj"]["WIDTH"]=inj_width
        self.dut["inj"]["EN"]=0
        
        if self.dut["inj"].get_phase()!=inj_phase:
            self.logger.error("inj:set_inj_phase=%d PHASE_DES=%x"%(inj_phase,self.dut["inj"]["PHASE_DES"]))

        self.logger.info("inj:%.4f,%.4f inj_width:%d inj_phase:%x inj_n:%d delay:%d ext:%d"%(
            inj_high,inj_low,inj_width,
            self.dut["inj"]["PHASE_DES"],
            self.dut["inj"]["REPEAT"],delay,
            int(ext)))