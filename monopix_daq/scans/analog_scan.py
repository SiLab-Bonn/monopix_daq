import os,sys,time

import numpy as np
import bitarray
import tables as tb
import logging
import yaml

import monopix_daq.scans.th_scan as th_scan

local_configuration={"inj": 1.5, # None
                     "th": 0.81, # None
                     "flavor": "16:20", #18,[18,19],"all",
                     "n_mask_pix": 25,
                     "with_mon": False
}

class AnalogScan(th_scan.ThScan):
    scan_id = "analog_scan"
    
    def scan(self,**kwargs):
        flavor = kwargs.pop('flavor', "all")
        if isinstance(flavor,str):
            if flavor=="all":
                collist=np.arange(0,self.monopix.COL_SIZE)
            else:
                tmp=flavor.split(":")
                collist=np.arange(int(tmp[0]),int(tmp[1]))
        elif isinstance(flavor,int):
            collist=[flavor]
        else:
            collist=flavor
        pix=[]
        for i in collist:
           for j in range(0,self.monopix.ROW_SIZE):
           #for j in range(20,30):
               pix.append([i,j])
        kwargs["pix"]=pix
        inj=kwargs.pop('inj', None)
        if inj is not None:
            inj=[inj]
        kwargs["injlist"]=inj
        th=kwargs.pop('th', None)
        if inj is not None:
            th=[th]
        kwargs["thlist"]=th
        kwargs["with_mon"]=False
        
        super(AnalogScan, self).scan(**kwargs)
                
    def plot(self,fev="",fraw=""):
        if fev =="":
            fev=self.output_filename[:-4]+'ev.h5'
        if fraw =="":
            fraw = self.output_filename +'.h5'
        fpdf = self.output_filename +'.pdf'

        import monopix_daq.analysis.plotting_base as plotting_base
        with plotting_base.PlottingBase(fpdf,save_png=True) as plotting:
            with tb.open_file(fraw) as f:
                firmware=yaml.load(f.root.meta_data.attrs.firmware)
                inj_n=firmware["inj"]["REPEAT"]
                ## page 1
                dat=yaml.load(f.root.meta_data.attrs.dac_status)
                dat.update(yaml.load(f.root.meta_data.attrs.power_status))
                dat["inj_n"]=inj_n
                dat["inj_delay"]=firmware["inj"]["DELAY"]
                dat["inj_width"]=firmware["inj"]["WIDTH"]
                plotting.table_1value(dat,page_title="Chip configuration before scan")#

                dat=yaml.load(f.root.meta_data.attrs.pixel_conf)
            with tb.open_file(fev) as f:
                injected=f.root.Injected[:]
                plotting.plot_2d_pixel_4(
                    [injected,injected,dat["MONITOR_EN"],dat["TRIM_EN"]],
                    page_title="Pixel configuration before scan",
                    title=["Preamp","Inj","Mon","TDAC"], 
                    z_min=[0,0,0,0], z_max=[1,1,1,15])

                dat=f.root.HistOcc[:]
                plotting.plot_2d_pixel_hist(dat,title=f.root.HistOcc.title,z_axis_title="Hits",
                                                   z_max=inj_n)
                
    
if __name__ == "__main__":
    from monopix_daq import monopix
    m=monopix.Monopix()

    scan = AnalogScan(m,online_monitor_addr="tcp://127.0.0.1:6500")
    scan.start(**local_configuration)
    scan.analyze()
    scan.plot()
