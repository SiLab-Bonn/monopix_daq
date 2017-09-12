import sys,time,os
import numpy as np
import matplotlib.pyplot as plt
from numba import njit
import tables
import yaml
               
hit_dtype=np.dtype([("event_number","<i8"),("column","<u2"),("row","<u2"),("charge","<u1"),("frame","<u1")])
                    
#inter_type=np.dtype([("col","<u1"),("row","<u1"),("le","<u1"),("te","<u1"),("cnt","<u4")
#                    ("timestamp","<i8")])

buf_dtype=np.dtype([("col","<u1"),("row","<u1"),("le","<u1"),("te","<u1"),("flg","<u1"),
                    ("token_timestamp","<u8"),("event_number","<u4"),("event_timestamp","<u8")])

@njit
def _build_with_tlu(hit,buf,token_timestamp,token_timestamp0,veto,
               tlu_timestamp,tlu,rx_stop,rx_shift,rx_freeze_start,debug):
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
                    #print "ts-1",h_ee["timestamp"]
                    #print h_ii,
                    pass
                elif h_ee["col"]==255:
                    #print "tlu%d"%h_ii,
                    pass
                else:
                    if tlu_flg==1:
                        if h_ee["cnt"]==0 and h_ee["timestamp"]!=token_timestamp1: # Find event
                            if h_ee["timestamp"] + rx_freeze_start < tlu_timestamp :
                                token_timestamp01=h_ee["timestamp"]
                                veto1=rx_stop
                                #print "change token0 new%d"%token_timestamp01,"old%d"%token_timestamp0
                            elif token_timestamp01 + np.uint64(veto1) > tlu_timestamp: 
                                noise=2
                                tlu_flg=2
                            else:
                                noise=0
                                tlu_flg=2
                                #print "tlu", tlu_flg, h_i, veto, token_timestamp, h_e
                                #print "noise2", h_i,h_ii+h_i+1,tlu_timestamp,"t0%d"%token_timestamp0,"t1%d"%token_timestamp1,h_ee
                            if tlu_flg==2 and debug & 0x2==0x2:
                                buf[buf_ii]["col"]=0xFF
                                buf[buf_ii]["row"]=0xFF
                                buf[buf_ii]["le"]= np.uint8(veto & 0xFF)
                                buf[buf_ii]["te"]= np.uint8((veto>>16) & 0xFF)
                                buf[buf_ii]["flg"]= np.uint8(noise)
                                buf[buf_ii]["token_timestamp"]=token_timestamp0
                                buf[buf_ii]["event_number"]=tlu
                                buf[buf_ii]["event_timestamp"]=tlu_timestamp
                                buf_ii=buf_ii+1
                            if tlu_flg==2 and (debug & 0x1 ==0x1 or (noise==0 and h_ee["cnt"]==0)):
                                buf[buf_ii]["col"]=h_ee["col"]
                                buf[buf_ii]["row"]=h_ee["row"]
                                buf[buf_ii]["le"]=h_ee["le"]
                                buf[buf_ii]["te"]=h_ee["te"]
                                buf[buf_ii]["flg"]= np.uint8(h_ee["cnt"] | noise)
                                buf[buf_ii]["token_timestamp"]=h_ee["timestamp"]
                                buf[buf_ii]["event_number"]=tlu
                                buf[buf_ii]["event_timestamp"]=tlu_timestamp
                                buf_ii=buf_ii+1
                                #print "tlu", tlu_flg, h_i, veto, token_timestamp, h_e
                                #print "find", tlu_flg, h_ii,veto1,"noise%d"%noise,"t0%d"%token_timestamp0,"t1%d"%token_timestamp1, h_ee,
                                #print tlu_timestamp,h_ee["timestamp"],np.int64(h_ee["timestamp"])-np.int64(tlu_timestamp)
                                #if tlu==504:
                                #    print "token",h_ee["timestamp"],"rx_freeze_start",rx_freeze_start,"tlu",tlu_timestamp
                                #    sys.exit()
                        elif h_ee["cnt"]==1 and h_ee["timestamp"]!=token_timestamp1: # not begging of event
                            veto1=veto1+rx_stop
                            #print "search noise", tlu_flg, noise, h_ii, veto1, "t1%d"%token_timestamp1, h_ee
                        else: # not begging of event
                            veto1=veto1+rx_shift
                            #print "search 2nd pix",tlu_flg, noise, h_i,veto1, "t1%d"%token_timestamp1, h_ee
                    elif tlu_flg==2:
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
                                buf[buf_ii]["event_number"]=tlu
                                buf[buf_ii]["event_timestamp"]=tlu_timestamp
                                buf_ii=buf_ii+1
                            #print "find hit", tlu_flg, noise, h_i, veto1, "t1%d"%token_timestamp1, h_ee
                    token_timestamp1=h_ee["timestamp"]
            if tlu_flg!=0:
               return 0,buf[:buf_i],h_i-1,token_timestamp,token_timestamp0,veto,tlu_timestamp,tlu
        else:   
            if h_e["cnt"]==0 and h_e["timestamp"]!=token_timestamp:  ### h["cnt"]==bit30, Begging of new event
                veto=rx_stop
                token_timestamp0=h_e["timestamp"]
                #print "beging", tlu_flg,  h_i,veto, token_timestamp, h_e
            elif h_e["cnt"]==1 and h_e["timestamp"]!=token_timestamp: #noise
                veto=veto+rx_stop
                #print "noise", tlu_flg, h_i,veto, token_timestamp, h_e
            else:
                veto=veto+rx_shift
                #print "2nd pix",tlu_flg, h_i,veto, token_timestamp, h_e
            token_timestamp=h_e["timestamp"]
    return 0,buf[:buf_i],h_i,token_timestamp,token_timestamp0,veto,tlu_timestamp,tlu
    
    
@njit
def _build_with_token(hit,buf,token_timestamp,token_timestamp0,cnt0,debug):
    buf_i=0
    for h_i,h in enumerate(hit):
        if h["col"]==254:
            pass
        elif h["col"]==255:
            pass
        else:   
            if h["cnt"]==0 and h["timestamp"]!=token_timestamp:
                cnt0=cnt0+1
                token_timestamp0=h["timestamp"]
            if (debug & 0x1 == 0x1) or (h["cnt"]==0):
                buf[buf_i]["col"]=h["col"]
                buf[buf_i]["row"]=h["row"]
                buf[buf_i]["le"]=h["le"]
                buf[buf_i]["te"]=h["te"]
                buf[buf_i]["flg"]= h["cnt"]
                buf[buf_i]["token_timestamp"]=h["timestamp"]
                buf[buf_i]["event_number"]=cnt0
                buf[buf_i]["event_timestamp"]=token_timestamp0
                buf_i=buf_i+1
            token_timestamp=h["timestamp"]
    return 0,buf[:buf_i],h_i,token_timestamp,token_timestamp0,cnt0
    
def build_h5(fraw,fhit,fout,event="tlu",debug=4, n=100000000):
    buf=np.empty(n,dtype=buf_dtype)
    token_timestamp=np.uint64(0)
    token_timestamp0=np.uint64(0)
    if event=="tlu":
        vito=0
        noise=0
        tlu_timestamp=np.uint64(0)
        tlu=0
        tlu_flg=0
        try:
            with tables.open_file(fraw) as f:
                rx_status=f.root.meta_data.attrs["rx_status"]
            rx_status=yaml.load(rx_status)
            rx_stop=rx_status["CONF_STOP"]
            rx_shift=rx_status["CONF_STOP_FREEZE"]-rx_status["CONF_START_READ"]
            rx_freeze_start=rx_status["CONF_START_FREEZE"]
        except:
            rx_stop=98
            rx_shift=36
            rx_freeze_start=50
    else:
        cnt0=0
 
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
                hit=f.root.Hits[start:tmpend]
                if event=="tlu":
                    ( err,buf_out,h_i,token_timestamp,token_timestamp0,vito,
                      tlu_timestamp,tlu
                      ) = _build_with_tlu(
                      hit,buf,token_timestamp,token_timestamp0,vito,tlu_timestamp,tlu,
                      rx_stop,rx_shift,rx_freeze_start,debug)
                else:
                    (err,buf_out,h_i,token_timestamp,token_timestamp0,cnt0
                      )=_build_with_token(
                      hit,buf,token_timestamp,token_timestamp0,cnt0,debug)

                hit_total=hit_total+len(buf_out)
                if err==0:
                    print "%d %d %.3f%% %.3fs %dhits"%(start,h_i,100.0*(start+h_i+1)/end,time.time()-t0,hit_total)
                else:
                    print "noise err",err,start,h_i,token_timestamp,token_timestamp0,tlu_timestamp,tlu

                hit_table.append(buf_out)
                hit_table.flush()
                #if debug &0x4 ==0x4 and start==0:
                #   n=100
                #   print "+++++++++++++++++++++++++++++="
                #else:
                #   print debug, start
                #   break
                start=start+h_i+1
                if tmpend==end:
                    break
                
                   
def convert(hit,pre_event_number,offset,row_offset,row_factor,col_offset,col_factor,tr,debug):
    buf_out=np.empty(len(hit),dtype=hit_dtype)
    if tr==True:
        buf_out["row"]=np.array(col_factor*np.array(hit["col"],dtype="int")+col_offset,dtype="<u2")
        buf_out["column"]=np.array(row_factor*np.array(hit["row"],dtype="int")+row_offset,dtype="<u2")
    else:
        buf_out["column"]=np.array(col_factor*np.array(hit["col"],dtype="int")+col_offset,dtype="<u2")
        buf_out["row"]=np.array(row_factor*np.array(hit["row"],dtype="int")+row_offset,dtype="<u2")
    
    buf_out["charge"]= (hit["te"]-hit["le"]) & 0xFF
    #te_timestamp = hit["token_timestamp"] - (hit["te"]-hit["token_timestamp"])&0xFF - offset + 0x10)
    buf_out["frame"]= (hit["le"]- hit["event_timestamp"]) & 0xFF
    
    buf_out["event_number"]=np.int64(hit["event_number"])+(pre_event_number & np.int64(0x7FFFFFFFFFFF8000))
    arg=np.argwhere((buf_out["event_number"][:]-np.append(pre_event_number,buf_out["event_number"][:-1])) & 0x7FFF > 0x3FFF)
    for a in arg:
        buf_out["event_number"][arg:] = buf_out["event_number"][arg:]+0x8000
    pre_event_number=buf_out["event_number"][-1]
    
    return 0,buf_out,pre_event_number
                   
def convert_h5(ftlu,fout,n=1000000,row_offset=1,row_factor=1,col_offset=1,col_factor=1,tr=True):
    
    with tables.open_file(fout, "w") as f_o:
        description=np.zeros((1,),dtype=hit_dtype).dtype
        hit_table=f_o.create_table(f_o.root,name="Hits",description=description,title='hit_data')
        with tables.open_file(ftlu) as f:
            end=len(f.root.Hits)
            pre_event_number=np.int64(f.root.Hits[0]["event_number"])
            t0=time.time()
            hit_total=0
            start=0
            while start<end:
                tmpend=min(end,start+n)
                hit=f.root.Hits[start:tmpend]
                if start==0:
                    offset=get_te_offset(hit,debug=fout[:-2]+"png")

                err,buf_out,pre_event_number=convert(
                  hit,pre_event_number,offset,row_offset=1,row_factor=1,col_offset=1,col_factor=1,tr=True,debug=0)
                  
                hit_total=hit_total+len(buf_out)
                if err==0:
                    print "%d %.3f%% %.3fs %dhits"%(start,100.0*(tmpend)/end,time.time()-t0,hit_total)
                else:
                    print "noise err",err,start,token_timestamp,token_timestamp0,cnt0,tlu_timestamp,tlu,tlu_flg

                hit_table.append(buf_out)
                hit_table.flush()
                start=tmpend
      
def get_te_offset(dat,debug=None):
     hist=np.histogram((dat["te"]-dat["token_timestamp"]) & 0xFF, bins=np.arange(0,0x101))
     if debug!=None:
         plt.step(hist[1][:-1],hist[0])
         plt.xlabel("TE-TOKEN")
         plt.savefig(debug)
     offset=hist[1][np.argmax(hist[0])]
     return offset
    
class BuildWithTlu():
    def __init__(self,chunck=100000,rx_stop=130,rx_read=52,
                 row_offset=1,row_factor=1,col_offset=1,col_factor=1,tr=True):
        self.reset()
        self.set_rx_stop(rx_stop,rx_read)
        self.set_orientation(self,row_offset,row_factor,col_offset,col_factor,tr)
        self.buf=np.empty(chunk,dtype=hit_dtype)
        self.n=chunk

    def set_orientation(self,row_offset,row_factor,col_offset,col_factor,tr):
        self.tr=tr
        self.row_offset=row_offset
        self.row_factor=row_factor
        self.col_offset=col_offset
        self.col_factor=col_factor

    def set_rx_params(self,rx_stop,rx_read):
        self.rx_stop=rx_stop
        self.rx_read=rx_read
        
    def reset(self):
        self.token_timestamp=np.uint64(0)
        self.token_timestamp0=np.uint64(0)
        self.cnt0=0
        self.noise=0
        self.tlu_timestamp=np.uint64(0)
        self.tlu=0
        self.tlu_flg=0
        self.offset=None
        self.event_number=0
        
    def set_te_offset(self,dat):
        self.offset=get_te_offset(dat)
        return self.offset
    
    def run(self,raw):
        start=0
        end=len(raw)
        ret=np.empty(0,dtype=hit_dtype)
        while start<end: ##TODO make chunck work
            tmpend=min(end,start+self.n)
            ( err,buf_data,h_i,
              self.token_timestamp,self.token_timestamp0,self.cnt0,self.noise,
              self.tlu_timestamp,self.tlu,self.tlu_flg
              ) = _build(
              raw[start,tmpend],self.buf,
              self.token_timestamp,self.token_timestamp0,self.cnt0,self.noise,
              self.tlu_timestamp,self.tlu,self.tlu_flg,
              self.rx_stop,0)
            if err!=0:
                self.reset()
            start=start+h_i+1
            
            if len(buf_data)==0:
                continue
                
            if self.offset==None:
                self.set_te_offset()
            err,ret_data,self.pre_event_number=convert(
                  hit,self.pre_event_number,self.offset,
                  self.row_offset,self.row_factor,self.col_offset,col_factor,self.tr,
                  0)
                            
            ret=np.append(ret,ret_data)
            
        return ret
        
if __name__ == "__main__":
    import sys

    event=sys.argv[1]
    fraw=sys.argv[2]
    
    fhit=fraw[:-7]+"_hit.h5"
    fout=fraw[:-7]+"_%s.h5"%event
    fev=fraw[:-7]+"_ev.h5"

    build_h5(fraw,fhit,fout,event=event,debug=0x3,n=100000000)
    print fout
    ##convert_h5(fout,fev,n=100000000)
    print fev

