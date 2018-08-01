import os,sys,time

import numpy as np
import bitarray
import tables as tb
import logging
import yaml

import monopix_daq.scan_base as scan_base
import monopix_daq.analysis.interpreter as interpreter
import monopix_daq.analysis.event_builder as event_builder
import monopix_daq.analysis.clusterizer as clusterizer

local_configuration={"with_tlu": True,
                     "with_timestamp": True,
                     "scan_time": 10, ## in second
                     "tlu_delay": 8,
}

class SimpleScan(scan_base.ScanBase):
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
        ## start_freeze=50,start_read=52,stop_read=52+2,stop_freeze=52+36,stop=52+36+10,
        start_freeze = kwargs.pop('start_freeze', 50)
        start_read = kwargs.pop('start_read', start_freeze+2)
        stop_read = kwargs.pop('stop_read', start_read+2)
        stop_freeze = kwargs.pop('stop_freeze', start_freeze+36)
        stop_rx = kwargs.pop('stop', stop_freeze+10)
        cnt=0
        scanned=0

        ####################
        ## start readout
        self.dut_extensions.set_monoread(start_freeze=start_freeze,start_read=start_read,
                                         stop_read=stop_read,stop_freeze=stop_freeze,stop=stop_rx)
        if with_tlu:
            tlu_delay = kwargs.pop('tlu_delay', 8)
            self.dut_extensions.set_tlu(tlu_delay)
        if with_timestamp:
            self.dut_extensions.set_timestamp()

        ####################
        ## start read fifo        
        with self.readout(scan_param_id=0,fill_buffer=False,clear_buffer=True,readout_interval=0.2,timeout=0):
            t0=time.time()

            self.logger.info("*****%s is running **** don't forget to start tlu ****"%self.__class__.__name__)
            while True:
                pre_cnt=cnt
                cnt=self.fifo_readout.get_record_count()
                #dqdata = self.fifo_readout.data
                #try:
                #    data = np.concatenate([item[0] for item in dqdata])
                #except ValueError:
                #    data = []
                #cnt=len(data)
                pre_scanned=scanned
                scanned=time.time()-t0
                self.logger.info('time=%.0fs dat=%d rate=%.3fk/s'%(scanned,cnt,(cnt-pre_cnt)/(scanned-pre_scanned)/1024))
                if scanned+10 > scan_time and scan_time>0:
                    break
                elif scanned < 30:
                    time.sleep(1)
                else:
                    time.sleep(10)
            time.sleep(max(0,scan_time-scanned))             
            ####################
            ## stop readout
            if with_timestamp:
                self.dut_extensions.stop_timestamp()
                self.meta_data_table.attrs.timestamp_status = yaml.dump(self.dut["timestamp"].get_configuration())
            if with_tlu:
                self.dut_extensions.stop_tlu()
                self.meta_data_table.attrs.tlu_status = yaml.dump(self.dut["tlu"].get_configuration())
            self.dut_extensions.stop_monoread()


    def analyze(self, h5_fin='',event="tlu",debug=3):
        if h5_fin == '':
           h5_fin = self.output_filename +'.h5'

        hit_fout=h5_fin[:-7]+'_hit.h5'
        interpreter.interpret_h5(h5_fin,hit_fout,debug=3)
        self.logger.info('interpreted file %s'%(hit_fout))

        tlu_fout=h5_fin[:-7]+'_tlu.h5'
        event_builder.build_h5(h5_fin,hit_fout,tlu_fout,event=event)
        self.logger.info('event_built file %s'%(tlu_fout))

        ev_fout=h5_fin[:-7]+'_ev.h5'
        event_builder.convert_h5(tlu_fout,ev_fout)
        self.logger.info('converted file %s'%(ev_fout))

        cl_fout=h5_fin[:-7]+'_cl.h5'
        clusterizer.clusterize_h5(ev_fout,cl_fout)
        
        #np_fout=h5_fin[:-7]+'hit.npy'
        #monopix_interpreter.mk_plot(h5_fout,np_fout)
    
if __name__ == "__main__":
    from monopix_daq.monopix_extension import MonopixExtensions
  
    #fname=time.strftime("%Y%m%d_%H%M%S_simples_can")
    #fname=(os.path.join(monopix_extra_functions.OUPUT_DIR,"simple_scan"),fname)
    m_ex = MonopixExtensions("../monopix_mio3.yaml")
    scan = SimpleScan(dut_extentions=m_ex, sender_addr="tcp://127.0.0.1:5500")
    scan.start(**local_configuration)
    scan.analyze()
