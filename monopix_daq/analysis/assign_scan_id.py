import time
import numpy as np
#import matplotlib.pyplot as plt
from numba import njit
import tables

@njit
def _assign_scan_id(dat,meta):
    m_i=0
    d_i=0
    while m_i<len(meta) and d_i< len(dat):
        if meta[m_i]["index_start"] <= dat[d_i]["index"] \
           and meta[m_i]["index_stop"] > dat[d_i]["index"]:
                dat[d_i]["index"]=meta[m_i]["scan_param_id"]
                d_i=d_i+1
        elif meta[m_i]["index_stop"] <= dat[d_i]["index"]:
            m_i=m_i+1
        else: # meta[m_i]["index_start"] > data[d_i]["index"]
            #print "error", m_i,d_i,meta[m_i]["index_start"],dat[d_i]["index"]
            #break
            return 1,dat,m_i,d_i
    return 0,dat,m_i, d_i
    
def assign_scan_id(fhit,fraw,fout):
    with tables.open_file(fhit) as f:
        dat=f.root.Hits[:]
    with tables.open_file(fraw) as f:
        meta=f.root.meta_data[:]
        param=f.root.scan_parameters[:]
    description=np.zeros((1,),dtype=dat.dtype).dtype
    err,dat,m_i, d_i=_assign_scan(dat,meta)
    if len(dat)!=d_i:
        print "ERROR some data does not have scan_id "
        
    with tables.open_file(fout,"w") as f:
        hit_table=f.create_table(f.root,name="Hits",description=description,title='hit_data')
        hit_table.append(dat)
        hit_table.flush()
        
if "__main__"==__name__:
    import sys
    if len(sys.arg)!=3 and len(sys.arg)!=2:
        print "assign_scan_id.py <fraw> [fhit]"
        sys.exit()
    fraw=sys.argv[1]
    if len(sys.argv)==3:
        fhit=sys.argv[2]
    else:
        fhit=fraw[:-7]+"hit.h5"
    fout=fraw[:-7]+"sid.h5"
    assign_scan(fhit,fraw,fout)
    
