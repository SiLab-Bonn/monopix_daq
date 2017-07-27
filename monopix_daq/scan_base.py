import logging
import basil
import time
import os
import tables as tb
import yaml
from monopix import monopix
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

    def __init__(self, dut_conf=None):
        logging.info('Initializing %s', self.__class__.__name__)
        self.dut_conf = dut_conf

        self.working_dir = os.path.join(os.getcwd(), "output_data")
        if not os.path.exists(self.working_dir):
            os.makedirs(self.working_dir)

        self.run_name = time.strftime("%Y%m%d_%H%M%S_") + self.scan_id
        self.output_filename = os.path.join(self.working_dir, self.run_name)

        self.fh = logging.FileHandler(self.output_filename + '.log')
        self.fh.setLevel(logging.DEBUG)
        self.logger = logging.getLogger()
        self.logger.addHandler(self.fh)

        self.dut = monopix(self.dut_conf)
        self.dut.init()

        self.filter_raw_data = tb.Filters(complib='blosc', complevel=5, fletcher32=False)
        self.filter_tables = tb.Filters(complib='zlib', complevel=5, fletcher32=False)

    def configure(self, injection=False, repeat=1000, scan_range=[0, 0.2, 0.05], mask_filename='', TH=1.5, mask=16, columns=range(0, 36), threshold_overdrive=0.001, **kwargs):
        self.dut['data_rx'].reset()
        self.dut['fifo'].reset()

        self.dut['TH'].set_voltage(1.5, unit='V')
        self.dut['VDDD'].set_voltage(1.7, unit='V')
        self.dut['VDD_BCID_BUFF'].set_voltage(1.7, unit='V')
        # self.dut['VPC'].set_voltage(1.5, unit='V')

        # If this is a scan with injection, initialize pulser and set needed values otherwise skip
        if injection:
            from basil.dut import Dut

            self.INJ_LO = 0.2
            try:
                self.pulser = Dut('../agilent33250a_pyserial.yaml')  # should be absolute path
                self.pulser.init()
                logging.info('Connected to ' + str(self.pulser['Pulser'].get_info()))
            except (RuntimeError, OSError):
                self.pulser = None
                logging.info('External injector not connected. Switch to internal one')

                self.dut['INJ_LO'].set_voltage(self.INJ_LO, unit='V')

            self.dut['inj'].set_delay(20 * 256 + 10)
            self.dut['inj'].set_width(20 * 256 - 10)
            self.dut['inj'].set_repeat(repeat)
            self.dut['inj'].set_en(True)
            self.dut['gate_tdc'].set_en(False)
            self.dut['gate_tdc'].set_delay(10)
            self.dut['gate_tdc'].set_width(2)
            self.dut['gate_tdc'].set_repeat(1)
            self.dut['CONF']['EN_GRAY_RESET_WITH_TDC_PULSE'] = 1

        self.dut["CONF_SR"]["PREAMP_EN"] = 1
        self.dut["CONF_SR"]["INJECT_EN"] = 1
        self.dut["CONF_SR"]["MONITOR_EN"] = 1
        self.dut["CONF_SR"]["REGULATOR_EN"] = 1
        self.dut["CONF_SR"]["BUFFER_EN"] = 1
        self.dut["CONF_SR"]["LSBdacL"] = 45
        self.dut["CONF_SR"]["VPFB"] = 32

        self.dut.write_global_conf()

        self.dut['CONF']['EN_OUT_CLK'] = 1
        self.dut['CONF']['EN_BX_CLK'] = 1
        self.dut['CONF']['EN_DRIVER'] = 1
        self.dut['CONF']['EN_DATA_CMOS'] = 0

        self.dut['CONF']['RESET_GRAY'] = 1
        self.dut['CONF']['EN_TEST_PATTERN'] = 0
        self.dut['CONF']['RESET'] = 1
        self.dut['CONF'].write()

        self.dut['CONF']['RESET'] = 0
        self.dut['CONF'].write()

        self.dut['CONF']['RESET_GRAY'] = 0  # Why do we enable and disable RESETs? (IDCS) ---Time while you write in between.
        self.dut['CONF'].write()

        self.dut['CONF_SR']['MON_EN'].setall(True)
        self.dut['CONF_SR']['INJ_EN'].setall(False)
        self.dut['CONF_SR']['ColRO_En'].setall(False)

        self.dut.PIXEL_CONF['PREAMP_EN'][:] = 0
        self.dut.PIXEL_CONF['INJECT_EN'][:] = 0
        self.dut.PIXEL_CONF['MONITOR_EN'][:] = 0
        self.dut.PIXEL_CONF['TRIM_EN'][:] = 15

    def get_basil_dir(self):
        return str(os.path.dirname(os.path.dirname(basil.__file__)))

    def start(self, **kwargs):

        # self.dut.init()

        self._first_read = False
        self.scan_param_id = 0

        filename = self.output_filename + '.h5'
        self.h5_file = tb.open_file(filename, mode='w', title=self.scan_id)
        self.raw_data_earray = self.h5_file.create_earray(self.h5_file.root, name='raw_data', atom=tb.UIntAtom(), shape=(0,), title='raw_data', filters=self.filter_raw_data)
        self.meta_data_table = self.h5_file.create_table(self.h5_file.root, name='meta_data', description=MetaTable, title='meta_data', filters=self.filter_tables)

        self.meta_data_table.attrs.kwargs = yaml.dump(kwargs)

        addr = "tcp://127.0.0.1:5500"  # TODO get from yaml conf file?
        if (addr != ""):
            try:
                self.socket = online_monitor.sender.init(addr)
            except:
                logging.info('error data_send.data_send_init %s' % addr)
                self.socket = None

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

        if self.socket is not None:
            try:
                online_monitor.sender.close(self.socket)
            except:
                pass

        logging.info('Power Status: %s', str(self.dut.power_status()))
        self.dut.power_down()
        # self.logger.removeHandler(self.fh)

        return self.output_filename + '.h5'

    def analyze(self, h5_filename='', param_func=None):
        """

        Parameters
        ----------
        param_func : function
            Function to call on the values in scan_param_id column to
            get desired information (e.g. retrieve injection votlage)

        Returns
        -------
        out : Numpy recarray with hit information (col, row, le, te, scan_param_id, TBD, tot)
        """
        import numpy as np
        # Added analyze from source_scan to check if it saves le and te

        if h5_filename == '':
            h5_filename = self.output_filename + '.h5'

        logging.info('Analyzing: %s', h5_filename)
        np.set_printoptions(linewidth=240)

        with tb.open_file(h5_filename, 'r+') as in_file_h5:
            raw_data = in_file_h5.root.raw_data[:]
            meta_data = in_file_h5.root.meta_data[:]

            # print raw_data
            hit_data = self.dut.interpret_rx_data(raw_data, meta_data)
            lista = list(hit_data.dtype.descr)
            new_dtype = np.dtype(lista + [('InjV', 'float'), ('tot', 'uint8')])
            new_hit_data = np.zeros(shape=hit_data.shape, dtype=new_dtype)
            for field in hit_data.dtype.names:
                new_hit_data[field] = hit_data[field]

            # TODO: Get InjV without additional parameters. Better save directly if needed
            # new_hit_data['InjV'] = hit_data['scan_param_id']

            tot = hit_data['te'] - hit_data['le']
            neg = hit_data['te'] < hit_data['le']
            print np.bincount(hit_data['le'])
            tot[neg] = hit_data['te'][neg] + (255 - hit_data['le'][neg])
            new_hit_data['tot'] = tot

            in_file_h5.create_table(in_file_h5.root, 'hit_data', new_hit_data, filters=self.filter_tables)

        return new_hit_data

    def scan(self, **kwargs):
        raise NotImplementedError('ScanBase.scan() not implemented')

    @contextmanager
    def readout(self, *args, **kwargs):
        timeout = kwargs.pop('timeout', 10.0)

        # self.fifo_readout.readout_interval = 10
        if not self._first_read:
            time.sleep(0.1)
            self.fifo_readout.print_readout_status()
            self._first_read = True

        self.start_readout(*args, **kwargs)
        yield
        self.fifo_readout.stop(timeout=timeout)

    def start_readout(self, scan_param_id=0, *args, **kwargs):
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
        # print data_tuple[0].shape[0] #, data_tuple

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
        # print len_raw_data

        if self.socket is not None:
            try:
                online_monitor.sender.send_data(self.socket, data_tuple)
            except:
                logging.info("error: send_data")

    def handle_err(self, exc):
        msg = '%s' % exc[1]
        if msg:
            logging.error('%s%s Aborting run...', msg, msg[-1])
        else:
            logging.error('Aborting run...')
