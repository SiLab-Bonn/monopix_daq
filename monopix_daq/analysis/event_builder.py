import sys,os,time

import tables
import matplotlib
matplotlib.use('Agg')

import matplotlib.pyplot as plt
import numpy as np
import yaml
from numba import njit

token_dtype=[('event_number','<i8'),('token_timestamp','<u8'),('min_tot','<u1'),('min_te','<u1'),
          ('tlu_timestamp','<u8'),('tlu','<u4'),('diff','<i8')]
corr_dtype=[('event_number','<i8'),('token_timestamp','<u8'),('min_tot','<u1'),('flg','<u1'),('diff','<i8'),
          ('event_timestamp','<u8'),('trigger_number','<u4')]
hit_dtype=[('event_number','<i8'),('token_timestamp','<u8'),('flg','<u1'),('diff','<i8'),
          ('col','<u1'),('row','<u1'),('le','<i8'),('te','<i8'),
          ('event_timestamp','<u8'),('trigger_number','<u4')]
@njit
def _corr(token,tlu,offset):
    tlu_idx=0
    for t_i,t in enumerate(token):
        diff=np.int64(0x7FFFFFFFFFFFFFFF)
        mintot_e=np.int64(t['min_tot'])
        token_e=np.int64(t['token_timestamp'])
        for l_i,l_e in enumerate(tlu[tlu_idx:]):
            tlu_e=np.int64(l_e['timestamp'])
            
            #if t_i%1000000 < 100: 
            #    print t_i, l_i, "pre_diff=%d"%diff,tlu_e,token_e,mintot_e,           
            if np.abs(diff)>np.abs(token_e-mintot_e-tlu_e+offset):
                diff = token_e-mintot_e-tlu_e
                token[t_i]['diff']=diff
                token[t_i]['tlu_timestamp']=l_e['timestamp']
                token[t_i]['tlu']=l_e['cnt']
                token[t_i]['event_number']=np.int64(tlu_idx)+np.int64(l_i)
            #if t_i%1000000 < 100:
            #    print "diff=%d"%(token_e-tlu_e-mintot_e), "new_diff=%d"%diff
            if token_e < tlu_e:
                tlu_idx=max(0,tlu_idx+l_i-1)
                break
    return token

def _build(corr,dat,buf):
    c_i=0
    buf_i=0
    m_i=0
    while m_i<len(dat) and c_i<len(corr):
        if dat[m_i]["timestamp"]<corr[c_i]["token_timestamp"]:
            m_i=m_i+1
        elif dat[m_i]["timestamp"]==corr[c_i]["token_timestamp"]:
            buf[buf_i]['event_number']=corr[c_i]["event_number"]
            buf[buf_i]['trigger_number']=corr[c_i]["trigger_number"]
            buf[buf_i]['event_timestamp']=corr[c_i]["event_timestamp"]
            buf[buf_i]['diff']=corr[c_i]["diff"]
            buf[buf_i]['token_timestamp']=dat[m_i]["timestamp"]
            buf[buf_i]['col']=dat[m_i]["col"]
            buf[buf_i]['row']=dat[m_i]["row"]
            buf[buf_i]['le']=dat[m_i]["le"]
            buf[buf_i]['te']=dat[m_i]["te"]
            buf[buf_i]['flg']=np.uint8(dat[m_i]["cnt"])
            buf_i=buf_i+1
            m_i=m_i+1
        else:
            c_i=c_i+1
    return buf[:buf_i],m_i,c_i

@njit
def _fix_timestamp(dat):
    pre_timestamp=dat[0]
    MASK=np.uint64(0xFFFFFFFF)
    NOT_MASK=np.uint64(0xFFFFFFFF00000000)
    TH = np.uint(0x7FFFFFFF)
    for d_i,d in enumerate(dat):
        d= (MASK  & d) | (NOT_MASK  & pre_timestamp)
        if d > pre_timestamp + (0x7FFFFFFF):
            d=d-np.uint64(0x100000000)
        elif d +(0x7FFFFFFF) < pre_timestamp:
            d=d+np.uint64(0x100000000)
        dat[d_i]=d
    return dat

def get_te_offset(dat,debug=None,field="timestamp"):
     hist=np.histogram((dat[field]-np.uint64(dat["te"])) & 0xFF, bins=np.arange(0,0x101))
     offset=np.int64(hist[1][np.argmax(hist[0])])
     if debug!=None:
         plt.step(hist[1][:-1],hist[0])
         plt.xlabel("TOKEN-TE")
         plt.title("offset %d"%offset)
         plt.yscale("log")
         plt.savefig(debug)
     return offset

def build_h5(fhit,fout,debug=0):
    with tables.open_file(fhit) as f:
        dat=f.root.Hits[:]
    print len(dat[dat["col"]==0xFF]),len(dat[dat["col"]==0xFE]),len(dat[dat["col"]==0xFD]),len(dat[dat["col"]<36])
    #if debug & 0x8 ==0x8:
    #    dat["timestamp"]=_fix_timestamp(dat["timestamp"])
    te_offset=get_te_offset(dat,debug=fout[:-3]+'.png')     
    print "te_offset=%d"%te_offset
    
    tlu=dat[dat["col"]==0xFF]
    dat=dat[np.bitwise_and(dat["col"]<36,dat["cnt"]==0)]
    tot=np.array(dat["te"]-dat["le"],dtype=np.int64)
    print 'TLU: increase only',np.all(tlu["timestamp"][1:] >= tlu["timestamp"][:-1]) 
    print 'MONO: increase only',np.all(dat["timestamp"][1:] >= dat["timestamp"][:-1])

    with tables.open_file(fout, "w") as f_o:
        uni,idx,cnt=np.unique(dat["timestamp"],return_index=True,return_counts=True)
        print "number of token",len(uni)
        token=np.empty(len(uni),dtype=token_dtype)
        for i,u in enumerate(uni):
            arg=np.argmin(np.abs(np.int8(u-dat["te"][idx[i]:idx[i]+cnt[i]]-te_offset)))
            token[i]['min_tot']= tot[idx[i]+arg]
            token[i]['min_te']= dat['te'][idx[i]+arg]
            token[i]['token_timestamp']=u
            dat[idx[i]:idx[i]+cnt[i]]["cnt"]=np.array(tot[idx[i]:idx[i]+cnt[i]] < token[i]['min_tot'],dtype=np.uint32)*4
            dat[idx[i]+arg]['cnt']=4
            #if np.any(dat["timestamp"][idx[i]:idx[i]+cnt[i]]!=u):
            #    print "ERROR!!", i,u,idx[i],cnt[i],dat[idx[i]:idx[i]+cnt[i]]
            #    break 

        if debug & 0x04 ==0x04:
            description=np.zeros((1,),dtype=token_dtype).dtype
            token_table=f_o.create_table(f_o.root,name="Tokens_tmp",description=description,title='token_data')
            token_table.append(token)
            token_table.flush()
        
        token=_corr(token,tlu,offset=0)
        
        if debug & 0x04 ==0x04:
            description=np.zeros((1,),dtype=token_dtype).dtype
            token_table=f_o.create_table(f_o.root,name="Tokens",description=description,title='token_data')
            token_table.append(token)
            token_table.flush()
        
        bins=np.arange(-2E4,2E4,1)
        hist=np.histogram(token["diff"][:],bins=bins);
        peak=hist[1][np.argmax(hist[0])]
        print "diff peak",peak
        print 'TLU increase after assingment',np.all(token["tlu_timestamp"][1:] >= token["tlu_timestamp"][:-1])
        
        uni,idx,cnt=np.unique(token["tlu_timestamp"],return_index=True,return_counts=True)
        corr=np.empty(len(uni),dtype=corr_dtype)
        for i,u in enumerate(uni):
            arg=np.argmin(np.abs(token[idx[i]:idx[i]+cnt[i]]['diff']-peak))
            corr[i]["token_timestamp"]= token[idx[i]+arg]["token_timestamp"]
            corr[i]["min_tot"]= token[idx[i]+arg]["min_tot"]
            corr[i]["event_timestamp"]= token[idx[i]+arg]["tlu_timestamp"]
            corr[i]["event_number"]= token[idx[i]+arg]["event_number"]
            corr[i]["trigger_number"]= token[idx[i]+arg]["tlu"]
            corr[i]["diff"]= token[idx[i]+arg]["diff"]
            token[i]['token_timestamp']=u
            #if np.any(token["tlu_timestamp"][idx[i]:idx[i]+cnt[i]]!=u):
            #    print i,u,idx[i],cnt[i],token[idx[i]:idx[i]+cnt[i]]
            #    break
        print "corr=%d"%len(corr),"# of token=%d"%len(token),"%f%%"%(100.0*len(corr)/len(token))

        if debug & 0x04 == 0x04:
            description=np.zeros((1,),dtype=corr_dtype).dtype
            corr_table=f_o.create_table(f_o.root,name="Corr",description=description,title='corr_data')
            token_table.append(corr)
            token_table.flush()
            
        buf=np.empty(len(dat),dtype=hit_dtype)
        buf_out,m_i,c_i=_build(corr,dat,buf)
        print "dat",m_i,len(dat),"corr",c_i,len(corr)        

        description=np.zeros((1,),dtype=hit_dtype).dtype
        hit_table=f_o.create_table(f_o.root,name="Hits",description=description,title='hit_data')
        hit_table.append(buf_out)
        hit_table.flush()
        hit_table.attrs.te_offset=te_offset
        hit_table.attrs.diff_peak=peak
        
if __name__ == "__main__":
    import sys

    fraw=sys.argv[1]

    fhit=fraw[:-3]+"_hit.h5"
    fout=fraw[:-3]+"_tlu.h5"
    build_h5(fhit,fout)
