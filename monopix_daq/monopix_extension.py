import sys,time,os
import numpy as np
import matplotlib.pyplot as plt
import logging
import warnings
import yaml
import monopix
import tables

COL_SIZE = 36 ##TODO change hard coded values
ROW_SIZE = 129
OUTPUT_DIR=os.path.join(os.path.dirname(os.path.abspath(__file__)),"output_data")

## TODO separated file
def format_power(dat):
    s="power:"
    for pwr in ['VDDA', 'VDDD', 'VDD_BCID_BUFF', 'VPC']:
        s=s+" %s=%fV(%fmA)"%(pwr,dat[pwr+'[V]'] ,dat[pwr+'[mA]']) 
    return s
def format_dac(dat):
    s="DAC:"
    return s
def format_pix(dat):
    s="Pixels:"
    return s
    
def mk_fname(prefix,ext="npy",dirname=None):
    if dirname==None:
        dirname=os.path.join(OUTPUT_DIR,prefix)
    if not os.path.exists(dirname):
        os.system("mkdir -p %s"%dirname)
    return os.path.join(dirname,prefix+time.strftime("_%Y%m%d_%H%M%S.")+ext)
    
class MonopixExtensions():
    def __init__(self,dut=None):
        ## set logger
        self.logger = logging.getLogger()
        logFormatter = logging.Formatter("%(asctime)s [%(levelname)-5.5s] (%(threadName)-10s) %(message)s")
        fname=mk_fname("log",ext="log")
        fileHandler = logging.FileHandler(fname)
        fileHandler.setFormatter(logFormatter) 
        self.logger.addHandler(fileHandler)
        ##TODO different fmt for stdout and file, change time format
        
        self.debug=0
        self.plot=1
        self.inj_device="gpac"

        if isinstance(dut,str):
            self.dut=monopix.monopix(dut)
            self.dut.init()
        elif dut==None:
            self.dut=monopix.monopix()
            self.dut.init()
        elif isinstance(dut,monopix.monopix):
            self.dut=dut

        self.dut.power_up()

        status=self.dut.power_status()
        s=format_power(status)
        self.logger.info(s)
        self.dut.write_global_conf()
        self.set_preamp_en("all")
        self.set_inj_en([18,25])
        self.set_mon_en([18,25])
        self.set_tdac(0)
        
        self.set_inj_all()
    
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
            self.dut['CONF_SR']['ColRO_En'].setall(True)
        elif ":" in ColRO_En:
            cols=np.zeros(COL_SIZE,int)
            tmp=ColRO_En.split(":")
            cols[int(tmp[0]):int(tmp[1])]=1
            for i in range(36):
                self.dut['CONF_SR']['ColRO_En'][35-i] = bool(cols[i])
        elif len(ColRO_En)==36:
            self.dut['CONF_SR']['ColRO_En'] = ColRO_En

        self.dut['CONF_SR']["PREAMP_EN"] = 1 
        self.dut._write_pixel_mask(self.dut.PIXEL_CONF["PREAMP_EN"])
        self.dut['CONF_SR']["PREAMP_EN"] = 0
        
        self.dut.write_global_conf()
        self.logger.info("set_preamp_en pix=%s ColRO_En=%s"%(
                        str(pix).replace("\n"," "),str(self.dut['CONF_SR']['ColRO_En'])))

    def set_mon_en(self,pix="none"):
        pixlist=self._cal_pix("MONITOR_EN",pix)
        self.dut["CONF_SR"]["BUFFER_EN"] = bool(np.any(self.dut.PIXEL_CONF["MONITOR_EN"][:,:]))
        self.dut['CONF_SR']['MON_EN'].setall(False)
        for i in range(36):
            self.dut['CONF_SR']['MON_EN'][35-i] = bool(np.any(self.dut.PIXEL_CONF["MONITOR_EN"][i,:]))
        self.dut['CONF_SR']["MONITOR_EN"] = 1 
        self.dut._write_pixel_mask(self.dut.PIXEL_CONF["MONITOR_EN"])
        self.dut['CONF_SR']["MONITOR_EN"] = 0

        self.dut.write_global_conf()
      
        self.logger.info("set_mon_en pix: %s"%str(pix).replace("\n"," "))

    def set_inj_en(self,pix="none"):
        pixlist=self._cal_pix("INJECT_EN",pix)
        self.dut['CONF_SR']['INJ_EN'].setall(False)
        for i in range(18):
            self.dut['CONF_SR']['INJ_EN'][17-i] = bool(np.any(self.dut.PIXEL_CONF["INJECT_EN"][2*i:2*(i+1),:]))
        self.dut['CONF_SR']["INJECT_EN"] = 1
        self.dut._write_pixel_mask(self.dut.PIXEL_CONF["INJECT_EN"])
        self.dut['CONF_SR']["INJECT_EN"] = 0
        
        self.dut.write_global_conf()

        self.logger.info("set_inj_en pix: %s"%str(pix).replace("\n"," "))
        
    def set_tdac(self,tdac):
        if isinstance(tdac,int):
            self.dut.PIXEL_CONF["TRIM_EN"][:,:]=tdac
        elif len(tdac)==len(self.dut.PIXEL_CONF["TRIM_EN"]) and \
             len(tdac[0])== len(self.dut.PIXEL_CONF["TRIM_EN"][0]):
            self.dut.PIXEL_CONF["TRIM_EN"]=np.array(tdac,dtype = np.uint8)
        else:
            self.logger.info("ERROR: wrong instance. tdac must be int or [36,129]")
            return 

        trim_bits = np.unpackbits(self.dut.PIXEL_CONF['TRIM_EN'])
        trim_bits_array = np.reshape(trim_bits, (36,129,8)).astype(np.bool)
        for bit in range(4):
            trim_bits_sel_mask = trim_bits_array[:,:,7-bit]
            self.dut['CONF_SR']['TRIM_EN'][bit] = 1
            self.dut._write_pixel_mask(trim_bits_sel_mask)
            self.dut['CONF_SR']['TRIM_EN'][bit] = 0
        
        self.dut.write_global_conf()
        if isinstance(tdac,int):
            self.logger.info("set_tdac_en pix: %s"%str(tdac)) #TODO reduce printing

    def set_tlu(self,tlu_delay=8):
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
        self.logger.info("stop_tlu:") 
        
    def set_timestamp(self,src="rx1"):
        if src=="gate":
            self.dut['CONF']['EN_GATE_TIMESTAMP'] = 1
            self.dut['CONF']['EN_DEBUG_TIMESTAMP'] = 0
        elif src=="inj":
            self.dut['CONF']['EN_GATE_TIMESTAMP'] = 1
            self.dut['CONF']['EN_DEBUG_TIMESTAMP'] = 1
        elif src=="token":
            self.dut['CONF']['EN_GATE_TIMESTAMP'] = 0
            self.dut['CONF']['EN_DEBUG_TIMESTAMP'] = 1
        else: #"rx1'
            self.dut['CONF']['EN_GATE_TIMESTAMP'] = 0
            self.dut['CONF']['EN_DEBUG_TIMESTAMP'] = 0
        self.dut['CONF'].write()
        self.dut["timestamp"].reset()
        self.dut["timestamp"]["EXT_TIMESTAMP"]=True
        self.dut["timestamp"]["ENABLE"]=1
        self.logger.info("set_timestamp:src=%s"%src)
        
    def stop_timestamp(self):
        self.dut["timestamp"]["ENABLE"]=0
        lost_cnt=self.dut["timestamp"]["LOST_COUNT"]
        if lost_cnt!=0:
            self.logger.warn("stop_timestamp: lost_cnt=%d"%lost_cnt)
        return lost_cnt
        
    def reset_monoread(self,wait=0.001):
        self.dut['CONF']['RESET_GRAY'] = 1
        self.dut['CONF']['RESET'] = 1
        self.dut['CONF'].write()
        time.sleep(0.001)
        self.dut['CONF']['RESET'] = 0
        self.dut['CONF'].write()
        time.sleep(0.001)
        self.dut['CONF']['RESET_GRAY'] = 0
        self.dut['CONF'].write()
        
    def set_monoread(self,start_freeze=50,start_read=55,stop_read=55+2,stop_freeze=55+38,stop=55+38+10,
                    gray_reset_by_tdc=0):
        # start_freeze=50,start_read=52,stop_read=52+2,stop_freeze=52+36,stop=52+36+10
        # start_freeze=50,start_read=60,stop_read=61,stop_freeze=120,stop=130
        # start_freeze=88,start_read=92,stop_read=94,stop_freeze=127,stop=128,
        # start_freeze=3,start_read=6,stop_read=7,stop_freeze=45,stop=46
        th=self.dut.SET_VALUE["TH"]
        self.dut["TH"].set_voltage(1.5,unit="V")
        self.dut.SET_VALUE["TH"]=1.5
        ## reaset readout module of FPGA
        self.dut['data_rx'].reset()  
        self.dut['data_rx'].CONF_START_FREEZE = start_freeze
        self.dut['data_rx'].CONF_START_READ = start_read
        self.dut['data_rx'].CONF_STOP_FREEZE = stop_freeze
        self.dut['data_rx'].CONF_STOP_READ = stop_read
        self.dut['data_rx'].CONF_STOP = stop
        
        ## set switches
        self.dut['CONF']['EN_GRAY_RESET_WITH_TDC_PULSE'] = gray_reset_by_tdc ## TODO for what?
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
        exp=self.dut["data_rx"]["EXPOSURE_TIME"]
        self.logger.info("stop_monoread:%d"%exp)
        self.dut['CONF']['RESET_GRAY'] = 1
        self.dut['CONF']['RESET'] = 1
        self.dut['CONF']['EN_DATA_CMOS'] = 0
        self.dut['CONF']['EN_TEST_PATTERN'] = 0
        self.dut['CONF']['EN_OUT_CLK'] = 0
        self.dut['CONF']['EN_BX_CLK'] = 0
        self.dut['CONF']['EN_DRIVER'] = 0
        self.dut['CONF'].write()
        return lost_cnt
        
    def set_inj_all(self,inj_high=1.0,inj_low=0.2,inj_n=100,inj_width=5000,delay=700,ext=False):
        self.set_inj_high(inj_high)
        self.set_inj_low(inj_low)

        self.dut["inj"].reset()
        self.dut["inj"]["REPEAT"]=inj_n
        self.dut["inj"]["DELAY"]=inj_width
        self.dut["inj"]["WIDTH"]=inj_width
        self.dut["inj"]["EN"]=1
        
        self.dut["gate_tdc"].reset()
        self.dut["gate_tdc"]["REPEAT"]=1
        self.dut["gate_tdc"]["DELAY"]=delay
        self.dut["gate_tdc"]["WIDTH"]=inj_n*inj_width*2+10
        self.dut["gate_tdc"]["EN"]=ext
        self.logger.info("inj:%.4f,%.4f inj_width:%d inj_n:%d delay:%d ext:%d"%(
            inj_high,inj_low,inj_width,inj_n,delay,int(ext)))
            
    def start_inj(self,inj_high=None):
        if inj_high!=None:
            self.set_inj_high(inj_high)
        self.dut["inj"].start()
        self.logger.info("start_inj:%.4f,%.4f"%(self.dut.SET_VALUE["INJ_HI"],self.dut.SET_VALUE["INJ_LO"]))
            
    def set_th(self,th):
        self.dut['TH'].set_voltage(th, unit='V')
        self.dut.SET_VALUE["TH"]=th
        th_meas=self.dut['TH'].get_voltage(unit='V')
        self.logger.info("set_th: TH=%f th_meas=%f"%(th,th_meas)) 
        
    def get_th(self):
        th_meas=self.dut['TH'].get_voltage(unit='V')
        self.logger.info("get_th:th_set=%f th_meas=%f"%(self.dut.SET_VALUE["TH"],th_meas))
        return th_meas
        
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
 
    def set_global(self,**kwarg):
        for k in kwarg.keys():
            self.dut["CONF_SR"][k]=kwarg[k]
        self.dut.write_global_conf()
        s="set_global:"
        for k in kwarg.keys():
            s=s+"%s=%d "%(k,kwarg[k])
        self.logger.info(s)
                    
    def save_config(self,fname=None):
        if fname==None:
            fname=mk_fname("config",ext="yaml")
        conf=self.dut.power_status()
        conf.update(self.dut.dac_status())
        for k in self.dut.PIXEL_CONF.keys():
            conf["pix_"+k]=np.array(self.dut.PIXEL_CONF[k],int).tolist()
        for k in ["ColRO_En","MON_EN","INJ_EN","BUFFER_EN","REGULATOR_EN"]:
            conf[k]=self.dut["CONF_SR"][k].to01()
        with open(fname,"w") as f:
            yaml.dump(conf,f)
        self.logger.info("save_config: %s"%fname)
        
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

    def save_config(self,fname=None):
        if fname==None:
            fname=mk_fname("config",ext="yaml")
        conf=self.dut.power_status()
        conf.update(self.dut.dac_status())
        conf.update(self.dut.SET_VALUE)
        for k in self.dut.PIXEL_CONF.keys():
            conf["pix_"+k]=np.array(self.dut.PIXEL_CONF[k],int).tolist()
        for k in ["ColRO_En","MON_EN","INJ_EN","BUFFER_EN","REGULATOR_EN"]:
            conf[k]=self.dut["CONF_SR"][k].to01()
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
        else:
            if fname[-3:] ==".h5":
                with tables.open_file(fname) as f:
                    ret=yaml.load(f.root.meta_data.attrs.dac_status)
                    ret.update(yaml.load(f.root.meta_data.attrs.power_status))
                    ret.update(yaml.load(f.root.meta_data.attrs.pixel_conf))
            else:
                with open(fname) as f:
                    ret=yaml.load(f)
            dac={}
            for k in ['BLRes', 'VAmp', 'VPFB', 'VPFoll', 'VPLoad', 'IComp', 'Vbias_CS', 'IBOTA', 'ILVDS', 'Vfs', 'LSBdacL', 'Vsf_dis1', 'Vsf_dis2','Vsf_dis3']:
                    dac[k]=ret[k]
            power={}
            for k in ['VDDA', 'VDDD', 'VDD_BCID_BUFF', 'VPC']:
                    power[k]=ret[k+"[V]"]
            for k in  ['BL', 'TH', 'VCascC', 'VCascN']:
                    power[k]=ret[k]

            self.set_global(**dac)
            self.set_power(**power)
            self.set_mon_en(ret["pix_MONITOR_EN"])
            self.set_preamp_en(ret["pix_PREAMP_EN"],ColRO_En=ret["ColRO_En"])
            self.set_inj_en(ret["pix_INJECT_EN"])
            self.set_tdac(ret["pix_TRIM_EN"])
            ## TODO check Col_RO_En etc
        return ret
        
    def set_power(self,**kwarg):
        for k in kwarg.keys():
            self.dut[k].set_voltage(kwarg[k])
            self.dut.SET_VALUE[k]=kwarg[k]
        s="set_power:"
        for k in kwarg.keys():
            s=s+"%s=%d "%(k,kwarg[k])
        self.logger.info(s)
        
    def get_temperature(self):
        vol=self.dut["NTC"].get_voltage()
        if not (vol>0.5 and vol<1.5):
          for i in np.arange(-2,-200,-2):
            self.dut["NTC"].set_current(i,unit="uA")
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
    
    def get_tdac_memory(self):
        return np.copy(self.dut.PIXEL_CONF["TRIM_EN"])

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
            ret=self.dut.power_status()
            s=format_power(ret)
            self.logger.info(s)
        if all=="all" or all=="dac":
            ret=self.dut.dac_status()
            s=format_dac(ret)
            self.logger.info(s)

    def pix_status(self):
        for k in ["ColRO_En","MON_EN","INJ_EN","BUFFER_EN","REGULATOR_EN","Pixels"]:
            ret[k]=self.dut["CONF_SR"]["INJ_EN"].to01()
        return ret
