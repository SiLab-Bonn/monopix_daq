''' Histograms the Mimosa26 hit table'''

import numpy as np
from numba import njit
import time

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

class MonopixHistogrammer(Transceiver):

    def setup_transceiver(self):
        self.set_bidirectional_communication()  # We want to be able to change the histogrammmer settings

    def setup_interpretation(self):
        self.occupancy = np.zeros(shape=(36,129), dtype=np.int32)
        self.tot = np.zeros(256, dtype=np.int32)  # Reset occ hists
        # Variables
        self.noisy_pixel = np.zeros(shape=(36,129), dtype=bool)
        self.total_hits = 0
        self.total_events = 0
        self.integ_start = time.time()
        self.integ_n = 0
        self.pix= [0xFFFF,0xFFFF] #[25,64] #[0xFFFF,0xFFFF] ########[col,row] for single pixel [0xFFFF,0xFFFF] for all pixel
        self.readout = 0
        self.plot_delay = 0

    def deserialize_data(self, data):
        # return jsonapi.loads(data, object_hook=utils.json_numpy_obj_hook)
        datar, meta = utils.simple_dec(data)
        if 'hits' in meta:
            meta['hits'] = datar
        return meta

    def interpret_data(self, data):
        if 'meta_data' in data[0][1]:  # Meta data is directly forwarded to the receiver, only hit data, event counters are histogramed; 0 from frontend index, 1 for data dict
            meta_data = data[0][1]["meta_data"]
            n_hits = meta_data['n_hits']
            n_events = meta_data['n_events']
            hps =  n_hits/ (meta_data['timestamp_stop']-self.integ_start)
            eps =  n_events/ (meta_data['timestamp_stop']-self.integ_start)
            self.total_hits = self.total_hits  + n_hits
            self.total_events = self.total_events + n_events

            meta_data.update({'hps': hps, 'total_hits': self.total_hits, 
                              'eps': eps, 'total_events': self.total_events})
            return [{"meta_data":meta_data}]
        elif 'hits' in data[0][1]:
            self.readout += 1
            if self.integ_n != 0:  # 0 for infinite integration
                if self.readout % self.integ_n == 0:
                    self.occupancy = np.zeros(shape=(36,129), dtype=np.int32)  # Reset occ hists
                    self.tot = np.zeros(256, dtype=np.int32)  # Reset occ hists
                    self.total_hits=0
                    self.total_events=0
                    self.integration_start=meta_data['timestamp_stop']
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
            self.occupancy[self.noisy_pixel]=0

            histogrammed_data = {
                'occupancies': self.occupancy,
                'tot': self.tot
            }

            return [histogrammed_data]

    def serialize_data(self, data):
        # return jsonapi.dumps(data, cls=utils.NumpyEncoder)

        if 'occupancies' in data:
            hits_data = data['occupancies']
            data['occupancies'] = None
            return utils.simple_enc(hits_data, data) ##????
        else:
            return utils.simple_enc(None, data)

    def handle_command(self, command):
        if command[0] == 'RESET':
            self.occupancy = np.zeros(shape=(36,129), dtype=np.int32)
            self.noisy_pixel = np.zeros(shape=(36,129), dtype=bool)
            self.tot = np.zeros(256, dtype=np.int32)  # Reset occ hists
            self.total_hits = 0
            self.total_events = 0
            self.integration_start = time.time()
            self.readout = 0
        elif 'MASK' in command[0]:
            if '0' in command[0]:
                self.noisy_pixel = np.zeros(shape=(36,129), dtype=bool)
            else:
                self.noisy_pixel = (self.occupancy > np.percentile(self.occupancy, 100 - self.config['noisy_threshold']))
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
            self.integ_n = int(command[0])
            self.occupancy = np.zeros(shape=(36,129), dtype=np.int32)
            self.noisy_pixel = np.zeros(shape=(36,129), dtype=bool)
            self.integration_start = time.time()
            self.readout = 0
