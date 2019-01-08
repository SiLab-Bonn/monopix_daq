import os, sys, time
import numpy as np
import tables
import yaml
import logging

COL_SIZE = 36 ##TODO change hard coded values
ROW_SIZE = 129
    
class AnalysisBase():
    def __init__(self,fhit,fraw,n=10000000):
        self.fhit=fhit
        self.fraw=fraw
        self.res={}
        with tables.open_file(fhit,"a") as f:
            end=len(f.root.Hits)
            start=0
            t0=time.time()
            hit_total=0
            self.init()
            while start<end:
                tmpend=min(end,start+n)
                hits=f.root.Hits[start:tmpend]
                self.run(hits)
                start=start+n
        self.save()
    def init(self):
        self.init_hist()
    def run(self,hits):
        if "event_number" in hits.dtype.names:
            self.run_hist_ev(hits)
        else:
            self.run_hist(hits)
    def save(self):
        self.save_hist()
        self.save_injected()
    
    def init_injected(self):
        pass
    def run_injected(self):
        pass
    def save_injected(self):
        with tables.open_file(self.fraw) as f:
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
        with tables.open_file(self.fhit,"a") as f:
            f.create_carray(f.root, name='Injected',
                            title='Injected pixels',
                            obj=injected,
                            filters=tables.Filters(complib='blosc', complevel=5, fletcher32=False))

    def init_hist(self):
        self.res["hist_occ"]=np.zeros([COL_SIZE,ROW_SIZE],dtype=np.int32)
    def run_hist(self,hits):
        hits=hits[np.bitwise_and(hits["col"]<COL_SIZE,hits["cnt"]==0)]
        if len(hits)!=0:
            self.res["hist_occ"]=self.res["hist_occ"]+np.histogram2d(
                       hits['col'],
                       hits['row'],
                       bins=[np.arange(0,COL_SIZE+1),np.arange(0,ROW_SIZE+1)])[0]
    def run_hist_ev(self,hits):
        #TODO clean data...
        if len(hits)!=0:
            self.res["hist_occ"]=self.res["hist_occ"]+np.histogram2d(
                       hits['col'],
                       hits['row'],
                       bins=[np.arange(0,COL_SIZE+1),np.arange(0,ROW_SIZE+1)])[0]
    def save_hist(self):
        with tables.open_file(self.fhit,"a") as f:
            f.create_carray(f.root, name='HistOcc',
                            title='Hit Occupancy',
                            obj=self.res["hist_occ"],
                            filters=tables.Filters(complib='blosc', complevel=5, fletcher32=False))

                            
if "__main__"==__name__:
    import sys
    fraw=sys.argv[1]
    read_config(fraw)