from monopix_daq.scan_base import ScanBase

from matplotlib import pyplot as plt

import time
import os

import numpy as np
import tables as tb
import yaml

from progressbar import ProgressBar

import logging
logging.basicConfig(level=logging.INFO, format="%(asctime)s - %(name)s - [%(levelname)-8s] (%(threadName)-10s) %(message)s")

show_info = False


class Tuning(ScanBase):
    scan_id = "fast_tuning"

    def get_hits(self):
        return self.hits

    def get_threshold_setting(self):
        return self.TRIM_EN

    def scan(self, repeat=1000, scan_range=[0, 0.2, 0.05], mask_filename='', TH=1.5, mask=16, columns=range(0, 36), threshold_overdrive=0.001, TRIM_EN=None):
        self.configure(repeat=repeat, columns=columns)

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
            if bit_index == 3:
                TRIM_EN = self.dut.PIXEL_CONF['TRIM_EN'].copy()
                for pix_col in columns:
                    TRIM_EN[pix_col, :] = 8
                    self.dut.PIXEL_CONF['PREAMP_EN'][pix_col, :] = 1
            else:
                # if TRIM_EN is given as parameter, do not change it
                for pix_col in columns:
                    self.dut.PIXEL_CONF['PREAMP_EN'][pix_col, :] = 1

        for pix_col in columns:
            dcol = int(pix_col / 2)
            self.dut['CONF_SR']['ColRO_En'][35 - pix_col] = 1

        print '### Scanning with setting: ###'
        print TRIM_EN[24:25, :]

        self.dut.PIXEL_CONF['TRIM_EN'][:] = TRIM_EN[:]
        self.dut.write_global_conf()
        self.dut.write_pixel_conf()

        scan_range = np.arange(scan_range[0], scan_range[1], scan_range[2])

        logging.info('Threshold: %f', TH)
        self.dut['TH'].set_voltage(TH, unit='V')

        self.hits = None

        self.hits_data_type = {'names': ['inj', 'col', 'row', 'hist'], 'formats': [np.float64, 'uint16', 'uint16', 'uint16']}
        self.hits = np.recarray((0), dtype=self.hits_data_type)

        for pix_col_indx, pix_col in enumerate(columns):

            self.dut.PIXEL_CONF['TRIM_EN'][:] = TRIM_EN[:]
            self.dut['CONF_SR']['INJ_EN'].setall(False)

            mask_steps = []
            for m in range(mask):
                col_mask = np.copy(self.dut.PIXEL_CONF['INJECT_EN'][pix_col, :])
                col_mask[m::mask] = True
                mask_steps.append(np.copy(col_mask))

            # begin scan loop here
            self.scan_loop(pix_col_indx, pix_col, mask, mask_steps, TRIM_EN, TH, scan_range, repeat)

    def scan_loop(self, pix_col_indx, pix_col, mask, mask_steps, TRIM_EN, TH, scan_range, inj_value=0.5):

        # activate mask
        for idx, mask_step in enumerate(mask_steps):
            dcol = int(pix_col / 2)
            self.dut['CONF_SR']['INJ_EN'].setall(False)
            # self.dut['CONF_SR']['PREAMP_EN'].setall(False)
            self.dut.PIXEL_CONF['TRIM_EN'][:] = 15
            self.dut.PIXEL_CONF['INJECT_EN'][:] = 0

            self.dut.PIXEL_CONF['INJECT_EN'][pix_col, :] = mask_step
            self.dut.PIXEL_CONF['TRIM_EN'][pix_col, :][mask_step] = TRIM_EN[pix_col, :][mask_step]
            self.dut['CONF_SR']['INJ_EN'][17 - dcol] = 1

#             print TRIM_EN[8:12, :]

            self.dut.write_global_conf()
            self.dut.write_pixel_conf()

            self.dut['CONF']['RESET_GRAY'] = 1
            self.dut['CONF'].write()

            self.dut['CONF']['RESET_GRAY'] = 0
            self.dut['CONF'].write()

            time.sleep(0.1)

            # for given mask change injection value
            inj_value = 0.15
            param_id = pix_col_indx * len(scan_range) * mask + idx * len(scan_range)

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
            hit_data = hit_data[hit_data['le'] < 25]
            pixel_data = hit_data['col'] * 129 + hit_data['row']
            hit_pixels = np.unique(pixel_data)
            hist = np.bincount(pixel_data)

            # calculate threshold for pixels in this mask step here

            msg = ' '

            # Give id to pixels, starting from 0 at (col, row) = (0, 0)
            for activated_pixel_id in pix_col * 129 + np.where(mask_step)[0]:
                if activated_pixel_id in hit_pixels:
                    # There was a hit in this pixel
                    self.hits = np.append(self.hits, np.array([tuple([inj_value, activated_pixel_id / 129, activated_pixel_id % 129, hist[activated_pixel_id]])], dtype=self.hits_data_type))
                else:
                    # There was no hit in this pixel (although charge was injected). Set hist to 0
                    self.hits = np.append(self.hits, np.array([tuple([inj_value, activated_pixel_id / 129, activated_pixel_id % 129, 0])], dtype=self.hits_data_type))

            if data_size:
                for pix in hit_pixels:
                    col = pix / 129
                    row = pix % 129
                    msg += '[%d, %d]=%d ' % (col, row, hist[pix])
#                     self.hits = np.append(self.hits, np.array([tuple([inj_value, col, row, hist[pix]])], dtype=self.hits_data_type))
                logging.info(msg)

            if data_size > 1000000:
                logging.error('Too much data!')

                return

            time.sleep(.5)

        # format hits
        self.TRIM_EN = TRIM_EN


def calculate_new_threshold_settings(bit_index, n_inj, hist_map, old_threshold):
    new_threshold = old_threshold

    # TODO can be omitted when saving closest distance
    # check if optimal threshold is already found

    # in any case, switch next bit (if bit is not least significant) to 1
    if bit_index > 0:
        new_threshold = new_threshold | (1 << bit_index - 1)

    # If needed raise threshold, otherwise keep 0
    new_threshold[hist_map < (n_inj / 2)] = ~(1 << bit_index) & new_threshold[hist_map < (n_inj / 2)]
    return new_threshold


def calculate_hist_map(hits, n_inj, old_threshold_setting):
    hist_map = np.zeros_like(old_threshold_setting, dtype=np.uint16)
    noisy = np.full_like(hist_map, True)

    # Iterate over all pixels
    for pixel in hits:
        hist_map[pixel["col"], pixel["row"]] = pixel["hist"]

    # exclude non-noisy pixels from mask
    noisy[hist_map < n_inj] = False

    return hist_map


# Initialize here
columns = (24, 28)

scan = Tuning()
configuration = {
    "repeat": 200,
    "mask_filename": '',
    "scan_range": [0.01, 0.5, 0.025],
    "mask": 8,
    "TH": 0.766,
    "columns": range(columns[0], columns[1]),
    "threshold_overdrive": 0.006
}

file_path = '/home/silab/Desktop/tuning/test_tuning'
if not os.path.exists(file_path):
    os.makedirs(file_path)
    print "Created folder:"
    print file_path

# MAIN LOOP
scan.configure(injection=True, **configuration)
TRIM_EN = np.full((36, 129), 8, dtype=np.uint8)

best_threshold_setting = None  # best trim settings
hist_best = None  # hits for best trim setting

# bit_index counts down from 3 to 0
for bit_index in np.arange(3, -1, -1):
    scan.start(TRIM_EN=TRIM_EN.copy(), **configuration)
    threshold_setting = scan.get_threshold_setting()

#     print threshold_setting[columns[0]:columns[1], :]

    trim_vals = threshold_setting
    hits = scan.get_hits()

    if len(hits) != 129 * (columns[1] - columns[0]):
        logging.error("Some hits were lost, information is missing!")
        raw_input("Proceed anyway?")

    # Calculate hsit_map
    hist_map = calculate_hist_map(hits, configuration["repeat"], threshold_setting)

    # Store best setting on the fly since search algo does not always
    # converge to best value
    if not np.any(best_threshold_setting):
        best_threshold_setting = TRIM_EN
        hist_best = hist_map
    else:
        selection = np.abs(hist_best - float(configuration["repeat"]) / 2) > np.abs(hist_map - float(configuration["repeat"]) / 2)
        logging.info("Updating %s values" % np.count_nonzero(selection))
        best_threshold_setting[selection] = TRIM_EN[selection]
        hist_best[selection] = hist_map[selection]

    np.save(file_path + "/trim_values_step" + str(3 - bit_index) + ".npy", best_threshold_setting)
#     print new_threshold_setting[columns[0]:columns[1], :].reshape(-1)
    plt.hist(best_threshold_setting[columns[0]:columns[1], :].reshape(-1), bins=np.arange(-0.5, 16.5, 1))
    plt.savefig(file_path + '/trim_0' + str(3 - bit_index) + '.pdf')
#     plt.show()
    plt.clf()

    new_threshold_setting = calculate_new_threshold_settings(bit_index, configuration["repeat"], hist_map, TRIM_EN)

    TRIM_EN = new_threshold_setting

# scan with last bit 0
fixed_TRIM = np.copy(~(1 << 0) & TRIM_EN)
scan.start(TRIM_EN=fixed_TRIM.copy(), **configuration)
threshold_setting = scan.get_threshold_setting()

# print threshold_setting[columns[0]:columns[1], :]

trim_vals = threshold_setting
hits = scan.get_hits()

if len(hits) != 129 * (columns[1] - columns[0]):
    logging.error("Some hits were lost, information is missing!")
    raw_input("Proceed anyway?")

# Calculate hsit_map
hist_map = calculate_hist_map(hits, configuration["repeat"], threshold_setting)

# Store best setting on the fly since search algo does not always converge to best value
if not np.any(best_threshold_setting):
    best_threshold_setting = fixed_TRIM
    hist_best = hist_map
else:
    selection = np.abs(hist_best - float(configuration["repeat"]) / 2) > np.abs(hist_map - float(configuration["repeat"]) / 2)
    logging.info("Updating %s values" % np.count_nonzero(selection))
    best_threshold_setting[selection] = fixed_TRIM[selection]
    hist_best[selection] = hist_map[selection]

np.save(file_path + "/trim_values_step" + str(4) + ".npy", best_threshold_setting)
plt.hist(best_threshold_setting[columns[0]:columns[1], :].reshape(-1), bins=np.arange(-0.5, 16.5, 1))
plt.savefig(file_path + '/trim_0' + str(4) + '.pdf')
plt.clf()

print scan.analyze()
