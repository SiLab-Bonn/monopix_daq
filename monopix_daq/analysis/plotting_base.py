import numpy as np
import math
import logging
import shutil
import os,sys
import matplotlib
import random
import datetime
import tables

import matplotlib.pyplot as plt
from collections import OrderedDict
from scipy.optimize import curve_fit
from scipy.stats import norm
from matplotlib.figure import Figure
from matplotlib.artist import setp
from matplotlib.backends.backend_agg import FigureCanvasAgg as FigureCanvas
from mpl_toolkits.axes_grid1 import make_axes_locatable
from matplotlib import colors, cm
from matplotlib.backends.backend_pdf import PdfPages
import matplotlib.ticker as ticker

COL_SIZE = 36 ##TODO change hard coded values
ROW_SIZE = 129
TITLE_COLOR = '#07529a'
OVERTEXT_COLOR = '#07529a'


class PlottingBase(object):
    def __init__(self, fhit, fraw, fpdf=None, save_png=False,save_single_pdf=False):
        self.logger = logging.getLogger()
        #self.logger.setLevel(loglevel)
        
        self.plot_cnt = 0
        self.save_png = save_png
        self.save_single_pdf = save_single_pdf
        if fpdf is None:
            self.filename = fhit[:-7] + '.pdf'
        else:
            self.filename = fpdf
        self.out_file = PdfPages(self.filename)
    def _save_plots(self, fig, suffix=None, tight=True):
        increase_count = False
        bbox_inches = 'tight' if tight else ''
        fig.tight_layout()
        if suffix is None:
            suffix = str(self.plot_cnt)
        self.out_file.savefig(fig) #, bbox_inches=bbox_inches)
        if self.save_png:
            fig.savefig(self.filename[:-4] + '_' +
                        suffix + '.png') #, bbox_inches=bbox_inches)
            increase_count = True
        if self.save_single_pdf:
            fig.savefig(self.filename[:-4] + '_' +
                        suffix + '.pdf') #, bbox_inches=bbox_inches)
            increase_count = True
        if increase_count:
            self.plot_cnt += 1

    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc_value, traceback):
        if self.out_file is not None and isinstance(self.out_file, PdfPages):
            self.logger.info('Closing output PDF file: %s', str(self.out_file._file.fh.name))
            self.out_file.close()
            shutil.copyfile(self.filename, os.path.join(os.path.split(self.filename)[0], 'last_scan.pdf'))
            
    def table_6col(self,dat):
        keys=np.sort(np.array(dat.keys()))
        cellText=[]
        for i in range(20):
            if i+20*2 < len(keys):
                cellText.append([keys[i],dat[keys[i]],
                             keys[i+20],dat[keys[i+20]],
                             keys[i+20*2],dat[keys[i+20*2]]
                             ])
            else:
                cellText.append([keys[i],dat[keys[i]],
                             keys[i+20],dat[keys[i+20]],
                             "",""])
        fig = Figure()
        FigureCanvas(fig)

        ax = fig.add_subplot(111)
        fig.patch.set_visible(False)
        ax.set_adjustable('box')
        ax.axis('off')
        ax.axis('tight')
        t=ax.table(cellText=cellText,
                 #rowLabels=rows[:20],
                 colLabels=["Param","Values","Param","Values","Param","Values"],
                 colWidths = [0.15,0.15,0.15,0.15,0.15,0.15],
                 loc='upper center')
        t.set_fontsize(10)
        self._save_plots(fig, suffix=None, tight=True)
                      
    def plot_2d_pixel_4(self, dat, title=["Preamp","Inj","Mon","TDAC"], 
                            x_axis_title="Column", y_axis_title="Row", z_axis_title=None, 
                            z_min=[0,0,0,0], z_max=[1,1,1,15], 
                            cmap=None):
        fig = Figure()
        FigureCanvas(fig)
        for i in range(4):
            ax = fig.add_subplot(221+i)
            ax.imshow(np.transpose(dat[i]),origin='lower',aspect="auto"
                     ,vmax=z_max[i],vmin=z_min[i])
            ax.set_title(title[i])
            ax.set_ylim((-0.5, ROW_SIZE-0.5))
            ax.set_xlim((-0.5, COL_SIZE-0.5))
        self._save_plots(fig)
        
    def plot_2d_pixel_hist(self, hist2d, title=None, 
                            x_axis_title="Column", y_axis_title="Row", z_axis_title=None, 
                            z_min=0, z_max=None, 
                            cmap=None):
        if z_max == 'median':
            z_max = 2 * np.ma.median(hist2d)
        elif z_max == 'maximum':
            z_max = np.ma.max(hist2d)
        elif z_max is None:
            z_max = np.percentile(hist2d, q=90)
            if np.any(hist2d > z_max):
                z_max = 1.1 * z_max
        if z_max < 1 or hist2d.all() is np.ma.masked:
            z_max = 1.0
        if z_min is None:
            z_min = np.ma.min(hist2d)
        if z_min == z_max or hist2d.all() is np.ma.masked:
            z_min = 0

        fig = Figure()
        FigureCanvas(fig)
        ax = fig.add_subplot(111)
        ax.set_adjustable('box')
        #extent = [0.5, 400.5, 192.5, 0.5]
        bounds = np.linspace(start=z_min, stop=z_max + 1, num=255, endpoint=True)
        cmap = cm.get_cmap('plasma')
        cmap.set_bad('w')
        cmap.set_over('r')  # Make noisy pixels red
        norm = colors.BoundaryNorm(bounds, cmap.N)

        im = ax.imshow(np.transpose(hist2d), interpolation='none', aspect='auto', 
                       cmap=cmap, norm=norm,
                       origin='lower')  # TODO: use pcolor or pcolormesh
        ax.set_ylim((-0.5, ROW_SIZE-0.5))
        ax.set_xlim((-0.5, COL_SIZE-0.5))
        ax.set_title(title + r' ($\Sigma$ = {0})'.format((0 if hist2d.all() is np.ma.masked else np.ma.sum(hist2d))), color=TITLE_COLOR)
        ax.set_xlabel(x_axis_title)
        ax.set_ylabel(y_axis_title)

        divider = make_axes_locatable(ax)

        cax = divider.append_axes("right", size="5%", pad=0.5)
        cb = fig.colorbar(im, cax=cax) #, ticks=np.linspace(start=z_min, stop=z_max, num=10, endpoint=True), orientation='horizontal')
        #cax.set_xticklabels([int(round(float(x.get_text().replace(u'\u2212', '-').encode('utf8')))) for x in cax.xaxis.get_majorticklabels()])
        cb.set_label(z_axis_title)
            
        self._save_plots(fig)
        

            
            
            