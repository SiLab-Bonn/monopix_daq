import sys,time,os
import numpy as np
import matplotlib.pyplot as plt
from numba import njit
import tables
import yaml
               
hit_dtype=np.dtype([("event_number","<i8"),("frame","<i8"),("column","<u2"),("row","<u2"),("charge","<u1")])
                    
#inter_type=np.dtype([("col","<u1"),("row","<u1"),("le","<u1"),("te","<u1"),("cnt","<u4")
#                    ("timestamp","<u8")])

buf_dtype=np.dtype([("event_number","<i8"),("col","<u1"),("row","<u1"),("le","<u1"),("te","<u1"),("flg","<u1"),
                    ("token_timestamp","<u8"),("event_timestamp","<u8"),("trigger_number","<u4"),])

@njit
def _build_with_tlu(hit,buf,token_timestamp,token_timestamp0,veto,
               tlu_timestamp,tlu,rx_stop,rx_shift,rx_freeze_start,event_number,debug):
    buf_i=0
    noise=0
    tlu_flg=0
    veto1=veto
    token_timestamp1=token_timestamp
    buf_ii=buf_i
    for h_i,h_e in enumerate(hit):
        if h_e["col"]==254:
            #print "ts",h_e["timestamp"]
            pass
        elif h_e["col"]==255:
            tlu_timestamp=h_e["timestamp"]
            tlu=h_e["cnt"]
            tlu_flg=1
            #print "tlu", tlu_flg, h_i, veto, token_timestamp, h_e
            token_timestamp1=token_timestamp
            token_timestamp01=token_timestamp0
            veto1=veto
            buf_ii=buf_i
            for h_ii,h_ee in enumerate(hit[h_i+1:]): ## search for hits
                if h_ee["col"]==254:
                    #print ".",
                    pass
                elif h_ee["col"]==255:
                    #print "-",
                    pass
                else:
                    if tlu_flg==1:
                        if h_ee["cnt"]==0 and h_ee["timestamp"]!=token_timestamp1: # Find event
                            #print "(%d)"%h_ii,
                            if h_ee["timestamp"] + rx_freeze_start < tlu_timestamp :
                                token_timestamp01=h_ee["timestamp"]
                                veto1=rx_stop
                            elif token_timestamp01 + np.uint64(veto1) > tlu_timestamp: 
                                noise=2
                                tlu_flg=2
                            else:
                                noise=0
                                tlu_flg=2
                            if tlu_flg==2 and debug & 0x2==0x2:
                                buf[buf_ii]["col"]=0xEF
                                buf[buf_ii]["row"]=0xFF
                                buf[buf_ii]["le"]= np.uint8(veto & 0xFF)
                                buf[buf_ii]["te"]= np.uint8((veto>>16) & 0xFF)
                                buf[buf_ii]["flg"]= np.uint8(noise)
                                buf[buf_ii]["token_timestamp"] = h_ee["timestamp"] #token_timestamp0
                                buf[buf_ii]["trigger_number"]=tlu
                                buf[buf_ii]["event_number"]=event_number
                                buf[buf_ii]["event_timestamp"]=tlu_timestamp
                                buf_ii=buf_ii+1
                            if tlu_flg==2 and (debug & 0x1 ==0x1 or (noise==0 and h_ee["cnt"]==0)):
                                buf[buf_ii]["col"]=h_ee["col"]
                                buf[buf_ii]["row"]=h_ee["row"]
                                buf[buf_ii]["le"]=h_ee["le"]
                                buf[buf_ii]["te"]=h_ee["te"]
                                buf[buf_ii]["flg"]= np.uint8(h_ee["cnt"] | noise)
                                buf[buf_ii]["token_timestamp"]=h_ee["timestamp"]
                                buf[buf_ii]["trigger_number"]=tlu
                                buf[buf_ii]["event_timestamp"]=tlu_timestamp
                                buf[buf_ii]["event_number"]=event_number
                                buf_ii=buf_ii+1
                        elif h_ee["cnt"]==1 and h_ee["timestamp"]!=token_timestamp1: # not begging of event
                            #print "!",
                            veto1=veto1+rx_stop
                            #pirint "search noise", tlu_flg, noise, h_ii, veto1, "t1%d"%token_timestamp1, h_ee
                        else: #not begging of event
                            veto1=veto1+rx_shift
                            #print "search 2nd pix",tlu_flg, noise, h_i,veto1, "t1%d"%token_timestamp1, h_ee
                    elif tlu_flg==2:
                        #print "--%d"%h_ii,h_ee["cnt"],h_ee["timestamp"],token_timestamp,"--",
                        if h_ee["cnt"]==0 and h_ee["timestamp"]!=token_timestamp1:   ## next event (break)
                            tlu_flg=0
                            buf_i=buf_ii
                            #print "break"
                            break
                        else: ## TODO copy noise=1 hits also
                            if debug & 0x1 ==0x1 or (noise==0 and h_ee["cnt"]==0):
                                buf[buf_ii]["col"]=h_ee["col"]
                                buf[buf_ii]["row"]=h_ee["row"]
                                buf[buf_ii]["le"]=h_ee["le"]
                                buf[buf_ii]["te"]=h_ee["te"]
                                buf[buf_ii]["flg"]= np.uint8(h_ee["cnt"] | noise)
                                buf[buf_ii]["token_timestamp"]=h_ee["timestamp"]
                                buf[buf_ii]["trigger_number"]=tlu
                                buf[buf_ii]["event_timestamp"]=tlu_timestamp
                                buf[buf_ii]["event_number"]=event_number
                                buf_ii=buf_ii+1
                            #print "find hit", tlu_flg, noise, h_i, veto1, "t1%d"%token_timestamp1, h_ee
                    token_timestamp1=h_ee["timestamp"]
            if tlu_flg==0:
               event_number=event_number+1
            else:
               return 0,buf[:buf_i],h_i-1,token_timestamp,token_timestamp0,veto,tlu_timestamp,tlu,event_number
        else:   
            if h_e["cnt"]==0 and h_e["timestamp"]!=token_timestamp:  ### h["cnt"]==bit30, Begging of new event
                veto=rx_stop
                token_timestamp0=h_e["timestamp"]
            elif h_e["cnt"]==1 and h_e["timestamp"]!=token_timestamp: #noise
                veto=veto+rx_stop
            else:
                veto=veto+rx_shift
            token_timestamp=h_e["timestamp"]
    return 0,buf[:buf_i],h_i,token_timestamp,token_timestamp0,veto,tlu_timestamp,tlu,event_number
    
def build_h5(fraw,fhit,fout,debug=4, n=100000000):
    buf=np.empty(n,dtype=buf_dtype)
    #pre_timestamp=np.uint64(0)
    token_timestamp=np.uint64(0)
    token_timestamp0=np.uint64(0)
    veto=0
    tlu_timestamp=np.uint64(0)
    tlu=0
    event_number=np.int64(0)
    try:
            with tables.open_file(fraw) as f:
                rx_status=f.root.meta_data.attrs["rx_status"]
            rx_status=yaml.load(rx_status)
            rx_stop=rx_status["CONF_STOP"]
            rx_shift=rx_status["CONF_STOP_FREEZE"]-rx_status["CONF_START_READ"]
            rx_freeze_start=rx_status["CONF_START_FREEZE"]
    except:
            rx_stop=138
            rx_shift=36
            rx_freeze_start=90
 
    with tables.open_file(fout, "w") as f_o:
        description=np.zeros((1,),dtype=buf_dtype).dtype
        hit_table=f_o.create_table(f_o.root,name="Hits",description=description,title='hit_data')
        with tables.open_file(fhit) as f:
            end=len(f.root.Hits)
            t0=time.time()
            hit_total=0
            start=0
            
            while True:
                tmpend=min(end,start+n)
#                hit,pre_timestamp=_fix_timestamp(hit,pre_timestamp) ## TODO fix firmware
                hit=f.root.Hits[start:tmpend]
                ( err,buf_out,h_i,token_timestamp,token_timestamp0,veto,
                      tlu_timestamp,tlu,event_number
                      ) = _build_with_tlu(
                      hit,buf,token_timestamp,token_timestamp0,veto,tlu_timestamp,tlu,
                      rx_stop,rx_shift,rx_freeze_start,event_number,debug)

                hit_total=hit_total+len(buf_out)
                if err==0:
                    #print tmpend,h_i,hit[h_i]
                    print "build %d %d %.3f%% %.3fs %dhits"%(start,h_i,100.0*(start+h_i+1)/end,time.time()-t0,hit_total)
                else:
                    print "noise err",err,start,h_i,token_timestamp,token_timestamp0,tlu_timestamp,tlu

                hit_table.append(buf_out)
                hit_table.flush()
                start=start+h_i+1
                if tmpend==end:
                    break

@njit
def _fix_timestamp(hit,pre_timestamp,debug=1):
    for h_i, h in enumerate(hit):
        hit[h_i]["event_timestamp"]=(h["event_timestamp"]& np.uint64(0xFFFFFFFF))+(pre_timestamp & np.uint64(0x7FFFFFFF00000000))
        if hit["event_timestamp"][h_i]+0x7FFFFFFF < pre_timestamp:
           hit["event_timestamp"][h_i]=hit["event_timestamp"][h_i] + 0x100000000
        elif hit["event_timestamp"][h_i] < pre_timestamp + 0x7FFFFFFF:
           hit["event_timestamp"][h_i]=hit["event_timestamp"][h_i] - 0x100000000
        pre_timestamp=hit["event_timestamp"][h_i]
    return hit,pre_timestamp              
    
def convert(hit,offset,row_offset,row_factor,col_offset,col_factor,tr,debug):
    buf_out=np.empty(len(hit),dtype=hit_dtype)
    buf_out["event_number"]=hit["event_number"]
    if tr==True:
        buf_out["row"]=np.array(col_factor*np.array(hit["col"],dtype="int")+col_offset,dtype="<u2")
        buf_out["column"]=np.array(row_factor*np.array(hit["row"],dtype="int")+row_offset,dtype="<u2")
    else:
        buf_out["column"]=np.array(col_factor*np.array(hit["col"],dtype="int")+col_offset,dtype="<u2")
        buf_out["row"]=np.array(row_factor*np.array(hit["row"],dtype="int")+row_offset,dtype="<u2")
    
    buf_out["charge"]= (hit["te"]-hit["le"]) & 0xFF
    buf_out["frame"] = np.int64(hit["token_timestamp"])-np.int64(hit["event_timestamp"])\
            - ( np.int64((hit["token_timestamp"]-hit["te"]+0xF0-offset) & 0xFF)-0xFF)\
            - np.int64(buf_out["charge"])
    return 0, buf_out

def apply_timewindow_tlu(hit,upper_limit=0xFF,lower_limit=0x00):
    sel=np.bitwise_and((hit["token_timestamp"] < hit["event_timestamp"]+upper_limit),
                       (hit["token_timestamp"] > hit["event_timestamp"]+lower_limit))
    return hit[sel]

@njit                  
def _assign_only_one_event(hit,buf,pre_token_timestamp):
    buf_i=0
    h_i_start=0
    ts_min=np.int64(0)
    #MASK=np.uint64(0x7FFFFFFF)
    MASK=np.uint64(0x7FFFFFFFFFFFFFFF)
    for h_i,h in enumerate(hit):
        #print h_i, np.int64(h["token_timestamp"]-h["event_timestamp"]),h["token_timestamp"],pre_token_timestamp
        if h["token_timestamp"]!=pre_token_timestamp:
            ts_min=MASK
            for hh in hit[h_i_start:h_i]:
                ts_tmp=np.abs(np.int64(hh["token_timestamp"] & MASK)-np.int64(hh["event_timestamp"]&MASK))
                ts_min=min(ts_min,ts_tmp) 
            for hh in hit[h_i_start:h_i]:
                ts_tmp=np.abs(np.int64(hh["token_timestamp"] & MASK)-np.int64(hh["event_timestamp"]&MASK))
                if ts_min==np.abs(np.int64(hh["token_timestamp"]-hh["event_timestamp"])):
                    buf[buf_i]=hh 
                    buf_i=buf_i+1
                else:
                    pass
            h_i_start=h_i   
            pre_token_timestamp=h["token_timestamp"]]
    return buf[:buf_i],pre_token_timestamp

def convert_h5(ftlu,fout,n=1000000,row_offset=1,row_factor=1,col_offset=1,col_factor=1,tr=True):
    buf=np.empty(n,dtype=buf_dtype) 
    with tables.open_file(fout, "w") as f_o:
        description=np.zeros((1,),dtype=hit_dtype).dtype
        hit_table=f_o.create_table(f_o.root,name="Hits",description=description,title='hit_data')
        description_tmp=np.zeros((1,),dtype=buf_dtype).dtype
        hit_tmp_table=f_o.create_table(f_o.root,name="Hits_tmp",
                                       description=description_tmp,title='hit_tmp_data')
        with tables.open_file(ftlu) as f:
            end=len(f.root.Hits)
            t0=time.time()
            hit_total=0
            start=0
            while start<end:
                tmpend=min(end,start+n)
                hit=f.root.Hits[start:tmpend]
                hit=hit[np.bitwise_and(hit["col"]<36,hit["flg"]==0)]
                if start==0:
                    offset=get_te_offset(hit,debug=fout[:-2]+"png")
                    pre_token_timestamp=np.int64(hit[0]["token_timestamp"])
                    
                hit_tmp,pre_token_timestamp=_assign_only_one_event(hit,buf,pre_token_timestamp)
                hit_tmp_table.append(hit_tmp)
                hit_tmp_table.flush()

                hit=apply_timewindow_tlu(hit,lower_limit=-100,upper_limit=300)
                
                (err,buf_out
                  )=convert(
                  hit,offset,row_offset=1,row_factor=1,col_offset=1,col_factor=1,tr=True,debug=0)
                  
                hit_total=hit_total+len(buf_out)
                if err==0:
                    print "%d %.3f%% %.3fs %dhits"%(start,100.0*(tmpend)/end,time.time()-t0,hit_total)
                else:
                    print "noise err",err,start,token_timestamp,token_timestamp0,cnt0,tlu_timestamp,tlu,tlu_flg

                hit_table.append(buf_out)
                hit_table.flush()
                start=tmpend

def find_invalid_event_h5(fin,fout,n=1000000):
    with tables.open_file(fout,"w") as f_o:
        description=np.zeros((1,),dtype=[("event_number","<i8")]).dtype
        hit_table=f_o.create_table(f_o.root,name="Triggers",description=description,title='trig_data')
        with tables.open_file(fin) as f:
            end=len(f.root.Hits)
            start=0
            while start<end:
                tmpend=min(end,start+n)
                hit=f.root.Hits[start:tmpend]
                hit=hit[hit["col"]==0xEF][["event_number","flg"]]
                start=tmpend
                hit_out=hit[hit["flg"]==2]["event_number"]
                print "valid=%d"%len(hit[hit["flg"]==0]),"noise=%d"%len(hit[hit["flg"]==1]),"readout=%d"%len(hit_out)
                hit_table.append(hit_out)
                hit_table.flush()
                
@njit
def _veto_event(hit,trigs):
    hit_i=0
    h_i=0
    trig_i=0
    while trig_i < len(trigs) and h_i < len(hit):
         if hit[h_i]["event_number"] == trigs[trig_i]:
              #print "del",h_i,trig_i,hit[h_i]["event_number"],trigs[trig_i]
              h_i=h_i+1
         elif hit[h_i]["event_number"] > trigs[trig_i]:
              #print "nexttrig",h_i,trig_i,hit[h_i]["event_number"],trigs[trig_i]
              trig_i=trig_i+1
         elif hit[h_i]["event_number"] < trigs[trig_i]:
              hit[hit_i]=hit[h_i]
              #print "copy",h_i,trig_i,hit[h_i]["event_number"],trigs[trig_i]
              hit_i=hit_i+1
              h_i=h_i+1
    return hit[:hit_i],trig_i
    
def veto_event_h5(fin,fref,fout,n=10000000):
    if isinstance(fin,str):
        fin=[fin]
    with tables.open_file(fref) as f:
        trigs=f.root.Triggers[:]["event_number"]
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

def get_te_offset(dat,debug=None):
     hist=np.histogram((dat["token_timestamp"]-dat["te"]) & 0xFF, bins=np.arange(0,0x101))
     offset=np.int64(hist[1][np.argmax(hist[0])])
     if debug!=None:
         plt.step(hist[1][:-1],hist[0])
         plt.xlabel("TOKEN-TE")
         plt.title("offset %d"%offset)
         plt.savefig(debug)
     return offset

if __name__ == "__main__":
    import sys

    fraw=sys.argv[1]
    ffe=[]
    for ffe_e in sys.argv[2:]:
        print ffe_e
        ffe.append(ffe_e)

    fhit=fraw[:-3]+"_hit.h5"
    fout=fraw[:-3]+"_tlu.h5"
    fev=fraw[:-3]+"_ev.h5"
    fveto=fraw[:-3]+"_veto.h5"
    ffe2=ffe[0][:-15]+"_vetoed.h5"

    print "================build================"
    build_h5(fraw,fhit,fout,debug=0x3,n=100000000)
    print fout
    print "================convert================"
    convert_h5(fout,fev,n=10000000)
    print fev
    print "================find invalid event================"
    find_invalid_event_h5(fout,fveto)
    print fveto
    print "================veto invalid event================"
    veto_event_h5(ffe,fveto,ffe2)
    print ffe2
