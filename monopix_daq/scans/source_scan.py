import os,sys,time

import numpy as np
import bitarray
import tables as tb
import yaml

import monopix_daq.scan_base as scan_base


local_configuration={"with_tlu": True,
                     "with_rx1": True,
                     "with_mon": True,
                     "scan_time": 10, ## in second
                     "tlu_delay": 8,
                     "pix": [28,25],
}

class SourceScan(scan_base.ScanBase):
    scan_id = "source_scan"
            
    def scan(self,**kwargs): 
        with_tlu = kwargs.pop('with_tlu', True)
        with_rx1 = kwargs.pop('with_rx1', True)
        with_mon = kwargs.pop('with_mon', True)
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
        if with_rx1:
            self.monopix.set_timestamp640(src="rx1")
        if with_mon:
            self.monopix.set_timestamp640(src="mon")

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
            self.monopix.stop_all_data()


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
                firmware=yaml.load(f.root.meta_data.attrs.firmware)
                inj_n=firmware["inj"]["REPEAT"]
                ## page 1
                dat=yaml.load(f.root.meta_data.attrs.dac_status)
                dat.update(yaml.load(f.root.meta_data.attrs.power_status))
                print firmware["data_rx"]
                for mod in ["data_rx","tlu","timestamp_tlu","timestamp_rx1","timestamp_mon"]:
                    for k,v in firmware[mod].iteritems():
                        dat['%s:%s'%(mod,k)]=v
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
    import argparse
    
    parser = argparse.ArgumentParser(usage="python source_scan.py",
             formatter_class=argparse.RawTextHelpFormatter)
    parser.add_argument("--config_file", type=str, default=None)
    parser.add_argument('-t',"--th", type=float, default=0.83)
    parser.add_argument("-f","--flavor", type=str, default=None)
    parser.add_argument("-p","--power_reset", action='store_const', const=1, default=0) ## defualt=True: skip power reset
    parser.add_argument("-time",'--scan_time', type=int, default=None,
                        help="Scan time in seconds.")
    args=parser.parse_args()
    
    m=monopix.Monopix(no_power_reset=not bool(args.power_reset))
    if args.config_file is not None:
        m.load_config(args.config_file)

    if args.th is not None:
        m.set_th(args.th)
    if args.flavor is not None:
        if args.flavor=="all":
            collist=np.arange(0,m.COL_SIZE)
        else:
            tmp=args.flavor.split(":")
            collist=np.arange(int(tmp[0]),int(tmp[1]))
        pix=[]
        for i in collist:
           for j in range(0,m.ROW_SIZE):
               pix.append([i,j])
    else:
        pix=list(np.argwhere(m.dut.PIXEL_CONF["PREAMP_EN"][:,:]))
    local_configuration["pix"]=pix
    
    if args.scan_time is not None:
        local_configuration["scan_time"]=args.scan_time
    
    
    scan = SourceScan(m,online_monitor_addr="tcp://127.0.0.1:6500")
    scan.start(**local_configuration)
    scan.analyze()
    scan.plot()
