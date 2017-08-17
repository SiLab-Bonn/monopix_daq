import os,sys,time

import numpy as np
import bitarray
import tables as tb
import logging

from monopix_daq.scan_base import ScanBase
from monopix_daq.analysis.interpreter import interpret_h5

local_configuration={"with_tlu": True,
                     "with_timestamp": True,
                     "scan_time": 10, ## in second
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
        with_tlu = kwargs.pop('with_tlu', False)
        with_timestamp = kwargs.pop('with_timestamp', False)
        scan_time = kwargs.pop('scan_time', 10)
        
        with self.readout(scan_param_id = 0, fill_buffer=True, clear_buffer=True,timeout=scan_time,readout_interval = 0.003):
            t0=time.time()
            if with_tlu:
                tlu_delay = kwargs.pop('tlu_delay', 8)
                self.dut_extensions.set_tlu(tlu_delay)
            if with_timestamp:
                self.dut_extensions.set_timestamp()
            ## start
            self.dut_extensions.set_monoread()
            ##self.logger.info("*****%s is running **** don't forget to start tlu ****"%self.__class__.__name__)
            while True:
                cnt=self.fifo_readout.get_record_count()
                scanned=time.time()-t0
                self.logger.info('time=%.0fs dat=%d rate=%.3fk/s'%(scanned,cnt,cnt/scanned/1024))
                if scanned> scan_time and scan_time>0:
                    break
                else:
                    time.sleep(5)
            self.dut_extensions.stop_monoread()
            self.dut_extensions.stop_timestamp()
            self.dut_extensions.stop_tlu()

    def analyze(self, h5_filename  = ''):
        if h5_fin == '':
           h5_fin = self.output_filename +'.h5'
        h5_fout=h5_fin[:-3]+'hit.h5'
        np_fout=h5_fin[:-3]+'hit.npy'
        interpret_h5(h5_fin,h5_fout)
        self.logger.info('interpreted file %s'%(h5_fout))

if __name__ == "__main__":
    from monopix_daq import monopix_extensions
    m=monopix_extensions.MonopixExtentions()
    ##m.load_config(fname)
    scan = SimpleScan(m,sender_addr="tcp://127.0.0.1:6500")
    scan.start(**local_configuration)
    scan.analyze()
