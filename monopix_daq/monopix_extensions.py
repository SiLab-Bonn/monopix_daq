import sys,time,os
import numpy as np
import matplotlib.pyplot as plt
import logging
import warnings
import yaml
import monopix
import tables

sys.path = [os.path.dirname(os.path.abspath(__file__))] + sys.path 
COL_SIZE = 36 ##TODO change hard coded values
ROW_SIZE = 129
OUTPUT_DIR=os.path.join(os.path.dirname(os.path.abspath(__file__)),"output_data")

from basil.dut import Dut

## TODO separated file        
def analyse_hit_timestamp(raw_data,fmt="img",debug=0):
    #print "raw_data",len(raw_data)
    packet=4
    data_type = {'names':['col','row','le','te','flg','timestamp','cnt'], 'formats':['uint8','uint8','uint8','uint8','uint8','int64','int32']}
    raw_data=raw_data[raw_data&0xC0000000==0x0]
    if len(raw_data[raw_data&0xC0000000!=0x0]):
        print("trash")
    size = len(raw_data)
    if "img" in fmt:
        ret_zero=np.zeros([COL_SIZE,ROW_SIZE],int)
    else:
        ret_zero=np.recarray((0), dtype=data_type)
    if size==0:
        return ret_zero
    ## check
    for i in range(len(raw_data)):
        if raw_data[i]&0xF0000000 == 0x10000000:
           break
        else:
            pass
            #warnings.warn("idx=%d data=%x"%(i,raw_data[i]))
    #if debug==1:
    #  for j in range(i,len(raw_data),packet):
    #    print j/packet, hex(raw_data[j]),hex(raw_data[j+1]),hex(raw_data[j+2])
    
    #if i!=0:
    #    print "analyse_hit_timestamp: n_of_trash_data=%d"%i

    for pack_i in range(packet):
        if np.any((raw_data[i+pack_i::packet] & 0xF0000000) != (((pack_i+1)&0x3) * 0x10000000)):
            j=0
            for i in np.arange(len(raw_data)):
                print(hex(raw_data[i])),
                if (raw_data[i]&0xF0000000==((packet&0x3)* 0x10000000)):
                        print("") 
            raise ValueError("analyse_hit_timestamp: broken data %d"%pack_i)

    ret = np.recarray((size-i)/packet, dtype=data_type)
    raw_data=raw_data[i:((size-i)/packet)*packet+i]
    #print i,size,(size-i)/packet, len(raw_data), len(ret),len(raw_data[::packet]),len(raw_data[1::packet]),len(raw_data[2::packet])
    ret['col'][:] = raw_data[::packet] & 0b111111
    ret['flg'][:] = (raw_data[::packet] >> 6) & 0b1
    ret['row'][:] = (raw_data[::packet] >> 8) & 0xff
    ret['te'][:] =  raw_data[1::packet] & 0xff
    ret['le'][:] = (raw_data[1::packet] >> 8) & 0xff
    ret['timestamp'][:] = np.int64(raw_data[::packet] >> 16) & 0xfff \
                       | (np.int64(raw_data[1::packet] >> 16) & 0xfff)<<12 \
                       | np.int64(raw_data[2::packet] & 0xfffffff)<<24
    ret['cnt'][:] = raw_data[3::packet] & 0xffffff
    if "without30" in fmt:
        ret=ret[ret["flg"]==0]
    if len(ret)==0:
        return ret_zero
    #print "ret",len(ret)
    if "img" in fmt:
        ret=np.histogram2d(ret["col"],ret["row"],bins=[np.arange(0,37,1),np.arange(0,130,1)])[0]
    return ret
    
class Monopix():

#    def set_tdc(self):
#        self.dut["timestamp_mon"].reset()
#        self.dut["timestamp_mon"]["EXT_TIMESTAMP"]=True
#        self.dut["timestamp_mon"]["ENABLE"]=1
#        self.logger.info("set_timestamp_mon:start")
        
#    def stop_tdc(self):
#        self.dut["timestamp_mon"]["ENABLE"]=0
#        lost_cnt=self.dut["timestamp_mon"]["LOST_COUNT"]
#        if lost_cnt!=0:
#            self.logger.warn("stop_timestamp: lost_cnt=%d"%lost_cnt)
#        return lost_cnt
        
    def scan_inj_simple(self,b=0.2,e=1.8,s=0.05,save=True):
        if isinstance(save,str):
            fname=save
            save=True
        elif save==True:
            fname=mk_fname("inj",ext="npy")
            
        inj_list=np.arange(b,e,s)
        if save==True:
            with open(fname,"ab") as f:
                np.save(f,inj_list)
                
        for inj_i,inj_high in enumerate(np.arange(b,e,s)):
            self.set_inj_high(inj_high)
            self.start_inj()
            while not self.dut["inj"]["READY"]:
                time.sleep(0.001)
            raw=self.get_data()
            ## analyse a bit
            if len(raw)==0:
                tot=0
                raw=np.empty(0,dtype="u4")
            else:
                dat=analyse_hit_timestamp(raw,"list")
                tot=np.average((dat["te"]-dat["le"])&0xFF)
            if save:
                with open(fname,"ab") as f:
                    np.save(f,raw)
            self.logger.info("scan_inj_simple: %f %d %f"%(inj_high,len(raw),tot))            
            #print inj_i,inj_high,len(dat),dat
                       
    def find_inj(self,b,e,s,save,pix,mode,
                 start_freeze,start_read,stop_read,stop_freeze,stop):        
        self.set_inj_high(b)
        self.logger.info("scan inj_low inj_high cnt_all cnt_pix")
        if isinstance(pix[0],int):
            pix=[pix]
        pix_org=pix
        pix=[]
        for p in pix_org:
            if self.dut.PIXEL_CONF["PREAMP_EN"][p[0],p[1]]:
                pix.append(p)
        if isinstance(save,str):
            fname=save
            save=True
        elif save==True:
            fname=mk_fname("inj",ext="npy")
        else:
            fname=""
        idx=0
        s0=s
        if e>b:
            s=max((e-b)/20,s0)
        else:
            s=min((e-b)/20,s0)
        injlist=np.arange(b+s,e,s)
        flg=0
        self.set_monoread(start_freeze=start_freeze,start_read=start_read,stop_read=stop_read,stop_freeze=stop_freeze,stop=stop)
        d=self.get_data()
        while idx<len(injlist):
            for i in range(5):
              try:
                d=self.get_data()
                img=analyse_hit_timestamp(d,"img")
                break
              except:
                print("==========trash data retry %d=========="%i)
                for dd in d:
                    print(hex(dd)), #end="")
                self.stop_monoread()
                time.sleep(1)
                self.set_monoread()
            tmps="find_inj %.4f %.4f"%(self.dut.SET_VALUE["INJ_LO"],self.dut.SET_VALUE["INJ_HI"])
            if save==True:
                with open(fname,"ab+") as f:
                   np.save(f,{"inj_high":self.dut.SET_VALUE["INJ_HI"],"inj_low":self.dut.SET_VALUE["INJ_LO"],"hit":d})
            self.set_inj_high(injlist[idx])

            
            if self.plot==True and self.debug==1:
                plt.clf()
                plt.pcolor(img)
                plt.pause(0.001)
            cnt=np.sum(img)
            cnt_pix=0
            for p in pix:
                cnt_pix=cnt_pix+min(img[p[0],p[1]],100)        
            self.logger.info("%s %d %d"%(tmps,cnt,cnt_pix))
            if cnt_pix!=0 and s!=s0:
                #print "small step"
                injlist=np.arange(max(self.dut.SET_VALUE["INJ_HI"]-2*s,b),e,s0)
                s=s0
                idx=0
                self.set_inj_high(injlist[idx])
            elif idx==len(injlist)-1 and s!=s0:
                s=s0
                injlist=np.arange(b,e,s0)
                idx=0
                self.set_inj_high(injlist[idx])
            elif cnt_pix==len(pix)*100 and flg==0:
                flg=1
            elif flg==10 and mode=="full":
                break
            elif flg>0:
                flg=flg+1
            idx=idx+1
        d=self.get_data()
        self.stop_monoread()
        self.stop_timestamp()
        if save==True:
            with open(fname,"ab+") as f:
                np.save(f,{"inj_high":self.dut.SET_VALUE["INJ_HI"],"inj_low":self.dut.SET_VALUE["INJ_LO"],"hit":d})
        tmps="scan_inj %.4f %.4f"%(self.dut.SET_VALUE["INJ_LO"],self.dut.SET_VALUE["INJ_HI"])
        img=analyse_hit_timestamp(d,"img")
        cnt=np.sum(img)
        cnt_pix=0
        for p in pix:
            cnt_pix=cnt_pix+img[p[0],p[1]]  
        self.logger.info("%s %d %d"%(tmps,cnt,cnt_pix))
        self.logger.info("scan_inj() fname=%s"%fname)
        return fname
        
    def scan_tdac(self,mode="inj",pix=[18,25],save=True):
        tdac=np.copy(self.dut.PIXEL_CONF["TRIM_EN"])
        if isinstance(pix[0],int):
            pix=[pix]
        if isinstance(save,str):
            fname=save
            save=True
            self.logger.info("find_tdac_tdc file:%s"%(fname))
        elif save==True:
            fname=mk_fname("scantdac",ext="npy")
            self.logger.info("find_tdac_tdc file:%s"%(fname))
        self.logger.info("find_tdac_tdc pix:%s"%(str(pix)))
        for t in range(15,-1,-1):
            for p in pix:
                tdac[p[0],p[1]]=t
            self.set_tdac(tdac)
            self.dut["fifo"].reset()
            d=self.get_data()
            if save==True:
                with open(fname,"ab+") as f:
                        np.save(f,d)
            self.dut["fifo"].reset()
            ret=analyse_hit_timestamp(d,"list")
            tot=(ret['te']-ret['le'])&0xFF
            
            self.logger.info("find_tdac_tdc %d %d %f %f"%(t,len(d),np.average(tot),np.average(ret['le'])))
        
            
    def source(self,mode="src",save=True,exp=2.0):
        if self.plot==True:
            plt.ion()
        if isinstance(save,str):
            fname=save
            save=True
        elif save==True:
            fname=mk_fname("source",ext="npy")
            self.logger.info("source: fname=%s"%fname)
            with open(fname,"ab+") as f:
                np.save(f,exp)
        self.set_monoread()
        t0=time.time()
        d=np.empty(0,dtype='uint32')
        img=np.zeros([36,129])
        done=-exp
        if self.plot:
            pre_done=-exp
        while done < 0:
            fdata = self.get_data_now()
            #print 'fdata', len(fdata)
            d=np.append(d,fdata)
            done= time.time()-t0-exp
            if done < -2 or done > 0:
                if save==True and (done < -2 or done > 0):
                    with open(fname,"ab+") as f:
                        np.save(f,d)
                if self.plot==True:   #and done-pre_done>1:
                    img=img+analyse_hit_timestamp(d,"img_without30")
                    plt.clf()
                    plt.pcolor(img,vmin=0)
                    plt.colorbar()
                    plt.title("%d %.2fs"%(np.sum(img), done))
                    plt.pause(0.001)
                    pre_done=done
                time.sleep(0.001)
                d=np.empty(0,dtype='uint32')
        self.stop_monoread()
            #self.logger.info("source: %d %s"%(np.sum(img),str(img[14,25])))
        self.logger.info("source: scan_time=%fs(%f)"%(exp,time.time()-t0))
        if save==True:
            return fname

    def scan_th_simple(self,b=0.9,e=0.75,s=-0.01,exp=10,save=True):
        if save==True:
            fname=mk_fname("scan_th_simple",ext="npy")
        self.logger.info("scan_th_simple: fname=%s"%fname)
        thlist=np.arange(b,e,s)
        with open(fname,"ab+") as f:
            np.save(f,{"thlist":thlist,"exp":exp})
        for th in thlist:
            self.set_th(th)
            self.source(save=fname,exp=exp)
            

        
#    def set_power(self,**kwarg):
#        for k in kwarg.keys():
#            self.dut[k].set_voltage(kwarg[k])
#            self.dut.SET_VALUE[k]=kwarg[k]
#        s="set_power:"
#        for k in kwarg.keys():
#            s=s+"%s=%d "%(k,kwarg[k])
#        self.logger.info(s)

    
    def tune_tdac_source(self, th_s=0.8, s=-0.0005, LSBdacL=52, flavor="all", preamp="all",
                         tdac=None,
                         exp=1, cnt_th=0, disable=0.002, save=True, flg="", col_n=129):
        self.set_inj_en("none")
        if isinstance(flavor,str):
            if ":" in flavor:
                tmp=flavor.split(":")
                f_s=int(tmp[0])
                f_e=int(tmp[1])
                col_list=np.arange(f_s,f_e,1)
            elif flavor=="all":
                f_s=0
                f_e=36
                col_list=np.arange(f_s,f_e,1)
        else:
            col_list=np.array(flavor)
            
        if self.plot==True:
                plt.ion()
                plt.clf()

        tdac_s=tdac
        tdac=np.copy(self.dut.PIXEL_CONF["TRIM_EN"])
        preamp_s=preamp

        while True:
          pixlist=[]
          for i in col_list:
            for j in range(0,col_n,1):
                pixlist.append([int(i),int(j)])
          pixlist=np.array(pixlist)
          
          if tdac_s==None:  
              tdac[:,:]=15
              for i in col_list:
                  for j in range(0,col_n,1):
                      tdac[i,j]=0
              self.set_tdac(tdac)
          else:
              self.set_tdac(tdac_s)
          tdac=np.copy(self.dut.PIXEL_CONF["TRIM_EN"])

          if preamp_s=="auto":
              self.set_preamp_en(pixlist,"auto")
          else:
              self.set_preamp_en(preamp_s,flavor)
          preamp=np.copy(self.dut.PIXEL_CONF["PREAMP_EN"])
          
          self.set_global(LSBdacL=LSBdacL)

          th=th_s
          self.set_th(th)

          if flg=="lsb":
              flg=""
          while True:
            self.set_monoread()
            time.sleep(exp)
            d=self.get_data_now()
            exp_meas=self.stop_monoread()
            print("----%.3f %d----%d"%(th, LSBdacL,len(d))),
            print("---- pix(tdac=15) %d"%len(np.argwhere(tdac[col_list,:col_n]==15))),
            print("---- pix(tdac=0) %d"%len(np.argwhere(tdac[col_list,:col_n]==0)))
            img=analyse_hit_timestamp(d,"img")  #analyse_hit_timestamp(d,"img_without30")
            plist=np.argwhere(img > cnt_th)
            if len(plist)>len(col_list)*col_n/3:
                print("ERROR ERROR ERROR %dpiexels fired ERROR ERROR ERROR"%len(plist))
                th=th-s
                self.set_th(th)
                continue
            for p in plist:
              if not p[0] in col_list:
                 print("a noisy pixel is firefing %d-%d"%(p[0],p[1]))
              if tdac[p[0],p[1]]==15:
                tdac[p[0],p[1]]=15
                preamp[p[0],p[1]]=False
                self.set_preamp_en(preamp,flavor)
                print("%d-%d %d disable=%d"%(p[0],p[1],img[p[0],p[1]],tdac[p[0],p[1]]))
              else:
                tdac[p[0],p[1]]=tdac[p[0],p[1]]+1
                print("%d-%d %d new=%d"%(p[0],p[1],img[p[0],p[1]],tdac[p[0],p[1]]))
            if len(plist)==0:
              res={"th":th,"tdac":tdac,"LSBdacL":LSBdacL,"preamp":preamp}
              if self.plot==True:
                  plt.clf()
                  plt.subplot(221)
                  plt.hist(np.reshape(tdac[col_list,:col_n],len(col_list)*col_n),bins=np.arange(0,17,1))
                  plt.title("LSB=%d"%LSBdacL)
                  plt.yscale("log")
                  plt.ylim(0.1,len(col_list)*col_n)
                  plt.subplot(222)
                  plt.pcolor(tdac[col_list,:col_n],vmax=15,vmin=0)
                  plt.subplot(223)
                  plt.pcolor(img,vmax=cnt_th+1,vmin=0)
                  plt.title("TH=%f"%th)
                  plt.tight_layout()
                  plt.pause(0.001)
              th=th+s
              self.set_th(th)
            else:
              self.set_tdac(tdac)
            if len(np.argwhere(tdac[col_list,:col_n]==0))<2:
              if flg!="fixlsb":
                  LSBdacL=LSBdacL-4
                  flg="lsb"
              break
            if len(np.argwhere(tdac[col_list,:col_n]==15))>len(col_list)*col_n*disable:
              print("disabled pixel>threshold %d"%(len(col_list)*col_n*disable))
              flg="done"
              break
            if len(np.argwhere(tdac[col_list,:col_n]==0))<len(col_list)*col_n*disable*0.1:
              print("tdac0 pixel<threshold %d"%(len(col_list)*col_n*disable))
              flg="done"
              break
          if flg=="done" or flg=="fixlsb":
            break
        self.set_tdac(res["tdac"])
        self.set_preamp_en(res["preamp"],flavor)
        self.set_th(res["th"])
        self.set_global(LSBdacL=res["LSBdacL"])
        if save==True:
            fname=mk_fname("tdac",ext="yaml")
            self.save_config(fname)
            np.save(fname[:-4]+"npy",res)
        if self.plot==True:
            plt.subplot(211)
            plt.hist(np.reshape(res["tdac"][col_list,:col_n],len(col_list)*col_n),bins=np.arange(0,16,1))
            plt.title("LSB=%d th=%f"%(res["LSBdacL"],res["th"]))
            plt.subplot(212)
            plt.pcolor(res["tdac"][col_list,:col_n],vmax=15,vmin=0)
            plt.pause(0.001)
        return res
        
    def scan_inj_all(self,b=0.2,e=1.5,s=0.005,flavor='16:20',mode="full",
                    save=True,mask=80,
                    start_freeze=50,start_read=55,stop_read=55+2,stop_freeze=55+36,stop=55+36+10):
        if flavor=="all":
            col_list=np.arange(0,36)
        elif ":" in flavor:
            tmp=flavor.split(":")
            col_list=np.arange(int(tmp[0]),int(tmp[1]))

        pixlist=[]
        for i in col_list:
           for j in range(0,129,1):
               pixlist.append([i,j])
        pixlist=np.array(pixlist)

        if isinstance(save,bool):
            save=mk_fname("inj",ext="npy")

        for mask_i in range(mask):
            injlist=[]
            for p in pixlist[mask_i::mask]:
                injlist.append([p[0],p[1]])
            self.set_inj_en(injlist)
            if isinstance(save,str):
                with open(save,"ab") as f:
                    np.save(f,{"injlist":injlist})
                    f.flush()
            self.find_inj(b=b,e=e,s=s,pix=injlist,save=save,mode=mode,
                          start_freeze=start_freeze,start_read=start_read,stop_read=stop_read, stop_freeze=stop_freeze,stop=stop)
        self.logger.info("scan_inj_all() mask=%d flavor=%s"%(mask,flavor))
        
        



        
    def find_noisy(self,b=0.8,e=0.6,s=-0.0005,exp=1,th_cnt=2,break_cnt=513,save=True):
        if isinstance(save,bool):
            save=mk_fname("noisy",ext="npy")
        for th in np.arange(b,e,s):
            self.set_th(th)
            en=np.copy(self.dut.PIXEL_CONF["PREAMP_EN"][:,:])
            self.set_monoread()
            self.dut["fifo"].reset()
            time.sleep(exp)
            d=self.get_data_now()
            self.stop_monoread()
            if len(d)==0:
                self.logger.info("find_noisy:no data th=%d en=%d"%(th,len(np.argwhere(en))))
                continue
            if save==True:
                np.save(fname,{"preamp_en":en,"dat":d,"th":th})
            ret=analyse_hit_timestamp(d,"img")
            plt.clf()
            plt.pcolor(ret,vmax=100,cmap="jet")
            plt.title("en=%d, noisy=%d th=%.4f"%(len(np.argwhere(en)),len(np.argwhere(ret>th_cnt)),th))
            plt.pause(0.01)
            en_next=np.bitwise_and(en, ret<=th_cnt)
            arg=np.argwhere(ret>th_cnt)
            print "noisy pixel %d"%len(arg),
            for a in arg:
                print "[%d,%d]=%d"%(a[0],a[1],ret[a[0],a[1]]),
            self.logger.info("find_noisy:th=%.4f en=%d"%(th,len(np.argwhere(en_next))))
            if break_cnt < len(np.argwhere(en_next)):
                self.set_preamp_en(en_next)
            else:
                return th-s,en
        return th,en_next
    def find_tdac(self,pix,exp=1,th_cnt=0,save=True,th_stop=100):
        tdac=np.copy(self.dut.PIXEL_CONF["TRIM_EN"])
        preamp=np.copy(self.dut.PIXEL_CONF["PREAMP_EN"])
        for t in range(15,-1,-1):
            #print "=====t%d pix%d START====="%(t,len(pix))
            flg=1
            while flg==1 and len(pix)!=0:
                for p in pix:
                  #print p[0],p[1],tdac[p[0],p[1]],t
                  #if tdac[p[0],p[1]] > t:
                    tdac[p[0],p[1]]=t
                self.set_tdac(tdac)
                self.set_preamp_en(preamp)
                self.set_monoread()
                time.sleep(exp)
                d=self.get_data_now()
                self.stop_monoread()
                #if len(d)==0:
                #     print "=====t%d pix%d no pulse go next t====="%(t,len(pix))
                #     ret=analyse_hit_timestamp(d,"img")
                #     print len(np.argwhere(ret>th_cnt))
                #     flg=0
                #     continue
                ret=analyse_hit_timestamp(d,"img")
                if len(np.argwhere(ret>1000))>th_stop:
                    print "=====t%d pix%d too many noisy pixel=====%d"%(t,len(pix),len(np.argwhere(ret>1000)))
                    return -1,ret
                pix_next=[]
                flg=0
                for p in pix:
                    if ret[p[0],p[1]]>th_cnt:
                       print "%d [%d,%d]=%d noise!!"%(tdac[p[0],p[1]],p[0],p[1],ret[p[0],p[1]])
                       if ret[p[0],p[1]]>1000:
                           flg=1
                       if tdac[p[0],p[1]]==15:
                           preamp[p[0],p[1]]=False
                       else:
                           tdac[p[0],p[1]]=tdac[p[0],p[1]]+1
                    else:
                        pix_next.append(p)
                pix=pix_next
        self.set_tdac(tdac)
        self.set_preamp_en(preamp)
        self.set_monoread()
        time.sleep(exp)
        d=self.get_data_now()
        self.stop_monoread()
        ret=analyse_hit_timestamp(d,"img")
        if isinstance(save,str):
           fname=save
           save=True
        else:
           fname=mk_fname("findtdac",ext="npy")
        if save:
           with open(fname,"ab") as f:
               np.save(f,{"tdac":tdac,"preamp":preamp,"data":d})
        return 0,ret
    
