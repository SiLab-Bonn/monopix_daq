import time
import logging
import numpy as np
import tables as tb
import yaml
import monopix_daq.analysis as analysis

from monopix_daq.scan_base import ScanBase
from progressbar import ProgressBar
from basil.dut import Dut

from monopix_daq.scans.scan_timewalk import ScanTimeWalk

logging.basicConfig(level=logging.INFO, format="%(asctime)s - %(name)s - [%(levelname)-8s] (%(threadName)-10s) %(message)s")

optimize_configuration = {
    "how_long": 60,
    "repeat": 1000,
    #"scan_injection": [0.2, 1.8, 0.2],#Should be hard-coded
    "threshold_range": [0.8, 0.8, -0.001],#[1.035, 1.035, -0.001],#[0.7818, 0.7818, -0.001], #[0.793, 0.793, -0.002],[29,64]  #[0.780, 0.780, -0.002]  [1,64]  #[21,64] [0.770, 0.770, -0.001]
    "pixel":  [25,64],
    "VPFBvalues": [i for i in range(5,65,5)],
    "allow_overshoot" : False,
    "tot_min" : 5
}

class TuneTimewalk(ScanTimeWalk):
    scan_id = 'tune_timewalk'
    
    def scan(self, repeat = 10, threshold_range = [0.8, 0.7, -0.05], pixel = [1,64] , how_long = 1, VPFBvalues = [32], allow_overshoot = False, tot_min = 5, **kwargs):
        
        tmp_configuration = dict(optimize_configuration)
        del tmp_configuration["VPFBvalues"]
        del tmp_configuration["allow_overshoot"]
        del tmp_configuration["tot_min"]
                                
        step = 0
        
        for vpfb in optimize_configuration["VPFBvalues"] :
            print 'VPFB value:', vpfb
            tmp_configuration["VPFBvalue"] = vpfb
            tmp_configuration["scan_dac_id"] = step
            ScanTimeWalk.scan(self, **tmp_configuration)
                        
            step += 1
            


            
    def analyze(self, h5_filename  = ''):
        
        ScanTimeWalk.analyze(self, h5_filename=h5_filename)
        
        self.time_walk_vals = {}
        for step, vpfb in enumerate(optimize_configuration["VPFBvalues"]) :
            self.time_walk_vals[vpfb] = ScanTimeWalk.get_timewalk_distance(self, optimize_configuration["allow_overshoot"], optimize_configuration["tot_min"], step, h5_filename)
            
        print self.time_walk_vals
        
        
            
if __name__ == "__main__":

    scan = TuneTimewalk()
    scan.start(**optimize_configuration)
    #scan.analyze(h5_filename='../../monopix_daq/scans/output_data/20170531_181717_tune_timewalk.h5')
    scan.analyze()

            
        
