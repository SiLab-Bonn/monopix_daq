import sys,time,os
import numpy as np
import matplotlib.pyplot as plt
from numba import njit
import tables
import yaml

veto_type=[('event_number','<u8'),('event_timestamp','<u8'),
             ('trigger_number','<u4'),('flg','<u1'),('veto_begin','<u8'),('veto_end','<u8')]
@njit
def _find_veto(buf,veto_begin,veto_end):
    idx=0
    for c_i,c in enumerate(buf):
        buf[c_i]["event_number"]=np.int64(c_i)
        for i in range(len(veto_begin[idx:])):
            if c["event_timestamp"] < veto_begin[idx+i]:
                ##buf[c_i]["flg"]=False ##Do not change
                buf[c_i]['veto_begin']=veto_begin[max(idx+i-1,0)]
                buf[c_i]['veto_end']=veto_end[max(idx+i-1,0)]
                #print (c_i,idx,i),"not found", (c["event_timestamp"], veto_begin[idx+i])
                idx=max(0,idx+i-1)
                break
            else:
                if c["event_timestamp"] <= veto_end[idx+i]:
                    buf[c_i]["flg"]= True 
                    buf[c_i]['veto_begin']=veto_begin[idx+i]
                    buf[c_i]['veto_end']=veto_end[idx+i]
                    #print (c_i,idx,i),"found!!!",(c["event_timestamp"],veto_begin[idx+i],veto_end[idx+i])
                    idx=max(0,idx+i)
                    break
                else: ## c["event_timestamp"] > veto_end[idx+i]:
                    pass
    return buf

def find_veto_h5(fin,fout,fparam=None,fref=None):
    ###############
    ## get parameters
    if fparam==None:
        rx_stop=147
        rx_shift=137-99
        rx_freeze=95
    else:
        try:
            with tables.open_file(fparam) as f:
                rx_status=yaml.load(f.root.meta_data.attrs.rx_status[:])
                print "find_veto_h5() rx_status",rx_status
                rx_stop=np.uint64(rx_status["CONF_STOP"])
                rx_shift=np.uint64(rx_status["CONF_STOP_FREEZE"]-rx_status["CONF_START_READ"])
                rx_freeze=np.uint64(rx_status["CONF_START_FREEZE"])
        except:
            rx_stop=147
            rx_shift=137-99
            rx_freeze=95
            print "find_veto_h5() no rx info in raw.h5 %d %d %d"%(rx_freeze,rx_shift,rx_stop)

    ###############
    ## read data  
    with tables.open_file(fin) as f:
        hit=f.root.Hits[:]    
    arg_tlu=np.argwhere(hit["col"]==0xFF)
    tlu=hit[hit["col"]==0xFF]
    mono=hit[hit["col"]<36]
    print "find_veto_h5() TLU=%d"%len(tlu),"TS1=%d"%len(hit[hit["col"]==0xFE]),
    print "TS2=%d"%len(hit[hit["col"]==0xFD]),"MONO=%d"%len(mono)
    
    buf=np.empty(len(tlu),dtype=veto_type)
    buf["event_timestamp"]=tlu["timestamp"]
    buf["trigger_number"]=tlu["cnt"]

    ###############
    ## mark when mimosa is not running
    arg=np.argwhere(np.bitwise_or(hit["col"]==0xFE,hit["col"]==0xFD))
    if len(arg)==0:
        buf["flg"]=np.zeros(len(tlu),dtype="bool")
    elif len(arg)!=0:
        print "find_veto_h5() delete data before 2nd mframe idx=%d"%arg[1]
        print "find_veto_h5() delete data after last mframe idx=%d"%(arg[-1]),"n_of_del_data=%d"%(len(hit)-arg[-1])
        print "find_veto_h5() 1st=%x,%x"%(hit["timestamp"][arg[0]-1],hit["timestamp"][arg[0]]),
        print "2nd=%x,%x"%(hit["timestamp"][arg[1]-1],hit["timestamp"][arg[1]])
        
        buf["flg"]=np.bitwise_or(arg_tlu[:,0]<arg[1][0],arg_tlu[:,0]>arg[-1][0])
        
        print "find_veto_h5() mark %d tlu_triggers(%.3f%%)"%(
            len(np.argwhere(buf["flg"]==True)),100.0*len(np.argwhere(buf["flg"]==True))/len(tlu))

    ###############
    ## check timestamp
    arg=np.argwhere(np.bitwise_and(tlu["timestamp"][1:] < tlu["timestamp"][:-1],
                                   buf["flg"][1:]==False))
    print 'find_veto_h5() TLU: increase only',len(arg)==0
    for a_i,a in enumerate(arg):
        print a_i,"ERROR! fix data!!! idx=%d"%a[0],tlu["timestamp"][a[0]],tlu["timestamp"][a[0]+1]
        if a_i>10:
            print "more... %d in total"%(len(arg))            
            
    arg=np.argwhere(mono["timestamp"][1:] < mono["timestamp"][:-1])
    print 'find_veto_h5() MONO: increase only',len(arg)==0
    for a_i,a in enumerate(arg):
        print a_i,"ERROR! fix data!!! idx=%d"%a[0],mono["timestamp"][a[0]],mono["timestamp"][a[0]+1]
        if a_i>10:
            print "more... %d in total"%(len(arg))

    ###############
    ## mark when monopix is busy 
    veto_begin,cnt=np.unique(mono["timestamp"],return_counts=True)
    veto_end=rx_stop+np.uint64(cnt[:]-1)*rx_shift+veto_begin
    veto_begin=veto_begin+rx_freeze    
    buf = _find_veto(buf,veto_begin,veto_end)
    
    ###############
    ## correct event_number 
    if fref!=None:
        with tables.open_file(fref) as f:
            ref=f.root.Hits[:][["trigger_number","event_number"]]
        idx_type=[("id","<u2"),("idx1","<u8"),("idx2","<u8")]
        idx_buf=np.empty(len(buf),dtype=idx_type)
        err,idx_buf,dummy,dummy=_correlate(buf["trigger_number"],ref["trigger_number"],idx_buf,mode=0x7,mask=0x4000)
        buf=buf[idx_buf["idx1"]]
        buf["event_number"]=ref["event_number"][idx_buf["idx2"]]
    
    with tables.open_file(fout,"w") as f_o:
        description=np.zeros((1,),dtype=veto_type).dtype
        hittmp_table=f_o.create_table(f_o.root,name="Triggers_tmp",description=description,title='hit_data')
        hittmp_table.append(buf)
        hittmp_table.flush()
        
        description=np.zeros((1,),dtype=veto_type).dtype
        hit_table=f_o.create_table(f_o.root,name="Triggers",description=description,title='hit_data')
        hit_table.append(buf[buf["flg"]==True])
        hit_table.flush()
 
    print "number of veto tlu %d"%len(buf[buf["flg"]==True]),"total number of tlu=%d"%len(buf),
    print "%f%%"%(100.0*len(buf[buf["flg"]==True])/len(buf))
     
@njit
def _correlate(dat1,dat2,buf,mode,mask):
    d1_idx=0
    d2_idx=0
    buf_i=0
    #print mode & 0x3
    while d1_idx < len(dat1) and d2_idx < len(dat2):
        #print d1_idx,d2_idx,dat1[d1_idx],dat2[d2_idx],
        if (dat1[d1_idx]-dat2[d2_idx]) & mask==mask:
            #print "next1"
            d1_idx=d1_idx+1
        elif (dat2[d2_idx]-dat1[d1_idx]) & mask==mask :
            #print "next2"
            d2_idx=d2_idx+1
        else: ##dat1[d1_idx]==dat2[d2_idx]
            for d1_i,d1 in enumerate(dat1[d1_idx:]):
                if dat1[d1_idx]!=d1:
                    break
            for d2_i,d2 in enumerate(dat2[d2_idx:]):
                if dat2[d2_idx]!=d2:
                    break
            #print "eq",d1_i,d2_i
            
            if dat1[d1_idx]==d1:
                if (mode & 0x4) ==0x4:
                    d1_i=d1_i+1
                else:
                    #print "more dat1",(dat1[d1_idx],dat1[-1],dat2[d2_idx],dat2[-1])
                    return 1,buf[:buf_i],d1_idx,d2_idx
            if dat2[d2_idx]==d2:
                if (mode & 0x4) == 0x4:
                    d2_i=d2_i+1
                else:
                    #print "more dat2",(dat1[d1_idx],dat1[-1],dat2[d2_idx],dat2[-1])
                    return 2,buf[:buf_i],d1_idx,d2_idx
            if len(buf)-buf_i <= d1_i*d2_i:
                #print "buffer full",(len(buf),buf_i,d1_i,d2_i)
                return 3,buf[:buf_i],d1_idx,d2_idx

            if (mode & 0x3) ==0x1:
                #print "mode1",d1_i,d2_i
                for c1_i in range(d1_i):
                    for c2_i in range(d2_i):
                        #print idx1[u1_i],idx2[u2_i],c1_i,c2_i,"event_number",hit1[idx1[u1_i]+c1_i],hit2[idx2[u2_i]+c2_i]
                        buf[buf_i]["idx1"]=d1_idx+c1_i
                        buf[buf_i]["idx2"]=d2_idx+c2_i
                        buf[buf_i]["id"]=dat2[d2_idx]
                        buf_i=buf_i+1                
            elif (mode & 0x3) ==0x2:
                for c_i in range(max(d1_i,d2_i)):
                    if c_i<d1_i:
                        buf[buf_i]["idx1"]=d1_idx+c_i
                    else:
                        buf[buf_i]["idx1"]=len(dat1)
                    if c_i<d2_i:
                        buf[buf_i]["idx2"]=d2_idx+c_i
                    else:
                        buf[buf_i]["idx2"]=len(dat2)
                    buf[buf_i]["id"]=dat2[d2_idx]
                    buf_i=buf_i+1
            elif (mode & 0x3) == 0x3:
                #print "mode3",d1_idx,d2_idx
                for c1_i in range(d1_i):
                    buf[buf_i]["idx1"]=d1_idx+c1_i
                    buf[buf_i]["idx2"]=d2_idx
                    buf[buf_i]["id"]=dat2[d2_idx]
                    buf_i=buf_i+1
            d1_idx=d1_idx+d1_i
            d2_idx=d2_idx+d2_i
    if d2_idx < len(dat2):
         # print read data2 more
         return 2,buf[:buf_i],d1_idx,d2_idx
    elif d1_idx < len(dat1):
         # print read data2 more
         return 1,buf[:buf_i],d1_idx,d2_idx
    return 0,buf[:buf_i],d1_idx,d2_idx

@njit
def _veto_event(hit,trigs):
    hit_i=0
    h_i=0
    trig_i=0
    while trig_i < len(trigs) and h_i < len(hit):
         hit_trig= hit[h_i]["event_number"]
         trig=trigs[trig_i]
         if hit_trig == trig:
              #print "del",h_i,trig_i,hit[h_i]["event_number"],trigs[trig_i]
              h_i=h_i+1
         elif hit_trig > trig:
              #print "nexttrig",h_i,trig_i,hit[h_i]["event_number"],trigs[trig_i]
              trig_i=trig_i+1
         else:
              hit[hit_i]=hit[h_i]
              #print "copy",h_i,trig_i,hit[h_i]["event_number"],trigs[trig_i]
              hit_i=hit_i+1
              h_i=h_i+1
    return hit[:hit_i],trig_i
    
def veto_event_h5(fin,fveto,fout,n=10000000):
    print "veto_event_h5() fveto= %s"%fveto
    with tables.open_file(fveto) as f:
        trigs=f.root.Triggers[:]["event_number"]
        trig_i=0
    print "veto_event_h5() veto %dtriggers"%len(trigs)

    with tables.open_file(fout,"w") as f_o:
        hit_cnt=0
        t0=time.time()
        with tables.open_file(fin) as f:
            hit_table=f_o.create_table(f_o.root,name="Hits",description=f.root.Hits.description,title='hit_data')
            start=0
            end=len(f.root.Hits)
            print "veto_event_h5() input_file %s"%(fin)
            print "veto_event_h5() #_fe_hit=%d"%end
            while start<end:
                tmpend=min(end,start+n)
                hit=f.root.Hits[start:tmpend]
                #print "trig_i",trig_i
                #print "hit",hit["event_number"]
                #print "trigs",trigs[trig_i:]
                hit,trig_i=_veto_event(hit,trigs[trig_i:])
                hit_cnt=hit_cnt+len(hit)
                print "veto_event_h5() hit=%d(%.3f%%) total_hit=%d %.3fs %3.f%%done"%(
                      len(hit),100.0*len(hit)/(tmpend-start),hit_cnt,
                      time.time()-t0,100.0*tmpend/end)
                hit_table.append(hit)
                hit_table.flush()
                start=tmpend
                
if __name__ == "__main__":
    import sys,string
    if len(sys.argv)<3:
        print " veto_ref.py <mono_raw file> <fe_ev>"

    fraw=sys.argv[1]
    fhit=fraw[:-3]+"_hit.h5"
    fveto=fraw[:-3]+"_ref.h5"

    ffe=sys.argv[2]

    fout=string.join(ffe.split("_")[:-1],"_")+"_vetoed.h5"
    
    find_veto_h5(fraw,fhit,fout=fveto,fref=ffe)
    veto_event_h5(fin=ffe,fveto=fveto,fout=fout,n=10000000)
    
