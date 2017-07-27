import time
import logging
import numpy as np
import tables as tb
import yaml
import monopix_daq.analysis as analysis
import matplotlib.pyplot as plt
# import re

from monopix_daq.scan_base import ScanBase
# from progressbar import ProgressBar

logging.basicConfig(level=logging.INFO, format="%(asctime)s - %(name)s - [%(levelname)-8s] (%(threadName)-10s) %(message)s")

local_configuration = {
    "how_long": 60,
    "repeat": 1000,
    "injection": 1.,
    "threshold": 0.855,
    "pixel": [25, 64],
    "VPFBvalue": 32,
    "delay_range": [0, 30, 1]  # ns
}


class ScanTimeJitter(ScanBase):
    scan_id = "scan_timejitter"

    def scan(self, repeat=10, threshold=1., pixel=[1, 64], how_long=1, injection=1., VPFBvalue=32, delay_range=[0, 30, 1], **kwargs):

        self.dut['fifo'].reset()

        # LOAD PIXEL DAC
        pix_col = pixel[0]
        pix_row = pixel[1]
        dcol = int(pix_col / 2)

        self.dut.PIXEL_CONF['TRIM_EN'][pix_col, pix_row] = 0
        self.dut.PIXEL_CONF['PREAMP_EN'][pix_col, pix_row] = 1
        self.dut['CONF_SR']['ColRO_En'][35 - pix_col] = 1

        np.set_printoptions(linewidth=260)

        self.dut['TH'].set_voltage(threshold, unit='V')

        self.dut.PIXEL_CONF['INJECT_EN'][pix_col, pix_row] = 1
        self.dut['CONF_SR']['INJ_EN'][17 - dcol] = 1

        self.dut.write_global_conf()
        self.dut.write_pixel_conf()

        self.dut['CONF']['RESET_GRAY'] = 1
        self.dut['CONF']['RESET'] = 1
        self.dut['CONF'].write()

        self.dut['CONF']['RESET'] = 0
        self.dut['CONF'].write()

        self.dut['CONF']['RESET_GRAY'] = 0
        self.dut['CONF'].write()

        self.dut['data_rx'].set_en(True)
        time.sleep(0.2)

        def print_hist(all_hits=False):
            # dqdata = self.fifo_readout.data[1:-1]
            dqdata = self.fifo_readout.data
            try:
                data = np.concatenate([item[0] for item in dqdata])
            except ValueError:
                data = []

            hit_data = self.dut.interpret_rx_data(data)
            data_size = len(data)

            pixel_data = hit_data['col'] * 129 + hit_data['row']

            # tot = (hit_data['te'] - hit_data['le']) & 0xFF
            tot = hit_data['te'] - hit_data['le']
            neg = hit_data['te'] < hit_data['le']
            tot[neg] = hit_data['te'][neg] + (255 - hit_data['le'][neg])

#            print "tot"
#            for i,d in enumerate(hit_data):
#                if d['te'] < d['le']:
#                    print d['te'], d['le'], tot[i], '*'
#                else:
#                    print d['te'], d['le'], tot[i]
#                     if i> 1000:
#                         break

            scan_pixel = pix_col * 129 + pix_row
            scan_pixel_hits = np.where(pixel_data == scan_pixel)[0]
            tot_hist = np.bincount(tot[scan_pixel_hits])

            argmax = -1
            if len(tot_hist):
                argmax = np.argmax(tot_hist)

            logging.info('Data Count: %d ToT Histogram: %s (argmax=%d)', data_size, str(tot_hist), argmax)

            if all_hits:
                hit_pixels = np.unique(pixel_data)
                hist = np.bincount(pixel_data)
                msg = ' '
                for pix in hit_pixels:
                    col = pix / 129
                    row = pix % 129

                    msg += '[%d, %d]=%d %f' % (col, row, hist[pix], np.mean(tot))

                logging.info(msg)

            return tot_hist[1:-1]

        inj_scan_dict = {}

        delay_scan_range = np.arange(delay_range[0], delay_range[1], delay_range[2])
        self.pulser['Pulser'].set_voltage(self.INJ_LO, self.INJ_LO + injection, unit='V')

        for inx, delay in enumerate(delay_scan_range):

            # Enabled before: (For GPAC injection)
            # self.dut['INJ_HI'].set_voltage( float(INJ_LO), unit='V')

            self.pulser['Pulser'].set_trigger_delay(delay * 1E-9)  # from s to ns (check http://literature.cdn.keysight.com/litweb/pdf/33250-90007.pdf page 5)

            logging.info('Scan : InjV=%f delay=%f ID=%d)', injection, delay, inx)
            time.sleep(2)
            # time.sleep(0.2)

            with self.readout(scan_param_id=inx, fill_buffer=True, clear_buffer=True):

                self.dut['data_rx'].reset()
                self.dut['fifo'].reset()
                self.dut['data_rx'].set_en(True)

                self.dut['gate_tdc'].start()
                while not self.dut['inj'].is_done():
                    pass

                time.sleep(0.2)

                self.dut['data_rx'].set_en(False)
                self.dut['TH'].set_voltage(1.5, unit='V')

            # print_hist()

            tot_hist = print_hist(all_hits=True)

            inj_scan_dict[float(delay)] = tot_hist.tolist()

        print inj_scan_dict
        with open('calib.yml', 'w') as outfile:
            yaml.dump(inj_scan_dict, outfile, default_flow_style=False)

    def analyze(self, h5_filename=''):
        if h5_filename == '':
            h5_filename = self.output_filename + '.h5'

        logging.info('Analyzing: %s', h5_filename)
        np.set_printoptions(linewidth=240)

        with tb.open_file(h5_filename, 'r+') as in_file_h5:
            raw_data = in_file_h5.root.raw_data[:]
            meta_data = in_file_h5.root.meta_data[:]

            # print raw_data
            hit_data = self.dut.interpret_rx_data(raw_data, meta_data)
            in_file_h5.create_table(in_file_h5.root, 'hit_data', hit_data, filters=self.filter_tables)


if __name__ == "__main__":

    scan = ScanTimeJitter()
    scan.configure(injection=True, **local_configuration)
    scan.start(**local_configuration)
    scan.analyze()
