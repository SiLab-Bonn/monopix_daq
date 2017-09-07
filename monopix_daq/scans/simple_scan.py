import os,sys,time

import numpy as np
import bitarray
import tables as tb
import logging
import yaml

from monopix_daq.scan_base import ScanBase
from monopix_daq.analysis.interpreter import interpret_h5

local_configuration={"with_tlu": True,
                     "with_timestamp": True,
                     "scan_time": 30, ## in second
                     "tlu_delay": 8,
}

class SimpleScan(ScanBase):
    scan_id = "simple_scan"
    
    def __init__(self, dut_extentions, fname=None, sender_addr=""):
        logging.info('Initializing %s', self.__class__.__name__)
        
        self.dut = dut_extentions.dut
        self.dut_extensions=dut_extentions
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
        with_tlu = kwargs.pop('with_tlu', True)
        with_timestamp = kwargs.pop('with_timestamp', True)
        scan_time = kwargs.pop('scan_time', 10)
        
        with self.readout(scan_param_id = 0, fill_buffer=False, clear_buffer=True,timeout=scan_time,readout_interval = 0.003):
            t0=time.time()
            ####################
            ## start readout
            if with_tlu:
                tlu_delay = kwargs.pop('tlu_delay', 8)
                self.dut_extensions.set_tlu(tlu_delay)
            if with_timestamp:
                self.dut_extensions.set_timestamp()
            ## start_freeze=50,start_read=52,stop_read=52+2,stop_freeze=52+36,stop=52+36+10,
            start_freeze = kwargs.pop('start_freeze', 50)
            start_read = kwargs.pop('start_read', start_freeze+2)
            stop_read = kwargs.pop('stop_read', start_read+2)
            stop_freeze = kwargs.pop('stop_freeze', start_freeze+36)
            stop = kwargs.pop('stop', stop_freeze+10)
            self.dut_extensions.set_monoread(start_freeze=start_freeze,start_read=start_read,
                                             stop_read=stop_read,stop_freeze=stop_freeze,stop=stop)
            ####################                    
            ## start
            self.logger.info("*****%s is running **** don't forget to start tlu ****"%self.__class__.__name__)
            while True:
                cnt=self.fifo_readout.get_record_count()
                #dqdata = self.fifo_readout.data
                #try:
                #    data = np.concatenate([item[0] for item in dqdata])
                #except ValueError:
                #    data = []
                #cnt=len(data)
                scanned=time.time()-t0
                self.logger.info('time=%.0fs dat=%d rate=%.3fk/s'%(scanned,cnt,cnt/scanned/1024))
                if scanned > scan_time and scan_time>0:
                    break
                else:
                    time.sleep(5)
                    
        ####################
        ## stop readout
        self.dut_extensions.stop_monoread()
        if with_timestamp:
            self.dut_extensions.stop_timestamp()
            self.meta_data_table.attrs.timestamp_status = yaml.dump(self.dut["timestamp"].get_configuration())
        if with_tlu:
            self.dut_extensions.stop_tlu()
            self.meta_data_table.attrs.tlu_status = yaml.dump(self.dut["tlu"].get_configuration())

    def analyze(self, h5_fin  = ''):
        if h5_fin == '':
           h5_fin = self.output_filename +'.h5'
        h5_fout=h5_fin[:-7]+'hit.h5'
        interpret_h5(h5_fin,h5_fout,debug=8+3)
        self.logger.info('interpreted file %s'%(h5_fout))
        
        #np_fout=h5_fin[:-7]+'hit.npy'
        #monopix_interpreter.mk_plot(h5_fout,np_fout)
    
if __name__ == "__main__":
    from monopix_daq import monopix_extension
    m=monopix_extension.MonopixExtensions()

    #fname=time.strftime("%Y%m%d_%H%M%S_simple_scan")
    #fname=(os.path.join(monopix_extra_functions.OUPUT_DIR,"simple_scan"),fname)
    
    scan = SimpleScan(m,fname=fname,sender_addr="tcp://127.0.0.1:5500")
    scan.start(**local_configuration)
    scan.analyze()
