import sys,time,os
import numpy as np
import matplotlib.pyplot as plt
from numba import njit
import tables

hit_dtype=np.dtype([("col","<u1"),("row","<u1"),("le","<u1"),("te","<u1"),("noise","<u1"),
                    ("timestamp","<u8"),("cnt","<u4")])

@njit
def _interpret(raw,buf,col,row,le,te,noise,timestamp,rx_flg,trig_timestamp,ts_flg,mframe,tlu,tlu_timestamp,debug):
    MASK1    =np.uint64(0x0000000000000FFF)
    NOT_MASK1=np.uint64(0x000FFFFFFFFFF000)
    MASK2    =np.uint64(0x0000000000FFF000)
    NOT_MASK2=np.uint64(0x000FFFFFFF000FFF)
    MASK3    =np.uint64(0x000FFFFFFF000000)
    NOT_MASK3=np.uint64(0x0000000000FFFFFF)
    TS_MASK_DAT        =0x0000000000FFFFFF
    TS_MASK1 =np.uint64(0xFFFFFFFFFF000000)
    TS_MASK2 =np.uint64(0xFFFF000000FFFFFF)
    TS_MASK3 =np.uint64(0x0000FFFFFFFFFFFF)

    buf_i=0
    for r_i,r in enumerate(raw):
        ########################
        ### MONOPIX_RX
        ########################
        if (r & 0xF0000000 == 0x10000000):
           col= (r & 0x3F)
           row= (r >> 8) & 0xFF
           timestamp= (timestamp & NOT_MASK1) | (np.uint64(r >> 16) & MASK1)
           noise = (r >> 6)  & 0x1
           if debug & 0x4 ==0x4:
               #print r_i,hex(r),rx_flg,"ts=",hex(timestamp),col,row,noise
               pass
           if rx_flg==0x0:
              rx_flg=0x1
           else:
              return 1,buf[:buf_i],r_i,col,row,le,te,noise,timestamp,rx_flg,trig_timestamp,ts_flg,mframe,tlu,tlu_timestamp
           
        elif (r & 0xF0000000 == 0x20000000):
           te = (r & 0xFF)
           le = (r >> 8) &  0xFF           
           timestamp = (timestamp & NOT_MASK2) | (np.uint64(r >> 4) & MASK2)  ### >>16 + <<12
           if debug & 0x4 ==0x4:
               #print r_i,hex(r),rx_flg,"ts=",hex(timestamp),le,te
               pass
               
           if rx_flg==0x1:
              rx_flg=0x2
           else:
              return 2,buf[:buf_i],r_i,col,row,le,te,noise,timestamp,rx_flg,trig_timestamp,ts_flg,mframe,tlu,tlu_timestamp

        elif (r & 0xF0000000 == 0x30000000):
           timestamp=(timestamp & NOT_MASK3) | ((np.int64(r) << np.uint64(24)) & MASK3)
           if debug & 0x4 ==0x4:
               #print r_i,hex(r),rx_flg,"ts=",hex(timestamp)
               pass
               
           if rx_flg == 0x2:
               buf[buf_i]["row"]=row
               buf[buf_i]["col"]=col
               buf[buf_i]["noise"]=noise
               buf[buf_i]["le"]=le
               buf[buf_i]["te"]=te
               buf[buf_i]["timestamp"]= timestamp
               buf[buf_i]["cnt"]=tlu
               buf_i=buf_i+1
               rx_flg=0
           else:
               if debug & 0x4 ==0x4:
                   #print "error3",r_i,hex(r),rx_flg
                   pass
               return 3,buf[:buf_i],r_i,col,row,le,te,noise,timestamp,rx_flg,trig_timestamp,ts_flg,mframe,tlu,tlu_timestamp
              
        ########################
        ### TIMESTMP
        ########################
        elif r & 0xFF000000 == 0x51000000: ## timestamp
            trig_timestamp = (trig_timestamp & TS_MASK1) | np.uint64(r & TS_MASK_DAT)
            mframe=mframe+1
            if debug & 0x4 ==0x4:
                #print r_i,hex(r),"timestamp1",hex(trig_timestamp),mframe
                pass
            if ts_flg==2:
               ts_flg=0
               if debug & 0x1 == 0x1:
                   buf[buf_i]["col"]=0xFE
                   buf[buf_i]["row"]=0xFF
                   buf[buf_i]["noise"]=0x0
                   buf[buf_i]["le"]=0xFF
                   buf[buf_i]["te"]=0xFF
                   buf[buf_i]["timestamp"]=trig_timestamp
                   buf[buf_i]["cnt"]=mframe
                   buf_i=buf_i+1
            else:
               return 6,buf[:buf_i],r_i,col,row,le,te,noise,timestamp,rx_flg,trig_timestamp,ts_flg,mframe,tlu,tlu_timestamp
        elif r & 0xFF000000 == 0x52000000: ## timestamp
            trig_timestamp=(trig_timestamp & TS_MASK2) + (np.uint64(r & TS_MASK_DAT) << np.uint64(24))
            if debug & 0x4 ==0x4:
                #print r_i,hex(r),"timestamp1",hex(trig_timestamp)
                pass
            if ts_flg==0x1:
              ts_flg=0x2
            else:
              return 5,buf[:buf_i],r_i,col,row,le,te,noise,timestamp,rx_flg,trig_timestamp,ts_flg,mframe,tlu,tlu_timestamp
        elif r & 0xFF000000 == 0x53000000: ## timestamp
            trig_timestamp=(trig_timestamp & TS_MASK3)+ (np.uint64(r & TS_MASK_DAT) << np.uint64(48))
            if debug & 0x4 ==0x4:
               #print r_i,hex(r),"timestamp2",hex(trig_timestamp)
               pass
            if ts_flg==0x0:
               ts_flg=0x1
            else:
               return 4,buf[:buf_i],r_i,col,row,le,te,noise,timestamp,rx_flg,trig_timestamp,ts_flg,mframe,tlu,tlu_timestamp

        ########################
        ### TLU
        ########################
        elif (r & 0x80000000 == 0x80000000):
            tlu= r & 0xFFFF
            tlu_tmp=(r>>16) & 0x7FFF
            trig_tmp=np.uint16(trig_timestamp & np.uint64(0x7FFF))
            tlu_timestamp= (trig_timestamp & np.uint64(0xFFFFFFFFFFFF8000)) | np.uint64(tlu_tmp)
            if tlu_tmp < trig_tmp:  ##TODO more precise.
                tlu_timestamp=tlu_timestamp+0x8000

            if debug & 0x4 ==0x4:
                #print r_i,hex(r),"ts=",hex(tlu_timestamp),"tlu",tlu,hex(tlu_tmp),tlu_tmp < trig_tmp
                pass
            if debug & 0x2 == 0x2:
                buf[buf_i]["col"]=0xFF
                buf[buf_i]["row"]=0xFF
                buf[buf_i]["noise"]=0x0
                buf[buf_i]["le"]= 0xFF 
                buf[buf_i]["te"]= 0xFF
                buf[buf_i]["timestamp"]=tlu_timestamp
                buf[buf_i]["cnt"]=tlu
                buf_i=buf_i+1
        else:
            if debug & 0x4 == 0x4:
                #print r_i,hex(r),"trash"
                pass
            return 7,buf[:buf_i],r_i,col,row,le,te,noise,timestamp,rx_flg,trig_timestamp,ts_flg,mframe,tlu,tlu_timestamp
    return 0,buf[:buf_i],r_i,col,row,le,te,noise,timestamp,rx_flg,trig_timestamp,ts_flg,mframe,tlu,tlu_timestamp

def interpret_h5(fin,fout,debug=3, n=100000000):
    buf=np.empty(n,dtype=hit_dtype)
    col=0xFF
    row=0xFF
    le=0xFF
    te=0xFF
    noise=0
    timestamp=np.uint64(0x0)
    rx_flg=0
    
    trig_timestamp=np.uint64(0x0)
    mframe=0x0
    ts_flg=0
    
    tlu=0
    tlu_timestamp=np.uint64(0x0)
    
    with tables.open_file(fout, "w") as f_o:
        description=np.zeros((1,),dtype=hit_dtype).dtype
        hit_table=f_o.create_table(f_o.root,name="Hits",description=description,title='hit_data')
        with tables.open_file(fin) as f:
            end=len(f.root.raw_data)
            start=0
            t0=time.time()
            hit_total=0
            while start<end:
               tmpend=min(end,start+n)
               raw=f.root.raw_data[start:tmpend]
               err,hit_dat,r_i,col,row,le,te,noise,timestamp,rx_flg,trig_timestamp,ts_flg,mframe,tlu,tlu_timestamp = _interpret(
                       raw,buf,col,row,le,te,noise,timestamp,rx_flg,trig_timestamp,ts_flg,mframe,tlu,tlu_timestamp,debug)
               hit_total=hit_total+len(hit_dat)
               if err==0:
                   print "%d %d %.3f%% %.3fs %dhits"%(start,r_i,100.0*(start+r_i+1)/end,time.time()-t0,hit_total)
               elif err==1 or err==2 or err==3:
                   print "monopix data broken",err,start,r_i,hex(raw[r_i]),"flg=",rx_flg,timestamp
                   rx_flg=0
                   timestamp=np.uint64(0x0)
               elif err==4 or err==5 or err==6:
                   print "monopix data broken",err,start,r_i,hex(raw[r_i]),"flg=",ts_flg,ts_timestamp
                   ts_flg=0
                   ts_timestamp=np.uint64(0x0)
               elif err==7:
                   print "trash data",err,start,r_i,hex(raw[r_i])
               hit_table.append(hit_dat)
               hit_table.flush()
               start=start+r_i+1
               if debug &0x4 ==0x4:
                   break

class InterRaw():
    def __init__(self,chunk=100000000,debug=0):
        self.reset()
        self.buf=np.empty(chunk,dtype=hit_dtype)
        self.n=chunk
        self.debug=0
    def reset(self):
        self.col=0xFF
        self.row=0xFF
        self.le=0xFF
        self.te=0xFF
        self.noise=0
        self.timestamp=np.int64(0x0)
        self.rx_flg=0
        
        self.trig_timestamp=np.uint64(0x0)
        self.mframe=0x0
        self.ts_flg=0
        
        self.tlu=0
        self.tlu_timestamp=np.uint64(0x0)
    def run(self,raw):
        start=0
        end=len(raw)
        ret=np.empty(0,dtype=hit_dtype)
        while start<end:
            tmpend=min(end,start+self.n)
            ( err,hit_dat,r_i,
              self.col,self.row,self.le,self.te,self.noise,self.timestamp,self.rx_flg,
              self.trig_timestamp,self.ts_flg,self.mframe,self.tlu,self.tlu_timestamp
              ) = _interpret(
              raw[start:tmpend],self.buf,
              self.col,self.row,self.le,self.te,self.noise,self.timestamp,self.rx_flg,
              self.trig_timestamp,self.ts_flg,self.mframe,self.tlu,self.tlu_timestamp,
              self.debug
            )
            if err!=0:
               raise(ValueError)
            ret=np.append(ret,hit_dat)
            start=start+r_i+1
        return ret

if __name__ == "__main__":
    import sys
    fin=sys.argv[1]
    fout=fin[:-3]+"hit.h5"
    interpret_h5(fin,fout,debug=3)
    print fout
               
