import os, sys, time
import numpy as np
import tables
import yaml
import logging

COL_SIZE = 36 ##TODO change hard coded values
ROW_SIZE = 129

def read_config(fraw):
    #if fraw[-3:]==".h5":
        #with tables.open_file(fraw) as f:
        #    ret=yaml.load(f.root.meta_data.attrs.dac_status)
        #    ret.update(yaml.load(f.root.meta_data.attrs.power_status))
        #    ret.update(yaml.load(f.root.meta_data.attrs.pixel_conf))
        #    ret.update(yaml.load(f.root.meta_data.attrs.firmware))
        #    print yaml.load(f.root.meta_data.attrs.kwargs)
        #    
    #with open(fraw) as f:
    #    ret=yaml.load(f)
    return ret
    
class AnalysisBase():
    def __init__(self,fhit,n=100000):
        self.fhit=fhit
        with tables.open_file(fhit,"a") as f:
            end=len(f.root.Hits)
            start=0
            t0=time.time()
            hit_total=0
            self.init_res()
            while start<end:
                tmpend=min(end,start+n)
                hits=f.root.Hits[start:tmpend]
                self.run(hits)
                start=start+n
        self.save_res()

    def init_res(self):
        self.res={}
        self.res["hist_occ"]=np.zeros([COL_SIZE,ROW_SIZE],dtype=np.int32)
        #return ret
    def run(self,hits):
        hits=hits[np.bitwise_and(hits["col"]<COL_SIZE,hits["cnt"]==0)]
        if len(hits)!=0:
            self.res["hist_occ"]=self.res["hist_occ"]+np.histogram2d(
                       hits['col'],
                       hits['row'],
                       bins=[np.arange(0,COL_SIZE+1),np.arange(0,ROW_SIZE+1)])[0]
        #return ret
    def save_res(self):
        with tables.open_file(self.fhit,"a") as f:
            f.create_carray(f.root, name='HistOcc',
                            title='Hit Occupancy',
                            obj=self.res["hist_occ"],
                            filters=tables.Filters(complib='blosc', complevel=5, fletcher32=False))

                            
if "__main__"==__name__:
    import sys
    fraw=sys.argv[1]
    read_config(fraw)