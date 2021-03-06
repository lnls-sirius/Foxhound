import os.path
import pandas as pd
import numpy as np
import scipy
import scipy.signal as sig
import scipy.interpolate as inter

"""
This module encapsulates functions related to correlation, causation and data formatting
"""

b = 1.5
c = 4
q1 = 1.540793
q2 = 0.8622731

z = lambda x: (x-x.mean())/np.std(x, ddof=1)
g = lambda x: x if abs(x) <= b else q1*np.tanh(q2*(c-abs(x)))*np.sign(x) if abs(x) <= c else 0

def correlate(x, y, margin, method='pearson'):
    """ Find delay and correlation between x and each column o y

    Parameters
    ----------
    x : `pandas.Series`
        Main signal
    y : `pandas.DataFrame`
        Secondary signals
    method : `str`, optional
        Correlation method. Defaults to `pearson`. Options: `pearson`,`robust`,`kendall`,`spearman`

    Returns
    -------
    `(List[float], List[int])`
        List of correlation coefficients and delays in samples in the same order as y's columns

    Notes
    -----
    Uses the pandas method corrwith (which can return pearson, kendall or spearman coefficients) to correlate. If robust
    correlation is used, the mapping presented in [1]_ is used and then Pearson correlation is used. To speedup the lag finding,
    the delays are calculated in log intervals and then interpolated by splines, as shown in [2]_, and the lag with maximum correlation
    found in this interpolated function is then used as the delay.

    References
    ----------
        .. [1] Raymaekers, J., Rousseeuw, P. "Fast Robust Correlation for High-Dimensional Data", Technometrics, vol. 63, Pages 184-198, 2021
        .. [2] Sakurai, Yasushi & Papadimitriou, Spiros & Faloutsos, Christos. (2005). BRAID: Stream mining through group lag correlations. Proceedings of the ACM SIGMOD International Conference on Management of Data. 599-610.


    """
    beg, end = (x.index.min(), x.index.max())
    y = interpolate(y,x.index,margin)
    
    if(method == 'robust'):
        method='pearson'
        x = pd.Series(z(sig.detrend(x)), index=x.index, name=x.name)
        x = x.apply(g)
        y = y.apply(lambda s: z(sig.detrend(s))).applymap(g)

    N = int(x.size*margin)

    l = int(np.log2(N))
    b = 4
    log_lags = np.array([int(2**i+(j*2**i/b)) for i in range(2,l+1) for j in range(4) if 2**i+(j*2**i/b) < N])
    log_lags = list(-1*log_lags)[::-1]+[-3,-2,-1,0,1,2,3]+list(log_lags)

    new_lags = list(range(-1*max(log_lags),max(log_lags)+1))

    vals = pd.DataFrame([lagged_corr(x,y,lag,method) for lag in log_lags])
    vals = vals.apply(lambda s: inter.make_interp_spline(log_lags, abs(s),k=3)(new_lags))
    peaks = vals.apply(lambda s: pd.Series([new_lags[i] for i in sig.find_peaks(s)[0]]+[new_lags[max(range(len(s)), key=s.__getitem__)]]).drop_duplicates())

    peak_corr = pd.DataFrame(np.array([[x.corr((y[col].shift(int(peak)))[beg:end], method=method) if not pd.isna(peak) else 0 for peak in peaks[col]] for col in peaks]).transpose(), columns=y.columns) 

    dela = [peak_corr[col].abs().idxmax() for col in peak_corr]
    delays = [int(peaks[col].iloc[dela[pos]]) for pos, col in enumerate(peak_corr)]
    corrs = [round(peak_corr[col].iloc[dela[pos]],2) for pos, col in enumerate(peak_corr)]
    
    return corrs, delays

def lagged_corr(x, y, lag, method='pearson'):
    """ Find correlation between x and each column o y for a specific time lag

    Parameters
    ----------
    x : `pandas.Series`
        Main signal
    y : `pandas.DataFrame`
        Secondary signals
    lag : `int`
        Number of samples to apply as lag before computing the correlation
    method : `str`, optional
        Correlation method. Defaults to `pearson`. Options: `pearson`,`kendall`,`spearman`

    Returns
    -------
    `pandas.DataFrame`
        Dataframe with the correlation value for each column of y


    """
    if(method in ['pearson', 'kendall', 'spearman']):
        return (y.shift(lag)[x.index[0]:x.index[-1]]).corrwith(x, method=method)
    else:
        return None

def find_delays(x, y):
    """ Find delay between x and each column o y

    Parameters
    ----------
    x : `pandas.Series`
        Main signal
    y : `pandas.DataFrame`
        Secondary signals

    Returns
    -------
    `pandas.DataFrame`
        Dataframe with the delay value for each column of y


    """
    return y.apply(lambda k: sig.correlate(k,x,mode='valid')).apply(lambda k: k.abs().idxmax()-int(len(k/2))+1)

def interpolate(x, idx, margin):
    """ Interpolate data to match idx+-margin

    Parameters
    ----------
    x : `pandas.Dataframe`
        Signal
    idx : `pandas.DatetimeIndex`
        Index to match
    margin : `float`
        Percentage of values to add to each side of index

    Returns
    -------
        `pandas.DataFrame`
            Dataframe with the same columns as x interpolated to match idx+-margin

    Notes
    -----
    It infers the frequency for the given DatetimeIndex and extends it to margin times prior
    and after. This new DatetimeIndex is then combined with the given DataFrame and the NaN
    values are completed with linear interpolation then. In the end, only the new index values
    are kept, so that it matches exactly the given idx dates (except for the margin values).


    """
    fs = pd.infer_freq(idx)
    T  = int(len(idx)*margin)
    prev = pd.date_range(end=idx.min(),freq=fs, periods=T).union(idx)
    post = pd.date_range(start=idx.max(),freq=fs, periods=T).union(prev)

    new_x = x.reindex(x.index.union(post))
    return new_x.interpolate(method='linear').loc[post]
