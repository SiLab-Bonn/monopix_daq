import time, sys, os
import numpy as np
import matplotlib.pyplot as plt
sys.path.append(r"/home/user/workspace/KEITHLEY2450")
import KEITHLEY2450
import KEITHLEY2634B
import KEITHLEY2410
sys.path.append("/home/user/workspace/MSO4104B")
import MSO4104B_sock
sys.path.append("/home/user/workspace/Agilent33250A")
import Agilent33250A
sys.path.append("/home/user/workspace/AgilentE3646A")
import AgilentE3631A
sys.path.append("/home/user/workspace/iseg-monitor/trunk/pyISEG")
import iseg_shq
import monopix_extensions

def init_all(dut=False,hv=True,hv2=False,hv3=False,mso=False):
    if dut==True:
        l=monopix_extensions.MonopixExtensions("monopix_mio3.yaml")
    else:
        l=None
    if hv==True:
        #hv=KEITHLEY2450.KEITHLEY2450_sock("192.168.10.17")
        hv=KEITHLEY2450.KEITHLEY2450_sock("131.220.165.163")
    else:
        hv=None
    if hv2==True:
        #hv2=KEITHLEY2634B.KEITHLEY2634B_sock("131.220.165.16")
        hv2=KEITHLEY2450.KEITHLEY2450_sock("131.220.165.164")
    else:
        hv2=None
    if hv3==True:
        hv3=KEITHLEY2410.KEITHLEY2410("/dev/ttyUSB0")
    else:
        hv3=None
    if mso==True:
        mso=MSO4104B_sock.Mso4104_sock('192.168.10.16')
    
    return l,hv,hv2,hv3,mso
    
        
        

####################################################################
def iv(dut,hv,nring=None,bias=None,scan_list=np.arange(-0.5,-400,-1.0),wait=1,ave_n=1,
       cur_limit=None,vol_limit=1.5,save=True,temp=True): ## vol_limit=1.5
    plt.ion()
    
    if not isinstance(hv, list):
        hv_list=[hv]
    else:
        hv_list=hv
    ch=[]
    chB=0
    for hv_ihv in enumerate(hv_list):
        if chB==0 and isinstance(hv,KEITHLEY2634B.KEITHLEY2634B_sock):
            ch.append("A")
            chB=1
        elif chB==1 and isinstance(hv,KEITHLEY2634B.KEITHLEY2634B_sock):
            ch.append("B")
        else:
            ch.append(None)
    
    dtype=[("hv_set","f4"),
           ('hv_cur','f4',(len(hv_list),ave_n)),('hv_vol','f4',(len(hv_list),ave_n))]
    if nring!=None:
        dtype.append(('nring_cur','f4',(ave_n,)))
        dtype.append(('nring_vol','f4',(ave_n,)))
    if bias!=None:
        dtype.append(('bias_cur','f4',(ave_n,)))
        dtype.append(('bias_vol','f4',(ave_n,)))
    if temp==True:
        dtype.append(("temp","f4"))

    res=np.zeros(len(scan_list),dtype=dtype) ##TODO merge meas_v,meas_i
    

    dut.logger.info("iv() hv_set hv_vol hv_cur nring_vol nring_cur bias_vol bias_cur")
    for j,v in enumerate(scan_list):
        for hv_i,hv in enumerate(hv_list):
            if ch[hv_i]==None:
                hv.set_voltage(v/len(hv_list))
            else:
                hv.set_voltage(v/len(hv_list),ch[hv_i])
        t0=time.time()
        #### plot
        plt.clf()
        plt.subplot(311)
        for hv_i in range(len(hv_list)):
            plt.plot(np.sum(np.average(res['hv_vol'][:][:,:], axis=2),axis=1),
                     np.average(res['hv_cur'][:][:,:], axis=2)[:,hv_i],"o")
        if nring!=None:
            plt.subplot(312)
            plt.plot(np.sum(np.average(res['hv_vol'][:][:,:], axis=2),axis=1),
                     np.average(res['nring_cur'],axis=1),"o")
        plt.subplot(313)
        if bias!=None:
            plt.plot(np.sum(np.average(res['hv_vol'][:][:,:], axis=2),axis=1),
                 np.average(res['bias_cur'],axis=1),"o")
        elif temp==True:
            plt.plot(np.sum(np.average(res['hv_vol'][:][:,:], axis=2),axis=1),
                 res['temp'],"o")
        plt.pause(0.001)
        print dut.dut.power_status()
        time.sleep(max(0,wait-time.time()+t0))
        
        #### measure
        res[j]['hv_set']=v
        for i in range(ave_n):
            if bias!=None:
                #meas_i_bias[i],meas_v_bias[i]=bias.get_current_voltage("B")
                res[j]['bias_vol'][i]=bias.get_voltage()
                res[j]['bias_cur'][i]=bias.get_current()
            for hv_i,hv in enumerate(hv_list):
                if ch[hv_i]==None:
                    res[j]['hv_vol'][hv_i,i]=hv.get_voltage()
                    res[j]['hv_cur'][hv_i,i]=hv.get_current()
                else:
                    res[j]['hv_cur'][hv_i,i],res[j]['hv_vol'][hv_i,i]=hv.get_current_voltage(ch[hv_i])
                
            if nring!=None:
                res[j]['nring_vol'][i]=nring.get_voltage()
                res[j]['nring_cur'][i]=nring.get_current()
                
        #### print
        s="iv() %d %g"%(j,v)
        meas_v_ave=0
        for hv_i in range(len(hv_list)):
            meas_v_ave_i=np.average(res[j]["hv_vol"][hv_i,:])
            meas_i_ave=np.average(res[j]["hv_cur"][hv_i,:])
            s=s+" %.9g %.9g"%(meas_v_ave_i,meas_i_ave)
            meas_v_ave=meas_v_ave+meas_v_ave_i
        if nring!=None:
            s="%s %.9g %.9g"%(s,np.average(res[j]["nring_vol"]),np.average(res[j]["nring_cur"]))
        if bias!=None:
            s="%s %.9g %.9g"%(s, np.average(res[j]["bias_vol"]),np.average(res[j]["bias_cur"]))
        if temp==True:
            res[j]["temp"]=temperature(dut)
            dut.logger.info("%s %f"%(s,res[j]["temp"]))
        
        #### check breakdown
        if cur_limit!=None:
          if abs(meas_i_ave)>cur_limit:
            dut.logger.info("iv() breakdown %f %.3g"%(meas_v_ave,meas_i_ave))
            for hv in hv_list:
                hv.set_voltage(0,ch[hv_i])
            break
        if vol_limit!=None:
          if abs(meas_v_ave-v) > vol_limit:
            print "meas",meas_v_ave, "set",v, "vol_limit",vol_limit
            dut.logger.info("iv() breakdown %f"%meas_v_ave)
            for hv_i,hv in enumerate(hv_list):
               if ch[hv_i]==None:
                   hv.set_voltage(0)
               else:
                   hv.set_voltage(0,ch[hv_i])
            break
           
    #### plot and save
    plt.clf()
    plt.subplot(311)
    for hv_i in range(len(hv_list)):
        plt.plot(np.sum(np.average(res['hv_vol'][:][:,:], axis=2),axis=1),
                 np.average(res['hv_cur'][:][:,:], axis=2)[:,hv_i],"o")
    if nring!=None:
        plt.subplot(312)
        plt.plot(np.sum(np.average(res['hv_vol'][:][:,:], axis=2),axis=1),
                 np.average(res['nring_cur'],axis=1),"o")
    plt.subplot(313)
    if bias!=None:
        plt.plot(np.sum(np.average(res['hv_vol'][:][:,:], axis=2),axis=1),
                 np.average(res['bias_cur'],axis=1),"o")
    elif temp==True:
        plt.plot(np.sum(np.average(res['hv_vol'][:][:,:], axis=2),axis=1),
                 res['temp'],"o")
    plt.pause(0.001)
    fname=time.strftime("output_data/iv/iv_%y%m%d-%H%M%S.npy")
    np.save(fname,res[:j])
    return meas_v_ave
####################################################################
def ampout(l,hv,mso,hv_set=-100,save=True):
    ## setting
    if isinstance(hv,list):
       ch=["A","B"]
       hv_list=hv
    else:
       hv_list=[hv]
       ch=[None]
    meas_vol=np.zeros(len(hv_list))
    meas_cur=np.zeros(len(hv_list))
    for hv_i,hv in enumerate(hv_list):
        if ch[hv_i]==None:
          hv.set_voltage(hv_set/len(hv_list))
        else:
         hv.set_voltage(hv_set/len(hv_list),ch[hv_i])
     
    l.set_tdac(15)
    tdac=np.copy(l.tdac)
    l.show()
    l.set_th(1.5)
    pixlist=[[4,25],[14,25],[14,26],[16,50],[20,25]]
    fblist=[1,2,4,8,16,32,47,63]
    res=np.empty(len(fblist)*len(pixlist),dtype=[("pix",">i4",(2,)),("VPFB",">i4")])
    fname=time.strftime("ampout_%y%m%d-%H%M%S.npy")
    wavename=os.path.join("output_data/ampout",fname[:-4]+".txt")
    chs=[2]
    
    print "#### HV is ON, CHECK current!!! ####"
    while True:
         time.sleep(1)
         for hv_i,hv in enumerate(hv_list):
             if ch[hv_i]==None:
               meas_cur[hv_i]=hv.get_current()
               meas_vol[hv_i]=hv.get_voltage()
             else:
               meas_cur[hv_i],meas_vol[hv_i]=hv.get_current_voltage(ch[0])
         print meas_vol[0],"V",meas_cur[0],"A",np.abs(meas_vol[0]*len(hv_list)-hv_set)
         if np.abs(np.sum(meas_vol)-hv_set)<1.5:
             break
    j=0
    for p in pixlist:
      l.set_preamp_en(p)
      l.set_inj_en(p)
      l.set_mon_en(p)
      tdac[:,:]=15
      tdac[p[0],p[1]]=0
      l.set_tdac(tdac)
      vol=0
      for hv_i,hv in enumerate(hv_list):
          meas_cur[hv_i]=hv.get_current()
          meas_vol[hv_i]=hv.get_voltage()
          #meas_vol[hv_i],meas_cur[hv_i]=hv.get_current_voltage(ch[hv_i])
      temp=temperature(l)
      ## measure Ampout
      mso.init(chs=chs,start=1,stop=-1)
      for fb in fblist:
          l.set_global(LSBdacL=63,VPFB=fb,VSTRETCH=63)
          l.set_th(1.5)
          l.set_inj_all(inj_n=0,inj_high=0.7,inj_low=0.2)
          l.inject()  
          mso.start()
          mso.query()
          wave=mso.get_alldata(chs)
          with open(wavename, "a+") as f:
              f.write(wave)
              f.flush()
          l.logger.info("ampout:%d hv=%g(%g) temp=%f pix=[%d,%d] VPFB=%d"%(
                        j,np.sum(meas_vol),meas_cur[0],temp,p[0],p[1],fb))
          res[j]["pix"][0]=p[0]
          res[j]["pix"][1]=p[1]
          res[j]["VPFB"]=fb
          j=j+1
    if save==True:
       np.save(os.path.join("output_data/ampout",fname),res)
       return fname
####################################################################            
def mon(l,hv,mso,inj_b=1.8,inj_e=0.3,inj_s=-0.02,save=True):
    ## setting
    if isinstance(hv,list):
        hv_list=hv
        ch=["A","B"]
    else:
        hv_list=[hv]
    meas_vol=np.zeros(len(hv_list))
    meas_cur=np.zeros(len(hv_list))

    l.set_tdac(15)
    tdac=np.copy(l.tdac)
    l.show()
    l.set_th(1.5)
    
    pixlist=[[4,25],[14,25],[14,26],[16,50],[20,25]]
    fblist=[1,2,4,8,16,32,47,63]
    injlist=[0.3,0.4,0.6,0.8,1.0,1.2,1.4,1.6]
    res=np.empty(len(fblist)*len(pixlist),dtype=[("pix",">i4",(2,)),("VPFB",">i4"),
                 ("edge",">f4"),("injtdc","S128")])
    j=0
    fname=time.strftime("mon_%y%m%d-%H%M%S.npy")
    wavename=os.path.join("output_data/mon",fname[:-4]+".txt")
    chs=[1,2,3,4]
 
    for p in pixlist:
      l.set_preamp_en(p)
      l.set_inj_en(p)
      l.set_mon_en(p)
      tdac[:,:]=15
      tdac[p[0],p[1]]=0
      l.set_tdac(tdac)
      vol=0
      for hv_i,hv in enumerate(hv_list):
          #meas_vol[hv_i],meas_cur[hv_i]=hv.get_current_voltage(ch[hv_i])
          meas_cur[hv_i]=hv.get_current()
          meas_vol[hv_i]=hv.get_voltage()
      temp=temperature(l)
      ## set_th
      l.set_global(LSBdacL=63,VPFB=47,VSTRETCH=63)
      l.set_inj(inj_high=0.5,inj_low=0.2)
      l.set_tdc_inj()
      thname=time.strftime("thtdc_%y%m%d-%H%M%S.npy")
      edge=l.find_th_tdc(full_scurve="edge", save=os.path.join("output_data/mon",thname))
      ## measure Monitor
      mso.init(chs=chs,start=1,stop=-1)
      for fb_i,fb in enumerate(fblist):
          l.set_th(edge)
          l.set_global(LSBdacL=63,VPFB=fb,VSTRETCH=63)
          l.set_inj_all(inj_n=0,inj_high=0.7,inj_low=0.2)
          l.inject()
          mso.start()
          mso.query()
          if fb_i==0:
              chs=[1,2,3,4]
          else:
              chs=[2,3]
          wave=mso.get_alldata(chs)
          with open(wavename, "a") as f:
              f.write(wave)
              f.flush()
          
          l.set_tdc_inj()
          injname=time.strftime("injtdc_%y%m%d-%H%M%S.npy")
          l.scan_inj_tdc(b=inj_b,e=inj_e,s=inj_s,inj_low=0.2,save=os.path.join("output_data/mon",injname))
          thname=os.path.join("output_data/mon","th"+injname[3:])
          for inj_i,inj_high in enumerate(injlist):
              l.set_inj(inj_high=inj_high,inj_low=0.2)
              with open(thname,"ab+") as f:
                  np.save(f,{"inj_high":inj_high,"inj_low":0.2})
              l.find_th_tdc(full_scurve="edge",save=thname)
          ### print
          l.logger.info("mon:%d hv=%g(%g) temp=%f pix=[%d,%d] VPFB=%d edge=%f injtdc=%s"%(
                        j,np.sum(meas_vol),meas_cur[0],temp,p[0],p[1],fb,edge,injname))
          res[j]["pix"][0]=p[0]
          res[j]["pix"][1]=p[1]
          res[j]["VPFB"]=fb
          res[j]["edge"]=edge
          res[j]["injtdc"]=injname
          j=j+1
    if save==True:
       np.save(os.path.join("output_data/mon",fname),res)
       return fname
####################################################################
def th(l,hv,hv_set=-50,inj_highlist=[0.5],thlist=np.arange(0.88,0.79,-0.04)):
    ## setting
    if isinstance(hv,list):
        ch=["A","B"]
        hv_list=hv
    else:
        hv_list=[hv]
        ch=[None]

    for hv_i,hv in enumerate(hv_list):
          if ch[hv_i]!=None:
              hv.set_voltage(hv_set/len(hv_list),ch[hv_i])
          else:
              hv.set_voltage(hv_set/len(hv_list))    
    meas_vol=np.zeros(len(hv_list))
    meas_cur=np.zeros(len(hv_list))
    print "#### HV is ON, CHECK current!!! ####"
    while True:
         time.sleep(1)
         for hv_i,hv in enumerate(hv_list):
             if ch[hv_i]==None:
                 meas_cur[hv_i]=hv.get_current()
                 meas_vol[hv_i]=hv.get_voltage()
             else:
                 meas_cur[hv_i],meas_vol[hv_i]=hv.get_current_voltage(ch[hv_i])
         print meas_vol[0],"V",meas_cur[0],"A",np.abs(meas_vol[0]*len(hv_list)-hv_set)
         if np.abs(np.sum(meas_vol)-hv_set)<1.5:
             break
             
    th_pixcnt={"pmos":3,"nmos":0,"cmos":0}
    for fl in ["pmos","nmos","cmos"]:
       l.set_preamp_en("all")
       for hv_i,hv in enumerate(hv_list):
          #meas_vol[hv_i],meas_cur[hv_i]=hv.get_current_voltage(ch[hv_i])
          meas_cur[hv_i]=hv.get_current()
          meas_vol[hv_i]=hv.get_voltage()
       temp=temperature(l)
       for ih_i,inj_high in enumerate(inj_highlist):
           l.set_inj(inj_high=inj_high,inj_low=0.2)
           tdacname=time.strftime("tdac_%y%m%d-%H%M%S.npy")
           th,LSBdacL=l.tune_tdac_inj(fl,th_pixcnt=th_pixcnt[fl],
                                      save=os.path.join("output_data/th",fl+tdacname))
           l.scan_inj_all(b=0.2,e=1.1,inj_low=0.2,s=0.005,flavor=fl,
                          save=os.path.join("output_data/th",fl+"tuned%.3f_"%th+tdacname[4:]))
           l.show(show="power")
           if ih_i==0:
               continue
       l.set_tdac(0)
       injname=time.strftime("inj_%y%m%d-%H%M%S.npy")
       for th in thlist:
           l.set_th(th)
           l.scan_inj_all(b=0.3,e=1.1,inj_low=0.2,s=0.005,flavor=fl,
                          save=os.path.join("output_data/th",fl+"th%.3f_"%th+injname))
       l.show(show="power")
       l.logger.info("th: hv=%g(%g) temp=%f flavor=%s inj=%s"%(
                      np.sum(meas_vol),meas_cur[0],temp,fl,injname))
    for hv in hv_list:
        hv.set_voltage(0)
    
def vdd(l,hv,nring,wait=2,hv_set=-2,duration=-1):
    ## setting
    if isinstance(hv,list):
        ch=["A","B"]
        hv_list=hv
    else:
        hv_list=[hv]
        ch=[]
    meas_vol=np.zeros(len(hv_list))
    meas_cur=np.zeros(len(hv_list))
    
    for hv_i,hv in enumerate(hv_list):
          if len(ch)!=0:
              hv.set_voltage(hv_set/len(hv_list),ch[hv_i])
          else:
              hv.set_voltage(hv_set/len(hv_list))
    if nring!=None:
        nring.set_voltage(1.8)
    
    l.set_preamp_en("all")
    l.set_th(1.5)
    
    i=0
    t_start=time.time()
    while True:
          if i%10000==0:
              vddd_cur=np.empty(0)  
              vdda_cur=np.empty(0)
              nring_cur=np.empty(0)
              hv_cur=np.empty(0)
              temp=np.empty(0)
          t0=time.time()
          s="hv:"
          for hv_i,hv in enumerate(hv_list):
              meas_cur[hv_i],meas_vol[hv_i]=hv.get_current_voltage(ch[hv_i])
              #meas_cur=hv.get_current()
              #meas_vol=hv.get_voltage()
              s=s+" hv%d=%g(%g)"%(hv_i,meas_vol[hv_i],meas_cur[hv_i])
          hv_cur=np.append(hv_cur,meas_cur[0])
          if nring!=None:
              nring_cur=np.append(nring_cur,nring.get_current())
              nring_vol=nring.get_voltage()
              s=s+" nring=%g(%g)"%(nring_vol,nring_cur[-1])
          temp=np.append(temp,temperature(l))
          s=s+" temp=%f"%temp[-1]
          l.logger.info(s)
          meas_power=l.get_power()
          l.logger.show(meas_power,"power")
          vddd_cur=np.append(vddd_cur,meas_power["Vddd_curr"])
          vdda_cur=np.append(vdda_cur,meas_power["Vdda_curr"])
          i=i+1
          plt.clf()
          plt.subplot(321)
          plt.plot(vddd_cur)
          plt.title("Vddd")
          plt.subplot(322)
          plt.plot(vdda_cur)
          plt.title("Vdda")
          plt.subplot(323)
          plt.plot(temp)
          plt.title("Temp")
          plt.subplot(324)
          plt.plot(nring_cur)
          plt.title("Nring")
          plt.subplot(325)
          plt.plot(hv_cur)
          plt.title("HV")
          plt.pause(0.001)

          if t0-t_start>duration and duration>0:
              break
          else:
              print "wait for", duration-t0+t_start,"sec"
              time.sleep(max(wait-time.time()+t0,0))
                      
####################################################################
def temperature(c,debug=0):
    vol=c.dut["CCPD_NTC"].get_voltage()
    if debug==1:
       print "temperature() voltage=%.3f"%vol
    if not (vol>0.5 and vol<1.5):
      for i in np.arange(-200,200,2):
        c.dut["CCPD_NTC"].set_current(i,unit="uA")
        time.sleep(0.1)
        vol=c.dut["CCPD_NTC"].get_voltage()
        if vol>0.7 and vol<1.3:
            break
      if i>190:
        c.logger.info("temperature() NTC error")
    temp=np.empty(10)
    for i in range(len(temp)):
        temp[i]=c.dut["CCPD_NTC"].get_temperature("C")
    return np.average(temp[temp!=float("nan")])

####################################################################
def xray(l,hv,mso,src="fe",pixlist=[[4,25],[14,25],[14,26],[16,50],[20,25]],hv_set=-100):
    
    hv_list=set_hv(hv, hv_set)
    meas_vol=np.zeros(len(hv_list))
    meas_cur=np.zeros(len(hv_list))

    others=0
    injlist=[0.21,0.22,0.24,0.26,0.28,0.3,0.35,0.4,0.45,0.5,0.6,0.7,0.8,0.9,1.0,
             1.1,1.2,1.4,1.6]

    if src=="inj":
        mso.set_trigger(ch=4,value=0.5)
        n=10
    else:
        mso.set_trigger(ch=2,value=None) ## set level mannaly
        if src=="fe":
            n=1000
        elif src=="am":
            n=200
        else:
            n=100

    fname='src'+time.strftime("_xray_%y%m%d-%H%M%S.npy")

    l.set_inj_all(inj_n=1,inj_low=0.2,inj_high=0.2)
    l.set_tdac(others)
    tdac=np.copy(l.tdac)
    l.set_th(1.5)
    l.show()
    
    for p in pixlist:
        l.set_preamp_en(p)
        l.set_inj_en(p)
        l.set_mon_en(p)
        tdac[:,:]=others
        tdac[p[0],p[1]]=0
        l.set_tdac(tdac)
        wavename=os.path.join("output_data/xray",fname[:-4]+"%02d-%03d.txt"%(p[0],p[1]))
        for hv_i,hv in enumerate(hv_list):
          #meas_vol[hv_i],meas_cur[hv_i]=hv.get_current_voltage(ch[hv_i])
          meas_vol[hv_i]=hv.get_voltage()
          meas_cur[hv_i]=hv.get_current()
          
        temp=temperature(l)
        if src=="inj":
            flg=0
            mso.set_scale(ch=1,value=0.100)
            mso.set_scale(ch=2,value=0.005)
            for inj in injlist:
                if inj>0.7 and flg==0:
                     mso.set_scale(ch=1,value=0.5)
                     mso.set_scale(ch=2,value=0.1)
                     flg=1
                l.set_inj_all(inj_n=0,inj_low=0.2,inj_high=inj)
                l.inject()
                mso.measure(n=10,chs=[1,2],save=wavename)
                l.logger.info("xray() mso=%s inj=%.3f,0.2 n=%d"%(wavename,inj,n))
            l.set_inj_all(inj_n=1,inj_low=0.2,inj_high=0.2)
        else:
            mso.measure(n=n,chs=[2],save=wavename)
            l.logger.info("xray() mso=%s n=%d"%(wavename,n))
            res[j]["pix"][:]=p[:]
            res[j]["n"]=n
            j=j+1

    if src=="inj":
        np.save(os.path.join("output_data/xray",fname),{"injlist":injlist,"inj_low":0.2,"n":n})
            

        

        
 
