import logging
import basil
import time
import os
import tables as tb
import yaml
import numpy as np

from monopix_daq import monopix
from fifo_readout import FifoReadout
from contextlib import contextmanager

import online_monitor.sender

class MetaTable(tb.IsDescription):
    index_start = tb.UInt32Col(pos=0)
    index_stop = tb.UInt32Col(pos=1)
    data_length = tb.UInt32Col(pos=2)
    timestamp_start = tb.Float64Col(pos=3)
    timestamp_stop = tb.Float64Col(pos=4)
    scan_param_id = tb.UInt16Col(pos=5)
    error = tb.UInt32Col(pos=6)

class ScanBase(object):
    '''Basic run meta class.

    Base class for scan- / tune- / analyse-class.
    '''

    def __init__(self, monopix=None, fout=None, online_monitor_addr="tcp://127.0.0.1:6500"):
        ### set dut
        if isinstance(monopix,str) or (monopix is None):
            self.monopix=monopix.Monopix(monopix)
        else:
            self.monopix = monopix ## todo better ???, self.dut.dut["CONF"].... :(
        self.dut=self.monopix.dut
        
        ### set file path and name
        if fout==None:
            self.working_dir = os.path.join(os.getcwd(),"output_data")
            self.run_name = time.strftime("%Y%m%d_%H%M%S_") + self.scan_id
        else:
            self.working_dir = os.path.dirname(os.path.realpath(fout))
            self.run_name = os.path.basename(os.path.realpath(fout)) + time.strftime("%Y%m%d_%H%M%S_") + self.scan_id
        if not os.path.exists(self.working_dir):
                os.makedirs(self.working_dir)
        self.output_filename = os.path.join(self.working_dir, self.run_name)
        
        ### set logger
        self.logger = logging.getLogger()
        flg=0
        for l in self.logger.handlers:
            if isinstance(l, logging.FileHandler):
               flg=1
        if flg==0:
            fh = logging.FileHandler(self.output_filename + '.log')
            fh.setFormatter(logging.Formatter("%(asctime)s [%(levelname)-5.5s] %(message)s"))
            #fh.setLevel(logging.WARNING)
            self.logger.addHandler(fh)
        #self.monopix.logging.info('Initializing %s', self.__class__.__name__)
        
	    self.logger.info('Initializing %s', self.__class__.__name__)
        self.logger.info("Scan start time: "+time.strftime("%Y-%m-%d_%H:%M:%S"))
        self.scan_start_time=time.localtime()
                
        ### set online monitor
        self.socket=online_monitor_addr
            
        self.filter_raw_data = tb.Filters(complib='blosc', complevel=5, fletcher32=False)
        self.filter_tables = tb.Filters(complib='zlib', complevel=5, fletcher32=False)
        
    def get_basil_dir(self):
        return str(os.path.dirname(os.path.dirname(basil.__file__)))

    def start(self, **kwargs):
        self._first_read = False
        self.scan_param_id = 0
        
        #### open file
        filename = self.output_filename +'.h5'
        self.h5_file = tb.open_file(filename, mode='w', title=self.scan_id)
        self.raw_data_earray = self.h5_file.create_earray (self.h5_file.root, name='raw_data', atom=tb.UIntAtom(), shape=(0,), title='raw_data', filters=self.filter_raw_data)
        self.meta_data_table = self.h5_file.create_table(self.h5_file.root, name='meta_data', description=MetaTable, title='meta_data', filters=self.filter_tables)
        self.kwargs = self.h5_file.create_vlarray(self.h5_file.root, 'kwargs', tb.VLStringAtom(), 'kwargs', filters=self.filter_tables)
        
        ### save args and chip configurations
        self.kwargs.append("kwargs")
        self.kwargs.append(yaml.dump(kwargs))
        self.meta_data_table.attrs.power_status_before = yaml.dump(self.monopix.power_status())
        self.meta_data_table.attrs.dac_status_before = yaml.dump(self.monopix.dac_status())
        tmp={}
        for k in self.monopix.dut.PIXEL_CONF.keys():
            tmp[k]=np.array(self.dut.PIXEL_CONF[k],int).tolist()
        self.meta_data_table.attrs.pixel_conf_before=yaml.dump(tmp)
        
        ### open socket for monitor
        if (self.socket==""): 
            self.socket=None
        else:
            try:
                self.socket=online_monitor.sender.init(self.socket)
            except:
                self.logger.warn('ScanBase.start:sender.init failed addr=%s'%self.socket)
                self.socket=None
        
        ### execute scan
        self.fifo_readout = FifoReadout(self.dut)
        self.logger.info('Power Status: %s', str(self.monopix.power_status()))
        self.logger.info('DAC Status: %s', str(self.monopix.dac_status()))
        self.monopix.show("all")
        self.scan(**kwargs) 
        self.fifo_readout.print_readout_status()
        self.monopix.show("all")
        self.logger.info('Power Status: %s', str(self.monopix.power_status()))
        self.logger.info('DAC Status: %s', str(self.monopix.dac_status()))
        
        ### save chip configurations
        self.meta_data_table.attrs.power_status = yaml.dump(self.monopix.power_status())
        self.meta_data_table.attrs.dac_status = yaml.dump(self.monopix.dac_status())
        tmp={}
        for k in self.monopix.dut.PIXEL_CONF.keys():  
            tmp[k]=np.array(self.dut.PIXEL_CONF[k],int).tolist()
        self.meta_data_table.attrs.pixel_conf=yaml.dump(tmp)
        self.meta_data_table.attrs.firmware = yaml.dump(self.dut.get_configuration())

        ### close file
        self.h5_file.close()
        self.logger.info("Scan end time: "+time.strftime("%Y-%m-%d_%H:%M:%S"))
        self.scan_end_time=time.localtime()
        self.scan_total_time=time.mktime(self.scan_end_time) - time.mktime(self.scan_start_time)
        self.logger.info("Total scan time: %i seconds", self.scan_total_time)
        self.logger.info('Data Output Filename: %s', self.output_filename + '.h5')

        ### close socket
        if self.socket!=None:
           try:
               online_monitor.sender.close(self.socket)
           except:
               pass
        return self.output_filename + '.h5'
        
    def analyze(self):
        raise NotImplementedError('ScanBase.analyze() not implemented')

    def scan(self, **kwargs):
        raise NotImplementedError('ScanBase.scan() not implemented')
        
    def plot(self, **kwargs):
        raise NotImplementedError('ScanBase.scan() not implemented')

    @contextmanager
    def readout(self, *args, **kwargs):
        timeout = kwargs.pop('timeout', 10.0)
        self.fifo_readout.readout_interval=kwargs.pop('readout_interval', 0.003)
        if not self._first_read:
            time.sleep(0.1)
            self.fifo_readout.print_readout_status()
            self._first_read = True
            
        self.start_readout(*args, **kwargs)
        yield
        self.fifo_readout.stop(timeout=timeout)

    def start_readout(self, scan_param_id = 0, *args, **kwargs):
        # Pop parameters for fifo_readout.start
        callback = kwargs.pop('callback', self.handle_data)
        clear_buffer = kwargs.pop('clear_buffer', False)
        fill_buffer = kwargs.pop('fill_buffer', False)
        reset_sram_fifo = kwargs.pop('reset_sram_fifo', False)
        errback = kwargs.pop('errback', self.handle_err)
        no_data_timeout = kwargs.pop('no_data_timeout', None)
        self.scan_param_id = scan_param_id
        self.fifo_readout.start(reset_sram_fifo=reset_sram_fifo, fill_buffer=fill_buffer, clear_buffer=clear_buffer, 
                                callback=callback, errback=errback, no_data_timeout=no_data_timeout)

    def handle_data(self, data_tuple):
        '''Handling of the data.
        '''
        total_words = self.raw_data_earray.nrows
        
        self.raw_data_earray.append(data_tuple[0])
        self.raw_data_earray.flush()
        
        len_raw_data = data_tuple[0].shape[0]
        self.meta_data_table.row['timestamp_start'] = data_tuple[1]
        self.meta_data_table.row['timestamp_stop'] = data_tuple[2]
        self.meta_data_table.row['error'] = data_tuple[3]
        self.meta_data_table.row['data_length'] = len_raw_data
        self.meta_data_table.row['index_start'] = total_words
        total_words += len_raw_data
        self.meta_data_table.row['index_stop'] = total_words
        self.meta_data_table.row['scan_param_id'] = self.scan_param_id
        self.meta_data_table.row.append()
        self.meta_data_table.flush()
        
        if self.socket!=None:
            try:
                online_monitor.sender.send_data(self.socket,data_tuple,scan_parameters={'scan_param_id':self.scan_param_id})
            except:
                self.logger.warn('ScanBase.handle_data:sender.send_data failed')
                try:
                    online_monitor.sender.close(self.socket)
                except:
                    pass
                self.socket=None

    def handle_err(self, exc):
        msg='%s' % exc[1]
        if msg:
            self.logger.error('%s%s Aborting run...', msg, msg[-1] )
        else:
            self.logger.error('Aborting run...')
            
    def close(self):
        try:
            self.fifo_readout.stop(timeout=0)
        except RuntimeError:
            self.logger.info("fifo has been already closed")
