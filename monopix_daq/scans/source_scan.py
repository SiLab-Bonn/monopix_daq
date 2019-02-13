import os,sys,time

import numpy as np
import bitarray
import tables as tb
import logging
import yaml

import monopix_daq.scan_base as scan_base


local_configuration={"with_tlu": True,
                     "with_timestamp": True,
                     "scan_time": 10, ## in second
                     "tlu_delay": 8,
}

class SimpleScan(scan_base.ScanBase):
    scan_id = "simple_scan"
            
    def scan(self,**kwargs): 
        with_tlu = kwargs.pop('with_tlu', True)
        with_timestamp = kwargs.pop('with_timestamp', True)
        scan_time = kwargs.pop('scan_time', 10)
        ## start_freeze=50,start_read=52,stop_read=52+2,stop_freeze=52+37,stop=52+37+10,
        ## start_freeze=90
        start_freeze = kwargs.pop('start_freeze', 90)
        start_read = kwargs.pop('start_read', start_freeze+2)
        stop_read = kwargs.pop('stop_read', start_read+2)
        stop_freeze = kwargs.pop('stop_freeze', start_freeze+37)
        stop_rx = kwargs.pop('stop', stop_freeze+10)
        cnt=0
        scanned=0

        ####################
        ## start readout
        self.monopix.set_monoread(start_freeze=start_freeze,start_read=start_read,
                                         stop_read=stop_read,stop_freeze=stop_freeze,stop=stop_rx)
        if with_tlu:
            tlu_delay = kwargs.pop('tlu_delay', 8)
            self.monopix.set_tlu(tlu_delay)
        if with_timestamp:
            self.monopix.set_timestamp()

        ####################
        ## start read fifo        
        with self.readout(scan_param_id=0,fill_buffer=False,clear_buffer=True,readout_interval=0.2,timeout=0):
            t0=time.time()

            self.logger.info("*****%s is running **** don't forget to start tlu ****"%self.__class__.__name__)
            while True:
                pre_cnt=cnt
                cnt=self.fifo_readout.get_record_count()
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
                self.monopix.stop_timestamp()
                self.meta_data_table.attrs.timestamp_status = yaml.dump(self.dut["timestamp"].get_configuration())
            if with_tlu:
                self.monopix.stop_tlu()
                self.meta_data_table.attrs.tlu_status = yaml.dump(self.dut["tlu"].get_configuration())
            self.monopix.stop_monoread()

    def analyze(self, event="tlu",debug=3):
        fraw = self.output_filename +'.h5'
           
        import monopix_daq.analysis.interpreter as interpreter
        fhit=fraw[:-7]+'hit.h5'
        interpreter.interpret_h5(fraw,fhit,debug=3)
        self.logger.info('interpreted file %s'%(fhit))
        
        import monopix_daq.analysis.analyze_hits as analyze_hits
        ana=analyze_hits.AnalyzeHits(fhit,fraw)
        ana.init_hist()
        ana.run()
     
    def plot(self,fhit="",fraw=""):
        if fhit =="":
            fhit=self.output_filename[:-4]+'hit.h5'
        if fraw =="":
            fraw = self.output_filename +'.h5'
        fpdf=self.output_filename+'.pdf'
        
        import monopix_daq.analysis.plotting_base as plotting_base
        with plotting_base.PlottingBase(fpdf,save_png=True) as plotting:
            ### configuration 
            with tb.open_file(fraw) as f:
                ###TODO!! format kwargs and firmware setting
                dat=yaml.load(f.root.meta_data.attrs.kwargs)
                dat=yaml.load(f.root.meta_data.attrs.firmware)

                dat=yaml.load(f.root.meta_data.attrs.dac_status)
                dat.update(yaml.load(f.root.meta_data.attrs.power_status))
                plotting.table_1value(dat,page_title="Chip configuration")

                dat=yaml.load(f.root.meta_data.attrs.pixel_conf)
                plotting.plot_2d_pixel_4(
                    [dat["PREAMP_EN"],dat["INJECT_EN"],dat["MONITOR_EN"],dat["TRIM_EN"]],
                    page_title="Pixel configuration",
                    title=["Preamp","Inj","Mon","TDAC"], 
                    z_min=[0,0,0,0], z_max=[1,1,1,15])

            ### plot data
            with tb.open_file(fhit) as f:
                dat=f.root.HistOcc[:]
                plotting.plot_2d_pixel_hist(dat,title=f.root.HistOcc.title,z_axis_title="Hits")
    
if __name__ == "__main__":
    from monopix_daq import monopix
    m=monopix.Monopix()
    m.set_th(0.805)
    scan = SimpleScan(m,fout=None,online_monitor_addr="tcp://127.0.0.1:6500")
    scan.start(**local_configuration)
    scan.analyze()
    scan.plot()
