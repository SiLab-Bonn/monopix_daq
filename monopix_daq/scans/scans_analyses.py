import time
import logging
import numpy as np
import tables as tb
import yaml
import monopix_daq.analysis as analysis
import matplotlib.pyplot as plt
from matplotlib.backends.backend_pdf import PdfPages
from scipy.optimize import curve_fit

import re

from monopix_daq.scan_base import ScanBase
from progressbar import ProgressBar
from basil.dut import Dut

def fit_func(x, p0, p1):
    return p0 + p1/x

def plot_le_vs_injV(filename, save_mode = 'pdf'):
    with tb.open_file(filename, 'r') as infile:
        hits = infile.root.hit_data[:]
        
        print hits.dtype

        mean_le = {}
        rms_le = {}

        slahses = [m.start() for m in re.finditer('/', filename)]
        dirpos = slahses[-1]+1
        dire = filename[0:dirpos]
        slahsesf = [m.start() for m in re.finditer('.', filename)]
        filepos = slahsesf[-1]+1
        filenamer = filename[0:filepos]
        
        binning = np.arange(0, 40)
        voltages = np.unique(hits['InjV'])
        if save_mode == 'pdf':
            output_pdf_file = filenamer + '_le_vs_Injv.pdf'
            output_pdf = PdfPages(output_pdf_file)
        for v in voltages:
            fig = plt.figure(figsize=(10,5))
            toplot = hits['InjV'] == v
            toplot = np.logical_and(toplot, hits['col'] == 25)
            toplot = np.logical_and(toplot, hits['row'] == 64)
            if len(hits['le'][toplot]) > 10: #only tot values with a decent number of hits
                mean_le[v] = np.mean(hits['le'][toplot])
                rms_le[v] = np.std(hits['le'][toplot])
            n, bins, patches = plt.hist(hits['le'][toplot], binning, normed=1, facecolor='green', alpha=0.75)
            plt.xlabel('le')
            plt.ylabel('# (normalized)')
            title = 'leading edge distribution for injection voltage of ' + str(v) + ' V'
            title += ', mean = %.2f' % (np.mean(hits['le'][toplot])) + ', rms = %.2f' % (np.std(hits['le'][toplot])) + ')'
            plt.title(title)
            if save_mode == 'pdf':
                output_pdf.savefig(fig)
                plt.close(fig)
            elif save_mode == 'show':
                plt.show()
            elif save_mode == 'png':
                imgname = dire + 'le_distributions_InjV%.02f' % v + '.png'
                print 'Saving', imgname
                plt.savefig(imgname)
                plt.close(fig)

        fig_mean = plt.figure(figsize=(10,5))
        plt.errorbar(mean_le.keys(), mean_le.values(), yerr=rms_le.values(), fmt='o')
        plt.xlabel('Injection Voltage (V)')
        plt.ylabel('mean le')
        plt.ylim([0,20])
        plt.yticks(np.arange(0,40))
        plt.grid(which='both', axis='y')
        plt.title('average le as a function of injected voltage')
        if save_mode == 'pdf':
            output_pdf.savefig(fig_mean)
            plt.close(fig_mean)
        elif save_mode == 'show':
            plt.show()
        elif save_mode == 'png':
            imgname_mean = dire + 'le_vs_InjV_mean.png'
            print 'Saving', imgname_mean
            plt.savefig(imgname_mean)
            plt.close(fig_mean)

        fig_rms = plt.figure(figsize=(10,5))
        plt.plot(rms_le.keys(), rms_le.values(), 'o')
        plt.xlabel('Injection Voltage (V)')
        plt.ylabel('rms le')
        plt.ylim([0,20])
        plt.yticks(np.arange(0,20))
        plt.grid(which='both', axis='y')
        plt.title('rms of le distribution as a function of injected voltage')
        if save_mode == 'pdf':
            output_pdf.savefig(fig_rms)
            plt.close(fig_rms)
        elif save_mode == 'show':
            plt.show()
        elif save_mode == 'png':
            imgname_rms = dire + 'le_vs_InjV_rms.png'
            print 'Saving', imgname_rms
            plt.savefig(imgname_rms)
            plt.close(fig_rms)
            
        if save_mode == 'pdf':
            output_pdf.close()


def plot_le_vs_tot(filename, save_mode = 'pdf'):
    with tb.open_file(filename, 'r') as infile:
        hits = infile.root.hit_data[:]
        
        print hits.dtype
        
        mean_le = {}
        rms_le = {}
        
        slahses = [m.start() for m in re.finditer('/', filename)]
        dirpos = slahses[-1]+1
        dire = filename[0:dirpos]
        slahsesf = [m.start() for m in re.finditer('.', filename)]
        filepos = slahsesf[-1]+1
        filenamer = filename[0:filepos]

        binning = np.arange(0, 40)
#        selection = len(hits['le'][toplot]) > 10
        voltages = np.unique(hits['tot'])
        selection = []
        if save_mode == 'pdf':
            output_pdf_file = filenamer + '_le_vs_tot.pdf'
            output_pdf = PdfPages(output_pdf_file)
        for v in voltages:
            fig = plt.figure(figsize=(10,5))
            toplot = hits['tot'] == v
            #toplot = np.logical_and(toplot, hits['InjV'] > 0.6)
            toplot = np.logical_and(toplot, hits['col'] == 25)
            toplot = np.logical_and(toplot, hits['row'] == 64)
            if len(hits['le'][toplot]) > 10: #only tot values with a decent number of hits
                if v != 0:
                    selection.append(True)
                else:
                    selection.append(False)
            else:
                selection.append(False)
            mean_le[v] = np.mean(hits['le'][toplot])
            rms_le[v] = np.std(hits['le'][toplot])
            n, bins, patches = plt.hist(hits['le'][toplot], binning, normed=1, facecolor='green', alpha=0.75)
            plt.xlabel('le')
            plt.ylabel('# (normalized)')
            title = 'leading edge distribution for tot of ' + str(v) + ' (' + str(len(hits['le'][toplot])) + ' events'
            title += ', mean = %.2f' % (np.mean(hits['le'][toplot])) + ', rms = %.2f' % (np.std(hits['le'][toplot])) + ')'
            plt.title(title)
            if save_mode == 'pdf':
                output_pdf.savefig(fig)
                plt.close(fig)
            elif save_mode == 'show':
                plt.show()
            elif save_mode == 'png':
                imgname = dire + 'le_distributions_tot%03d' % v + '.png'
                print 'Saving', imgname
                plt.savefig(imgname)
                plt.close(fig)
            
        fig_mean = plt.figure(figsize=(10,5))
        selection = np.array(selection)
        fit, _ = curve_fit(fit_func, voltages[selection], np.array(mean_le.values())[selection])  # Fit 1/x function
        plt.plot(voltages[selection], fit_func(voltages[selection], *fit), 'r-', label='fit p0 + p1/x \n p0 = %.2f \n p1 = %.2f' %(fit[0], fit[1]))
        mean_le_keys = np.array(mean_le.keys())
        plt.errorbar(mean_le_keys[selection], np.array(mean_le.values())[selection], yerr=np.array(rms_le.values())[selection], fmt='--o')
        plt.xlabel('tot')
        plt.ylabel('mean le')
        plt.ylim([0,20])
        plt.yticks(np.arange(0,20))
        plt.grid(which='both', axis='y')
        plt.title('average le as a function of tot')
        plt.legend()
        if save_mode == 'pdf':
            output_pdf.savefig(fig_mean)
            plt.close(fig_mean)
        elif save_mode == 'show':
            plt.show()
        elif save_mode == 'png':
            imgname_mean = dire + 'le_vs_tot_mean.png'
            print 'Saving', imgname_mean
            plt.savefig(imgname_mean)
            plt.close(fig_mean)

        fig_rms = plt.figure(figsize=(10,5))
        rms_le_keys = np.array(rms_le.keys())
        plt.plot(rms_le_keys[selection], np.array(rms_le.values())[selection], 'o-')
        plt.xlabel('tot')
        plt.ylabel('rms le')
        plt.ylim([0,20])
        plt.yticks(np.arange(0,20))
        plt.grid(which='both', axis='y')
        plt.title('rms of le distribution as a function of tot')
        if save_mode == 'pdf':
            output_pdf.savefig(fig_rms)
            plt.close(fig_rms)
        elif save_mode == 'show':
            plt.show()
        elif save_mode == 'png':
            imgname_rms = dire + 'le_vs_tot_rms.png'
            print 'Saving', imgname_rms
            plt.savefig(imgname_rms)
            plt.close(fig_rms)
            
        if save_mode == 'pdf':
            output_pdf.close()

            
if __name__ == "__main__":
    plot_le_vs_injV('../../monopix_daq/scans/output_data/20170531_131058_scan_timewalk.h5', save_mode='png')
    plot_le_vs_tot ('../../monopix_daq/scans/output_data/20170531_131058_scan_timewalk.h5', save_mode = 'png')
    
    