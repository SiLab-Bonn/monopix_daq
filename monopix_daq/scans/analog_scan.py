#!/usr/bin/env python
import os,sys,time

import numpy as np
import bitarray
import tables as tb
import logging
import yaml

import monopix_daq.scans.injection_scan as injection_scan

local_configuration={"pix": [28,25],
                     "n_mask_pix": 23,
}

#This scan injects a certain amount of times and returns a map of the chip response.

class AnalogScan(injection_scan.InjectionScan):
    scan_id = "analog_scan"
    
    def scan(self,**kwargs):
        ## convert kwargs for thscan
        kwargs["injlist"]=None
        kwargs["thlist"]=None
        kwargs["phaselist"]=None
        kwargs["with_mon"]=False
        kwargs["pix"]=kwargs.pop("pix",local_configuration["pix"])
        kwargs["n_mask_pix"]=kwargs.pop("n_mask_pix",local_configuration["n_mask_pix"])
        kwargs["disable_noninjected_pixel"]=True
        ## run scan
        super(AnalogScan, self).scan(**kwargs)
    def help(self):
        print "pix: pixel or list of pixels ex:[28,25], [[31,81],[31,82]]"
        print "n_mask_pix: n of pixels injected at once"
        print "inj,th,phase: set before scan.start()"
        print "with_mon: always False"
        print "disable_noninjected_pixel: always True"
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
    
    parser = argparse.ArgumentParser(usage="python analog_scan.py",
             formatter_class=argparse.RawTextHelpFormatter)
    parser.add_argument("--config_file", type=str, default=None)
    parser.add_argument('-t',"--th", type=float, default=0.83)
    parser.add_argument('-i',"--inj", type=float, default=1.5)
    parser.add_argument('-nmp',"--n_mask_pix", type=int, default=local_configuration["n_mask_pix"])
    parser.add_argument("-f","--flavor", type=str, default="28:32")
    parser.add_argument("-p","--power_reset", action='store_const', const=1, default=0) ## defualt=True: skip power reset
    args=parser.parse_args()
    
    m=monopix.Monopix(no_power_reset=not bool(args.power_reset))
    if args.config_file is not None:
        m.load_config(args.config_file)

    if args.th is not None:
        m.set_th(args.th)
    if args.inj is not None:
        m.set_inj_high(args.inj+m.dut.SET_VALUE["INJ_LO"])
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
    local_configuration["n_mask_pix"]=args.n_mask_pix

    scan = AnalogScan(m,online_monitor_addr="tcp://127.0.0.1:6500")
    scan.start(**local_configuration)
    scan.analyze()
    scan.plot()
