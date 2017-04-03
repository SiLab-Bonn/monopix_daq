
import logging
import basil
from monopix import monopix
from fifo_readout import FifoReadout
from contextlib import contextmanager
import time
import os
import tables as tb
import yaml

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

    def __init__(self, dut_conf=None):
        logging.info('Initializing %s', self.__class__.__name__)
        self.dut_conf = dut_conf
        
        self.working_dir = os.path.join(os.getcwd(),"output_data")
        if not os.path.exists(self.working_dir):
            os.makedirs(self.working_dir)
        
        self.run_name = time.strftime("%Y%m%d_%H%M%S_") + self.scan_id
        self.output_filename = os.path.join(self.working_dir, self.run_name)
        
        self.fh = logging.FileHandler(self.output_filename + '.log')
        self.fh.setLevel(logging.DEBUG)
        self.logger = logging.getLogger()
        self.logger.addHandler(self.fh)
        
        self.dut = monopix(self.dut_conf)
        
        self.filter_raw_data = tb.Filters(complib='blosc', complevel=5, fletcher32=False)
        self.filter_tables = tb.Filters(complib='zlib', complevel=5, fletcher32=False)

    def get_basil_dir(self):
        return str(os.path.dirname(os.path.dirname(basil.__file__)))

    def start(self, **kwargs):
                
       
        self.dut.init()
        
        self._first_read = False
        self.scan_param_id = 0
        
        filename = self.output_filename +'.h5'
        self.h5_file = tb.open_file(filename, mode='w', title=self.scan_id)
        self.raw_data_earray = self.h5_file.create_earray (self.h5_file.root, name='raw_data', atom=tb.UIntAtom(), shape=(0,), title='raw_data', filters=self.filter_raw_data)
        self.meta_data_table = self.h5_file.create_table(self.h5_file.root, name='meta_data', description=MetaTable, title='meta_data', filters=self.filter_tables)
        
        self.meta_data_table.attrs.kwargs = yaml.dump(kwargs)
        
        self.dut.power_up()

        time.sleep(0.1)
        
        self.fifo_readout = FifoReadout(self.dut)
        
        #
        # some init
        #
        
        logging.info('Power Status: %s', str(self.dut.power_status()))
        
        self.scan(**kwargs)
        
        self.fifo_readout.print_readout_status()
        
        self.meta_data_table.attrs.power_status = yaml.dump(self.dut.power_status())
        self.meta_data_table.attrs.dac_status = yaml.dump(self.dut.dac_status())

        self.h5_file.close()
        logging.info('Data Output Filename: %s', self.output_filename + '.h5')
        
        logging.info('Power Status: %s', str(self.dut.power_status()))
        self.dut.power_down()
        #self.logger.removeHandler(self.fh)
        
        return self.output_filename + '.h5'
        
    def analyze(self):
        raise NotImplementedError('ScanBase.analyze() not implemented')

    def scan(self, **kwargs):
        raise NotImplementedError('ScanBase.scan() not implemented')

    @contextmanager
    def readout(self, *args, **kwargs):
        timeout = kwargs.pop('timeout', 10.0)
        
        #self.fifo_readout.readout_interval = 10
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
        self.fifo_readout.start(reset_sram_fifo=reset_sram_fifo, fill_buffer=fill_buffer, clear_buffer=clear_buffer, callback=callback, errback=errback, no_data_timeout=no_data_timeout)

    def handle_data(self, data_tuple):
        '''Handling of the data.
        '''
        #print data_tuple[0].shape[0] #, data_tuple
        
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
        #print len_raw_data
        
    def handle_err(self, exc):
        msg='%s' % exc[1]
        if msg:
            logging.error('%s%s Aborting run...', msg, msg[-1] )
        else:
            logging.error('Aborting run...')
