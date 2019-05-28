import os,sys,time

import numpy as np
import bitarray
import tables as tb
import logging
import yaml

import monopix_daq.scan_base as scan_base

local_configuration={"injlist": None, #np.arange(0.1,0.6,0.05),
                     "thlist": None, # None, [0.82], np.arange(),
                     "phaselist": None, # np.arange(0,16,1),
                     "pix":[18,25],
                     "n_mask_pix":12,
                     "with_mon": False
}

class InjectionScan(scan_base.ScanBase):
    scan_id = "injection_scan"
            
    def scan(self,**kwargs):
        """ List of kwargs
            pix: list of pixel
            n_mask_pix: number of pixels injected at onece
            injlist: list of inj (inj_high-inj_low)
            thlist: list of th
            phaselist: list of phase
            with_mon: get timestamp of mon (mon will be enabled)
        """
        ####################
        ## get scan params from args
        pix=kwargs.pop("pix")
        if isinstance(pix[0],int):
            pix=[pix]

        n_mask_pix = min(kwargs.pop("n_mask_pix"),len(pix))
        mask_n=int((len(pix)-0.5)/n_mask_pix+1)
        en=np.copy(self.dut.PIXEL_CONF["PREAMP_EN"])
        
        injlist=kwargs.pop("injlist")
        if injlist is None or len(injlist)==0:
            injlist=[self.dut.SET_VALUE["INJ_HI"]-self.dut.SET_VALUE["INJ_LO"]]
        thlist=kwargs.pop("thlist")
        if thlist is None or len(thlist)==0:
            thlist=[self.dut.SET_VALUE["TH"]]
        phaselist=kwargs.pop("phaselist")
        if phaselist is None or len(phaselist)==0:
            phaselist=[self.dut["inj"].get_phase()]
        inj_th_phase = np.reshape(np.stack(np.meshgrid(injlist,thlist,phaselist),axis=3),[-1,3])
        
        with_mon=kwargs.pop("with_mon")
        disable_noninjected_pixel=kwargs.pop("disable_noninjected_pixel")
        
        debug=kwargs.pop("debug",0)
        
        if (debug & 0x1)==1:
            print "++++++++ injlist",len(injlist),injlist
            print "++++++++ thlist",len(thlist),thlist
            print "++++++++ phaselist",len(phaselist),phaselist
            print "++++++++ with_mon",with_mon
            print "++++++++ n_mask_pix, mask_n",n_mask_pix,mask_n

        param_dtype=[("scan_param_id","<i4"),("pix","<i2",(n_mask_pix,2))]

        glist=[]
        #for k,v in kwargs.iteritems():
        #    param_dtype.append((k,"<u1"))
        #    for v_e in v:
        #        glist.append({k:v_e})
        if len(glist)==0:
            glist=[None]

        ####################
        ## create a table for scan_params
        description=np.zeros((1,),dtype=param_dtype).dtype
        self.scan_param_table = self.h5_file.create_table(self.h5_file.root, 
                      name='scan_parameters', title='scan_parameters',
                      description=description, filters=self.filter_tables)
        self.kwargs.append("thlist")
        self.kwargs.append(yaml.dump(inj_th_phase[:,1]))
        self.kwargs.append("injlist")
        self.kwargs.append(yaml.dump(inj_th_phase[:,0]))
        self.kwargs.append("phaselist")
        self.kwargs.append(yaml.dump(inj_th_phase[:,2]))
        self.kwargs.append("with_mon")
        self.kwargs.append(yaml.dump(with_mon)) 
        self.kwargs.append("disable_noninjected_pixel")
        self.kwargs.append(yaml.dump(disable_noninjected_pixel))
        
        t0=time.time()
        scan_param_id=0
        inj_delay_org=self.dut["inj"].DELAY
        inj_width_org=self.dut["inj"].WIDTH
        for g in glist:
          if g is not None:
              self.monopix.set_global(**g)
          for mask_i in range(mask_n):
            mask_pix=[]
            for i in range(mask_i,len(pix),mask_n):
                if en[pix[i][0],pix[i][1]]==1:
                    mask_pix.append(pix[i])
            self.monopix.set_inj_en(mask_pix)
            if disable_noninjected_pixel:
                self.monopix.set_preamp_en(mask_pix)
            if with_mon:
                self.monopix.set_mon_en(mask_pix)

            ####################
            ## start readout
            self.monopix.set_monoread()
            self.monopix.set_timestamp640("inj")
            if with_mon:
                self.monopix.set_timestamp640("mon")

            ####################
            ## save scan_param
            self.scan_param_table.row['scan_param_id'] = scan_param_id
            mask_pix_tmp=mask_pix
            for i in range(n_mask_pix-len(mask_pix)):
                mask_pix_tmp.append([-1,-1])
            self.scan_param_table.row['pix']=mask_pix_tmp
            if g is not None:
              for g_key in g.keys():
                self.scan_param_table.row[g_key]=g[g_key]
            self.scan_param_table.row.append()
            self.scan_param_table.flush()

            ####################
            ## start read fifo 
            cnt=0
            with self.readout(scan_param_id=scan_param_id,fill_buffer=False,clear_buffer=True,
                              readout_interval=0.001):
                for inj,th,phase in inj_th_phase:
                  if th>0 and self.dut.SET_VALUE["TH"]!=th:
                    self.dut["TH"].set_voltage(th,unit="V")
                    self.dut.SET_VALUE["TH"]=th
                  inj_high=inj+self.dut.SET_VALUE["INJ_LO"]
                  if inj_high>0 and self.dut.SET_VALUE["INJ_HI"]!=inj_high:
                    self.dut["INJ_HI"].set_voltage(inj_high,unit="V")
                    self.dut.SET_VALUE["INJ_HI"]=inj_high
                  if phase>0 and self.dut["inj"].get_phase()!=phase:
                      self.dut["inj"].set_phase(int(phase)%16)
                      
                      self.dut["inj"].DELAY=inj_delay_org+int(phase)/16
                      self.dut["inj"].WIDTH=inj_width_org-int(phase)/16
                      if (debug & 0x1)==1:
                         self.logger.info("inj phase=%x,period=%d"%(
                         self.dut["inj"].PHASE_DES,self.dut["inj"].DELAY+self.dut["inj"].WIDTH))
                  self.dut["inj"].start()
                  while self.dut["inj"].is_done()!=1:
                        time.sleep(0.005)
                  pre_cnt=cnt
                  
                  if (debug & 0x2)==2:
                    cnt=self.fifo_readout.get_record_count()
                    self.logger.info('mask=%d th=%.3f inj=%.3f phase=%d dat=%d'%(
                      scan_param_id,th,inj,self.dut["inj"].get_phase(),cnt-pre_cnt))    
                       
                ####################
                ## stop readout
                self.monopix.stop_timestamp640("inj")
                self.monopix.stop_timestamp640("mon")
                self.monopix.stop_monoread()
                time.sleep(0.2)
                pre_cnt=cnt
                cnt=self.fifo_readout.get_record_count()
                
            self.logger.info('mask=%d pix=%s dat=%d'%(mask_i,str(mask_pix),cnt-pre_cnt))
            scan_param_id=scan_param_id+1

    def analyze(self):
        fraw = self.output_filename +'.h5'
        fhit=fraw[:-7]+'hit.h5'
        fev=fraw[:-7]+'ev.h5'
        
        ##interpret and event_build
        import monopix_daq.analysis.interpreter_idx as interpreter_idx
        interpreter_idx.interpret_idx_h5(fraw,fhit,debug=0x8+0x3)
        self.logger.info('interpreted %s'%(fhit))
        import monopix_daq.analysis.event_builder_inj as event_builder_inj
        event_builder_inj.build_inj_h5(fhit,fraw,fev,n=10000000)
        self.logger.info('timestamp assigned %s'%(fev))
        
        ##analyze
        import monopix_daq.analysis.analyze_hits as analyze_hits
        ana=analyze_hits.AnalyzeHits(fev,fraw)
        ana.init_apply_ts_inj_window()
        ana.init_delete_noise()
        ana.init_delete_noninjected()
        ana.init_hist_ev()
        ana.init_injected()
        ana.init_cnts()
        ana.run()
        
    def plot(self):
        fev=self.output_filename[:-4]+'ev.h5'
        fraw = self.output_filename +'.h5'
        fpdf = self.output_filename +'.pdf'

        import monopix_daq.analysis.plotting_base as plotting_base
        with plotting_base.PlottingBase(fpdf,save_png=False) as plotting:
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
