import os, sys, time
import numpy as np
import tables as tb
import yaml
import logging

COL_SIZE = 36 
ROW_SIZE = 129
    
class AnalyzeHits():
    def __init__(self,fhit,fraw):
        self.fhit=fhit
        self.fraw=fraw
        self.res={}

    def run(self,n=10000000):
        with tb.open_file(self.fhit,"a") as f:
            end=len(f.root.Hits)
            start=0
            t0=time.time()
            hit_total=0
            while start<end:
                tmpend=min(end,start+n)
                hits=f.root.Hits[start:tmpend]
                if tmpend!=end:
                    last=hits[-1]
                    for i,h in enumerate(hits[::-1][1:]):
                        if h["scan_param_id"]!= last["scan_param_id"]:
                            hits=hits[:len(hits)-i-1]
                            break
                    if last["scan_param_id"]==h["scan_param_id"]:
                        print "ERROR data chunck is too small increase n"
                self.analyze(hits,f.root)
                start=start+len(hits)
        self.save()

    def analyze(self, hits, fhit_root):
        if "apply_ts_inj_window" in self.res.keys():
            hits=self.run_apply_ts_inj_window(hits)
        if "delete_noise" in self.res.keys():
            hits=self.run_delete_noise(hits)
        if "delete_noninjected" in self.res.keys():
            hits=self.run_delete_noninjected(hits)
        if "hist_occ" in self.res.keys():
            self.run_hist(hits)
        if "hist_occ_ev" in self.res.keys():
            self.run_hist_ev(hits)
        if "cnts" in self.res.keys():
            self.run_cnts(hits,fhit_root)
        if "le_hist" in self.res.keys():
            self.run_le_hist(hits,fhit_root)
        if "le_cnts" in self.res.keys():
            self.run_le_cnts(hits,fhit_root)

    def save(self):
        if "hist_occ" in self.res.keys():
            self.save_hist(res_name="hist_occ")
        if "hist_occ_ev" in self.res.keys():
            self.save_hist(res_name="hist_occ_ev")
        if "injected" in self.res.keys():
            self.save_injected()
        if "cnts" in self.res.keys():
            self.save_cnts()

######### cleaning
    def init_delete_noise(self):
        self.res["delete_noise"]=True
    def run_delete_noise(self, hits):
        len0=len(hits)
        hits=hits[hits["flg"]==0]
        print "delete_noise from %d to %d %.3f percent"%(len0,len(hits),100.0*len(hits)/len0)
        return hits
        
    def init_apply_ts_inj_window(self,inj_window=None):
        if inj_window is None:
            with tb.open_file(self.fraw) as f:
                firmware=yaml.load(f.root.meta_data.attrs.firmware)
                inj_window=int(firmware["inj"]["WIDTH"]*0.85)
                print "Using an injection timestamp window cut of %i (25ns clocks)"%inj_window
        self.res["apply_ts_inj_window"]=inj_window

    def run_apply_ts_inj_window(self, hits):
        len0=len(hits)
        ts_inj40=((np.int64(hits["ts_token"])>>4) - np.int64(hits["tot"]) - (np.int64(hits["ts_inj"])>>4))
        hits=hits[ts_inj40 < self.res["apply_ts_inj_window"]]
        print "apply_ts_inj_window from %d to %d %.3f percent"%(len0,len(hits),100.0*len(hits)/len0)
        return hits
        
    def init_delete_noninjected(self):
        with tb.open_file(self.fraw) as f: 
            self.res["delete_noninjected"]=f.root.scan_parameters[:][["scan_param_id","pix"]]
    def run_delete_noninjected(self, hits):
        len0=len(hits)
        uni,idx,cnt=np.unique(hits["scan_param_id"],return_index=True,return_counts=True)
        buf=np.empty(0,dtype=hits.dtype)
        for u_i,u in enumerate(uni):
            tmp=hits[hits["scan_param_id"]==u]
            injected_pix=list() 
            for injmask_part in range(len(self.res["delete_noninjected"][self.res["delete_noninjected"]["scan_param_id"]==u]['pix'])): #Takes into account different measurements with same scan_param_id
                curr_injmask_part=self.res["delete_noninjected"][self.res["delete_noninjected"]["scan_param_id"]==u]['pix'][injmask_part]
                injected_pix.extend(curr_injmask_part)
            detected_pix=np.transpose(np.array([tmp["col"],tmp["row"]]))
            mask=np.zeros(len(detected_pix),dtype=bool)
            for ip in injected_pix:
               tmp_mask=np.bitwise_and(tmp["col"]==ip[0],tmp["row"]==ip[1])
               mask=np.bitwise_or(tmp_mask,mask)
            buf=np.append(buf,tmp[mask])
        print "delete_noninjected from %d to %d %.3f percent"%(len0,len(buf),100.0*len(buf)/len0)
        return buf
        
        
            
######### le-counts
    def init_le_cnts(self):
        with tb.open_file(self.fraw) as f:
            cnt_dtype=f.root.scan_parameters.dtype
        cnt_dtype=cnt_dtype.descr
        for i in range(len(cnt_dtype)):
            if cnt_dtype[i][0]=="pix":
                cnt_dtype.pop(i)
                break
        cnt_dtype = cnt_dtype + [
                    ('col', "<i2"),('row', "<i2"),('inj', "<f4"),('toa', "<u1"),
                    ('th', "<f4"),('phase', "<i4")]

        self.res["le_cnts"]=list(np.zeros(0,dtype=cnt_dtype).dtype.names)
        with tb.open_file(self.fhit,"a") as f:
            try:
                f.remove_node(f.root,"LECnts")
            except:
                pass
            f.create_table(f.root,name="LECnts",
                           description=np.zeros(0,dtype=cnt_dtype+[('cnt',"<i4")]).dtype,
             title='le_cnt_data')
        print "AnalyzeHits: le_cnts will be analyzed"

    def run_le_cnts(self,hits,fhit_root):
        hits["toa"] = hits["toa"] - np.uint8( np.uint64(hits["ts_inj"]-hits["phase"])>>np.uint(4) )
        uni,cnt=np.unique(hits[self.res["le_cnts"]],return_counts=True)
        buf=np.empty(len(uni),dtype=fhit_root.LECnts.dtype)
        for c in self.res["le_cnts"]:
            buf[c]=uni[c]
        buf["cnt"]=cnt
        #### TODO copy scan_param_id to the data here
        fhit_root.LECnts.append(buf)
        fhit_root.LECnts.flush()
            
######### counts
    def init_cnts(self):
        with tb.open_file(self.fraw) as f:
            param_len=len(f.root.scan_parameters)
            cnt_dtype=f.root.scan_parameters.dtype
        n_mask_pix=cnt_dtype["pix"].shape[0]
        cnt_dtype=cnt_dtype.descr
        for i in range(len(cnt_dtype)):
            if cnt_dtype[i][0]=="pix":
                cnt_dtype.pop(i)
                break
        cnt_dtype = cnt_dtype + [
                    ('col', "<i2"),('row', "<i2"),('inj', "<f4"),
                    ('th', "<f4"),('phase', "<i4"),('cnt',"<i4")]

        self.res["cnts"]=list(np.zeros(0,dtype=cnt_dtype).dtype.names)[:-1]
        with tb.open_file(self.fhit,"a") as f:
            try:
                f.remove_node(f.root,"Cnts")
            except:
                pass
            f.create_table(f.root,name="Cnts",
                           description=np.zeros(0,dtype=cnt_dtype).dtype,
                           title='cnt_data')

    def run_cnts(self,hits,fhit_root):
        uni,cnt=np.unique(hits[self.res["cnts"]],return_counts=True)
        buf=np.empty(len(uni),dtype=fhit_root.Cnts.dtype)
        for c in self.res["cnts"]:
            buf[c]=uni[c]
        buf["cnt"]=cnt
        #### TODO copy scan_param_id to the data here
        fhit_root.Cnts.append(buf)
        fhit_root.Cnts.flush()
    def save_cnts(self):
        self.res["cnts"]=False

######### injected pixels
    def init_injected(self):
        self.res["injected"]=True
    def save_injected(self):
        with tb.open_file(self.fraw) as f:
            param=f.root.scan_parameters[:]
            if "pix" not in param.dtype.names:
                return
            dat=yaml.load(f.root.meta_data.attrs.pixel_conf_before)
        en=np.copy(dat["PREAMP_EN"])
        injected=np.zeros(np.shape(en))
        for pix in param["pix"]:
            for p in pix:
                if p[0]==-1:
                    continue
                injected[p[0],p[1]]= int(en[p[0],p[1]])
        with tb.open_file(self.fhit,"a") as f:
            try:
                f.remove_node(f.root,"Injected")
            except:
                pass
            f.create_carray(f.root, name='Injected',
                            title='Injected pixels',
                            obj=injected,
                            filters=tb.Filters(complib='blosc', complevel=5, fletcher32=False))

######### hit occupancy
    def init_hist(self):
        self.res["hist_occ"]=np.zeros([COL_SIZE,ROW_SIZE],dtype=np.int32)
    def run_hist(self,hits):
        hits=hits[np.bitwise_and(hits["col"]<COL_SIZE,hits["cnt"]==0)]
        if len(hits)!=0:
            self.res["hist_occ"]=self.res["hist_occ"]+np.histogram2d(
                       hits['col'],
                       hits['row'],
                       bins=[np.arange(0,COL_SIZE+1),np.arange(0,ROW_SIZE+1)])[0]
    def save_hist(self,res_name="hist_occ"):
        with tb.open_file(self.fhit,"a") as f:
            try:
                f.remove_node(f.root,"HistOcc")
            except:
                pass
            f.create_carray(f.root, name='HistOcc',
                            title='Hit Occupancy',
                            obj=self.res[res_name],
                            filters=tb.Filters(complib='blosc', complevel=5, fletcher32=False))
        self.res[res_name]=False
    def init_hist_ev(self):
        self.res["hist_occ_ev"]=np.zeros([COL_SIZE,ROW_SIZE],dtype=np.int32)
    def run_hist_ev(self,hits):
        if len(hits)!=0:
            self.res["hist_occ_ev"]=self.res["hist_occ_ev"]+np.histogram2d(
                       hits['col'],
                       hits['row'],
                       bins=[np.arange(0,COL_SIZE+1),np.arange(0,ROW_SIZE+1)])[0]
######### analyze delay
    def init_le_hist(self):
        with tb.open_file(self.fraw) as f:
            for i in range(0,len(f.root.kwargs),2):
                if f.root.kwargs[i]=="phaselist":
                    phaselist=np.sort(np.unique(np.array(
                          yaml.load(f.root.kwargs[i+1]))))
        with tb.open_file(self.fhit,"a") as f_o:
            try:
                f_o.remove_node(f_o.root,"LEHist")
                f_o.remove_node(f_o.root,"LEDist")
            except:
                pass
            dat_dtype=[('scan_param_id', '<i4'),('col', 'u1'),
                       ('row', 'u1'), ('inj', '<f4'), ('th', '<f4')]
            t=f_o.create_table(
                f_o.root,name="LEHist",
                description=np.empty(0,dtype=dat_dtype+[('LE','u1',(len(phaselist),256))]),
                title='LE_hist_data')
            t.attrs.phaselist=phaselist
            f_o.create_table(
                f_o.root,name="LEDist",
                description=np.empty(0,dtype=dat_dtype+[('ts_le','<i4'),('cnt','<f4')]),
                title='LE_distribution_data')
        self.res["le_hist"]=phaselist

    def run_le_hist(self,hits,fhit_root):
        buf=np.empty(1,dtype=fhit_root.LEHist.dtype)
        buf_dist=np.empty(16*256,dtype=fhit_root.LEDist.dtype)

        uni,idx,cnt=np.unique(hits[['scan_param_id', 'col', 'row','th','inj']],
                          return_counts=True,return_index=True)
        for u_i,u in enumerate(uni):
            dat=hits[hits[['scan_param_id', 'col', 'row', 'th','inj']]==u]
            ph0=dat[0]["phase"]
            
            for i,ph in enumerate(self.res["le_hist"]):
                tmp=dat[dat["phase"]==ph]
                buf[0]["LE"][i,:]=np.bincount(
                          tmp["tof"]- np.uint8(np.uint64(tmp["ts_inj"]-ph)>>np.uint64(4)),
                          minlength=256)
            for c in ['scan_param_id', 'col', 'row', 'th','inj']:
                buf[0][c]=u[c]
            fhit_root.LEHist.append(buf)
            fhit_root.LEHist.flush()

            if False: ### debug
                import matplotlib.pyplot as plt
                plt.imshow(np.transpose(buf[0]["LE"]),origin="lower",
                       cmap="viridis",
                       aspect="auto",interpolation="none",
                       #vmax=1,vmin=0
                       )
                plt.title("inj=%.3f"%buf[0]["inj"])
                a_start=min(np.argwhere(buf[0]["LE"][0,:]!=0)-10,0)
                a_stop=max(np.argwhere(buf[0]["LE"][-1,:]!=0)+10,256)
                plt.ylim(a_start,a_stop)
                c=plt.colorbar()
                c.set_label("#")
                plt.xlabel("Injection delay [%.3fns]"%(25/16.))
                plt.ylabel("Monopix timestamp")
                plt.savefig("LE_inj%.4f_th%.4f.png"%(buf[0]["inj"],buf[0]["th"]),fmt="png",dpi=300)
                print "LE_inj%.4f_th%.4f.png"%(buf[0]["inj"],buf[0]["th"])
                plt.clf()

if "__main__"==__name__:
    import sys
    fraw=sys.argv[1]
