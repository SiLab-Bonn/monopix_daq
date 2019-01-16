import os, sys, time
import numpy as np
import tables as tb
import yaml
import logging

COL_SIZE = 36 
ROW_SIZE = 129
    
class AnalyzeHits():
    def __init__(self,fhit,fraw):
        self.fhit=fhit
        self.fraw=fraw
        self.res={}

    def run(self,n=10000000):
        with tb.open_file(self.fhit,"a") as f:
            end=len(f.root.Hits)
            start=0
            t0=time.time()
            hit_total=0
            while start<end:
                tmpend=min(end,start+n)
                hits=f.root.Hits[start:tmpend]
                self.analyze(hits,f.root)
                start=start+n
        self.save()

    def analyze(self, hits, fhit_root):
        if "hist_occ" in self.res.keys():
            self.run_hist(hits)
        if "hist_occ_ev" in self.res.keys():
            self.run_hist_ev(hits)
        if "cnts" in self.res.keys():
            self.run_cnts(hits,fhit_root)

    def save(self):
        if "hist_occ" in self.res.keys():
            self.save_hist(res_name="hist_occ")
        if "hist_occ_ev" in self.res.keys():
            self.save_hist(res_name="hist_occ_ev")
        if "injected" in self.res.keys():
            self.save_injected()
        if "cnts" in self.res.keys():
            self.save_cnts()

######### counts
    def init_cnts(self):
        with tb.open_file(self.fraw) as f:
            param_len=len(f.root.scan_parameters)
            cnt_dtype=f.root.scan_parameters.dtype
            inj_th_len=len(yaml.load(f.root.meta_data.attrs.inj_th))
        n_mask_pix=cnt_dtype["pix"].shape[0]
        cnt_dtype=cnt_dtype.descr
        for i in range(len(cnt_dtype)):
                if cnt_dtype[i][0]=="pix":
                    break
        cnt_dtype.pop(i)
        cnt_dtype = cnt_dtype + [
                    ('col', "<i2"),('row', "<i2"),('inj', "<f4"),('th', "<f4"),('cnt',"<i4")]
        self.res["cnts"]=np.zeros(0,dtype=cnt_dtype)
        with tb.open_file(self.fhit,"a") as f:
            f.create_table(f.root,name="Cnts",
                           description=self.res["cnts"].dtype,
                           title='cnt_data')
    def run_cnts(self,hits,fhit_root):
        cols=["scan_param_id","col","row",'inj','th']
        uni,cnt=np.unique(hits[cols],return_counts=True)
        if len(fhit_root.Cnts)==0:
           last_flg=False
        else:
           last=fhit_root.Cnts[len(fhit_root.Cnts)-1]
           last_flg=False
           for c in cols:
             if uni[-1][c]!=last[c]:
               last_flg=True
               break
        if last_flg==True:
            fhit_root.Cnts[len(fhit_root.Cnts)-1]["cnt"]=uni[-1]['cnt']+last["cnt"]
            uni=uni[1:]
            cnt=cnt[1:]
        fhit_root.Cnts.flush()
        buf=np.empty(len(uni),self.res["cnts"].dtype)
        for c in cols:
            buf[c]=uni[c]
        buf["cnt"]=cnt
        fhit_root.Cnts.append(buf)
        fhit_root.Cnts.flush()
    def save_cnts(self):
        self.res["cnts"]=False

######### injected pixels
    def init_injected(self):
        self.res["injected"]=True
    def save_injected(self):
        with tb.open_file(self.fraw) as f:
            param=f.root.scan_parameters[:]
            if "pix" not in param.dtype.names:
                return
            dat=yaml.load(f.root.meta_data.attrs.pixel_conf_before)
        en=np.copy(dat["PREAMP_EN"])
        injected=np.zeros(np.shape(en))
        for pix in param["pix"]:
            for p in pix:
                if p[0]==-1:
                    continue
                injected[p[0],p[1]]= int(en[p[0],p[1]])
        with tb.open_file(self.fhit,"a") as f:
            f.create_carray(f.root, name='Injected',
                            title='Injected pixels',
                            obj=injected,
                            filters=tb.Filters(complib='blosc', complevel=5, fletcher32=False))

######### hit occupancy
    def init_hist(self):
        self.res["hist_occ"]=np.zeros([COL_SIZE,ROW_SIZE],dtype=np.int32)
    def run_hist(self,hits):
        hits=hits[np.bitwise_and(hits["col"]<COL_SIZE,hits["cnt"]==0)]
        if len(hits)!=0:
            self.res["hist_occ"]=self.res["hist_occ"]+np.histogram2d(
                       hits['col'],
                       hits['row'],
                       bins=[np.arange(0,COL_SIZE+1),np.arange(0,ROW_SIZE+1)])[0]
    def save_hist(self,res_name="hist_occ"):
        with tb.open_file(self.fhit,"a") as f:
            f.create_carray(f.root, name='HistOcc',
                            title='Hit Occupancy',
                            obj=self.res[res_name],
                            filters=tb.Filters(complib='blosc', complevel=5, fletcher32=False))
        self.res[res_name]=False
    def init_hist_ev(self):
        self.res["hist_occ_ev"]=np.zeros([COL_SIZE,ROW_SIZE],dtype=np.int32)
    def run_hist_ev(self,hits):
        if len(hits)!=0:
            self.res["hist_occ_ev"]=self.res["hist_occ_ev"]+np.histogram2d(
                       hits['col'],
                       hits['row'],
                       bins=[np.arange(0,COL_SIZE+1),np.arange(0,ROW_SIZE+1)])[0]

                            
if "__main__"==__name__:
    import sys
    fraw=sys.argv[1]
