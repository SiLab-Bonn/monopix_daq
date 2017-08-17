
import numpy as np
from monopix_daq.analysis.interpreter import InterRaw 

def interpret_rx_data_scan(raw_data, meta_data):
        data_type = {'names':['col','row','le','te','scan_param_id'], 'formats':['uint16','uint16','uint8','uint8','uint8','uint16']}
        ret = np.recarray((0), dtype=data_type)
        inter=InterRaw()        
        if len(meta_data):
            param, index = np.unique(meta_data['scan_param_id'], return_index=True)
            index = index[1:]
            index = np.append(index, meta_data.shape[0])
            index = index - 1
            stops = meta_data['index_stop'][index]
            split = np.split(raw_data, stops)
            for i in range(len(split[:-1])):
                tmp=inter.run(split[i])
                tmp=tmp[tmp["col"]<36]
                int_pix_data = np.recarray(len(tmp), dtype=data_type)
                int_pix_data['col']=tmp['col'] 
                int_pix_data['row']=tmp['row']
                int_pix_data['le']=tmp['le']
                int_pix_data['te']=tmp['te']
                int_pix_data['scan_param_id'][:] = param[i]
                if len(ret):
                    ret = np.hstack((ret, int_pix_data))
                else:
                    ret = int_pix_data
        return ret
        
def interpret_rx_data(raw_data):
    inter=InterRaw()
    ret=inter.run(raw_data)
    return ret[['col','row','le','te']][ret["col"]<36]
    