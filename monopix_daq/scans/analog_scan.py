#!/usr/bin/env python
import os,sys,time

import numpy as np
import bitarray
import tables as tb
import logging
import yaml

import monopix_daq.scans.injection_scan as injection_scan

local_configuration={"flavor": "16:20", ## "all", [16,17,18,19], 18
                     "n_mask_pix": 25,
}

class AnalogScan(injection_scan.InjectionScan):
    scan_id = "analog_scan"
    
    def scan(self,**kwargs):
        ## convert kwargs for thscan
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
               pix.append([i,j])
        kwargs["pix"]=pix
        kwargs["injlist"]=None
        kwargs["thlist"]=None

        ## run scan
        super(AnalogScan, self).scan(**kwargs)

    def plot(self):
        fev=self.output_filename[:-4]+'ev.h5'
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
                plotting.table_1value(dat,page_title="Chip configuration")

                dat=yaml.load(f.root.meta_data.attrs.pixel_conf)
            with tb.open_file(fev) as f:
                ## page 2
                injected=f.root.Injected[:]
                plotting.plot_2d_pixel_4(
                    [injected,injected,dat["MONITOR_EN"],dat["TRIM_EN"]],
                    page_title="Pixel configuration",
                    title=["Preamp","Inj","Mon","TDAC"], 
                    z_min=[0,0,0,0], z_max=[1,1,1,15])
                ## page 3
                dat=f.root.HistOcc[:]
                plotting.plot_2d_pixel_hist(dat,title=f.root.HistOcc.title,z_axis_title="Hits",
                                                   z_max=inj_n)
                
    
if __name__ == "__main__":
    from monopix_daq import monopix
    import argparse
    
    parser = argparse.ArgumentParser(usage="analog_scan.py xxx_scan",
             formatter_class=argparse.RawTextHelpFormatter)
    parser.add_argument('-t',"--th", type=float, default=0.83)
    parser.add_argument('-i',"--inj", type=float, default=1.5)
    parser.add_argument("-p","--plot_only", action='store_const',const=True, default=False)
    parser.add_argument("-f","--flavor", type=str,
                        default=local_configuration["flavor"])
    parser.add_argument("--fin", metavar="fin", type=str, default=None)
    args=parser.parse_args()
    
    m=monopix.Monopix()
    m.set_th(args.th)
    m.set_inj_high(args.inj+m.dut.SET_VALUE["INJ_LO"])

    local_configuration["flavor"]=args.flavor
    scan = AnalogScan(m,online_monitor_addr="tcp://127.0.0.1:6500")
    scan.start(**local_configuration)
    scan.analyze()
    scan.plot()
