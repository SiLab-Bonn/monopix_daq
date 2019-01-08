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
    def __init__(self, fout, save_png=False,save_single_pdf=False):
        self.logger = logging.getLogger()
        #self.logger.setLevel(loglevel)
        
        self.plot_cnt = 0
        self.save_png = save_png
        self.save_single_pdf = save_single_pdf
        self.filename = fout
        self.out_file = PdfPages(self.filename)
        
    def _save_plots(self, fig, suffix=None, tight=True):
        increase_count = False
        #bbox_inches = 'tight' if tight else ''
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
            
    def _add_text(self,text,fig):
        #fig.subplots_adjust(top=0.85)
        #y_coord = 0.92
        #fig.text(0.1, y_coord, text, fontsize=12, color=OVERTEXT_COLOR, transform=fig.transFigure)
        fig.suptitle(text, fontsize=12)

    def table_1value(self,dat,n_row=20,n_col=3,
                     page_title="Chip configurations before scan"):
        keys=np.sort(np.array(dat.keys()))
        ##fill table
        cellText=[["" for i in range(n_col*2)] for j in range(n_row)]
        for i,k in enumerate(keys):
            cellText[i%20][i/20*2]=k
            cellText[i%20][i/20*2+1]=dat[k]
        colLabels=[]
        colWidths=[]
        for i in range(n_col):
            colLabels.append("Param")
            colWidths.append(0.15) ## width for param name
            colLabels.append("Value")
            colWidths.append(0.15) ## width for value
        fig = Figure()
        FigureCanvas(fig)
        ax = fig.add_subplot(111)
        fig.patch.set_visible(False)
        ax.set_adjustable('box')
        ax.axis('off')
        ax.axis('tight')

        tab=ax.table(cellText=cellText,
                 colLabels=colLabels,
                 colWidths = colWidths,
                 loc='upper center')
        tab.set_fontsize(10)
        for key, cell in tab.get_celld().items():
           cell.set_linewidth(0.1)
        if page_title is not None and len(page_title)>0:
            self._add_text(page_title,fig)
        tab.scale(1,0.5)
        
        self._save_plots(fig, suffix=None, tight=True)
                      
    def plot_2d_pixel_4(self, dat, page_title="Pixel configurations before scan",
                        title=["Preamp","Inj","Mon","TDAC"], 
                        x_axis_title="Column", y_axis_title="Row", z_axis_title="",
                        z_min=[0,0,0,0], z_max=[1,1,1,15]):
        fig = Figure()
        FigureCanvas(fig)
        for i in range(4):
            ax = fig.add_subplot(221+i)
            
            cmap = cm.get_cmap('plasma')
            cmap.set_bad('w')
            cmap.set_over('r')  # Make noisy pixels red
#            if z_max[i]+2-z_min[i] < 20:
#                bounds = np.linspace(start=z_min[i], stop=z_max[i] + 1,
#                                 num=z_max[i]+2-z_min[i],
#                                 endpoint=True)
#                norm = colors.BoundaryNorm(bounds, cmap.N)
#            else:
#                norm = colors.BoundaryNorm()

            im=ax.imshow(np.transpose(dat[i]),origin='lower',aspect="auto",
                     vmax=z_max[i]+1,vmin=z_min[i], interpolation='none',
                     cmap=cmap #, norm=norm
                     )
            ax.set_title(title[i])
            ax.set_ylim((-0.5, ROW_SIZE-0.5))
            ax.set_xlim((-0.5, COL_SIZE-0.5))

            divider = make_axes_locatable(ax)
            cax = divider.append_axes("right", size="5%", pad=0.1)
            cb = fig.colorbar(im, cax=cax)
            cb.set_label(z_axis_title)
        if page_title is not None and len(page_title)>0:
            self._add_text(page_title, fig)
        self._save_plots(fig)
        
    def plot_2d_pixel_hist(self, hist2d, page_title=None,
                           title="Hit Occupancy",
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
        #norm = colors.BoundaryNorm(bounds, cmap.N)

        im = ax.imshow(np.transpose(hist2d), interpolation='none', aspect='auto', 
                       vmax=z_max+1,vmin=z_min,
                       cmap=cmap, # norm=norm,
                       origin='lower')  # TODO: use pcolor or pcolormesh
        ax.set_ylim((-0.5, ROW_SIZE-0.5))
        ax.set_xlim((-0.5, COL_SIZE-0.5))
        ax.set_title(title + r' ($\Sigma$ = {0})'.format((0 if hist2d.all() is np.ma.masked else np.ma.sum(hist2d))), color=TITLE_COLOR)
        ax.set_xlabel(x_axis_title)
        ax.set_ylabel(y_axis_title)

        divider = make_axes_locatable(ax)

        cax = divider.append_axes("right", size="5%", pad=0.2)
        cb = fig.colorbar(im, cax=cax) #, ticks=np.linspace(start=z_min, stop=z_max, num=10, endpoint=True), orientation='horizontal')
        #cax.set_xticklabels([int(round(float(x.get_text().replace(u'\u2212', '-').encode('utf8')))) for x in cax.xaxis.get_majorticklabels()])
        cb.set_label(z_axis_title)
        if page_title is not None and len(page_title)>0:
            self._add_text(page_title,fig)
        self._save_plots(fig)
