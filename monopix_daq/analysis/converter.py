import sys,time,os
import numpy as np
import matplotlib.pyplot as plt
from numba import njit
import tables
import yaml

hit_dtype=np.dtype([("event_number","<i8"),("frame","<u1"),("column","<u2"),("row","<u2"),("charge","<u2")])

def _convert(mono,ref,hit,offset,peak,row_offset,row_factor,col_offset,col_factor,tr,debug):
    hit_i=0
    ref_i=0
    mono_i=0
    while hit_i<len(hit) and ref_i<len(ref):
        mono_trig=np.uint16(mono[mono_i]["trigger_number"] & 0x7FFF)
        ref_trig=np.uint16(ref[ref_i]["trigger_number"] & 0x7FFF)
        if (mono_trig-ref_trig) & 0x4000 ==0x4000:
            if debug & 0x4 == 0x4:
                print "del mono",(mono_i,ref_i,mono_trig,ref_trig,ref[ref_i]["event_number"],mono[mono_i]["diff"])
            mono_i=mono_i+1
        elif mono_trig==ref_trig:
            hit[hit_i]["event_number"]=ref[ref_i]["event_number"]
            if tr==True:
                hit[hit_i]["row"]=col_offset+col_factor*mono[mono_i]["col"]
                hit[hit_i]["column"]=row_offset+row_factor*mono[mono_i]["row"]
            else:
                hit[hit_i]["column"]=col_offset+col_factor*mono[mono_i]["col"]
                hit[hit_i]["row"]=row_offset+row_factor*mono[mono_i]["row"]
            hit[hit_i]["charge"]= np.uint16((mono[mono_i]["te"]-mono[mono_i]["le"]) & 0xFF)
            tmp = np.int64(mono[mono_i]["token_timestamp"]) - np.int64(mono[mono_i]["event_timestamp"])\
                - np.int64(hit[hit_i]["charge"]) \
                - np.int64((mono[mono_i]["token_timestamp"]-np.uint64(mono[mono_i]["te"])+np.uint64(0xF0)-offset) & np.uint64(0xFF))\
                + np.int64(0xF0) - peak + np.int64(0x80)
            tmp = max(tmp,0)
            tmp = min(tmp,0xFF)
            hit[hit_i]["frame"] = np.uint8(tmp)
            hit_i=hit_i+1
            mono_i=mono_i+1
        else:
            ref_i=ref_i+1
    return 0, hit[:hit_i],hit_i,ref_i
    
def convert_h5(fin,fref,fout,n=1000000,
               row_offset=1,row_factor=1,col_offset=1,col_factor=1,tr=False,
               debug=1):
    buf=np.empty(n,dtype=hit_dtype) 
    print fref
    with tables.open_file(fref) as f:
        ref=f.root.Hits[:][["event_number","trigger_number"]]
    ref,dummy=np.unique(ref,return_index=True)
    print "ref",len(ref)
    ref_start=0
    
    with tables.open_file(fout, "w") as f_o:
        description=np.zeros((1,),dtype=hit_dtype).dtype
        hit_table=f_o.create_table(f_o.root,name="Hits",description=description,title='hit_data')
        with tables.open_file(fin) as f:
            offset=np.uint64(f.root.Hits.attrs.te_offset)
            peak=np.int64(f.root.Hits.attrs.diff_peak)
            end=len(f.root.Hits)
            t0=time.time()
            hit_total=0
            start=0
            while start<end:
                tmpend=min(end,start+n)
                hit=f.root.Hits[start:tmpend]
                
                (err,buf_out,mono_i,ref_i
                  )=_convert(
                  hit,ref[ref_start:],buf,offset,peak,
                  row_offset=row_offset,row_factor=row_factor,col_offset=col_offset,col_factor=col_factor,tr=tr,
                  debug=0)
                  
                hit_total=hit_total+len(buf_out)
                if err==0:
                    print "%d %.3f%% %.3fs %dhits"%(start,100.0*(tmpend)/end,time.time()-t0,hit_total)
                else:
                    print "noise err",err,start,token_timestamp,token_timestamp0,cnt0,tlu_timestamp,tlu,tlu_flg
                if debug & 0x01==0x0:
                    buf_out=buf_out[np.bitwise_and(buf_out['frame']!=0, buf_out['frame']!=255)]
                hit_table.append(buf_out)
                hit_table.flush()
                start=tmpend
                ref_start=ref_start+ref_i
                if start>=end:
                   break
                
if __name__ == "__main__":
    import sys
    
    fraw=sys.argv[1]
    fref=sys.argv[2] ## vetoed fe data

    ftlu=fraw[:-3]+"_tlu.h5"
    fev=fraw[:-3]+"_ev.h5"
    convert_h5(ftlu,fref,fev,col_offset=1,col_factor=1,debug=0)
