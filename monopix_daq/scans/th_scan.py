import os,sys,time

import numpy as np
import bitarray
import tables as tb
import logging
import yaml

import monopix_daq.scans.injection_scan as injection_scan
INJCAP=2.7E-15

local_configuration={"injlist": np.arange(0.1,1.9,0.005),
                     'pix': [18,25],
                     "n_mask_pix": 30,
}

class ThScan(injection_scan.InjectionScan):
    scan_id = "th_scan"
    
    def scan(self,**kwargs):
        
        super(ThScan, self).scan(**kwargs)

    def analyze(self):
        fraw = self.output_filename +'.h5'
        fhit=fraw[:-7]+'hit.h5'
        fev=fraw[:-7]+'ev.h5'
        
        super(ThScan, self).analyze()

        import monopix_daq.analysis.analyze_cnts as analyze_cnts
        ana=analyze_cnts.AnalyzeCnts(fev,fraw)
        ana.init_scurve()
        ana.init_scurve_fit()
        ana.init_th_dist()
        ana.init_noise_dist()
        ana.run()

    def plot(self):
        fev=self.output_filename[:-4]+'ev.h5'
        fraw = self.output_filename +'.h5'
        fpdf = self.output_filename +'.pdf'

        import monopix_daq.analysis.plotting_base as plotting_base
        with plotting_base.PlottingBase(fpdf,save_png=True) as plotting:
            with tb.open_file(fraw) as f:
                firmware=yaml.load(f.root.meta_data.attrs.firmware)
                inj_n=firmware["inj"]["REPEAT"]
                ## DAC Configuration page
                dat=yaml.load(f.root.meta_data.attrs.dac_status)
                dat.update(yaml.load(f.root.meta_data.attrs.power_status))
                dat["inj_n"]=inj_n
                dat["inj_delay"]=firmware["inj"]["DELAY"]
                dat["inj_width"]=firmware["inj"]["WIDTH"]
                plotting.table_1value(dat,page_title="Chip configuration")

                dat=yaml.load(f.root.meta_data.attrs.pixel_conf)
            with tb.open_file(fev) as f:
                ## Pixel configuration page
                injected=f.root.Injected[:]
                plotting.plot_2d_pixel_4(
                    [injected,injected,dat["MONITOR_EN"],dat["TRIM_EN"]],
                    page_title="Pixel configuration",
                    title=["Preamp","Inj","Mon","TDAC"], 
                    z_min=[0,0,0,0], z_max=[1,1,1,15])

                    
                ## Scurve
                for i in range(len(f.root.Scurve)):
                  dat=f.root.Scurve[i]["scurve"]
                  bins=yaml.load(f.root.Scurve.attrs.bins)
                  plotting.plot_2d_hist(dat,
                       bins=bins,
                       title=f.root.Scurve.title,
                       z_axis_title="",z_min=1,z_max="maximum",z_scale="log")

                ## Threshold distribution
                for i in range(len(f.root.ThDist)):
                    dat=f.root.ThDist[i]
                    plotting.plot_2d_pixel_hist(dat["mu"],title=f.root.ThDist.title,
                                                z_min=0.5)
                plotting.plot_1d_pixel_hists([dat["mu"]],mask=injected,
                                             top_axis_factor=INJCAP/1.602E-19,
                                             top_axis_title="Threshold [e]",
                                             x_axis_title="Testpulse injection [V]",
                                             title=f.root.ThDist.title)
                ## Threshold distribution
                for i in range(len(f.root.NoiseDist)):
                    dat=f.root.NoiseDist[i]
                    plotting.plot_2d_pixel_hist(dat["sigma"],title=f.root.NoiseDist.title,
                                                z_min=0.5)
                plotting.plot_1d_pixel_hists([dat["sigma"]],mask=injected,
                                             top_axis_factor=INJCAP/1.602E-19,
                                             top_axis_title="Noise [e]",
                                             x_axis_title="Testpulse [V]",
                                             title=f.root.ThDist.title)

if __name__ == "__main__":
    from monopix_daq import monopix
    import argparse
    
    parser = argparse.ArgumentParser(usage="analog_scan.py xxx_scan",
             formatter_class=argparse.RawTextHelpFormatter)
    parser.add_argument("--config_file", type=str, default=None)
    parser.add_argument('-t',"--th", type=float, default=None)
    parser.add_argument("--tdac", type=float, default=None)
    parser.add_argument('-ib',"--inj_start", type=float, 
         default=local_configuration["injlist"][0])
    parser.add_argument('-ie',"--inj_stop", type=float, 
         default=local_configuration["injlist"][-1])
    parser.add_argument('-is',"--inj_step", type=float, 
         default=local_configuration["injlist"][1]-local_configuration["injlist"][0])
    parser.add_argument("-n","--n_mask_pix",type=int,default=local_configuration["n_mask_pix"])
    args=parser.parse_args()
    local_configuration["injlist"]=np.arange(args.inj_start,args.inj_stop,args.inj_step)
    local_configuration["n_mask_pix"]=args.n_mask_pix

    m=monopix.Monopix()
    scan = ThScan(m,online_monitor_addr="tcp://127.0.0.1:6500")
    
    if args.config_file is not None:
        m.load_config(args.config_file)
    if args.th is not None:
        m.set_th(args.th)
    if args.tdac is not None:
        m.set_tdac(args.tdac)
    en=np.copy(m.dut.PIXEL_CONF["PREAMP_EN"][:,:])
    local_configuration["pix"]=np.argwhere(en)    
    
    scan.start(**local_configuration)
    scan.analyze()
    scan.plot()
