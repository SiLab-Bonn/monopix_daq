import numpy as np
#import matplotlib.pyplot as plt
from scipy.special import erf
from scipy.optimize import curve_fit, leastsq

def scurve(x, A, mu, sigma):
    return 0.5*A*erf((x-mu)/(np.sqrt(2)*sigma))+0.5*A

def scurve_rev(x, A, mu, sigma):
    return 0.5*A*erf((mu-x)/(np.sqrt(2)*sigma))+0.5*A

def fit_scurve(xarray,yarray,A=None,cut_ratio=0.05,reverse=True,debug=0):
    if reverse==True:
        arg=np.argsort(xarray)[::-1]
    else:
        arg=np.argsort(xarray)
    yarray=yarray[arg]
    xarray=xarray[arg]
    if debug==1:
        plt.plot(xarray,yarray,".")
    ### estimate
    if A==None:
        A=np.max(yarray)
    mu=xarray[np.argmin(np.abs(yarray-A*0.5))]
    try:
        sig2=xarray[np.argwhere(yarray>A*cut_ratio)[0]][0]
        sig1=xarray[np.argwhere(yarray>A*(1-cut_ratio))[0]][0]
        sigma=abs(sig1-sig2)/3.5
    except:
        sigma=1
    if debug==1:
        print "estimation",A,mu,sigma
    #### cut
    cut_high=np.argwhere(yarray>=A*(1+cut_ratio))
    cut_low=np.argwhere(yarray>=A*(1-cut_ratio))
    if len(cut_high)>0:
        cut=cut_high[0]
    else:
        cut=len(yarray)
    if len(cut_low)>0:
        cut=min(cut,cut_low[-1])
    yarray=yarray[:cut]
    xarray=xarray[:cut]
    #if debug==1:
    #    plt.plot(xarray,yarray,"o")
    #    plt.plot(xarray,scurve_rev(xarray,A,mu,sigma),"--")
    try:
        if reverse:
            p,cov = curve_fit(scurve_rev, xarray, yarray, p0=[A,mu,sigma])
        else:
            p,cov = curve_fit(scurve, xarray, yarray, p0=[A,mu,sigma])
    except RuntimeError:
        if debug==2:
            print('fit did not work')
        return A,mu,sigma,float("nan"),float("nan"),float("nan")
    err=np.sqrt(np.diag(cov))
    return p[0],p[1],p[2],err[0],err[1],err[2]
    
def scurve_from_fit1(th,A_fit,mu_fit,sigma_fit,reverse=True):
    sort_th=th[np.argsort(th)]
    if reverse:
        return sort_th,scurve_rev(sort_th,A_fit,mu_fit,sigma_fit)
    else:
        return sort_th,scurve(sort_th,A_fit,mu_fit,sigma_fit)