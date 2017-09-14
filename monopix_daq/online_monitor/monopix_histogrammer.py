''' Histograms the Mimosa26 hit table'''

import numpy as np
from numba import njit

# Online monitor imports
from online_monitor.converter.transceiver import Transceiver
from online_monitor.utils import utils

@njit
def fill_occupancy_hist(occ,tot,hits,pix): 
    for hit_i in range(hits.shape[0]):
        occ[hits[hit_i]['col'], hits[hit_i]['row']] += 1
        if pix[0]==0xFFFF and pix[1]==0xFFFF:
              tot[hits[hit_i]['tot']] += 1
        elif pix[0]==hits[hit_i]['col'] and pix[1]==hits[hit_i]['row']:
              tot[hits[hit_i]['tot']] += 1

def apply_noisy_pixel_cut(hists, noisy_threshold):
     hists = hists[hists < noisy_threshold]

class MonopixHistogrammer(Transceiver):

    def setup_transceiver(self):
        self.set_bidirectional_communication()  # We want to be able to change the histogrammmer settings

    def setup_interpretation(self):
        self.occupancy = np.zeros(shape=(36,129), dtype=np.int32)
        self.tot = np.zeros(256, dtype=np.int32)
        self.pix= [0xFFFF,0xFFFF] #[25,64] #[0xFFFF,0xFFFF] ########[col,row] for single pixel [0xFFFF,0xFFFF] for all pixel
        # Variables
        self.n_readouts = 0
        self.readout = 0
        self.fps = 0  # data frames per second
        self.hps = 0  # hits per second
        self.eps = 0  # events per second
        self.plot_delay = 0
        self.total_hits = 0
        self.total_events = 0
        self.updateTime = 1 ##### It was 0 before adding timestamp_start_fornext
        self.mask_noisy_pixel = False
        self.timestamp_start_fornext=0 #####
        # Histogrammes from interpretation stored for summing
#         self.error_counters = None
#         self.trigger_error_counters = None

    def deserialze_data(self, data):
        # return jsonapi.loads(data, object_hook=utils.json_numpy_obj_hook)
        datar, meta = utils.simple_dec(data)
        if 'hits' in meta:
            meta['hits'] = datar
#            print "datar"
#            print len(datar)
#            print "-----"
        return meta


    def interpret_data(self, data):
        
#        print "data[0][1]"
#        print data
#        print "////////"
        if 'meta_data' in data[0][1]:  # Meta data is directly forwarded to the receiver, only hit data, event counters are histogramed; 0 from frontend index, 1 for data dict
            meta_data = data[0][1]['meta_data']
            now = float(meta_data['timestamp_stop'])
            recent_total_hits = meta_data['n_hits']
#            print "recent"
#            print recent_total_hits
            recent_total_events = meta_data['n_events']
#            recent_fps = 1.0 / (now - self.updateTime)  # calculate FPS
            recent_fps = 1.0 / (self.updateTime - self.timestamp_start_fornext)  # calculate FPS
#            recent_hps = (recent_total_hits - self.total_hits) / (now - self.updateTime)
#            recent_eps = (recent_total_events - self.total_events) / (now - self.updateTime)

            recent_hps = (meta_data['n_hits']) / (self.updateTime - self.timestamp_start_fornext)
            recent_eps = (recent_total_events - self.total_events) / (self.updateTime - self.timestamp_start_fornext)
            self.timestamp_start_fornext= float(meta_data['timestamp_start'])
            self.updateTime = now
            self.total_hits += recent_total_hits
            self.total_events += recent_total_events
            self.fps = self.fps * 0.7 + recent_fps * 0.3
            self.hps = self.hps + (recent_hps - self.hps) * 0.3 / self.fps
            self.eps = self.eps + (recent_eps - self.eps) * 0.3 / self.fps

            meta_data.update({'fps': self.fps, 'hps': self.hps, 'total_hits': self.total_hits, 'eps': self.eps, 'total_events': self.total_events})
            return [data[0][1]]

        self.readout += 1

        if self.n_readouts != 0:  # 0 for infinite integration
            if self.readout % self.n_readouts == 0:
                self.occupancy = np.zeros(shape=(36,129), dtype=np.int32)  # Reset occ hists
                self.tot = np.zeros(256, dtype=np.int32)  # Reset occ hists
                self.readout = 0

        tmp = data[0][1]['hits']
        tmp = tmp[tmp["cnt"]==0] ## remove noise
        tmp = tmp[tmp["col"]<36] ## remove TLU and timestamp
        hits = np.recarray(len(tmp), dtype=[('col','u2'),('row','u2'),('tot','u1')]) 
        hits['tot'][:] = (tmp["te"] - tmp["le"]) & 0xff
        hits['col'][:] = tmp["col"]
        hits['row'][:] = tmp["row"] 

        if hits.shape[0] == 0:  # Empty array
            return
        fill_occupancy_hist(self.occupancy, self.tot, hits, self.pix)
        #print "occupancy", np.sum(self.occupancy)
        

        if self.mask_noisy_pixel:   #Improve
            self.occupancy[self.occupancy > np.percentile(self.occupancy, 100 - self.config['noisy_threshold'])] = 0

        histogrammed_data = {
            'occupancies': self.occupancy,
            'tot': self.tot
        }

        return [histogrammed_data]

    def serialze_data(self, data):
        # return jsonapi.dumps(data, cls=utils.NumpyEncoder)

        if 'occupancies' in data:
            hits_data = data['occupancies']
            data['occupancies'] = None
            return utils.simple_enc(hits_data, data)
        else:
            return utils.simple_enc(None, data)

    def handle_command(self, command):
        if command[0] == 'RESET':
            self.occupancy = np.zeros(shape=(36,129), dtype=np.int32)  # Reset occ hists
            self.tot = np.zeros(256, dtype=np.int32)  # Reset occ hists
            self.total_hits = 0
            self.total_events = 0
        elif 'MASK' in command[0]:
            if '0' in command[0]:
                self.mask_noisy_pixel = False
            else:
                self.mask_noisy_pixel = True
        elif 'PIX_X' in command[0]: ### TODO get pixel from command
            self.tot = np.zeros(256, dtype=np.int32)  # Reset occ hists
            value=command[0].split()[1]
            if '-1' in value:
                self.pix[0]=0xFFFF
                self.pix[1]=0xFFFF
            else:
                self.pix[0]=int(value)
        elif 'PIX_Y' in command[0]: ### TODO get pixel from command
            self.tot = np.zeros(256, dtype=np.int32)  # Reset occ hists
            value=command[0].split()[1]
            if '-1' in value:
                self.pix[0]=0xFFFF
                self.pix[1]=0xFFFF
            else:
                self.pix[1]=int(value)
        else:
            self.n_readouts = int(command[0])
            self.occupancy = np.zeros(shape=(36,129), dtype=np.int32)  # Reset occ hists
            self.tot = np.zeros(256, dtype=np.int32)  # Reset occ hists
