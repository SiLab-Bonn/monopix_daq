from monopix_daq.scan_base import ScanBase
from monopix_daq import analysis

from matplotlib import pyplot as plt

import time

import numpy as np
import tables as tb
import yaml

from progressbar import ProgressBar
from basil.dut import Dut

import logging
logging.basicConfig(level=logging.INFO, format="%(asctime)s - %(name)s - [%(levelname)-8s] (%(threadName)-10s) %(message)s")

show_info = False

local_configuration = {
    "repeat": 100,
    "mask_filename": '',
    "scan_range": [0.4, 0.401, 0.02],
    "mask": 16,
    "TH": 0.783,
    "columns": range(12, 16),
    "threshold_overdrive": 0.006
}


class AnalogScan(ScanBase):
    scan_id = "scan_analog"

    def get_filename(self):
        return self.output_filename

    def configure(self, repeat=100, scan_range=[0, 0.2, 0.05], mask_filename='', TH=1.5, mask=16, columns=range(0, 36), threshold_overdrive=0.001, **kwargs):
        self.INJ_LO = 0.2
        try:
            self.pulser = Dut('../agilent33250a_pyserial.yaml')  # should be absolute path
            self.pulser.init()
            logging.info('Connected to ' + str(self.pulser['Pulser'].get_info()))
        except (RuntimeError, OSError):
            self.pulser = None
            logging.info('External injector not connected. Switch to internal one')

        self.dut['data_rx'].reset()
        self.dut['fifo'].reset()

        self.dut['data_rx'].CONF_START_FREEZE = 88
        self.dut['data_rx'].CONF_START_READ = 92
        self.dut['data_rx'].CONF_STOP_FREEZE = 98
        self.dut['data_rx'].CONF_STOP_READ = 94
        self.dut['data_rx'].CONF_STOP = 110

        self.dut['INJ_LO'].set_voltage(self.INJ_LO, unit='V')

        self.dut['TH'].set_voltage(1.5, unit='V')
        self.dut['VDDD'].set_voltage(1.7, unit='V')
        self.dut['VDD_BCID_BUFF'].set_voltage(1.7, unit='V')

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
        self.dut["CONF_SR"]["MONITOR_EN"] = 0
        self.dut["CONF_SR"]["REGULATOR_EN"] = 1
        self.dut["CONF_SR"]["BUFFER_EN"] = 1
        self.dut["CONF_SR"]["LSBdacL"] = 45
        
        self.dut["CONF_SR"]["VPFB"] = 4

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

        self.dut['CONF']['RESET_GRAY'] = 0
        self.dut['CONF'].write()

        self.dut['CONF_SR']['MON_EN'].setall(True)
        self.dut['CONF_SR']['INJ_EN'].setall(False)
        self.dut['CONF_SR']['ColRO_En'].setall(False)

        self.dut.PIXEL_CONF['PREAMP_EN'][:] = 0
        self.dut.PIXEL_CONF['INJECT_EN'][:] = 0
        self.dut.PIXEL_CONF['MONITOR_EN'][:] = 0
#         self.dut.PIXEL_CONF['TRIM_EN'][:] = 15

    def scan(self, repeat=100, scan_range=[0, 0.2, 0.05], mask_filename='', TH=1.5, mask=16, columns=range(0, 36), threshold_overdrive=0.001, TRIM_EN=None, **kwargs):
        self.configure()
        self.mus = np.zeros(shape=(36, 129), dtype='f')
        self.sigmas = np.zeros(shape=(36, 129), dtype='f')

        # LOAD PIXEL DAC
        if mask_filename:
            with tb.open_file(str(mask_filename), 'r') as in_file_h5:
                logging.info('Loading configuration from: %s', mask_filename)

                TRIM_EN = in_file_h5.root.scan_results.TRIM_EN[:]
                PREAMP_EN = in_file_h5.root.scan_results.PREAMP_EN[:]

                self.dut.PIXEL_CONF['TRIM_EN'][:] = TRIM_EN[:]
                self.dut.PIXEL_CONF['PREAMP_EN'][:] = PREAMP_EN[:]

                dac_status = yaml.load(in_file_h5.root.meta_data.attrs.dac_status)
                power_status = yaml.load(in_file_h5.root.meta_data.attrs.power_status)

                TH = in_file_h5.root.meta_data.attrs.final_threshold + threshold_overdrive
                logging.info('Loading threshold values (+mv): %f', TH)

                logging.info('Loading DAC values from: %s', str(dac_status))
                dac_names = ['BLRes', 'VAmp', 'VPFB', 'VPFoll', 'VPLoad', 'IComp', 'Vbias_CS', 'IBOTA', 'ILVDS', 'Vfs', 'LSBdacL', 'Vsf_dis1', 'Vsf_dis2', 'Vsf_dis3']
                for dac in dac_names:
                    self.dut['CONF_SR'][dac] = dac_status[dac]
                    print dac, self.dut['CONF_SR'][dac]

                scan_kwargs = yaml.load(in_file_h5.root.meta_data.attrs.kwargs)
                columns = scan_kwargs['column_enable']
                logging.info('Column Enable: %s', str(columns))

        else:
            # first time, get TRIM_EN from configuration
            if np.any(TRIM_EN is None):
                for pix_col in columns:
                    self.dut.PIXEL_CONF['PREAMP_EN'][pix_col, :] = 1

            else:
                # if TRIM_EN is given as parameter, do not change it
                for pix_col in columns:
                    self.dut.PIXEL_CONF['PREAMP_EN'][pix_col, :] = 1

        for pix_col in columns:
            dcol = int(pix_col / 2)
            self.dut['CONF_SR']['ColRO_En'][35 - pix_col] = 1

#         self.dut.PIXEL_CONF['TRIM_EN'][:] = 8
        self.dut.PIXEL_CONF['TRIM_EN'][:] = np.load(file_path + '/trim_values_step4.npy')
        self.dut.write_global_conf()
        self.dut.write_pixel_conf()

        scan_range = np.arange(scan_range[0], scan_range[1], scan_range[2])

        logging.info('Threshold: %f', TH)
        self.dut['TH'].set_voltage(TH, unit='V')

        for pix_col_indx, pix_col in enumerate(columns):

            self.dut['CONF_SR']['INJ_EN'].setall(False)

            mask_steps = []
            for m in range(mask):
                col_mask = np.copy(self.dut.PIXEL_CONF['INJECT_EN'][pix_col, :])
                col_mask[m::mask] = True
                mask_steps.append(np.copy(col_mask))

            # begin scan loop here
            self.scan_loop(pix_col_indx, pix_col, mask, mask_steps, TRIM_EN, TH, scan_range, repeat)

        plt.ylim(0, 130)
#         plt.clf()
        plt.savefig(file_path + '/s_curve_tuned.pdf')
        plt.clf()

    def scan_loop(self, pix_col_indx, pix_col, mask, mask_steps, TRIM_EN, TH, scan_range, repeat):

        # activate mask
        for idx, mask_step in enumerate(mask_steps):
            # raw_input("New mask starts now. Check data and press Enter to proceed")

            dcol = int(pix_col / 2)
            self.dut['CONF_SR']['INJ_EN'].setall(False)
            # self.dut['CONF_SR']['PREAMP_EN'].setall(False)
#             self.dut.PIXEL_CONF['TRIM_EN'][:] = 15
            self.dut.PIXEL_CONF['INJECT_EN'][:] = 0

            self.dut.PIXEL_CONF['INJECT_EN'][pix_col, :] = mask_step
#             self.dut.PIXEL_CONF['TRIM_EN'][pix_col, :][mask_step] = TRIM_EN[pix_col, :][mask_step]
            self.dut['CONF_SR']['INJ_EN'][17 - dcol] = 1

#             print TRIM_EN[8:12, :]

            self.dut.write_global_conf()
            self.dut.write_pixel_conf()

            self.dut['CONF']['RESET_GRAY'] = 1
            self.dut['CONF'].write()

            self.dut['CONF']['RESET_GRAY'] = 0
            self.dut['CONF'].write()

            time.sleep(0.1)

            data_type = {'names': ['inj', 'col', 'row', 'hist'], 'formats': [np.float64, 'uint16', 'uint16', 'uint16']}
            hits = np.recarray((0), dtype=data_type)

            # for given mask change injection value
            for vol_idx, inj_value in enumerate(scan_range):
                param_id = pix_col_indx * len(scan_range) * mask + idx * len(scan_range) + vol_idx

                if show_info:
                    logging.info('Scan : Column = %s MaskId=%d InjV=%f ID=%d)', pix_col, idx, inj_value, param_id)

                if self.pulser:
                    self.pulser['Pulser'].set_voltage(self.INJ_LO, float(self.INJ_LO + inj_value), unit='V')
                    if abs(inj_value) < 0.00001:
                        time.sleep(2)
                else:
                    # Enabled before: (For GPAC injection)
                    self.dut['INJ_LO'].set_voltage(self.INJ_LO, unit='V')
                    self.dut['INJ_HI'].set_voltage(float(self.INJ_LO + inj_value), unit='V')
                self.dut['TH'].set_voltage(TH, unit='V')

                time.sleep(0.1)
                self.dut['data_rx'].reset()
                self.dut['data_rx'].set_en(True)
                time.sleep(0.2)
                self.dut['fifo'].reset()
                self.dut['data_rx'].set_en(False)

                with self.readout(scan_param_id=param_id, fill_buffer=True, clear_buffer=True):

                    self.dut['data_rx'].reset()
                    self.dut['fifo'].reset()

                    self.dut['data_rx'].CONF_START_FREEZE = 88
                    self.dut['data_rx'].CONF_START_READ = 92
                    self.dut['data_rx'].CONF_STOP_FREEZE = 98
                    self.dut['data_rx'].CONF_STOP_READ = 94
                    self.dut['data_rx'].CONF_STOP = 110

                    self.dut['data_rx'].set_en(True)

                    # self.dut['inj'].start()
                    self.dut['gate_tdc'].start()

                    while not self.dut['inj'].is_done():
                        pass

                    time.sleep(0.1)

                    self.dut['data_rx'].set_en(False)
                    self.dut['TH'].set_voltage(1.5, unit='V')

                dqdata = self.fifo_readout.data
                try:
                    data = np.concatenate([item[0] for item in dqdata])
                except ValueError:
                    data = []

                data_size = len(data)

                logging.info('Scan Pixel Finished: V=%f DATA_COUNT=%d', inj_value, data_size)

                hit_data = self.dut.interpret_rx_data(data)
                pixel_data = hit_data['col'] * 129 + hit_data['row']
                hit_pixels = np.unique(pixel_data)
                hist = np.bincount(pixel_data)

                # calculate threshold for pixels in this mask step here

                msg = ' '

                if data_size:
                    for pix in hit_pixels:
                        col = pix / 129
                        row = pix % 129
                        msg += '[%d, %d]=%d ' % (col, row, hist[pix])
                        hits = np.append(hits, np.array([tuple([inj_value, col, row, hist[pix]])], dtype=data_type))
                    logging.info(msg)

                if data_size > 1000000:
                    logging.error('Too much data!')

                    return

            time.sleep(5)

            logging.info("Analyze data of column %d" % pix_col)
            TRIM_EN = self.calculate_pixel_threshold(hits, scan_range, TRIM_EN, repeat)

        self.TRIM_EN = TRIM_EN

    def calculate_pixel_threshold(self, hits, scan_range, TRIM_EN, repeat):
        hits['col'] = hits['col'] * 129 + hits['row']

        # TODO: ignore pixels that are not in mask
        for pixel in np.unique(hits['col']):
            pixel_data = hits[np.where(hits['col'] == pixel)[0]]

            hist = np.zeros(shape=(len(scan_range)))

            # pad all other injection values where no hits are with 0
            for index, inj_value in enumerate(pixel_data['inj']):
                hist[scan_range == inj_value] = pixel_data['hist'][index]

            # fit s curve
            A, mu, sigma = analysis.fit_scurve(hist, scan_range, repeat)
            self.mus[pixel / 129, pixel % 129] = mu
            self.sigmas[pixel / 129, pixel % 129] = sigma


#             plt.title('scurve for pixel %d' % pixel)
#             plt.step(scan_range, hist)
            plt.plot(np.arange(scan_range[0], scan_range[-1], 0.001), analysis.scurve(np.arange(scan_range[0], scan_range[-1], 0.001), A, mu, sigma))


scan = AnalogScan()
configuration = {
    "repeat": 100,
    "mask_filename": '',
    "scan_range": [0.01, 0.3, 0.025],
    "mask": 8,
    "TH": 0.769,
    "columns": range(24, 28),
    "threshold_overdrive": 0.006
}

file_path = '/home/idcs/STREAM/Devices/MONOPIX_01/Tests/20170720_FastTuning/22_cols24-27_target0,15_TH0,769_VPFB4'

# TODO make this a loop

scan.configure(**configuration)

scan.start(**configuration)
TRIM_EN = scan.TRIM_EN
# trim_vals = TRIM_EN[8:12, :].reshape(-1)

mus = scan.mus
sigmas = scan.sigmas
np.save(file_path + '/mu_values.npy', mus)
np.save(file_path + '/sigma_values.npy', sigmas)

print len(np.where(np.logical_or(mus[24:28, :] > 0.2, mus[24:28, :] < 0.1))[0])

# plt.clf()
# plt.hist(trim_vals, bins=np.arange(-0.5, 16.5, 1))
# plt.savefig(file_path + '/trim_01.pdf')

plt.clf()
