
import logging
import numpy as np
import tables as tb
from scipy.optimize import curve_fit
from scipy.special import erf
import yaml


def cap_fac():
    return 7.9891

def analyze_threshold_scan(h5_file_name):
    pass

def scurve(x, A, mu, sigma):
    return 0.5 * A * erf((x - mu) / (np.sqrt(2) * sigma)) + 0.5 * A

def fit_scurve(scurve_data, scurve_indexes, repeat_command):  # data of some pixels to fit, has to be global for the multiprocessing module
    index = np.argmax(np.diff(scurve_data))
    max_occ = np.median(scurve_data[index:])
    threshold = scurve_indexes[index]
    if abs(max_occ) <= 1e-08:  # or index == 0: occupancy is zero or close to zero
        popt = [0, 0, 0]
    else:
        try:
            popt, _ = curve_fit(scurve, scurve_indexes, scurve_data, p0=[repeat_command, threshold, 0.01], check_finite=False) #0.01 vorher
            logging.debug('Fit-params-scurve: %s %s %s ', str(popt[0]),str(popt[1]),str(popt[2]))
        except RuntimeError:  # fit failed
            popt = [0, 0, 0]
            logging.info('Fit did not work scurve: %s %s %s', str(popt[0]),
                         str(popt[1]), str(popt[2]))

    if popt[1] < 0:  # threshold < 0 rarely happens if fit does not work
        popt = [0, 0, 0]
    return popt


def gauss(x_data, *parameters):
    """Gauss function"""
    A_gauss, mu_gauss, sigma_gauss = parameters
    return A_gauss*np.exp(-(x_data-mu_gauss)**2/(2.*sigma_gauss**2))

def fit_gauss(x_data, y_data):
    """Fit gauss"""
    x_data = np.array(x_data)
    y_data = np.array(y_data)
    y_maxima=x_data[np.where(y_data[:]==np.max(y_data))[0]]
    params_guess = np.array([np.max(y_data), y_maxima[0], np.std(x_data)]) # np.mean(y_data)
    logging.info('Params guessed: %s ', str(params_guess))
    try:
        params_from_fit = curve_fit(gauss, x_data, y_data, p0=params_guess)
        logging.info('Fit-params-gauss: %s %s %s ', str(params_from_fit[0][0]),str(params_from_fit[0][1]),str(params_from_fit[0][2]))
    except RuntimeError:
        logging.info('Fit did not work gauss: %s %s %s', str(np.max(y_data)), str(x_data[np.where(y_data[:] == np.max(y_data))[0]][0]), str(np.std(x_data)))
        return params_guess[0],params_guess[1],params_guess[2]
    A_fit = params_from_fit[0][0]
    mu_fit = params_from_fit[0][1]
    sigma_fit = np.abs(params_from_fit[0][2])
    return A_fit, mu_fit, sigma_fit

if __name__ == "__main__":
    pass
