import numpy as np
from matplotlib import pyplot as plt
from matplotlib import colors, cm
from scipy.optimize import curve_fit

def gauss(x, A, mu, sigma):
    return A * np.exp(-(x-mu)*(x-mu) / (2 * sigma * sigma))

def tick_function(X, Cinj):
    e = X * Cinj / 1.602
    return ["%.0f" % z for z in e]

def get1D_array(array, columns):
    thearray= np.zeros(shape=(0))
    for i in columns:
        for x in array[i]:
            thearray=np.append(thearray, x)
    return thearray

def plot_thresholdscanresults(file_path='/tmp/', inj_target_v=0, Cinj=2.75e4, columns=range(0,36), after=True, before=False, plotTrims=False):
    
    inj_Target_e = int(inj_target_v * Cinj / 1.602)
    
    # mus_Before = np.load("./mu_values_step0.npy")
    mus_After = np.load(file_path+"/mu_values.npy")
    
    # print mus_Before
    print mus_After
    
    #mus_Before1D = get1D_array(mus_Before, columns[0], columns[1]+1)
    mus_After1D = get1D_array(mus_After, columns)
    
    #print mus_Before1D
    print mus_After1D
    
    #sigma_Before = np.load("./sigma_values_step0.npy")
    sigma_After = np.load(file_path+"/sigma_values.npy")
    
    
    #sigma_Before1D = get1D_array(sigma_Before, columns[0], columns[1]+1)
    sigma_After1D = get1D_array(sigma_After, columns)
    
            
    fig = plt.figure()    
    ax1 = fig.add_subplot(111)
    ax1.set_xlim(0.0,1.0)
    ax2 = ax1.twiny()
    
    #hist, edges = np.histogram(mus_Before1D, bins=np.arange(0.0 - 0.025, 0.6 + 0.025, 0.005))
    #popt, _ = curve_fit(gauss, edges[:-1] + 0.0025, hist)
    #plt.xlim(0,0.6)
    #plt.hist(mus_Before1D[mus_Before1D>0], bins=np.arange(0.0 - 0.025, 0.6 + 0.025, 0.005), label="Before tuning")
    #plt.plot(np.arange(0, 0.6, 0.001), gauss(np.arange(0, 0.6, 0.001), *popt), label="Threshold before tuning\n$\mu$=%.4fV=%de\n$\sigma$=%.4fV=%de" %(popt[1], popt[1] * Cinj / 1.602, np.abs(popt[2]), np.abs(popt[2]) * 2.75e4 / 1.602))
    
    hist2, edges2 = np.histogram(mus_After1D, bins=np.arange(0.0 - 0.025, 1.0 + 0.025, 0.005))
    popt2, _ = curve_fit(gauss, edges2[:-1] + 0.0025, hist2)
    plt.hist(mus_After1D[mus_After1D>0], bins=np.arange(0.0 - 0.025, 1.0 + 0.025, 0.005), label="After tuning")
    plt.plot(np.arange(0.0, 1.0, 0.001), gauss(np.arange(0.0, 1.0, 0.001), *popt2), label="Threshold after tuning\n$\mu$=%.4fV=%de\n$\sigma$=%.4fV=%de" %(popt2[1], popt2[1] * Cinj / 1.602, np.abs(popt2[2]), np.abs(popt2[2]) * 2.75e4 / 1.602))
    
    
    
    ax1Ticks = ax1.get_xticks()   
    ax2Ticks = ax1Ticks
    ax2.set_xticks(ax2Ticks)
    ax2.set_xbound(ax1.get_xbound())
    ax2.set_xticklabels(tick_function(ax2Ticks,Cinj=Cinj))
    ax2.grid(True)
    
    ax1.set_xlabel("Injection voltage [V]") 
    ax2.set_xlabel('Charge [e-]')
    
    #plt.xlabel("Injection voltage")
    ax1.set_ylabel("Number of Pixels")
    title=plt.title("Columns "+str(columns[0])+'-'+str(columns[0])+'. Tuning target: '+str(inj_target_v)+'V = '+str(inj_Target_e)+" e-.")
    title.set_y(1.2)
    fig.subplots_adjust(top=0.8)
    
    plt.legend(loc=0)
    
    plt.savefig(file_path+'/tuning_results.pdf')
    plt.savefig(file_path+'/tuning_results.png', dpi=600)
    plt.clf()
    #plt.show()


    fig = plt.figure()    
    ax1 = fig.add_subplot(111)  
    ax1.set_xlim(0,0.04)  
    ax2 = ax1.twiny()
    
    #hist, edges = np.histogram(sigma_Before1D, bins=np.arange(0.0 - 0.0025, 0.6 + 0.0025, 0.0005))
    #popt, _ = curve_fit(gauss, edges[:-1] + 0.00025, hist)
    #plt.hist(sigma_Before1D[sigma_Before1D>0], bins=np.arange(0.0 - 0.0025, 0.6 + 0.0025, 0.0005), label="Before tuning")
    #plt.plot(np.arange(0, 0.6, 0.0005),gauss(np.arange(0, 0.6, 0.0005), *popt),label="ENC before tuning\n$\mu$=%.4fV=%de\n$\sigma$=%.4fV=%de" %(popt[1], popt[1] * Cinj / 1.602, np.abs(popt[2]), np.abs(popt[2]) * 2.75e4 / 1.602))
    
    hist2, edges2 = np.histogram(sigma_After1D, bins=np.arange(0.0 - 0.0025, 1.0 + 0.0025, 0.0005))
    popt2, _ = curve_fit(gauss, edges2[:-1] + 0.00025, hist2)
    plt.hist(sigma_After1D[sigma_After1D>0], bins=np.arange(0.0 - 0.0025, 1.0 + 0.0025, 0.0005), label="After tuning")
    plt.plot(np.arange(0, 1.0, 0.0005),gauss(np.arange(0, 1.0, 0.0005), *popt2),label="ENC after tuning\n$\mu$=%.4fV=%de\n$\sigma$=%.4fV=%de" %(popt2[1], popt2[1] * Cinj / 1.602, np.abs(popt2[2]), np.abs(popt2[2]) * 2.75e4 / 1.602))
    
    
    ax1Ticks = ax1.get_xticks()   
    ax2Ticks = ax1Ticks
    ax2.set_xticks(ax2Ticks)
    ax2.set_xbound(ax1.get_xbound())
    ax2.set_xticklabels(tick_function(ax2Ticks, Cinj=Cinj))
    ax2.grid(True)
    
    ax1.set_xlabel("ENC [V]") 
    ax2.set_xlabel('Charge [e-]')
    
    #plt.xlabel("Injection voltage")
    ax1.set_ylabel("Number of Pixels")
    title=plt.title("Columns "+str(columns[0])+'-'+str(columns[0])+'. Tuning target: '+str(inj_target_v)+'V = '+str(inj_Target_e)+" e-.")
    title.set_y(1.2)
    fig.subplots_adjust(top=0.8)
    
    plt.legend(loc=0)
    
    
    plt.savefig(file_path+'/ENC_results.pdf')
    plt.savefig(file_path+'/ENC_results.png', dpi=600)
    plt.clf()
    #plt.show()
    
    
    if plotTrims==True: 
        trims_After = np.load(file_path+"/trim_values_step4.npy")
        tras=trims_After.transpose()
        bounds = np.linspace(start=0, stop=16, num=17, endpoint=True)
        cmap = cm.get_cmap('viridis')
        norm = colors.BoundaryNorm(bounds, cmap.N)
        cmap.set_bad('black', 0.0)
        plt.xlabel('X [Pixels]', {'fontsize':20})
        plt.ylabel('Y [Pixels]', {'fontsize':20})
        plt.xlim(35.5,-0.5)
        plt.ylim(128.5,0-0.25)
        plt.imshow(tras, cmap=cmap, norm=norm, interpolation='nearest', aspect=0.2)    
        plt.colorbar()
        plt.title("Cols"+str(columns[0])+'-'+str(columns[0])+"_TRIM")
        plt.savefig(file_path+'/trim_map.pdf')
        plt.savefig(file_path+'/trim_map.png', dpi=600)
        plt.clf()  
        #plt.show()
    
    """tras=mus_Before.transpose()
    bounds = np.linspace(start=0, stop=0.5, num=50, endpoint=True)
    cmap = cm.get_cmap('viridis')
    norm = colors.BoundaryNorm(bounds, cmap.N)
    cmap.set_bad('black', 0.0)
    plt.xlabel('X [Pixels]', {'fontsize':20})
    plt.ylabel('Y [Pixels]', {'fontsize':20})
    plt.xlim(35.5,-0.5)
    plt.ylim(128.5,0-0.25)
    plt.imshow(tras, cmap=cmap, interpolation='nearest', aspect=0.2, norm=norm)  
    plt.colorbar()
    plt.title("Cols"+str(columns[0])+'-'+str(columns[1])+"_ScurveEdges Before Tuning")
    plt.savefig('./mubefore_map.pdf')
    plt.savefig('./mubefore_map.png', dpi=600)  
    plt.show()"""
    
    tras=mus_After.transpose()
    bounds = np.linspace(start=0, stop=0.6, num=50, endpoint=True)
    cmap = cm.get_cmap('viridis')
    norm = colors.BoundaryNorm(bounds, cmap.N)
    cmap.set_bad('black', 0.0)
    plt.xlabel('X [Pixels]', {'fontsize':20})
    plt.ylabel('Y [Pixels]', {'fontsize':20})
    plt.xlim(35.5,-0.5)
    plt.ylim(128.5,0-0.25)
    plt.imshow(tras, cmap=cmap, interpolation='nearest', aspect=0.2, norm=norm)  
    plt.colorbar()
    plt.title("Cols"+str(columns[0])+'-'+str(columns[0])+"_ScurveEdges")
    plt.savefig(file_path+'/mu_map.pdf')
    plt.savefig(file_path+'/mu_map.png', dpi=600)  
    plt.clf()
    #plt.show()
    
    """tras=sigma_After.transpose()
    bounds = np.linspace(start=0, stop=0.02, num=50, endpoint=True)
    cmap = cm.get_cmap('viridis')
    norm = colors.BoundaryNorm(bounds, cmap.N)
    cmap.set_bad('black', 0.0)
    plt.xlabel('X [Pixels]', {'fontsize':20})
    plt.ylabel('Y [Pixels]', {'fontsize':20})
    plt.xlim(35.5,-0.5)
    plt.ylim(128.5,0-0.25)
    plt.imshow(tras, cmap=cmap, interpolation='nearest', aspect=0.2, norm=norm)    
    plt.colorbar()
    plt.title("Cols"+str(columns[0])+'-'+str(columns[1])+"_ScurveSigmas")
    plt.savefig('./sigma_map.pdf')
    plt.savefig('./sigma_map.png', dpi=600)  
    plt.show()
    
    
    tras=sigma_Before.transpose()
    bounds = np.linspace(start=0, stop=0.02, num=50, endpoint=True)
    cmap = cm.get_cmap('viridis')
    norm = colors.BoundaryNorm(bounds, cmap.N)
    cmap.set_bad('black', 0.0)
    plt.xlabel('X [Pixels]', {'fontsize':20})
    plt.ylabel('Y [Pixels]', {'fontsize':20})
    plt.xlim(35.5,-0.5)
    plt.ylim(128.5,0-0.25)
    plt.imshow(tras, cmap=cmap, interpolation='nearest', aspect=0.2, norm=norm)    
    plt.colorbar()
    plt.title("Cols"+str(columns[0])+'-'+str(columns[1])+"_ScurveSigmas Before Tuning")
    plt.savefig('./sigmabefore_map.pdf')
    plt.savefig('./sigmabefore_map.png', dpi=600)  
    plt.show()"""

