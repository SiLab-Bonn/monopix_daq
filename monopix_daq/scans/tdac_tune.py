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
import monopix_daq.analysis.interpreter as interpreter
import monopix_daq.online_monitor.sender

local_configuration={"exp_time": 1.0,
                     "cnt_th": 1,
                     "cnt_repeat_th": 100,
                     "pix": [18,25],
                     "n_mask_pix": 30,
                     "mode": "active",
}

class TdacTune(scan_base.ScanBase):
    scan_id = "tdac_tune"
    
    def scan(self,**kwargs):
        cnt_th=kwargs.pop("cnt_th",1)
        cnt_repeat_th=kwargs.pop("cnt_repeat_th",100)
        exp_time=kwargs.pop("exp_time",1.0)
        pix=kwargs.pop("pix",None)
        mode=kwargs.pop("mode","active")
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
        en=np.copy(self.dut.PIXEL_CONF["PREAMP_EN"][:,:])
        tdac=np.copy(self.dut.PIXEL_CONF["TRIM_EN"][:,:])
        
        for mask_i in range(mask_n):
          mask_pix=[]
          for i in range(mask_i,len(pix),mask_n):
              if en[pix[i][0],pix[i][1]]==1:
                  mask_pix.append(pix[i])
          for t in range(15,-1,-1):
            for p in mask_pix:
                tdac[p[0],p[1]]=t
            flg=1
            while flg==1 and len(mask_pix)>0:
                ##########################
                ### set pixel config
                self.monopix.set_tdac(tdac)
                self.monopix.set_preamp_en(en)
                if exp_time < 0:
                    self.monopix.set_inj_en(mask_pix)
                
                ##########################
                #### write to param_table
                self.scan_param_table.row['scan_param_id'] = scan_param_id
                self.scan_param_table.row['tdac'] = t
                mask_pix_tmp=mask_pix
                for i in range(n_mask_pix-len(mask_pix)):
                    mask_pix_tmp.append([-1,-1])
                self.scan_param_table.row['pix']=mask_pix_tmp
                self.scan_param_table.row.append()
                self.scan_param_table.flush()

                ##########################
                ## read data
                with self.readout(scan_param_id=scan_param_id,fill_buffer=True,clear_buffer=True,
                              readout_interval=0.005):
                    self.monopix.set_monoread()
                    if exp_time < 0:
                        self.monopix.set_timestamp640("inj")
                        self.monopix.start_inj()
                        while self.dut["inj"].is_done()!=1:
                            time.sleep(0.001)
                        time.sleep(0.1)
                        self.monopix.stop_timestamp640("inj")
                    else:
                        time.sleep(exp_time)
                    self.monopix.stop_monoread()
                scan_param_id=scan_param_id+1
                
                ##########################
                ## get data from buffer
                buf = self.fifo_readout.data
                if len(buf)==0:
                    self.logger.info("tune_tdac:tdac=%d pix=%d, no data"%(t,len(np.argwhere(mask_pix))))
                    flg=0
                    continue
                data = np.concatenate([buf.popleft()[0] for i in range(len(buf))])
                img=interpreter.raw2img(data)
                
                ##########################
                ## showing status
                self.logger.info("tune_tdac:%2d===data %d=====cnt %d==========="%(mask_i,len(data),np.sum(img)))
                fig,ax=plt.subplots(2,2)
                ax[0,0].imshow(np.transpose(img),vmax=min(np.max(img),100),origin="low",aspect="auto")
                ax[0,0].set_title("mask_pix=%d th=%.4f"%(len(mask_pix),self.dut.SET_VALUE["TH"]))
                ax[1,0].imshow(np.transpose(tdac),vmax=16,vmin=0,origin="low",aspect="auto")
                ax[1,0].set_title("mask_i=%d tdac=%d"%(mask_i, t))
                ax[1,1].hist(np.reshape(tdac[en],[-1]),bins=np.arange(0,16,1))
                ax[1,1].set_title("TDAC0=%d"%len(np.where(tdac==0)))
                ax[0,1].imshow(np.transpose(en),vmax=1,vmin=0,origin="low",aspect="auto")
                ax[0,1].set_title("en=%d"%len(np.where(en[0])))
                fig.tight_layout()
                fig.savefig(os.path.join(self.working_dir,"last_scan.png"),format="png")
                
                ##########################
                ## find next tdac value
                flg=0
                next_pix=[]
                for p_i, p in enumerate(mask_pix):
                    if img[p[0],p[1]] > cnt_repeat_th:
                        flg=1
                    if img[p[0],p[1]] > cnt_th:
                        self.logger.info("tune_tdac:%2d-%3d tdac=%2d cnt=%d"%(p[0],p[1],tdac[p[0],p[1]],img[p[0],p[1]]))
                        if tdac[p[0],p[1]]==15:
                            en[p[0],p[1]]=False
                            img[p[0],p[1]]=0
                        else:
                            tdac[p[0],p[1]]=tdac[p[0],p[1]]+1
                            img[p[0],p[1]]=0
                    else:
                        next_pix.append([p[0],p[1]])
                if mode=="active":
                  for p in np.argwhere(img>cnt_repeat_th):
                    self.logger.info("tune_tdac(active):%2d-%3d tdac=%2d cnt=%d"%(p[0],p[1],tdac[p[0],p[1]],img[p[0],p[1]]))
                    if tdac[p[0],p[1]]==15:
                        tdac[p[0],p[1]]=15
                        #en[p[0],p[1]]=False
                        img[p[0],p[1]]=0
                    else:
                        tdac[p[0],p[1]]=tdac[p[0],p[1]]+1
                        img[p[0],p[1]]=0
                        
                if flg!=0:
                    self.logger.info("tune_tdac:repeat tdac=%d"%(t))
                mask_pix=next_pix

        ### set tdac and en from the last step
        self.monopix.set_tdac(tdac)
        self.monopix.set_preamp_en(en)

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
                                             x_axis_title="Testpulse [V]",
                                             title="TDAC distribution",
                                             bins=np.arange(0,16,1))

if __name__ == "__main__":
    from monopix_daq import monopix
    import glob
    import argparse
    
    #########################
    ##### set parameters 
    parser = argparse.ArgumentParser(usage="analog_scan.py xxx_scan",
             formatter_class=argparse.RawTextHelpFormatter)
    parser.add_argument('-e',"--exp_time", type=float, default=local_configuration["exp_time"])
    parser.add_argument('-c',"--cnt_th", type=int, default=local_configuration["cnt_th"])
    parser.add_argument('-n',"--n_mask_pix", type=int, default=local_configuration["n_mask_pix"])
    parser.add_argument("-t","--th_offset", type=float, default=0.002)
    parser.add_argument("--config_file", type=str, default=None)
    parser.add_argument("--mode", type=str, default=local_configuration["mode"])
    args=parser.parse_args()
    local_configuration["exp_time"]=args.exp_time
    local_configuration["n_mask_pix"]=args.n_mask_pix
    local_configuration["cnt_th"]=args.cnt_th
    local_configuration["mode"]=args.mode

    #########################
    ##### intialize DUT
    m=monopix.Monopix()
    scan = TdacTune(m,online_monitor_addr="tcp://127.0.0.1:6500")
    
    if args.config_file==None:
        flist=glob.glob(os.path.join(scan.working_dir,"*_th_tune.h5"))
        args.config_file= max(flist, key=os.path.getctime)
    print args.config_file
    m.load_config(args.config_file)
    en=np.copy(m.dut.PIXEL_CONF["PREAMP_EN"][:,:])
    en[16:20,:]=True
    m.set_preamp_en(en)
    m.set_th(m.dut.SET_VALUE["TH"]+args.th_offset)
    local_configuration["pix"]=np.argwhere(en)

    scan.start(**local_configuration)
    #scan.analyze()
    scan.plot()
    #plt.plot(np.arange(10))