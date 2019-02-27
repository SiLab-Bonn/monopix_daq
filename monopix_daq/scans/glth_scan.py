import os,sys,time

import numpy as np
import bitarray
import tables as tb
import logging
import yaml

import monopix_daq.scans.injection_scan as injection_scan
INJCAP=2.7E-15

def get_inj_high(e,inj_low=0.1,factor=1):
    print("factor of %.2f is applied"%factor)
    return factor*e*1.602E-19/INJCAP+inj_low

local_configuration={"thlist": np.arange(0.8,0.75,-0.0005),     #A list of values where the threshold will move
                     'pix': [18,25],                         #A list of pixels to go through
                     'n_mask_pix': 25,                             #A list of pixels to go through
                     "disable_noninjected_pixel":True
}

#This is a simple threshold scan for a given set of pixels. Values of the steps are provided in order as a list.

class GlthScan(injection_scan.InjectionScan):
    scan_id = "glth_scan"
    def scan(self,**kwargs):
        """
           pix: [col,row]
           thlist: array of threshold voltage
           all other parameters should be configured before scan.start()
        """
        kwargs["pix"]=kwargs.pop("pix",local_configuration['pix'])
        kwargs["thlist"]=kwargs.pop("thlist",local_configuration['thlist'])
        kwargs["injlist"]=None
        kwargs["phaselist"]=None
        
        kwargs["n_mask_pix"]=kwargs.pop("n_mask_pix",local_configuration['n_mask_pix'])
        kwargs["with_mon"]=False
        kwargs["disable_noninjected_pixel"]=kwargs.pop("disable_noninjected_pixel",local_configuration['disable_noninjected_pixel'])
        super(GlthScan, self).scan(**kwargs)

    def analyze(self):
        fraw = self.output_filename +'.h5'
        fhit=fraw[:-7]+'hit.h5'
        fev=fraw[:-7]+'ev.h5'
        super(GlthScan, self).analyze()
        
        import monopix_daq.analysis.analyze_cnts as analyze_cnts
        ana=analyze_cnts.AnalyzeCnts(fev,fraw)
        ana.init_scurve_fit("th")
        ana.run()
        with tb.open_file(fev) as f:
           dat=f.root.ScurveFit[:]
        return dat

    def plot(self,save_png=False,pixel_scurve=False):
        fev=self.output_filename[:-4]+'ev.h5'
        fraw = self.output_filename +'.h5'
        fpdf = self.output_filename +'.pdf'

        import monopix_daq.analysis.plotting_base as plotting_base
        with plotting_base.PlottingBase(fpdf,save_png=save_png) as plotting:
            with tb.open_file(fraw) as f:
                for i in range(0,len(f.root.kwargs),2):
                    if f.root.kwargs[i]=="disable_noninjected_pixel":
                        disable_noninjected_pixel=yaml.load(f.root.kwargs[i+1])
                    if f.root.kwargs[i]=="with_mon":
                        with_mon=yaml.load(f.root.kwargs[i+1])
                firmware=yaml.load(f.root.meta_data.attrs.firmware)
                inj_n=firmware["inj"]["REPEAT"]
                ## DAC Configuration page
                dat=yaml.load(f.root.meta_data.attrs.dac_status)
                dat.update(yaml.load(f.root.meta_data.attrs.power_status))
                dat["inj_n"]=inj_n
                dat["inj_delay"]=firmware["inj"]["DELAY"]
                dat["inj_width"]=firmware["inj"]["WIDTH"]
                inj=dat["INJ_HIset"]-dat["INJ_LOset"]
                plotting.table_1value(dat,page_title="Chip configuration")

                dat=yaml.load(f.root.meta_data.attrs.pixel_conf)
                
            with tb.open_file(fev) as f:
                ## Pixel configuration page
                injected=f.root.Injected[:]
                if disable_noninjected_pixel:
                    dat["PREAMP_EN"]=injected
                if with_mon:
                    dat["MONITOR_EN"]=injected
                plotting.plot_2d_pixel_4(
                        [dat["PREAMP_EN"],injected,dat["MONITOR_EN"],dat["TRIM_EN"]],
                        page_title="Pixel configuration",
                        title=["Preamp","Inj","Mon","TDAC"], 
                        z_min=[0,0,0,0], z_max=[1,1,1,15])

                if pixel_scurve:
                    res=get_scurve(f.root,injected)
                    for p_i,p in enumerate(np.argwhere(injected)):
                        plotting.plot_scurve([res[p_i]],
                                dat_title=["mu=%.4f sigma=%.4f"%(res[0]["mu"],res[0]["sigma"])],
                                title="Pixel [%d %d], Inj=%.4f"%(p[0],p[1],inj),
                                y_min=0,
                                y_max=inj_n*1.5,
                                reverse=True)
                else:
                    pass #TODO make superimpose plot
                                
def get_scurve(fhit_root,injected):
    x=fhit_root.ScurveFit.attrs.thlist
    res=np.empty(len(np.argwhere(injected)),dtype=[("x","<f4",(len(x),)),("y","<f4",(len(x),)),
                                      ("A","<f4"),("mu","<f4"),("sigma","<f4")])
    dat=fhit_root.Cnts[:]
    fit=fhit_root.ScurveFit[:]
    for p_i,p in enumerate(np.argwhere(injected)):
        tmp=dat[np.bitwise_and(dat["col"]==p[0],dat["row"]==p[1])]
        cnt=np.zeros(len(x))
        for d in tmp:
            a=np.argwhere(np.isclose(x,d["th"]))
            cnt[a[0][0]]=d["cnt"]
        res[p_i]["x"]=x
        res[p_i]["y"]=np.copy(cnt)
        tmp=fit[np.bitwise_and(fit["col"]==p[0],fit["row"]==p[1])]
        if len(tmp)!=1:
            print "onepix_scan.get_scurve() 1error!! pix=[%d %d]"%(p[0],p[1])
            res[p_i]["A"]=float("nan")
            res[p_i]["mu"]=float("nan")
            res[p_i]["sigma"]=float("nan")
        else:
            res[p_i]["A"]=tmp[0]["A"]
            res[p_i]["mu"]=tmp[0]["mu"]
            res[p_i]["sigma"]=tmp[0]["sigma"]
    return res

if __name__ == "__main__":
    from monopix_daq import monopix
    import argparse
    
    parser = argparse.ArgumentParser(usage="python glth_scan.py",
             formatter_class=argparse.RawTextHelpFormatter)
    parser.add_argument("--config_file", type=str, default=None)
    parser.add_argument('-i',"--inj", type=float, default=None)
    parser.add_argument('-t',"--th", type=float, default=None)
    parser.add_argument("--tdac", type=float, default=None)
    parser.add_argument('-tb',"--th_start", type=float, 
         default=local_configuration["thlist"][0])
    parser.add_argument('-te',"--th_stop", type=float, 
         default=local_configuration["thlist"][-1])
    parser.add_argument('-ts',"--th_step", type=float, 
         default=local_configuration["thlist"][1]-local_configuration["thlist"][0])
    parser.add_argument("-nmp","--n_mask_pix",type=int,default=local_configuration["n_mask_pix"])
    parser.add_argument("-f","--flavor", type=str, default=None)
    parser.add_argument("-p","--power_reset", action='store_const', const=1, default=0) ## defualt=True: skip power reset


    args=parser.parse_args()
    local_configuration["thlist"]=np.arange(args.th_start,args.th_stop,args.th_step)
    local_configuration["n_mask_pix"]=args.n_mask_pix
    
    m=monopix.Monopix(no_power_reset=not bool(args.power_reset))
    scan = GlthScan(m,online_monitor_addr="tcp://127.0.0.1:6500")
    
    if args.config_file is not None:
        m.load_config(args.config_file)
    if args.th is not None:
        m.set_th(args.th)
    if args.tdac is not None:
        m.set_tdac(args.tdac)
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
        m.set_preamp_en(pix)
    else:
        pix=list(np.argwhere(m.dut.PIXEL_CONF["PREAMP_EN"][:,:]))
    local_configuration["pix"]=pix
    #if args.pix is not None: 
        #local_configuration["pix"]=np.arange(args.phase_start,args.phase_stop,args.phase_step)
    #en=np.copy(m.dut.PIXEL_CONF["PREAMP_EN"][:,:])
    #local_configuration["pix"]=np.argwhere(en)
     #########TODO: Make it smart, and able to get a list of pixels as argument
    
    scan.start(**local_configuration)
    scan.analyze()
    scan.plot()
