import time,sys,os
import matplotlib.pyplot as plt
import numpy as np
import monopix_extensions

def find_tdac(l, pix, exp=1,th_cnt=0):
    tdac=np.copy(l.dut.PIXEL_CONF["TRIM_EN"])
    preamp=np.copy(l.dut.PIXEL_CONF["PREAMP_EN"])
    
    for t in range(15,-1,-1):
        for p in pix:
            if tdac[p[0],p[1]] > t:
                tdac[p[0],p[1]]=t
        l.set_tdac(tdac)
        l.set_preamp_en(preamp)
        l.set_monoread()
        time.sleep(exp)
        d=l.get_data_now()
        l.stop_monoread()
        if len(d)==0:
             print "=====t%d pix%d no pulse go next t====="%(t,len(pix))
             continue
        ret=monopix_extensions.analyse_hit_timestamp(d,"img")
        if len(np.argwhere(ret>1000))>len(pixlist)/10:
            print "=====t%d pix%d too many noisy pixel====="%(t,len(pix))
        pix=[]
        flg=0
        for p in pix:
           if ret[p[0],p[1]]>th_cnt:
               if tdac[p[0],p[1]]==15:
                  preamp[p[0],p[1]]=False
               else:
                  tdac[p[0],p[1]]=tdac[p[0],p[1]]+1
           else:
               pix_next.append(pix)

            
                  
              
        
    inj=0.2
    l.set_inj_all(inj_high=inj)
    tdac_s=15
    l.set_th(0.763)
    mask=40
    collist=[16,17,18,19]
    save=True
    fname=monopix_extensions.mk_fname("scantdac",ext="npy")
    fig,ax=plt.subplots(2,2)
    th_cnt=80
    noise=2
    plt.ion()
    l.set_tdac(15)
    #l.set_global(LSBdacL=LSBdacL)
    pixlist=[]
    for j in collist:
        for i in range(129):
            pixlist.append([j,i])
    l.set_preamp_en(pixlist)
    tdac=np.copy(l.dut.PIXEL_CONF["TRIM_EN"])
    preamp=np.copy(l.dut.PIXEL_CONF["PREAMP_EN"])
    tdac_status=np.copy(l.dut.PIXEL_CONF["TRIM_EN"])
    for j in range(mask):
        pix=[]
        for i in range(j,len(pixlist),mask):
                  pix.append(pixlist[i])
        l.logger.info("tune_tdac_inj: tobe_tuned=%d pix=%s"%(len(pix),str(pix)))
        t=15
        for t in np.arange(15,-1,-1):
            for p in pix:
                tdac[p[0],p[1]]=t
                tdac_status[p[0],p[1]]=t
            flg=1
            while flg==1:
                l.set_tdac(tdac)
                l.set_preamp_en(preamp)   
                l.set_monoread()
                time.sleep(1)
                d=l.get_data_now()
                l.stop_monoread()
                if len(d)==0:
                    break
                ret=monopix_extensions.analyse_hit_timestamp(d,"img")
                ax[0,0].cla()
                ax[0,0].pcolor(ret[16:20,:],vmax=100)
                plt.pause(0.001)
                if len(np.argwhere(ret>noise)) > 100:
                      print l.logger.info("!!!!!!!!!!!!!error!!!!!!!!!!!!!!%d"%len(np.argwhere(ret>noise)))
                flg=0
                for p_i, p in enumerate(pix):
                    if ret[p[0],p[1]]>1000:
                        flg=1
                    if ret[p[0],p[1]]>noise:
                        print "mask%d==========noise tdac%d pix[%d,%d]=================%d"%(j,t, p[0],p[1] ,ret[p[0],p[1]])
                        print t, p ,ret[p[0],p[1]],"noise!!"
                        if tdac[p[0],p[1]]==15:
                            tdac[p[0],p[1]]=15
                            preamp[p[0],p[1]]=False
                            tdac_status[p[0],p[1]]=-16
                        else:
                            tdac[p[0],p[1]]=tdac[p[0],p[1]]+1
                            tdac_status[p[0],p[1]]=-tdac[p[0],p[1]]
            pix_next=[]
            for p in pix:
                #print "mask%d=============tdac_status[%d,%d]=========%d,t=%d"%(j,p[0],p[1],tdac_status[p[0],p[1]],t)
                if tdac_status[p[0],p[1]]==t:
                    pix_next.append(p)
            pix=pix_next
            l.set_preamp_en(preamp)
            flg=1
            while flg==1 and len(pix)>0:
                l.set_tdac(tdac)
                l.set_inj_en(pix)
                l.set_mon_en(pix[0])
                l.set_monoread()
                l.dut["fifo"].reset()
                #ax[1,0].cla()
                #ax[1,0].hist(np.reshape(tdac[16:20,:], 4*129),bins=np.arange(-1,18,1))
                #plt.pause(0.001)
                l.dut["fifo"].reset()
                d=l.get_data()
                l.stop_monoread()
                if len(d)==0:
                    print "mask%d=============no pulse=============%d,pix=%d"%(j,t,len(pix)),d
                    break
                ret=monopix_extensions.analyse_hit_timestamp(d,"img")
                s="find_tdac: tdac=%d"%t
                flg=0
                pix_next=[]
                for p_i,p in enumerate(pix):
                    if ret[p[0],p[1]] >=th_cnt:
                          print p_i,p[0],p[1],ret[p[0],p[1]],"count!!!"
                          if ret[p[0],p[1]]>1000:
                              flg=1
                          if tdac[p[0],p[1]]==15:
                             tdac[p[0],p[1]]=15
                             tdac_status[p[0],p[1]]=16
                          else:
                             tdac[p[0],p[1]]=tdac[p[0],p[1]]+1
                             tdac_status[p[0],p[1]]=tdac[p[0],p[1]]
                          s=s+" [%d,%d]=%d"%(p[0],p[1],ret[p[0],p[1]])
                    else:
                        pix_next.append(p)
                l.logger.info(s+" rest=%d"%len(pix_next))
                pix=pix_next
            if len(pix)==0:
                print "mask%d has been tuned min tdac=%d+1"%(j,t)
                break
        ax[1,0].cla()
        ax[1,0].hist(np.reshape(tdac[16:20,:], 4*129),bins=np.arange(-1,18,1))
        ax[1,0].set_title("mask%d inj=%.4f tdac=%d"%(j,inj,t))
        ax[1,0].set_yscale("log")
        plt.pause(0.001)
        s="find_tdac: tdac=%d!!"%t
        for p_i,p in enumerate(pix):
            tdac_status[p[0],p[1]]=0
            s=s+" [%d,%d]=%d"%(p[0],p[1],ret[p[0],p[1]])
        l.logger.info(s)
