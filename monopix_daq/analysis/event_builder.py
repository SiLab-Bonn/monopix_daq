import sys,time,os
import numpy as np
import matplotlib.pyplot as plt
from numba import njit
import tables
import yaml
               
hit_dtype=np.dtype([("event_number","<i8"),("column","<u2"),("row","<u2"),("charge","<u2"),("frame","<u1")])
                    
#inter_type=np.dtype([("col","<u1"),("row","<u1"),("le","<u1"),("te","<u1"),("cnt","<u4")
#                    ("timestamp","<i8")])

buf_dtype=np.dtype([("col","<u1"),("row","<u1"),("le","<u1"),("te","<u1"),("flg","<u1"),
                    ("token_timestamp","<u8"),("tlu","<u4"),("tlu_timestamp","<u8")])

@njit
def _build_with_tlu(hit,buf,token_timestamp,token_timestamp0,cnt0,noise,
               tlu_timestamp,tlu,tlu_flg,rx_stop,debug):
    buf_i=0
    for h_i,h in enumerate(hit):
        if h["col"]==254:
            pass
        elif h["col"]==255:
            tlu_timestamp=h["timestamp"]
            tlu=h["cnt"]
            tlu_flg=1
        else:   
            if h["cnt"]==0 and h["timestamp"]!=token_timestamp:  ### h["cnt"]==bit30, Begging of new event
                if tlu_flg==1:
                    tlu_flg=2
                    if token_timestamp0 + np.uint64(cnt0*rx_stop) < tlu_timestamp:
                        noise=0
                    else:
                        noise=2
                    if debug & 0x1 == 0x1 or noise==2:
                        buf[buf_i]["col"]=0xEF
                        buf[buf_i]["row"]=0xFF
                        buf[buf_i]["le"]=cnt0
                        buf[buf_i]["te"]=0xFF
                        buf[buf_i]["flg"]= np.uint8(h["cnt"] | noise)
                        buf[buf_i]["token_timestamp"]=token_timestamp0
                        buf[buf_i]["tlu"]=tlu
                        buf[buf_i]["tlu_timestamp"]=tlu_timestamp
                        buf_i=buf_i+1
                else:
                    tlu_flg=0
                cnt0=1
                token_timestamp0=h["timestamp"]
            else:
                cnt0=cnt0+1
            if tlu_flg==2 and (debug & 0x1 == 0x1 or noise==0):
                buf[buf_i]["col"]=h["col"]
                buf[buf_i]["row"]=h["row"]
                buf[buf_i]["le"]=h["le"]
                buf[buf_i]["te"]=h["te"]
                buf[buf_i]["flg"]= np.uint8(h["cnt"] | noise)
                buf[buf_i]["token_timestamp"]=h["timestamp"]
                buf[buf_i]["tlu"]=tlu
                buf[buf_i]["tlu_timestamp"]=tlu_timestamp
                buf_i=buf_i+1

            token_timestamp=h["timestamp"]

    return 0,buf[:buf_i],h_i,token_timestamp,token_timestamp0,cnt0,noise,tlu_timestamp,tlu,tlu_flg
 
def build_with_tlu_h5(fraw,fhit,fout,debug=3, n=100000000):
    buf=np.empty(n,dtype=buf_dtype)
    token_timestamp=np.uint64(0)
    token_timestamp0=np.uint64(0)
    cnt0=0
    noise=0
    tlu_timestamp=np.uint64(0)
    tlu=0
    tlu_flg=0
    
    with tables.open_file(fraw) as f:
        rx_status=f.root.meta_data.attrs["rx_status"]
    rx_status=yaml.load(rx_status)
    rx_stop=rx_status["CONF_STOP"]
 
    with tables.open_file(fout, "w") as f_o:
        description=np.zeros((1,),dtype=buf_dtype).dtype
        hit_table=f_o.create_table(f_o.root,name="Hits",description=description,title='hit_data')
        with tables.open_file(fhit) as f:
            end=len(f.root.Hits)
            t0=time.time()
            hit_total=0
            start=0
            while start<end:
                tmpend=min(end,start+n)
                hit=f.root.Hits[start:tmpend]

                ( err,buf_out,h_i,token_timestamp,token_timestamp0,cnt0,noise,
                  tlu_timestamp,tlu,tlu_flg
                  ) = _build_with_tlu(
                  hit,buf,token_timestamp,token_timestamp0,cnt0,noise,tlu_timestamp,tlu,tlu_flg,
                  rx_stop,debug)

                hit_total=hit_total+len(buf_out)
                if err==0:
                    print "%d %d %.3f%% %.3fs %dhits"%(start,h_i,100.0*(start+h_i+1)/end,time.time()-t0,hit_total)
                else:
                    print "noise err",err,start,h_i,token_timestamp,token_timestamp0,cnt0,tlu_timestamp,tlu,tlu_flg

                hit_table.append(buf_out)
                hit_table.flush()
                start=start+h_i+1
                if debug &0x4 ==0x4:
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
    te_timestamp = hit["token_timestamp"] - (hit["te"]-hit["token_timestamp"])&0xFF - offset + 0x10)
    buf_out["frame"]= (hit["le"]- hit["tlu_timestamp"]) & 0xFF
    
    buf_out["event_number"]=np.int64(hit["tlu"])+ (pre_event_number&0xFFFFFFFFFFFF8000)
    arg=np.argwhere((buf_out["event_number"][:]-np.append(pre_event_number,buf_out["event_number"][:-1])) & 0x7FFF > 0x3FFF)
    for a in arg:
        buf_out["event_number"][arg:] = buf_out["event_number"][arg:]+0x8000
    pre_event_number=buf_out["event_number"][-1]
    
    return 0,buf_out,pre_event_number
                   
def convert_h5(ftlu,fout,n=1000000,row_offset=1,row_factor=1,col_offset=1,col_factor=1,tr=True):
    pre_event_number=-1
    with tables.open_file(fout, "w") as f_o:
        description=np.zeros((1,),dtype=hit_dtype).dtype
        hit_table=f_o.create_table(f_o.root,name="Hits",description=description,title='hit_data')
        with tables.open_file(ftlu) as f:
            end=len(f.root.Hits)
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
    def __init__(self,chunck=100000,rx_stop=130,row_offset=1,row_factor=1,col_offset=1,col_factor=1,tr=True):
        self.reset()
        self.set_rx_stop(rx_stop)
        self.set_orientation(self,row_offset,row_factor,col_offset,col_factor,tr)
        self.buf=np.empty(chunk,dtype=hit_dtype)
        self.n=chunk

    def set_orientation(self,row_offset,row_factor,col_offset,col_factor,tr):
        self.tr=tr
        self.row_offset=row_offset
        self.row_factor=row_factor
        self.col_offset=col_offset
        self.col_factor=col_factor

    def set_rx_stop(self,rx_stop):
        self.rx_stop=rx_stop
        
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

    fraw=sys.argv[1]
    fhit=fraw[:-7]+"hit.h5"
    ftlu=fraw[:-7]+"tlu.h5"
    fev=fraw[:-7]+"ev.h5"

    build_with_tlu_h5(fraw,fhit,ftlu,debug=3,n=100000000)
    print ftlu
    
    convert_h5(ftlu,fev,n=100000000)
    print fev
