import os, sys, time
import numpy as np
import tables as tb
import yaml
import logging
import matplotlib.pyplot as plt

import monopix_daq.analysis.utils as utils
COL_SIZE = 36
ROW_SIZE = 129

class AnalyzeCnts():
    def __init__(self,fev,fraw):
        self.fdat=fev
        self.fraw=fraw
        self.res={}
        with tb.open_file(self.fraw) as f:
            param=f.root.scan_parameters[:]
            inj_th=yaml.load(f.root.meta_data.attrs.inj_th)
            self.inj_n=yaml.load(f.root.meta_data.attrs.firmware)["inj"]["REPEAT"]
        self.injlist=np.unique(inj_th[:,0])
        self.thlist=np.unique(inj_th[:,1])
 
    def run(self,n=10000000):
        with tb.open_file(self.fdat,"a") as f:
            end=len(f.root.Cnts)
            start=0
            t0=time.time()
            hit_total=0
            while start<end:
                tmpend=min(end,start+n)
                dat=f.root.Cnts[start:tmpend]
                if tmpend!=end:
                    dat=dat[dat["scan_param_id"]!=dat[-1]["scan_param_id"]]
                    if len(dat)==0:
                        print  "ERROR ERROR ERROR increase n!!!"
                    tmpend=len(dat)
                self.analyze(dat,f.root)
                start=tmpend
        self.save()
        
    def analyze(self, dat, fdat_root):
        if "scurve_fit" in self.res.keys():
            self.run_scurve_fit(dat,fdat_root)
        if "scurve" in self.res.keys():
            self.run_scurve(dat,fdat_root)
            
    def save(self):
        if "scurve_fit" in self.res.keys():
            self.save_scurve_fit()
        if "scurve" in self.res.keys():
            self.save_scurve()
        if "th_dist" in self.res.keys():
            self.save_th_dist()
        if "noise_dist" in self.res.keys():
            self.save_noise_dist()

######### superimposed s-curve
    def init_scurve(self):
        with tb.open_file(self.fdat,"a") as f:
            dat_dtype=f.root.Cnts.dtype.descr
            for c in ["inj","cnt",'col','row','scan_param_id']:
                for i in range(len(dat_dtype)):
                    if dat_dtype[i][0]==c:
                        break
                dat_dtype.pop(i)
            self.res["scurve"]=dat_dtype
            
            s=self.injlist[1]-self.injlist[0]
            bins=[np.arange(np.min(self.injlist)-0.5*s,np.max(self.injlist)+0.5*s,s),
                  np.arange(0,self.inj_n+10)]
            
            dat_dtype=dat_dtype+[("scurve","<i4",(len(bins[0])-1,len(bins[1])-1))]
            buf=np.zeros(1,dtype=dat_dtype)
            table=f.create_table(f.root,name="Scurve",
                               description=buf.dtype,
                               title='Superimposed scurve')
            table.attrs.bins=yaml.dump(bins)
            for th in self.thlist:
                buf[0]["th"]=th
                table.append(buf)
            table.flush()

    def run_scurve(self,dat,fdat_root):
        bins=yaml.load(fdat_root.Scurve.attrs.bins)
        for th_i,th in enumerate(self.thlist):
            tmp=dat[dat["th"]==th]
            #print len(tmp)
            fdat_root.Scurve.cols.scurve[th_i]=fdat_root.Scurve.cols.scurve[th_i]\
                    +np.histogram2d(tmp["inj"],tmp["cnt"],bins=bins)[0]
            #fdat_root.Scurve[th_i].update()
            fdat_root.Scurve.flush()
            #print "buf",np.argwhere(buf["scurve"]!=0)
            #print "table",np.argwhere(fdat_root.Scurve[th_i]["scurve"]!=0)
            #sys.exit()
            
    def save_scurve(self):
        self.res["scurve"]=False

######### Threshold distribution
    def init_th_dist(self):
        self.res["th_dist"]=True
    def save_th_dist(self):
        with tb.open_file(self.fdat,"a") as f:
           dat=f.root.ScurveFit[:]
           dat_type=f.root.ScurveFit.dtype.descr
           for c in ["col","row","scan_param_id","mu","mu_err","A","A_err","sigma","sigma_err"]:
                for i in range(len(dat_type)):
                    if dat_type[i][0]==c:
                        break
                dat_type.pop(i)
           
           p_names=[]
           for d in dat_type:
              p_names.append(d[0])

           uni=np.unique(dat[p_names])
           dat_type=np.empty(0,dtype=dat_type+[("mu","<f4",(COL_SIZE,ROW_SIZE))]).dtype
           try:
               f.root.remove_node("ThDist")
           except:
               pass
           table=f.create_table(f.root,name="ThDist",
                               description=dat_type,
                               title='Threshold distribution')
           buf=np.zeros(1,dtype=dat_type)
           for u in uni:
             tmp=dat[dat[p_names]==u]
             for d in tmp:
               buf[0]["mu"][d["col"],d["row"]]=d["mu"]
             for p in p_names:
               buf[0][p]=u[p]
             table.append(buf)
             table.flush()
             
    def init_noise_dist(self):
        self.res["noise_dist"]=True
    def save_noise_dist(self):
        with tb.open_file(self.fdat,"a") as f:
           dat=f.root.ScurveFit[:]
           dat_type=f.root.ScurveFit.dtype.descr
           for c in ["col","row","scan_param_id","mu","mu_err","A","A_err","sigma","sigma_err"]:
                for i in range(len(dat_type)):
                    if dat_type[i][0]==c:
                        break
                dat_type.pop(i)
           
           p_names=[]
           for d in dat_type:
              p_names.append(d[0])

           uni=np.unique(dat[p_names])
           dat_type=np.empty(0,dtype=dat_type+[("sigma","<f4",(COL_SIZE,ROW_SIZE))]).dtype
           try:
               f.root.remove_node("ThDist")
           except:
               pass
           table=f.create_table(f.root,name="NoiseDist",
                               description=dat_type,
                               title='Noise distribution')
           buf=np.zeros(1,dtype=dat_type)
           for u in uni:
             tmp=dat[dat[p_names]==u]
             for d in tmp:
               buf[0]["sigma"][d["col"],d["row"]]=d["sigma"]
             for p in p_names:
               buf[0][p]=u[p]
             table.append(buf)
             table.flush()

######### s-curve fit
    def init_scurve_fit(self):
        with tb.open_file(self.fdat,"a") as f:
            dat_dtype=f.root.Cnts.dtype.descr
            ## delete inj and cnt from dtype and 
            ## give list of parameters to res["scurve"] TODO better coding?
            for i in range(len(dat_dtype)):
                if dat_dtype[i][0]=="inj":
                    break
            dat_dtype.pop(i)
            for i in range(len(dat_dtype)):
                if dat_dtype[i][0]=="cnt":
                    break
            dat_dtype.pop(i)
            self.res["scurve_fit"]=[]
            for d in dat_dtype:
                  self.res["scurve_fit"].append(d[0])

            dat_dtype = dat_dtype + [('A', "<f4"),('A_err', "<f4"),
                        ('mu', "<f4"),('mu_err', "<f4"),('sigma',"<f4"),('sigma_err', "<f4")]
            try:
                f.remove_node(f.root,"ScurveFit")
            except:
                pass
            f.create_table(f.root,name="ScurveFit",
                           description=np.empty(0,dtype=dat_dtype).dtype,
                           title='scurve_fit')
    def run_scurve_fit(self,dat,fdat_root):
        uni=np.unique(dat[self.res["scurve_fit"]])
        buf=np.empty(len(uni),dtype=fdat_root.ScurveFit.dtype)
        for u_i,u in enumerate(uni):
            args=np.argwhere(dat[self.res["scurve_fit"]]==u)
            if len(args)==0:
                fit=[float("nan")]*6
            else:
                inj=dat["inj"][args]
                cnt=dat["cnt"][args]
                plt.plot(inj,cnt,"o")
                inj=np.append(self.injlist[self.injlist<np.min(inj)],inj)
                cnt=np.append(np.zeros(len(inj)-len(cnt)),cnt)
                fit=utils.fit_scurve(inj,cnt,A=self.inj_n,reverse=False)
            for i in self.res["scurve_fit"]:
                buf[u_i][i]=u[i]
            buf[u_i]["A"]=fit[0]
            buf[u_i]["A_err"]=fit[3]
            buf[u_i]["mu"]=fit[1]
            buf[u_i]["mu_err"]=fit[4]
            buf[u_i]["sigma"]=fit[2]
            buf[u_i]["sigma_err"]=fit[5]
        fdat_root.ScurveFit.append(buf)
        fdat_root.ScurveFit.flush()
    def save_scurve_fit(self):
        self.res["scurve_fit"]=False