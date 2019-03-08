#!/usr/bin/env python
import os,sys,time

import numpy as np
import bitarray
import tables as tb
import logging
import yaml
import matplotlib.pyplot as plt

ROW_SIZE=129
COL_SIZE=36

import monopix_daq.scan_base as scan_base
import monopix_daq.analysis.interpreter_idx as interpreter
import monopix_daq.online_monitor.sender

local_configuration={"exp_time": 1.0,
                     "cnt_th": 1,
                     #"cnt_repeat_th": 100,
                     "pix": [18,25],
                     "n_mask_pix": 30,
                     "mode": "disable_noninjected_pixel",
}

class TdacTune(scan_base.ScanBase):
    scan_id = "tdac_tune"
    
    def scan(self,**kwargs):
        cnt_th=kwargs.pop("cnt_th",local_configuration["cnt_th"])
        #cnt_repeat_th=kwargs.pop("cnt_repeat_th",100)
        exp_time=kwargs.pop("exp_time",local_configuration["exp_time"])
        pix=kwargs.pop("pix",local_configuration["pix"])
        mode=kwargs.pop("mode",local_configuration["mode"])
        if pix is None:
            pix=np.argwhere(self.dut.PIXEL_CONF["PREAMP_EN"])
        elif isinstance(pix[0],int):
            pix=np.array([pix])
        else:
            pix=np.array(pix)
        n_mask_pix = kwargs.pop('n_mask_pix', 30)
        n_mask_pix = min(n_mask_pix,len(pix))
        mask_n=int((len(pix)-0.5)/n_mask_pix+1)
        
        ####################
        ## create a table for scan_params
        param_dtype=[("scan_param_id","<i4"),("pix","<i2",(n_mask_pix,2)),("tdac","<f2")]
        description=np.zeros((1,),dtype=param_dtype).dtype
        self.scan_param_table = self.h5_file.create_table(self.h5_file.root,
                      name='scan_parameters', title='scan_parameters',
                      description=description, filters=self.filter_tables)
                      
        scan_param_id=0
        fig,ax=plt.subplots(2,2)

        tdac=self.monopix.get_tdac_memory()
        en=np.copy(self.dut.PIXEL_CONF["PREAMP_EN"])
        cnt=np.ones([16,COL_SIZE,ROW_SIZE])*100

        m=0
        for m in range(mask_n):
          m_pix=[]
          for i in range(m,len(pix),mask_n):
             m_pix.append(pix[i])

          for t in range(15,-1,-1):
              flg=1
              while flg==1 and len(m_pix)>0:
                if mode=="disable_noninjected_pixel":
                    self.monopix.set_preamp_en(m_pix)
                else:
                    self.monopix.set_preamp_en(en)
                if exp_time<0:
                    self.monopix.set_inj_en(m_pix)
                #self.monopix.set_mon_en(m_pix)
                for p in m_pix:
                    tdac[p[0],p[1]]=t
                self.monopix.set_tdac(tdac)
                ##########################
                ## read data
                self.monopix.set_monoread()
                with self.readout(scan_param_id=scan_param_id,fill_buffer=True,clear_buffer=True,
                              readout_interval=0.005):
                    if exp_time < 0:
                        self.monopix.set_timestamp640("inj")
                        self.monopix.start_inj()
                        while self.dut["inj"].is_done()!=1:
                            time.sleep(0.001)
                        self.monopix.stop_timestamp640("inj")
                        time.sleep(0.2)
                    else:
                        time.sleep(exp_time)
                    self.monopix.stop_monoread()
                scan_param_id=scan_param_id+1
                
                ##########################
                ### get data from buffer
                buf = self.fifo_readout.data
                if len(buf)==0:
                    self.logger.info("tdac_tune: mask=%d tdac=%d no data"%(t,m))
                    flg=0
                    for p_i,p in enumerate(m_pix):
                        cnt[t,p[0],p[1]]=0
                    continue
                data = np.concatenate([buf.popleft()[0] for i in range(len(buf))])
                img=interpreter.raw2img(data,delete_noise=False)
                
                ax[0,0].cla()
                ax[0,0].hist(tdac[pix[:,0],pix[:,1]],bins=np.arange(-1,17,1))
                ax[0,0].set_title("tdac=%d"%t)
                ax[1,0].cla()
                ax[1,0].imshow(img,origin="lower",vmax=max(1,cnt_th)*3,aspect="auto")
                ax[0,1].set_title("cnt=%d"%(np.sum(img)))
                ax[0,1].cla()
                for p in pix[m:len(pix):mask_n]:
                    ax[0,1].plot(cnt[:,p[0],p[1]],".-")
                ax[0,1].set_title("mask=%d/%d n_pix=%d"%(m,mask_n,len(m_pix)))
                ax[0,1].set_ybound(0,max(1,cnt_th)*3)
                ax[1,1].cla()
                fig.tight_layout()
                plt.pause(0.005)
                
                ##########################
                ### set for next iteration
                m_pix_next=[]
                flg=0
                for p_i,p in enumerate(m_pix):
                    cnt[t,p[0],p[1]]=img[p[0],p[1]]
                    print "=====%d====="%t,p,img[p[0],p[1]]
                    if img[p[0],p[1]] > cnt_th:
                        flg=1
                        if tdac[p[0],p[1]]==15:
                            en[p[0],p[1]]=False
                        tdac[p[0],p[1]]=min(tdac[p[0],p[1]]+1,15)
                    else:
                        m_pix_next.append(p)
                    img[p[0],p[1]]=0
                for p in np.argwhere(img>cnt_th):
                    cnt[tdac[p[0],p[1]],p[0],p[1]]=img[p[0],p[1]]
                    print "=====*%d*====="%tdac[p[0],p[1]],p,img[p[0],p[1]]
                    if mode=="active":
                        flg=1
                        if tdac[p[0],p[1]]==15:
                            en[p[0],p[1]]=False
                        tdac[p[0],p[1]]=min(tdac[p[0],p[1]]+1,15)
                    elif mode=="disable_noninjected_pixel":
                        print "wrong pixel!!"
                        print interpreter.raw2cnt(data,delete_noise=False)
                        return
                m_pix=m_pix_next

        self.h5_file.create_carray(self.h5_file.root, name='TDACCnts',
                        title='TDAC Cnts',
                        obj=cnt,
                        filters=tb.Filters(complib='blosc', complevel=5, fletcher32=False))
        if exp_time<0:
            for i in range(0,len(pix)):
                p=pix[i]
                t=np.argmin(np.abs(cnt[:,p[0],p[1]]-cnt_th))
                if t==0 and cnt[15,p[0],p[1]] >= cnt_th*2 :
                   t= 15
                elif t==15 and cnt[0,p[0],p[1]]==0 :
                   t=0
                tdac[p[0],p[1]]=t
            self.monopix.set_tdac(tdac)
        self.monopix.set_preamp_en(en)

        ax[0,0].hist(tdac[pix[:,0],pix[:,1]],bins=np.arange(-1,17,1),histtype="step")
        plt.pause(0.005)

    def analyze(self):
        pass
    def plot(self):
        fraw = self.output_filename +'.h5'
        fpdf = self.output_filename +'.pdf'

        import monopix_daq.analysis.plotting_base as plotting_base
        with plotting_base.PlottingBase(fpdf,save_png=True) as plotting:
            with tb.open_file(fraw) as f:
                firmware=yaml.load(f.root.meta_data.attrs.firmware)
                ## DAC Configuration page
                dat=yaml.load(f.root.meta_data.attrs.dac_status)
                dat.update(yaml.load(f.root.meta_data.attrs.power_status))
                plotting.table_1value(dat,page_title="Chip configuration")

                dat=yaml.load(f.root.meta_data.attrs.pixel_conf_before)
                plotting.plot_2d_pixel_4(
                    [dat["PREAMP_EN"],dat["INJECT_EN"],dat["MONITOR_EN"],dat["TRIM_EN"]],
                    page_title="Pixel configuration before tuninig",
                    title=["Preamp","Inj","Mon","TDAC"], 
                    z_min=[0,0,0,0], z_max=[1,1,1,15])

                dat=yaml.load(f.root.meta_data.attrs.pixel_conf)
                plotting.plot_2d_pixel_4(
                    [dat["PREAMP_EN"],dat["INJECT_EN"],dat["MONITOR_EN"],dat["TRIM_EN"]],
                    page_title="Pixel configuration",
                    title=["Preamp","Inj","Mon","TDAC"], 
                    z_min=[0,0,0,0], z_max=[1,1,1,15])
                plotting.plot_1d_pixel_hists([np.array(dat["TRIM_EN"])],mask=dat["PREAMP_EN"],
                                             x_axis_title="TDAC",
                                             title="TDAC distribution",
                                             bins=np.arange(0,16,1))

if __name__ == "__main__":
    from monopix_daq import monopix
    import glob
    import argparse
    
    #########################
    ##### set parameters 
    parser = argparse.ArgumentParser(usage="python tdac_tune.py",
             formatter_class=argparse.RawTextHelpFormatter)
    parser.add_argument('-e',"--exp_time", type=float, default=local_configuration["exp_time"])
    parser.add_argument('-c',"--cnt_th", type=int, default=local_configuration["cnt_th"])
    parser.add_argument('-nmp',"--n_mask_pix", type=int, default=local_configuration["n_mask_pix"])
    parser.add_argument("-to","--th_offset", type=float, default=None)
    parser.add_argument("-t","--th", type=float, default=None)
    parser.add_argument('-i',"--inj", type=float, default=None)
    parser.add_argument("--config_file", type=str, default=None)
    parser.add_argument("--mode", type=str, default=local_configuration["mode"])
    parser.add_argument("-f","--flavor", type=str, default=None)
    parser.add_argument("-p","--power_reset", action='store_const', const=1, default=0) ## defualt=True: skip power reset

    args=parser.parse_args()
    local_configuration["exp_time"]=args.exp_time
    local_configuration["n_mask_pix"]=args.n_mask_pix
    local_configuration["cnt_th"]=args.cnt_th
    local_configuration["mode"]=args.mode

    #########################
    ##### intialize DUT
    m=monopix.Monopix(no_power_reset=not bool(args.power_reset))
    scan = TdacTune(m,online_monitor_addr="tcp://127.0.0.1:6500")
    
    if args.config_file is not None:
        m.load_config(args.config_file)
    else:
        flist=glob.glob(os.path.join(scan.working_dir,"*_th_tune.h5"))
        args.config_file= max(flist, key=os.path.getctime)
	m.load_config(args.config_file)
    print args.config_file

    if args.th is not None:
        m.set_th(args.th)
    if args.th_offset is not None:
        print "threshold was %.4fV but will be added offset of %.4f"%(m.dut.SET_VALUE["TH"],args.th_offset)        
        m.set_th(m.dut.SET_VALUE["TH"]+args.th_offset)
    if args.flavor is not None:
        if args.flavor=="all":
            collist=np.arange(0,m.COL_SIZE)
        else:
            tmp=args.flavor.split(":")
            collist=np.arange(int(tmp[0]),int(tmp[1]))
        pix=[]
        for i in collist:
           for j in range(0,m.ROW_SIZE):
               pix.append([i,j])
        m.set_preamp_en(pix)
    else:
        pix=list(np.argwhere(m.dut.PIXEL_CONF["PREAMP_EN"][:,:]))
    local_configuration["pix"]=pix
        
    if args.inj is not None:
        m.set_inj_high(args.inj+m.dut.SET_VALUE["INJ_LO"])
        if local_configuration["exp_time"]>0 :
            print "tdac will be tuned by injection!!!!!"
        local_configuration["exp_time"]=-1


    scan.start(**local_configuration)
    #scan.analyze()
    scan.plot()