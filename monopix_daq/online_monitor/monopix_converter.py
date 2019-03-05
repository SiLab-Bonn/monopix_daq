from online_monitor.converter.transceiver import Transceiver
from zmq.utils import jsonapi
import numpy as np

from online_monitor.utils import utils
from monopix_daq.analysis.interpreter import InterRaw

class MonopixConverter(Transceiver):

    def setup_interpretation(self):
        self.n_hits = 0
        self.n_events = 0
        self.inter=InterRaw()
        self.meta_data={}

    def deserialize_data(self, data):
        ## meta data
        try:
            data=jsonapi.loads(data)
            if "dtype" in data:
                self.meta_data=data
            return data
        except ValueError:
            pass  # if data is raw data, it will be ValueError

        ### raw data
        if "dtype" not in self.meta_data or "shape" not in self.meta_data:
            return None 
        dtype = self.meta_data.pop('dtype')
        shape = self.meta_data.pop('shape')
        try:
            raw_data_array = np.frombuffer(buffer(data), dtype=dtype).reshape(shape)
            return raw_data_array
        except:
            print "Monopix_converter.deserialze_data() broken data"
            return None

    def interpret_data(self, data):
        ### meta data
        if isinstance(data[0][1], dict): 
            if "cmd" in data[0][1].keys():
                return [data[0][1]]
            else:
                self.meta_data.update({'n_hits': self.n_hits, 'n_events': self.n_events})
                return [{"meta_data":self.meta_data}]
        ### raw data
        hits=self.inter.run(data[0][1])
        self.n_hits = hits.shape[0]
        if self.n_hits==0:
            self.n_events=0
        else:
            self.n_events=len(np.where(hits["col"]==0xFF))
        return [{'hits': hits}]

    def serialize_data(self, data):
        if 'hits' in data:
            hits_data = data['hits']
            data['hits'] = None
            return utils.simple_enc(hits_data, data) ###??? why coded like this???
        else:
            return utils.simple_enc(None, data)
