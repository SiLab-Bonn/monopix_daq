import sys,time,os
import numpy as np
import matplotlib.pyplot as plt
from numba import njit
import tables
import yaml

TS_TLU=251
TS_INJ=252
TS_MON=253
TS_GATE=254
TLU=255
COL_SIZE=36
ROW_SIZE=129

@njit
def _assign_timestamp(dat,param,inj_th,inj_period,inj_n,mode,buf,sid,pre_inj,inj_i,inj_cnt):
    b_i=0
    d_i=0
    while d_i < len(dat):
        if sid!=dat[d_i]["index"]:
            inj_i=-1
            inj_cnt=inj_n-1
        sid=dat[d_i]["index"]
        if dat[d_i]["col"]==TS_INJ:
            ts_inj=np.int64(dat[d_i]["timestamp"])
            if (ts_inj-pre_inj)!=inj_period*16:
                #if inj_n-1!=inj_cnt:
                #    print("ERROR inj_n",col, row, inj_cnt)
                inj_cnt=0
                inj_i=inj_i+1
            else:
                inj_cnt=inj_cnt+1
            d_ii=d_i+1
            ts_mon=0x7FFFFFFFFFFFFFFF
            ts_mon_t=0x7FFFFFFFFFFFFFFF
            ts_token=0x7FFFFFFFFFFFFFFF
            b_ii=b_i
            while d_ii < len(dat):
                if dat[d_ii]["col"]==TS_INJ:
                    d_i=d_ii
                    b_i=b_ii
                    break
                elif dat[d_ii]["col"]==TS_MON and dat[d_ii]["row"]==0 \
                     and ts_mon==0x7FFFFFFFFFFFFFFF:
                    ts_mon=np.int64(dat[d_ii]["timestamp"])
                elif dat[d_ii]["col"]==TS_MON and dat[d_ii]["row"]==1 \
                     and ts_mon_t==0x7FFFFFFFFFFFFFFF:
                    ts_mon_t=np.int64(dat[d_ii]["timestamp"])
                elif dat[d_ii]["col"]<COL_SIZE:
                    ts_token=np.int64(dat[d_ii]["timestamp"])
                    buf[b_ii]["event_number"]= sid*len(inj_th)*inj_n+inj_i*inj_n+inj_cnt
                    buf[b_ii]["col"]= dat[d_ii]["col"]
                    buf[b_ii]["row"]= dat[d_ii]["row"]
                    buf[b_ii]["inj"]= inj_th[inj_i,0]
                    buf[b_ii]["th"]= inj_th[inj_i,1]
                    buf[b_ii]["ts_mon"]= ts_mon
                    buf[b_ii]["ts_inj"]= ts_inj
                    buf[b_ii]["ts_token"]= ts_token 
                    buf[b_ii]["tot"]= (dat[d_ii]["te"]-dat[d_ii]["le"])&0xFF
                    buf[b_ii]["tot_mon"]= ts_mon_t-ts_mon
                    #buf[b_ii]["flg"]= dat[d_ii]["cnt"]
                    b_ii=b_ii+1
                d_ii=d_ii+1
            pre_inj=ts_inj
            if d_ii==len(dat):
                d_i=d_ii
                b_i=b_ii
                return 0,d_i,buf[:b_i],sid,pre_inj,inj_i,inj_cnt
        else:
            d_i=d_i+1
    return 1,d_i,buf[:b_i],sid,pre_inj,inj_i,inj_cnt

buf_type=[("event_number","<i8"),("col","<u1"),("row","<u1"),("tot","<u1"),
                           ("ts_inj","<i8"),("ts_mon","<i8"),("ts_token","<i8"),("tot_mon","<i8"),
                           ("inj","<f4"),("th","<f4")]

def assign_timestamp_h5(fhit,fraw,fout,n=5000000):
    hit_dat=np.empty(n,dtype=buf_type)
    with tables.open_file(fraw) as f:
        meta=f.root.meta_data[:]
        param=f.root.scan_parameters[:]
        inj_low=yaml.load(f.root.meta_data.attrs.power_status)["INJ_LOset"]
        firmware=yaml.load(f.root.meta_data.attrs.firmware)
        inj_th=yaml.load(f.root.meta_data.attrs.inj_th)
    inj_th[:,0]=inj_th[:,0]-inj_low  ############## change inj_high to inj !!!!!
    inj_period=firmware['inj']["WIDTH"]+firmware['inj']["DELAY"]
    inj_n=firmware['inj']["REPEAT"]
    sid=-1
    inj_i=-1
    inj_cnt=inj_n-1
    pre_inj=0
    with tables.open_file(fout,"w") as f_o:
      description=np.zeros((1,),dtype=buf_type).dtype
      hit_table=f_o.create_table(f_o.root,name="Hits",description=description,title='hit_data')
      with tables.open_file(fhit) as f:
        end=len(f.root.Hits)
        start=0
        t0=time.time()
        while start<end:   ## this does not work, need to read with one chunck
            tmpend=min(end,start+n)
            dat=f.root.Hits[start:tmpend]
            if end==tmpend:
                mode=0
            else:
                mode=1
            err,d_i,hit_dat,sid,pre_inj,inj_i,inj_cnt =_assign_timestamp(
                dat,param,inj_th,inj_period,inj_n,mode,hit_dat,
                sid,pre_inj,inj_i,inj_cnt)
            hit_table.append(hit_dat)
            hit_table.flush()
            start=start+d_i
            print "%d %d %.3f%% %.3fs %dhits %derrs"%(start,d_i,100.0*(start+d_i)/end,time.time()-t0,len(hit_dat),err)
            
if __name__ == "__main__":
    import sys
    fraw=sys.argv[1]
    fhit=fraw[:-7]+"hit.h5"
    fout=fraw[:-7]+"ts.h5"
    assign_ts(fhit,fraw,fts,n=10000000)
    # debug 
    # 
    # 0x20 correct tlu_timestamp based on timestamp2 0x00 based on timestamp
    print fout
               