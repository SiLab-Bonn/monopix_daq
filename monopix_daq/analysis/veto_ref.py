import sys,time,os
import numpy as np
import matplotlib.pyplot as plt
from numba import njit
import tables
import yaml

veto_type=[('event_number','<u8'),('event_timestamp','<u8'),
             ('trigger_number','<u4'),('flg','<u1'),('veto_begin','<u8'),('veto_end','<u8')]

@njit
def _find_veto( buf,veto_begin,veto_end):
    idx=0
    for c_i,c in enumerate(buf):
        buf[c_i]["flg"]=False
        buf[c_i]["event_number"]=np.int64(c_i)
        flg=False
        for i in range(len(veto_begin[idx:])):
            if c["event_timestamp"] < veto_begin[idx+i]:
                buf[c_i]["flg"]=False
                buf[c_i]['veto_begin']=veto_begin[max(idx+i-1,0)]
                buf[c_i]['veto_end']=veto_end[max(idx+i-1,0)]
                #print (c_i,idx,i),"not found", (c["event_timestamp"], veto_begin[idx+i])
                idx=max(0,idx+i-1)
                break
            else:
                if c["event_timestamp"] <= veto_end[idx+i]:
                    buf[c_i]["flg"]=True
                    buf[c_i]['veto_begin']=veto_begin[idx+i]
                    buf[c_i]['veto_end']=veto_end[idx+i]
                    #print (c_i,idx,i),"found!!!",(c["event_timestamp"],veto_begin[idx+i],veto_end[idx+i])
                    idx=max(0,idx+i)
                    break
                else: ## c["event_timestamp"] > veto_end[idx+i]:
                    pass
    return buf

def find_veto_h5(fraw,fhit,fout):
    with tables.open_file(fraw) as f:#
        rx_status=yaml.load(f.root.meta_data.attrs.rx_status[:])
    print rx_status
    
    fhit=fraw[:-3]+"_hit.h5"
    with tables.open_file(fhit) as f:
        hit=f.root.Hits[:]
    print len(hit[hit["col"]==0xFF]),len(hit[hit["col"]==0xFE]),len(hit[hit["col"]==0xFD]),len(hit[hit["col"]<36])
    
    rx_stop=np.uint64(rx_status["CONF_STOP"])
    rx_shift=np.uint64(rx_status["CONF_STOP_FREEZE"]-rx_status["CONF_START_READ"])
    rx_freeze=np.uint64(rx_status["CONF_START_FREEZE"])
    
    tlu=hit[hit["col"]==0xFF]
    mono=hit[hit["col"]<36]
    
    ## check timestamp
    print 'TLU: increase only',np.all(tlu["timestamp"][1:] >= tlu["timestamp"][:-1]) 
    print 'MONO: increase only',np.all(mono["timestamp"][1:] >= mono["timestamp"][:-1])
    
    veto_begin,cnt=np.unique(mono["timestamp"],return_counts=True)
    veto_end=rx_stop+np.uint64(cnt[:]-1)*rx_shift+veto_begin
    veto_begin=veto_begin+rx_freeze
    
    buf=np.empty(len(tlu),dtype=veto_type)
    buf["event_timestamp"]=tlu["timestamp"]
    buf["trigger_number"]=tlu["cnt"]
    
    buf_out = _find_veto(buf,veto_begin,veto_end)
    
    with tables.open_file(fout,"w") as f_o:
        description=np.zeros((1,),dtype=veto_type).dtype
        hittmp_table=f_o.create_table(f_o.root,name="Triggers_tmp",description=description,title='hit_data')
        hittmp_table.append(buf_out)
        hittmp_table.flush()
        
        description=np.zeros((1,),dtype=veto_type).dtype
        hit_table=f_o.create_table(f_o.root,name="Triggers",description=description,title='hit_data')
        hit_table.append(buf[buf["flg"]==True])
        hit_table.flush()
 
    print "number of veto tlu %d"%len(buf[buf["flg"]==True]),"total number of tlu=%d"%len(buf),
    print "%f%%"%(100.0*len(buf[buf["flg"]==True])/len(buf))
    
@njit
def _veto_event(hit,trigs):
    hit_i=0
    h_i=0
    trig_i=0
    while trig_i < len(trigs) and h_i < len(hit):
         hit_trig= np.uint16(hit[h_i]["trigger_number"] & 0x7FFF)
         trig=np.uint16(trigs[trig_i] & 0x7FFF)
         if hit_trig == trig:
              #print "del",h_i,trig_i,hit[h_i]["event_number"],trigs[trig_i]
              h_i=h_i+1
         elif (hit_trig - trig) & np.uint16(0x4000) ==0:
              #print "nexttrig",h_i,trig_i,hit[h_i]["event_number"],trigs[trig_i]
              trig_i=trig_i+1
         else:
              hit[hit_i]=hit[h_i]
              #print "copy",h_i,trig_i,hit[h_i]["event_number"],trigs[trig_i]
              hit_i=hit_i+1
              h_i=h_i+1
    return hit[:hit_i],trig_i
    
def veto_event_h5(fin,fref,fout,n=10000000):
    if isinstance(fin,str):
        fin=[fin]
    with tables.open_file(fref) as f:
            trigs=f.root.Triggers[:]["trigger_number"]
            trig_i=0

    with tables.open_file(fout,"w") as f_o:
        hit_cnt=0
        for fin_i,fin_e in enumerate(fin):
            with tables.open_file(fin_e) as f:
                if fin_i==0:
                    offset=0
                    hit_table=f_o.create_table(f_o.root,name="Hits",description=f.root.Hits.description,title='hit_data')
                elif pre_trigger_number==f.root.Hits[0]["trigger_number"]:
                    offset=pre_event_number
                else:
                    offset=pre_event_number+1
                start=0
                end=len(f.root.Hits)
                print fin_i,"total hit %d"%end, "event_number offset",offset
                while start<end:
                    tmpend=min(end,start+n)
                    hit=f.root.Hits[start:tmpend]
                    hit["event_number"]=hit["event_number"]+offset
                    hit,trig_i=_veto_event(hit,trigs[trig_i:])
                    hit_cnt=hit_cnt+len(hit)
                    print "hit=%d, total_hit=%d %3.f%%"%(len(hit),hit_cnt,100.0*tmpend/end)
                    hit_table.append(hit)
                    hit_table.flush()
                    start=tmpend
                pre_event_number=f.root.Hits[-1]["event_number"]
                pre_trigger_number=f.root.Hits[-1]["trigger_number"]
                
if __name__ == "__main__":
    ##datdir="/sirrush/thirono/testbeam/2017-09-20/run151"
    fraw=sys.argv[1] ##os.path.join(datdir,"m2_151_170926-205321.h5")
    fhit=fraw[:-3]+"_hit.h5"
    fref=fraw[:-3]+"_ref.h5"

    ffe=[]
    for ffe_e in sys.argv[2:]:
        print ffe_e
        ffe.append(ffe_e)
    fout=ffe[0][:-15]+"_vetoed.h5"
    
    find_veto_h5(fraw,fhit,fref)
    veto_event_h5(ffe,fref,fout)
