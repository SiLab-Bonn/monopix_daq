import os,sys,time

import numpy as np
import bitarray
import tables as tb
import logging
import yaml

sys.path.append("/home/user/workspace/monopix/monopix_thinn")
import monopix_daq.scan_base as scan_base
import monopix_daq.analysis.interpreter as interpreter

local_configuration={"injlist":np.arange(0.1,1.9,0.005),
                     "thlist": None, #[b,e,s]=[1.5,0.5,0.05],
                     "pix":[18.25]
}
class ScanParam(tb.IsDescription):
    scan_param_id = tb.UInt32Col(pos=0)
    col = tb.UInt32Col(pos=1)
    row = tb.UInt32Col(pos=2)

class TWScan(scan_base.ScanBase):
    scan_id = "tw_scan"
    
    def __init__(self, dut_extentions, fname=None, sender_addr=""):
        logging.info('Initializing %s', self.__class__.__name__)
        
        self.dut = dut_extentions.dut
        self.dut_extensions = dut_extentions
        self.socket=sender_addr
        
        if fname==None:
            self.working_dir = os.path.join(os.getcwd(),"output_data")
            self.run_name = time.strftime("%Y%m%d_%H%M%S_") + self.scan_id
        else:
            self.working_dir = os.path.dirname(os.path.realpath(fname))
            self.run_name = os.path.basename(os.path.realpath(fname))
        if not os.path.exists(self.working_dir):
                os.makedirs(self.working_dir)
        self.output_filename = os.path.join(self.working_dir, self.run_name)
        
        self.logger = logging.getLogger()
        flg=0
        for l in self.logger.handlers:
            if isinstance(l, logging.FileHandler):
               flg=1
        if flg==0:
            fh = logging.FileHandler(self.output_filename + '.log')
            fh.setFormatter(logging.Formatter("%(asctime)s [%(levelname)-5.5s] %(message)s"))
            fh.setLevel(logging.WARNING)
            self.logger.addHandler(fh)
            
        self.filter_raw_data = tb.Filters(complib='blosc', complevel=5, fletcher32=False)
        self.filter_tables = tb.Filters(complib='zlib', complevel=5, fletcher32=False)
            
    def scan(self,**kwargs): 
        ####################
        ## get scan params from args
        pix = kwargs.pop('pix', [18.25])
        if isinstance(pix[0],int):
            pix=[pix]
        injlist= kwargs.pop('injlist', np.arange(0.1,1.9,0.005))
        if injlist is None or len(injlist)==0:
            injlist=[self.dut.SET_VALUE["INJ_HI"]]
        thlist = kwargs.pop('thlist', None)
        if thlist is None or len(thlist)==0:
            thlist=[self.dut.SET_VALUE["TH"]]
        inj_th=np.reshape(np.stack(np.meshgrid(injlist,thlist),axis=2),[-1,2])
        ####################
        ## save scan params
        self.scan_param_table = self.h5_file.create_table(self.h5_file.root, 
                      name='scan_parameters', title='scan_parameters',
                      description=ScanParam, filters=self.filter_tables)
        self.meta_data_table.attrs.inj_th = yaml.dump(inj_th)
        
        t0=time.time()
        for i,p in enumerate(pix):
            self.dut_extensions.set_preamp_en(p)
            self.dut_extensions.set_inj_en(p)
            self.dut_extensions.set_mon_en(p)

            ####################
            ## start readout
            self.dut_extensions.set_monoread()
            self.dut_extensions.set_timestamp640("inj")
            self.dut_extensions.set_timestamp640("mon")
            
            self.scan_param_table.row['scan_param_id'] = i
            self.scan_param_table.row['col'] = p[0]
            self.scan_param_table.row['row'] = p[1]
            self.scan_param_table.row.append()
            self.scan_param_table.flush()

            ####################
            ## start read fifo 
            cnt=0     
            with self.readout(scan_param_id=i,fill_buffer=False,clear_buffer=True,readout_interval=0.005):
                for inj,th in inj_th:
                    if th!=self.dut.SET_VALUE["TH"]:
                        self.dut["TH"].set_voltage(th,unit="V")
                        self.dut.SET_VALUE["TH"]=th
                    if inj!=self.dut.SET_VALUE["INJ_HI"]:
                        self.dut["INJ_HI"].set_voltage(inj,unit="V")
                        self.dut.SET_VALUE["INJ_HI"]=inj                       
                    pre_cnt=cnt
                    cnt=self.fifo_readout.get_record_count()
                    self.dut["inj"].start()
                    while self.dut["inj"].is_done()!=1:
                        time.sleep(0.001)
                    self.logger.info('pix=[%d,%d] inj=%.3f th=%.4f dat=%d'%(p[0],p[1],inj,th,cnt-pre_cnt))    
                    #self.dut_extensions.start_inj(inj_high=inj,wait=True)
                       
                ####################
                ## stop readout
                self.dut_extensions.stop_timestamp640("inj")
                self.dut_extensions.stop_timestamp640("mon")
                #self.meta_data_table.attrs.timestamp_status = yaml.dump(self.dut["timestamp"].get_configuration())
                self.dut_extensions.stop_monoread()
            self.logger.info('pix=[%d,%d] dat=%d'%(p[0],p[1],cnt-pre_cnt)) 


    def analyze(self, h5_fin='',debug=3):
        if h5_fin == '':
           h5_fin = self.output_filename +'.h5'

        fhit=h5_fin[:-7]+'hit.h5'
        fsid=h5_fin[:-7]+'sid.h5'
        fout=h5_fin[:-7]+'ts.h5'
        interpreter.interpret_h5(h5_fin,fhit,debug=0x3)
        assign_scan_id.assign_scan(fhit,h5_fin,fsid)
        ### assign_ts(fsid,fraw,fout)
        self.logger.info('interpreted file %s'%(fout))

    
if __name__ == "__main__":
    from monopix_daq import monopix_extensions
    m=monopix_extensions.MonopixExtentions()
    
    #fname=time.strftime("%Y%m%d_%H%M%S_simples_can")
    #fname=(os.path.join(monopix_extra_functions.OUPUT_DIR,"simple_scan"),fname)
    
    scan = TWScan(m,fname=fname,sender_addr="tcp://127.0.0.1:6500")
    scan.start(**local_configuration)
    scan.analyze()
