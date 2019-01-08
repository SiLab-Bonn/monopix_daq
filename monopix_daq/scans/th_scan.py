import os,sys,time

import numpy as np
import bitarray
import tables as tb
import logging
import yaml

import monopix_daq.scan_base as scan_base

local_configuration={"injlist": np.arange(0.1,1.9,0.05),
                     "thlist": [0.82], # None, #[b,e,s]=[1.5,0.5,0.05],
                     "pix":[18,25],
                     "n_mask_pix":12,
                     "with_mon": False
}

class ThScan(scan_base.ScanBase):
    scan_id = "th_scan"
            
    def scan(self,**kwargs): 
        print "##############################"
        print kwargs
        
        ####################
        ## get scan params from args
        pix = kwargs.pop('pix', [18,25])
        if isinstance(pix[0],int):
            pix=[pix]
        injlist= kwargs.pop('injlist', np.arange(0.1,1.9,0.005))
        if injlist is None or len(injlist)==0:
            injlist=[self.dut.SET_VALUE["INJ_HI"]]
        thlist = kwargs.pop('thlist', None)
        if thlist is None or len(thlist)==0:
            thlist=[self.dut.SET_VALUE["TH"]]
        inj_th=np.reshape(np.stack(np.meshgrid(injlist,thlist),axis=2),[-1,2])
        n_mask_pix = kwargs.pop('n_mask_pix', 30)
        with_mon = kwargs.pop('with_mon', False)
        
        ####################
        ## save scan params
        param_dtype=np.dtype([("scan_param_id","<i4"),("pix","<i2",(n_mask_pix,2))])
        description=np.zeros((1,),dtype=param_dtype).dtype
        self.scan_param_table = self.h5_file.create_table(self.h5_file.root, 
                      name='scan_parameters', title='scan_parameters',
                      description=description, filters=self.filter_tables)
        self.meta_data_table.attrs.inj_th = yaml.dump(inj_th)
        
        t0=time.time()

        mask_n=int((len(pix)-0.5)/n_mask_pix+1)
        en=np.copy(self.dut.PIXEL_CONF["PREAMP_EN"])
        for mask_i in range(mask_n):
            mask_pix=[]
            for i in range(mask_i,len(pix),mask_n):
                if en[pix[i][0],pix[i][1]]==1:
                    mask_pix.append(pix[i])
            self.monopix.set_preamp_en(mask_pix)
            self.monopix.set_inj_en(mask_pix)
            if with_mon:
                self.monopix.set_mon_en(mask_pix)

            ####################
            ## start readout
            self.monopix.set_monoread()
            self.monopix.set_timestamp640("inj")
            if with_mon:
                self.monopix.set_timestamp640("mon")
            
            self.scan_param_table.row['scan_param_id'] = i
            mask_pix_tmp=mask_pix
            for i in range(n_mask_pix-len(mask_pix)):
                mask_pix_tmp.append([-1,-1])
            self.scan_param_table.row['pix']=mask_pix_tmp
            self.scan_param_table.row.append()
            self.scan_param_table.flush()

            ####################
            ## start read fifo 
            cnt=0     
            with self.readout(scan_param_id=i,fill_buffer=False,clear_buffer=True,
                              readout_interval=0.005):
              for inj,th in inj_th:
                  if th>0 and self.dut.SET_VALUE["TH"]!=th:
                    self.dut["TH"].set_voltage(th,unit="V")
                    self.dut.SET_VALUE["TH"]=th
                  if inj>0 and self.dut.SET_VALUE["INJ_HI"]!=inj:
                    self.dut["INJ_HI"].set_voltage(inj,unit="V")
                    self.dut.SET_VALUE["INJ_HI"]=inj
                  pre_cnt=cnt
                  cnt=self.fifo_readout.get_record_count()
                  self.dut["inj"].start()
                  while self.dut["inj"].is_done()!=1:
                        time.sleep(0.001)
                  self.logger.info('mask=%d inj=%.3f dat=%d'%(i,inj,cnt-pre_cnt))    
                       
              ####################
              ## stop readout
              self.monopix.stop_timestamp640("inj")
              self.monopix.stop_timestamp640("mon")
              self.monopix.stop_monoread()
              time.sleep(0.2)
              cnt=self.fifo_readout.get_record_count()
            self.logger.info('mask=%d pix=%s dat=%d'%(mask_i,str(mask_pix),cnt-pre_cnt)) 

    def analyze(self, fraw='',debug=0):
        if fraw == '':
           fraw = self.output_filename +'.h5'
        fhit=fraw[:-7]+'hit.h5'
        fev=fraw[:-7]+'ev.h5'
        
        ##interpret and event_build
        import monopix_daq.analysis.interpreter_idx as interpreter_idx
        interpreter_idx.interpret_idx_h5(fraw,fhit,debug=0x8+0x3)
        self.logger.info('interpreted %s'%(fhit))
        import monopix_daq.analysis.assign_timestamp as assign_timestamp
        assign_timestamp.assign_timestamp_h5(fhit,fraw,fev,n=10000000)
        self.logger.info('timestamp assigned %s'%(fev))
        
        ##analyze
        import monopix_daq.analysis.analysis_base as analysis_base
        analysis_base.AnalysisBase(fev,fraw)
        
    def plot(self,fev="",fraw=""):
        if fev =="":
            fev=self.output_filename[:-4]+'ev.h5'
        if fraw =="":
            fraw = self.output_filename +'.h5'
        fpdf = self.output_filename +'.pdf'

        import monopix_daq.analysis.plotting_base as plotting_base
        with plotting_base.PlottingBase(fpdf,save_png=True) as plotting:
            ### configuration 
            with tb.open_file(fraw) as f:
                ###TODO!! format kwargs and firmware setting
                dat=yaml.load(f.root.meta_data.attrs.kwargs)
                dat=yaml.load(f.root.meta_data.attrs.firmware)
                inj_n=dat["inj"]["REPEAT"]

                dat=yaml.load(f.root.meta_data.attrs.dac_status)
                dat.update(yaml.load(f.root.meta_data.attrs.power_status))
                plotting.table_1value(dat,page_title="Chip configuration")

                dat=yaml.load(f.root.meta_data.attrs.pixel_conf)
                plotting.plot_2d_pixel_4(
                    [dat["PREAMP_EN"],dat["INJECT_EN"],dat["MONITOR_EN"],dat["TRIM_EN"]],
                    page_title="Pixel configuration",
                    title=["Preamp","Inj","Mon","TDAC"],
                    z_min=[0,0,0,0], z_max=[1,1,1,15])
            ### plot data
            with tb.open_file(fev) as f:
                dat=f.root.HistOcc[:]
                plotting.plot_2d_pixel_hist(dat,title=f.root.HistOcc.title,z_axis_title="Hits",
                                            z_max=inj_n)
        

    
if __name__ == "__main__":
    from monopix_daq import monopix
    m=monopix.Monopix()
    
    #fname=time.strftime("%Y%m%d_%H%M%S_simples_can")
    #fname=(os.path.join(monopix_extra_functions.OUPUT_DIR,"simple_scan"),fname)
    
    scan = ThScan(m,online_monitor_addr="tcp://127.0.0.1:6500")
    scan.start(**local_configuration)
    scan.analyze()
    scan.plot()
