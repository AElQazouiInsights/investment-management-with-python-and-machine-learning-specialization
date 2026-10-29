import json

import pandas as pd
import numpy as np
import scipy.stats
import matplotlib.pyplot as plt
import statsmodels.api as sm
from scipy.optimize import minimize
from numpy.linalg import inv


# ---------------------------------------------------------------------------------
# Load and format data files
# ---------------------------------------------------------------------------------
def path_to_data_folder():
    return "/assets/data/"


def get_ffme_returns():
    """
    Load the bundled Kenneth French equally weighted size-portfolio returns.
    Select Lo 10 (small caps) and Hi 10 (large caps), convert percentages to
    decimal returns, and index observations by monthly periods.
    """
    filepath = path_to_data_folder() + "/Portfolios_Formed_on_ME_monthly_EW.csv"
    rets = pd.read_csv(filepath, index_col=0, na_values=[-99.99, -999])
    rets = rets[["Lo 10", "Hi 10"]] / 100
    rets.index = pd.to_datetime(rets.index.astype(str), format="%Y%m").to_period("M")
    return rets


def get_hfi_returns():
    """
    Load bundled monthly hedge-fund index returns as decimals.
    The CSV uses day/month/year dates and percentage returns.
    """
    filepath = path_to_data_folder() + "/edhec-hedgefundindices.csv"
    hfi = pd.read_csv(filepath, index_col=0, na_values=[-99.99, -999]) / 100.0
    hfi.index = pd.to_datetime(hfi.index, format="%d/%m/%Y")
    return hfi

def get_stock_dynamic():
    """
    Load the bundled daily Close-price snapshot in its original price units.
    Keep each timestamp's local trading date; this is not a live download.
    """
    filepath = path_to_data_folder() + "/stocks_dynamic.csv"
    stocks = pd.read_csv(filepath, index_col=0, na_values=[-99.99, -999])
    stocks.index = pd.to_datetime(stocks.index.astype(str).str[:10], format="%Y-%m-%d")
    if stocks.empty or not stocks.index.is_unique or not stocks.index.is_monotonic_increasing:
        raise ValueError("Expected a nonempty, chronologically ordered price history with unique dates")
    if not np.isfinite(stocks.to_numpy()).all() or (stocks <= 0).any().any():
        raise ValueError("Stock prices must be positive, finite, and complete before computing returns")
    return stocks

def get_brka_rets(monthly=False):
    """Load bundled daily BRKA decimal returns; optionally compound by month.

    Require complete finite observations and unique ordered dates. Monthly
    aggregation does not fill absent trading days or manufacture empty months.
    The CSV alone does not document price-adjustment or publication history.
    """
    filepath = path_to_data_folder() + "/brka_d_ret.csv"
    rets = pd.read_csv(filepath, index_col=0, parse_dates=True)
    if (rets.empty or not isinstance(rets.index, pd.DatetimeIndex)
            or rets.index.hasnans or not rets.index.is_unique or not rets.index.is_monotonic_increasing):
        raise ValueError("Expected a nonempty Berkshire history with unique ordered dates")
    if not np.isfinite(rets.to_numpy()).all() or (rets < -1).any().any():
        raise ValueError("Berkshire observations must be complete finite simple returns of at least -1")
    if monthly:
        months = rets.index.to_period("M")
        if not months.unique().equals(pd.period_range(months[0], months[-1], freq="M")):
            raise ValueError("Cannot aggregate a history with missing calendar months")
        rets = rets.groupby(months).agg(compound)
    return rets


def get_fff_returns():
    """
    Load the Fama-French Research Factors Monthly Dataset.
    Factors returned are those of the Fama-French model:
    - Excess return of the market, i.e., Market minus Risk-Free Rate,
    - Small (size) Minus Big (size) SMB,
    - High (B/P ratio) Minus Low (B/P ratio) HML,
    - and the Risk Free Rate
    """
    filepath = path_to_data_folder() + "/F-F_Research_Data_Factors_m.csv"
    fff = pd.read_csv(filepath, index_col=0, na_values=[-99.99, -999]) / 100
    fff.index = pd.to_datetime(fff.index.astype(str), format="%Y%m").to_period("M")
    if fff.empty or not fff.index.is_unique or not fff.index.is_monotonic_increasing:
        raise ValueError("Expected factors with unique ordered monthly dates")
    return fff


def get_ind_file(filetype="rets", nind=30, ew=False):
    """
    Load and format the Kenneth French Industry Portfolios files.
    - filetype: can be "rets", "nfirms", "size"
    - nind: can be 30 or 49
    - ew: if True, equally weighted portfolio dataset are loaded.
      Also, it has a role only when filetype="rets".
    """
    if nind != 30 and nind != 49:
        raise ValueError("Expected either 30 or 49 number of industries")
    if filetype == "rets":
        portfolio_w = "ew" if ew == True else "vw"
        name = "{}_rets".format(portfolio_w)
        divisor = 100.0
    elif filetype == "nfirms":
        name = "nfirms"
        divisor = 1
    elif filetype == "size":
        name = "size"
        divisor = 1
    else:
        raise ValueError("filetype must be one of: rets, nfirms, size")

    filepath = path_to_data_folder() + f"/ind{nind}_m_{name}.csv"
    ind = pd.read_csv(filepath, index_col=0, na_values=[-99.99, -999]) / divisor
    ind.index = pd.to_datetime(ind.index.astype(str), format="%Y%m").to_period("M")
    ind.columns = ind.columns.str.strip()
    if ind.empty or not ind.index.is_unique or not ind.index.is_monotonic_increasing:
        raise ValueError("Expected a nonempty industry history with unique, ordered monthly dates")

    return ind


def get_ind_market_caps(nind=30, weights=False):
    """Implied industry capitalization: firm count times average firm size.

    With weights=True return same-row fractions summing to one, not percent
    numbers or lagged investment weights. Require complete aligned metadata.
    """
    ind_nfirms = get_ind_file(filetype="nfirms", nind=nind)
    ind_size = get_ind_file(filetype="size", nind=nind)
    if not ind_nfirms.index.equals(ind_size.index) or not ind_nfirms.columns.equals(ind_size.columns):
        raise ValueError("Firm counts and sizes must have identical dates and industry order")
    for frame in (ind_nfirms, ind_size):
        if not np.isfinite(frame.to_numpy()).all() or (frame.to_numpy() < 0).any():
            raise ValueError("Capitalization metadata must be complete, finite, and nonnegative")
    ind_caps = ind_nfirms * ind_size
    total_cap = ind_caps.sum(axis=1)
    if not np.isfinite(ind_caps.to_numpy()).all() or not np.isfinite(total_cap).all() or (total_cap <= 0).any():
        raise ValueError("Each month must have positive finite total capitalization")
    return ind_caps.div(total_cap, axis=0) if weights else ind_caps


def get_total_market_index_returns(nind=30):
    """One-month-lagged industry-market proxy, not an official market index.

    Weight each month's value-weighted industry returns using the preceding
    month's implied capitalization. Drop only the first month, which lacks
    prior weights. Lag before selecting a backtest window. The bundled files
    do not establish point-in-time publication availability of the metadata.
    """
    ind_rets = get_ind_file(filetype="rets", nind=nind)
    weights = get_ind_market_caps(nind=nind, weights=True)
    if not ind_rets.index.equals(weights.index) or not ind_rets.columns.equals(weights.columns):
        raise ValueError("Returns and capitalization weights must have identical dates and industry order")
    if len(ind_rets) < 2 or not isinstance(ind_rets.index, pd.PeriodIndex) or ind_rets.index.freqstr != "M":
        raise ValueError("The market proxy requires at least two monthly observations")
    if not ind_rets.index.equals(pd.period_range(ind_rets.index[0], ind_rets.index[-1], freq="M")):
        raise ValueError("Monthly observations must be consecutive before lagging weights")
    if not np.isfinite(ind_rets.to_numpy()).all() or (ind_rets.to_numpy() < -1).any():
        raise ValueError("Industry returns must be complete, finite simple returns of at least -1")
    return (weights.shift(1) * ind_rets).sum(axis=1, min_count=ind_rets.shape[1]).iloc[1:]


def get_total_market_index(nind=30, capital=1000):
    """
    Return the cap-weighted total market index from Kenneth French Industry portfolios
    """
    total_market_return = get_total_market_index_returns(nind=nind)
    total_market_index = capital * (1 + total_market_return).cumprod()
    return total_market_index


# ---------------------------------------------------------------------------------
# Return Analysis and general statistics
# ---------------------------------------------------------------------------------
def terminal_wealth(s):
    """
    Computes the terminal wealth of a sequence of return, which is, in other words,
    the final compounded return.
    The input s is expected to be either a pd.DataFrame or a pd.Series
    """
    if not isinstance(s, (pd.DataFrame, pd.Series)):
        raise ValueError("Expected either a pd.DataFrame or pd.Series")
    return (1 + s).prod()


def compound(s):
    """
    Single compound rule for a pd.Dataframe or pd.Series of returns.
    The method returns a single number - using prod().
    See also the TERMINAL_WEALTH method.
    """
    if not isinstance(s, (pd.DataFrame, pd.Series)):
        raise ValueError("Expected either a pd.DataFrame or pd.Series")
    return (1 + s).prod() - 1
    # Note that this is equivalent to (but slower than)
    # return np.expm1( np.logp1(s).sum() )


def compound_returns(s, start=100):
    """
    Compound a pd.Dataframe or pd.Series of returns from an initial default value equal to 100.
    In the former case, the method compounds the returns for every column (Series) by using pd.aggregate.
    The method returns a pd.Dataframe or pd.Series - using cumprod().
    See also the COMPOUND method.
    """
    if isinstance(s, pd.DataFrame):
        return s.aggregate(compound_returns, start=start)
    elif isinstance(s, pd.Series):
        return start * (1 + s).cumprod()
    else:
        raise TypeError("Expected pd.DataFrame or pd.Series")


def compute_returns(s):
    """
    Computes the returns (percentage change) of a Dataframe of Series.
    In the former case, it computes the returns for every column (Series) by using pd.aggregate
    """
    if isinstance(s, pd.DataFrame):
        return s.aggregate(compute_returns)
    elif isinstance(s, pd.Series):
        return s / s.shift(1) - 1
    else:
        raise TypeError("Expected pd.DataFrame or pd.Series")


def compute_logreturns(s):
    """
    Computes the log-returns of a Dataframe of Series.
    In the former case, it computes the returns for every column (Series) by using pd.aggregate
    """
    if isinstance(s, pd.DataFrame):
        return s.aggregate(compute_logreturns)
    elif isinstance(s, pd.Series):
        return np.log(s / s.shift(1))
    else:
        raise TypeError("Expected pd.DataFrame or pd.Series")


def drawdown(rets: pd.Series, start=1000):
    """
    Compute wealth, running peaks, and signed drawdowns for ordered returns.
    The high-water mark includes positive initial capital, so a first-period
    loss is a drawdown. Keep the input index and end-of-period observations;
    maximum drawdown as a positive magnitude is -result["Drawdown"].min().
    """
    if not isinstance(rets, pd.Series):
        raise TypeError("Expected pd.Series of returns")
    if not np.isfinite(start) or start <= 0:
        raise ValueError("start must be positive and finite")
    wealth_index = compound_returns(rets, start=start)
    previous_peaks = wealth_index.cummax().clip(lower=start)
    drawdowns = (wealth_index - previous_peaks) / previous_peaks
    df = pd.DataFrame(
        {"Wealth": wealth_index, "Peaks": previous_peaks, "Drawdown": drawdowns}
    )
    return df


def skewness(s):
    """
    Estimate skewness as m3 / m2**1.5 using moments with denominator n.
    Process DataFrame columns separately and omit missing observations.
    Constant, insufficient, or non-finite data have undefined moments (np.nan).
    """
    if isinstance(s, pd.DataFrame):
        return s.aggregate(skewness)
    observed = pd.Series(s, dtype=float).dropna()
    if len(observed) < 2 or observed.nunique() == 1 or not np.isfinite(observed).all():
        return np.nan
    scale = observed.std(ddof=0)
    if not np.isfinite(scale) or scale <= 0:
        return np.nan
    return (((observed - observed.mean()) / scale) ** 3).mean()


def kurtosis(s):
    """
    Estimate Pearson kurtosis as m4 / m2**2 (Gaussian population value 3).
    Use moments with denominator n, omitting missing observations per column.
    Match scipy.stats.kurtosis with fisher=False and bias=True on observed data.
    Constant, insufficient, or non-finite data return np.nan.
    """
    if isinstance(s, pd.DataFrame):
        return s.aggregate(kurtosis)
    observed = pd.Series(s, dtype=float).dropna()
    if len(observed) < 2 or observed.nunique() == 1 or not np.isfinite(observed).all():
        return np.nan
    scale = observed.std(ddof=0)
    if not np.isfinite(scale) or scale <= 0:
        return np.nan
    return (((observed - observed.mean()) / scale) ** 4).mean()


def exkurtosis(s):
    """
    Returns the Excess Kurtosis, i.e., Kurtosis minus 3
    """
    return kurtosis(s) - 3


def is_normal(s, level=0.01):
    """
    Return whether Jarque-Bera does not reject normality (p-value >= level).
    True is not proof of a Gaussian distribution. The test uses asymptotic
    calibration under iid normal sampling. Test DataFrame columns separately,
    omitting missing observations. Return np.nan for fewer than two observed
    values, constant/non-finite data, or an unavailable test result.
    """
    if not np.isfinite(level) or not 0 < level < 1:
        raise ValueError("level must be between 0 and 1")
    if isinstance(s, pd.DataFrame):
        return s.aggregate(is_normal, level=level)
    observed = pd.Series(s, dtype=float).dropna()
    if len(observed) < 2 or observed.nunique() == 1 or not np.isfinite(observed).all():
        return np.nan
    _, pvalue = scipy.stats.jarque_bera(observed)
    if not np.isfinite(pvalue):
        return np.nan
    return bool(pvalue >= level)


def semivolatility(s):
    """
    Return std(ddof=0) within the negative-return subset, not target deviation.
    Omit missing observations per column. No negative observations give np.nan;
    identical negative observations have zero conditional dispersion.
    """
    if isinstance(s, pd.DataFrame):
        return s.aggregate(semivolatility)
    observed = pd.Series(s, dtype=float).dropna()
    if not np.isfinite(observed).all():
        return np.nan
    negative = observed[observed < 0]
    if negative.empty:
        return np.nan
    if negative.nunique() == 1:
        return 0.0
    return negative.std(ddof=0)


def var_historic(s, level=0.05):
    """
    Estimate VaR as the negative linear-interpolated return quantile.
    level is the lower-tail probability (0.05 means 95% confidence). Output
    is a signed loss fraction at the input return horizon. Omit missing values
    per column; empty or non-finite observed samples return np.nan.
    """
    if not np.isfinite(level) or not 0 < level < 1:
        raise ValueError("level must be between 0 and 1")
    if isinstance(s, pd.DataFrame):
        return s.aggregate(var_historic, level=level)
    elif isinstance(s, pd.Series):
        observed = s.dropna()
        if observed.empty or not np.isfinite(observed).all():
            return np.nan
        return -np.percentile(observed, level * 100, method="linear")
    else:
        raise TypeError("Expected pd.DataFrame or pd.Series")


def var_gaussian(s, level=0.05, cf=False):
    """
    Estimate Gaussian or Cornish-Fisher VaR as a signed loss fraction.
    level is the lower-tail probability (0.05 means 95% confidence). Use the
    observed mean and std(ddof=0), omitting missing values per column. The
    optional Cornish-Fisher correction is an approximation, not a guarantee
    of valid tail quantiles. A constant sample is treated as a point mass.
    """
    if not np.isfinite(level) or not 0 < level < 1:
        raise ValueError("level must be between 0 and 1")
    if isinstance(s, pd.DataFrame):
        return s.aggregate(var_gaussian, level=level, cf=cf)
    if not isinstance(s, pd.Series):
        raise TypeError("Expected pd.DataFrame or pd.Series")
    observed = s.dropna()
    if observed.empty or not np.isfinite(observed).all():
        return np.nan
    mean = observed.mean()
    volatility = observed.std(ddof=0)
    if observed.nunique() == 1 or volatility == 0:
        return -mean
    if not np.isfinite(volatility):
        return np.nan
    za = scipy.stats.norm.ppf(level, 0, 1)
    if cf:
        S = skewness(observed)
        K = kurtosis(observed)
        za = (
            za
            + (za**2 - 1) * S / 6
            + (za**3 - 3 * za) * (K - 3) / 24
            - (2 * za**3 - 5 * za) * (S**2) / 36
        )
    return -(mean + za * volatility)


def cvar_historic(s, level=0.05):
    """
    Estimate empirical expected shortfall (CVaR) as a signed loss fraction.
    Average exactly the worst level*n observations under equal empirical
    probabilities, fractionally weighting the boundary observation. This
    integrates the empirical tail rather than conditioning on the separately
    interpolated historical VaR. Omit missing values per column; empty or
    non-finite observed samples return np.nan.
    """
    if not np.isfinite(level) or not 0 < level < 1:
        raise ValueError("level must be between 0 and 1")
    if isinstance(s, pd.DataFrame):
        return s.aggregate(cvar_historic, level=level)
    elif isinstance(s, pd.Series):
        observed = s.dropna()
        if observed.empty or not np.isfinite(observed).all():
            return np.nan
        ordered = np.sort(observed.to_numpy(dtype=float))
        tail_mass = level * len(ordered)
        weights = np.clip(tail_mass - np.arange(len(ordered)), 0, 1)
        return -np.dot(weights, ordered) / tail_mass
    else:
        raise TypeError("Expected pd.DataFrame or pd.Series")


def annualize_rets(s, periods_per_year):
    """
    Compute annualized geometric growth from equally spaced simple returns.
    periods_per_year is the observation frequency (e.g., 12, 52, or 252),
    not the sample length. Non-missing returns are counted per Series or
    DataFrame column; an empty or entirely missing Series returns np.nan.
    Missing calendar periods must be resolved by the caller: this function
    measures growth over observed periods and does not infer elapsed time.
    Observed returns must be finite and at least -1. Compute in log space to
    avoid overflowing or underflowing the intermediate terminal-wealth product.
    """
    if not np.isfinite(periods_per_year) or periods_per_year <= 0:
        raise ValueError("periods_per_year must be positive and finite")
    if isinstance(s, pd.DataFrame):
        return s.aggregate(annualize_rets, periods_per_year=periods_per_year)
    elif isinstance(s, pd.Series):
        observed = s.dropna()
        if observed.empty:
            return np.nan
        if not np.isfinite(observed).all() or (observed < -1).any():
            raise ValueError("Expected finite simple returns of at least -1")
        if (observed == -1).any():
            return -1.0
        return np.expm1(np.log1p(observed).mean() * periods_per_year)
    else:
        raise TypeError("Expected pd.DataFrame or pd.Series")


def annualize_vol(s, periods_per_year, ddof=1):
    """
    Computes the volatility per year, or, annualized volatility.
    The variable periods_per_year can be, e.g., 12, 52, 252, in
    case of monthly, weekly, and daily data.
    The method takes in input either a DataFrame, a Series, a list or a single number.
    In the former case, it computes the annualized volatility of every column
    (Series) by using pd.aggregate. In the latter case, s is a volatility
    computed beforehand, hence only annulization is done
    ddof controls the standard-deviation denominator for return samples and
    is applied consistently to each DataFrame column. Square-root-of-time
    scaling assumes constant period variance and zero serial covariances.
    """
    if not np.isfinite(periods_per_year) or periods_per_year <= 0:
        raise ValueError("periods_per_year must be positive and finite")
    if isinstance(s, pd.DataFrame):
        return s.aggregate(annualize_vol, periods_per_year=periods_per_year, ddof=ddof)
    elif isinstance(s, pd.Series):
        return s.std(ddof=ddof) * (periods_per_year) ** (0.5)
    elif isinstance(s, list):
        return np.std(s, ddof=ddof) * (periods_per_year) ** (0.5)
    elif isinstance(s, (int, float)):
        return s * (periods_per_year) ** (0.5)


def sharpe_ratio(s, risk_free_rate, periods_per_year, v=None):
    """
    Compute a conventional annualized arithmetic-mean Sharpe ratio.
    For return Series/DataFrames, risk_free_rate is a constant effective
    annual rate, converted to the observation period before subtraction.
    Use the sample standard deviation of excess returns and sqrt(p) scaling;
    missing returns are excluded per column. Fewer than two observations or
    identical observed returns give np.nan rather than an undefined ratio.
    For scalar inputs, retain (s - risk_free_rate) / v: both return inputs
    must already be on the same annual basis and v is annual volatility.
    """
    if not np.isfinite(periods_per_year) or periods_per_year <= 0:
        raise ValueError("periods_per_year must be positive and finite")
    if not np.isfinite(risk_free_rate) or risk_free_rate <= -1:
        raise ValueError("risk_free_rate must be finite and greater than -1")
    if isinstance(s, pd.DataFrame):
        return s.aggregate(
            sharpe_ratio,
            risk_free_rate=risk_free_rate,
            periods_per_year=periods_per_year,
            v=None,
        )
    elif isinstance(s, pd.Series):
        observed_returns = s.dropna()
        if len(observed_returns) < 2 or observed_returns.nunique() == 1:
            return np.nan
        rf_to_period = (1 + risk_free_rate) ** (1 / periods_per_year) - 1
        excess_return = observed_returns - rf_to_period
        ann_ex_rets = excess_return.mean() * periods_per_year
        ann_vol = annualize_vol(excess_return, periods_per_year)
        if not np.isfinite(ann_vol) or ann_vol <= 0:
            return np.nan
        return ann_ex_rets / ann_vol
    elif isinstance(s, (int, float)) and v is not None:
        if not np.isfinite(v) or v <= 0:
            return np.nan
        return (s - risk_free_rate) / v
    else:
        raise TypeError("Expected a return Series/DataFrame or an annual return with v")


# ---------------------------------------------------------------------------------
# Modern Portfolio Theory
# ---------------------------------------------------------------------------------
def portfolio_return(weights, vec_returns):
    """
    Compute a weighted one-period return or expected return.
    Use beginning-of-period weights and returns on a common horizon, in the
    same asset order. A weighted average of asset CAGRs is not portfolio CAGR.
    """
    return np.dot(weights, vec_returns)


def portfolio_volatility(weights, cov_rets):
    """
    Compute sqrt(w.T @ covariance @ w) at the covariance matrix's horizon.
    Supply 1-D weights and a covariance matrix in the same asset order.
    Clip only roundoff-sized negative variance, as can occur for exact hedges;
    materially negative variance is an invalid covariance/portfolio input.
    """
    weights = np.asarray(weights, dtype=float)
    covariance = np.asarray(cov_rets, dtype=float)
    if weights.ndim != 1 or covariance.shape != (weights.size, weights.size):
        raise ValueError("Expected 1-D weights and a matching square covariance matrix")
    if not np.isfinite(weights).all() or not np.isfinite(covariance).all():
        raise ValueError("Weights and covariance must be finite")
    variance = float(weights @ (covariance @ weights))
    scale = float(np.abs(weights) @ (np.abs(covariance) @ np.abs(weights)))
    tolerance = 64 * np.finfo(float).eps * scale
    if variance < -tolerance:
        raise ValueError("Covariance implies a negative portfolio variance")
    return float(np.sqrt(max(variance, 0.0)))


def efficient_frontier(
    n_portfolios,
    rets,
    covmat,
    periods_per_year,
    risk_free_rate=0.0,
    iplot=False,
    hsr=False,
    cml=False,
    mvp=False,
    ewp=False,
):
    """
    Return an estimated long-only efficient frontier from arithmetic mean returns.
    rets contains common-period observations and covmat their period covariance.
    Fully missing rows (such as the first price-derived return) are excluded;
    partially missing observations must be resolved by the caller.
    Flat variance ties retain the highest-return point, so the boundary can
    contain fewer than n_portfolios rows.
    The method returns a dataframe containing the volatilities, returns, sharpe ratios and weights
    of the portfolios as well as a plot of the efficient frontier in case iplot=True.
    Other inputs are:
        hsr: if True the method plots the maximum-Sharpe portfolio,
        cml: if True the method plots the capital market line;
        mvp: if True the method plots the minimum volatility portfolio;
        ewp: if True the method plots the equally weigthed portfolio.
    The variable periods_per_year can be, e.g., 12, 52, 252, in case of monthly, weekly, and daily data.
    """

    def append_row_df(df, vol, ret, spr, weights):
        row = pd.DataFrame([[vol, ret, spr, *weights]], columns=df.columns)
        return pd.concat([df, row], ignore_index=True)

    if not np.isfinite(periods_per_year) or periods_per_year <= 0:
        raise ValueError("periods_per_year must be positive and finite")
    if not isinstance(rets, pd.DataFrame):
        raise TypeError("Expected a DataFrame of common-period asset returns")
    observed = rets.dropna(how="all")
    if observed.empty or not np.isfinite(observed.to_numpy()).all():
        raise ValueError("Expected complete, finite asset returns on a common sample")
    ann_rets = observed.mean() * periods_per_year

    # generates optimal weights of porfolios lying of the efficient frontiers
    weights = optimal_weights(n_portfolios, ann_rets, covmat, periods_per_year)
    # in alternative, if only the portfolio consists of only two assets, the weights can be:
    # weights = [np.array([w,1-w]) for w in np.linspace(0,1,n_portfolios)]

    # portfolio returns
    portfolio_ret = [portfolio_return(w, ann_rets) for w in weights]

    # portfolio volatility
    vols = [portfolio_volatility(w, covmat) for w in weights]
    portfolio_vol = [annualize_vol(v, periods_per_year) for v in vols]

    # portfolio sharpe ratio
    portfolio_spr = [
        sharpe_ratio(r, risk_free_rate, periods_per_year, v=v)
        for r, v in zip(portfolio_ret, portfolio_vol)
    ]

    df = pd.DataFrame(
        {
            "volatility": portfolio_vol,
            "return": portfolio_ret,
            "sharpe ratio": portfolio_spr,
        }
    )
    df = pd.concat([df, pd.DataFrame(weights)], axis=1)

    # Keep the higher-return representative when a flat variance boundary
    # makes lower-return points dominated (including nonunique GMV cases).
    keep = []
    best_vol = np.inf
    tolerance = 1e-10 * max(df["volatility"].max(), np.finfo(float).tiny)
    for i in range(len(df) - 1, -1, -1):
        if df.loc[i, "volatility"] < best_vol - tolerance:
            keep.append(i)
        best_vol = min(best_vol, df.loc[i, "volatility"])
    df = df.loc[keep[::-1]].reset_index(drop=True)

    if iplot:
        ax = df.plot.line(
            x="volatility",
            y="return",
            style="--",
            color="coral",
            grid=True,
            label="Efficient frontier",
            figsize=(8, 4),
        )
        if hsr or cml:
            w = maximize_sharpe_ratio(
                ann_rets, covmat, risk_free_rate, periods_per_year
            )
            ret = portfolio_return(w, ann_rets)
            vol = annualize_vol(portfolio_volatility(w, covmat), periods_per_year)
            spr = sharpe_ratio(ret, risk_free_rate, periods_per_year, v=vol)
            df = append_row_df(df, vol, ret, spr, w)
            if cml:
                # Draw the CML: the endpoints of the CML are [0,risk_free_rate] and [port_vol,port_ret]
                ax.plot(
                    [0, vol],
                    [risk_free_rate, ret],
                    color="g",
                    linestyle="-.",
                    label="CML",
                )
                ax.set_xlim(left=0)
                ax.legend()
            if hsr:
                # Plot the highest sharpe ratio portfolio
                ax.scatter([vol], [ret], marker="o", color="g", label="MSR portfolio")
                ax.legend()
        if mvp:
            # Plot the global minimum portfolio:
            w = minimize_volatility(ann_rets, covmat)
            ret = portfolio_return(w, ann_rets)
            vol = annualize_vol(portfolio_volatility(w, covmat), periods_per_year)
            spr = sharpe_ratio(ret, risk_free_rate, periods_per_year, v=vol)
            df = append_row_df(df, vol, ret, spr, w)
            ax.scatter(
                [vol], [ret], color="midnightblue", marker="o", label="GMV portfolio"
            )
            ax.legend()
        if ewp:
            # Plot the equally weighted portfolio:
            w = np.repeat(1 / ann_rets.shape[0], ann_rets.shape[0])
            ret = portfolio_return(w, ann_rets)
            vol = annualize_vol(portfolio_volatility(w, covmat), periods_per_year)
            spr = sharpe_ratio(ret, risk_free_rate, periods_per_year, v=vol)
            df = append_row_df(df, vol, ret, spr, w)
            ax.scatter(
                [vol], [ret], color="goldenrod", marker="o", label="EW portfolio"
            )
            ax.legend()
        return df, ax
    else:
        return df


def summary_stats(s, risk_free_rate=0.03, periods_per_year=12, var_level=0.05):
    """
    Returns a dataframe containing annualized returns, annualized volatility, sharpe ratio,
    skewness, kurtosis, historic VaR, Cornish-Fisher VaR, and Max Drawdown
    """
    if isinstance(s, pd.Series):
        stats = {
            "Ann. return": annualize_rets(s, periods_per_year=periods_per_year),
            "Ann. vol": annualize_vol(s, periods_per_year=periods_per_year),
            "Sharpe ratio": sharpe_ratio(
                s, risk_free_rate=risk_free_rate, periods_per_year=periods_per_year
            ),
            "Skewness": skewness(s),
            "Kurtosis": kurtosis(s),
            "Historic CVar": cvar_historic(s, level=var_level),
            "C-F Var": var_gaussian(s, level=var_level, cf=True),
            "Max drawdown": drawdown(s)["Drawdown"].min(),
        }
        return pd.DataFrame(stats, index=["0"])

    elif isinstance(s, pd.DataFrame):
        stats = {
            "Ann. return": s.aggregate(
                annualize_rets, periods_per_year=periods_per_year
            ),
            "Ann. vol": s.aggregate(annualize_vol, periods_per_year=periods_per_year),
            "Sharpe ratio": s.aggregate(
                sharpe_ratio,
                risk_free_rate=risk_free_rate,
                periods_per_year=periods_per_year,
            ),
            "Skewness": s.aggregate(skewness),
            "Kurtosis": s.aggregate(kurtosis),
            "Historic CVar": s.aggregate(cvar_historic, level=var_level),
            "C-F Var": s.aggregate(var_gaussian, level=var_level, cf=True),
            "Max Drawdown": s.aggregate(lambda r: drawdown(r)["Drawdown"].min()),
        }
        return pd.DataFrame(stats)


def summary_stats_terminal(
    rets, floor=0.8, periods_per_year=2, name="Stats", target=np.inf
):
    """Cross-scenario terminal outcomes per unit of starting wealth.

    Legacy labels are retained: 'Mean wealth std' is the SAMPLE standard
    deviation of terminal wealth, not time-series volatility. 'Exp shortfall'
    is conditional on a terminal floor miss, reported as zero if none occur.
    'Mean shortfall' is unconditional. A finite target adds its attainment
    frequency and unconditional surplus. These are sample statistics, not
    calibrated probabilities; equality is respected up to roundoff tolerance.
    """
    rets = _ldi_return_frame(rets)
    if not np.isscalar(floor) or not np.isfinite(floor) or floor < 0:
        raise ValueError("The terminal floor must be finite and nonnegative")
    if not np.isscalar(target) or np.isnan(target) or target < 0:
        raise ValueError("The terminal target must be nonnegative or positive infinity")
    terminal = terminal_wealth(rets)
    if not np.isfinite(terminal).all():
        raise ValueError("Terminal wealth must be finite")
    breach = terminal < floor - 1e-10 * max(1, floor)
    losses = (floor - terminal).where(breach, 0.0)
    stats = {
        "Mean ann. ret.": annualize_rets(rets, periods_per_year).mean(),
        "Mean wealth": terminal.mean(),
        "Mean wealth std": terminal.std(ddof=1),
        "Prob breach": breach.mean(),
        "Exp shortfall": losses[breach].mean() if breach.any() else 0.0,
        "Mean shortfall": losses.mean(),
    }
    if np.isfinite(target):
        stats["Prob reach target"] = (terminal >= target - 1e-10 * max(1, target)).mean()
        stats["Mean surplus"] = (terminal - target).clip(lower=0).mean()
    return pd.Series(stats).to_frame(name)

def get_portfolio_features(weights, rets, covmat, risk_free_rate, periods_per_year):
    """
    Calculate and print portfolio return, volatility, and Sharpe ratio.

    Parameters:
    - weights: Array of asset weights in the portfolio.
    - rets: Annualized returns for each asset.
    - covmat: Covariance matrix of asset returns.
    - risk_free_rate: Risk-free rate for Sharpe ratio calculation.
    - periods_per_year: Number of periods in a year (trading days).

    Returns:
    Tuple of (return, volatility, sharpe ratio) for the portfolio.
    """
    # Calculate portfolio volatility
    vol = portfolio_volatility(weights, covmat)
    vol = annualize_vol(vol, periods_per_year)

    # Calculate portfolio return
    ret = portfolio_return(weights, rets)

    # Calculate portfolio Sharpe ratio
    shp = sharpe_ratio(ret, risk_free_rate, periods_per_year, v=vol)

    # Display the calculated metrics
    print("Portfolio return:       {:.2f}%" .format(ret*100))
    print("Portfolio volatility:   {:.2f}%" .format(vol*100))
    print("Portfolio Sharpe ratio: {:.2f}" .format(shp))
    
    return ret, vol, shp

def _optimization_inputs(rets, covmatrix):
    """Validate ordered expected returns and a symmetric PSD covariance matrix."""
    if isinstance(rets, pd.Series) and isinstance(covmatrix, pd.DataFrame):
        if not rets.index.equals(covmatrix.index) or not rets.index.equals(covmatrix.columns):
            raise ValueError("Expected returns and covariance must use the same asset order")
    rets = np.asarray(rets, dtype=float)
    covmatrix = np.asarray(covmatrix, dtype=float)
    if rets.ndim != 1 or not rets.size or covmatrix.shape != (rets.size, rets.size):
        raise ValueError("Expected a nonempty return vector and matching covariance matrix")
    if not np.isfinite(rets).all() or not np.isfinite(covmatrix).all():
        raise ValueError("Expected returns and covariance must be finite")
    tolerance = 1e-10 * np.max(np.abs(covmatrix))
    if not np.allclose(covmatrix, covmatrix.T, rtol=1e-10, atol=tolerance):
        raise ValueError("Covariance matrix must be symmetric")
    if np.linalg.eigvalsh((covmatrix + covmatrix.T) / 2).min() < -tolerance:
        raise ValueError("Covariance matrix must be positive semidefinite")
    return rets, covmatrix


def _checked_long_only_weights(result, n_assets):
    """Reject failed solves and invalid allocations rather than returning them."""
    if not result.success:
        raise RuntimeError(f"Portfolio optimization failed: {result.message}")
    weights = np.asarray(result.x, dtype=float)
    if (weights.shape != (n_assets,) or not np.isfinite(weights).all()
            or not np.isfinite(result.fun)
            or not np.isclose(weights.sum(), 1.0, atol=1e-7, rtol=0)
            or (weights < -1e-7).any() or (weights > 1 + 1e-7).any()):
        raise RuntimeError("Portfolio optimizer returned an invalid long-only allocation")
    return weights


def optimal_weights(n_points, rets, covmatrix, periods_per_year):
    """
    Trace target returns from a GMV solution to the highest expected asset return.
    rets is an expected-return vector, already on its reporting horizon.
    The periods_per_year argument is retained for API compatibility.
    """
    if not isinstance(n_points, (int, np.integer)) or n_points < 1:
        raise ValueError("n_points must be a positive integer")
    gmv = minimize_volatility(rets, covmatrix)
    target_rets = np.linspace(portfolio_return(gmv, rets), np.max(rets), n_points)
    weights = [gmv] + [minimize_volatility(rets, covmatrix, target) for target in target_rets[1:]]
    return weights


def minimize_volatility(rets, covmatrix, target_return=None):
    """
    Minimize volatility with fully invested, long-only weights.
    rets contains expected returns on the target_return horizon. Without a
    target, return GMV; targets below GMV's return can lie on the dominated
    boundary. Reject infeasible targets and failed or invalid solver results.
    """
    rets, covmatrix = _optimization_inputs(rets, covmatrix)
    n_assets = rets.shape[0]
    # initial guess weights
    init_guess = np.repeat(1 / n_assets, n_assets)
    weights_constraint = {"type": "eq", "fun": lambda w: 1.0 - np.sum(w)}
    if target_return is not None:
        if not np.isfinite(target_return) or target_return < rets.min() - 1e-10 or target_return > rets.max() + 1e-10:
            raise ValueError("Target return is outside the feasible long-only range")
    if target_return is not None and np.ptp(rets) > 1e-12:
        return_constraint = {
            "type": "eq",
            "args": (rets,),
            "fun": lambda w, r: target_return - portfolio_return(w, r),
        }
        constr = (return_constraint, weights_constraint)
    else:
        constr = weights_constraint

    result = minimize(
        portfolio_volatility,
        init_guess,
        args=(covmatrix,),
        method="SLSQP",
        options={"disp": False, "ftol": 1e-12, "maxiter": 1000},
        constraints=constr,
        bounds=((0.0, 1.0),) * n_assets,
    )  # bounds of each individual weight, i.e., w between 0 and 1
    weights = _checked_long_only_weights(result, n_assets)
    if target_return is not None and not np.isclose(portfolio_return(weights, rets), target_return, atol=1e-7, rtol=0):
        raise RuntimeError("Portfolio optimizer did not meet the target return")
    return weights


def minimize_volatility_2(
    rets,
    covmatrix,
    target_return=None,
    weights_norm_const=True,
    weights_bound_const=True,
):
    """
    Returns the optimal weights of the minimum volatility portfolio.
    If target_return is not None, then the weights correspond to the minimum volatility portfolio
    having a fixed target return (such portfolio will be on the efficient frontier).
    The variables weights_norm_const and weights_bound_const impose two more conditions, the firt one on
    weight that sum to 1, and the latter on the weights which have to be between zero and 1
    The method uses the scipy minimize optimizer which solves the minimization problem
    for the volatility of the portfolio
    """
    n_assets = rets.shape[0]

    # initial guess weights
    init_guess = np.repeat(1 / n_assets, n_assets)

    if weights_bound_const:
        # bounds of the weights (between 0 and 1)
        bounds = ((0.0, 1.0),) * n_assets
    else:
        bounds = None

    constraints = []
    if weights_norm_const:
        weights_constraint = {"type": "eq", "fun": lambda w: 1.0 - np.sum(w)}
        constraints.append(weights_constraint)
    if target_return is not None:
        return_constraint = {
            "type": "eq",
            "args": (rets,),
            "fun": lambda w, r: target_return - portfolio_return(w, r),
        }
        constraints.append(return_constraint)

    result = minimize(
        portfolio_volatility,
        init_guess,
        args=(covmatrix,),
        method="SLSQP",
        options={"disp": False},
        constraints=tuple(constraints),
        bounds=bounds,
    )
    return result.x


def maximize_sharpe_ratio(
    rets, covmatrix, risk_free_rate, periods_per_year, target_volatility=None
):
    """
    Numerically maximize Sharpe with fully invested, long-only weights.
    rets and risk_free_rate are annual return inputs on a common basis;
    covmatrix is period covariance, annualized using periods_per_year.
    target_volatility, if supplied, is an exact positive annual volatility,
    between GMV risk and the highest individual asset risk. Solver and constraint failures
    raise errors instead of returning an unverified allocation.
    """
    rets, covmatrix = _optimization_inputs(rets, covmatrix)
    if not np.isfinite(periods_per_year) or periods_per_year <= 0:
        raise ValueError("periods_per_year must be positive and finite")
    if not np.isfinite(risk_free_rate):
        raise ValueError("risk_free_rate must be finite")
    n_assets = rets.shape[0]
    init_guess = np.repeat(1 / n_assets, n_assets)
    # Include the vertices even without a risk target: when all excess means
    # are negative, equal weights can be a stationary Sharpe MINIMUM.
    initial_guesses = [init_guess, *np.eye(n_assets)]
    weights_constraint = {"type": "eq", "fun": lambda w: 1.0 - np.sum(w),
                          "jac": lambda w: -np.ones_like(w)}
    if target_volatility is not None:
        if not np.isfinite(target_volatility) or target_volatility <= 0:
            raise ValueError("target_volatility must be positive and finite; Sharpe is undefined at zero volatility")
        annual_covariance = covmatrix * periods_per_year
        gmv_weights = minimize_volatility(rets, annual_covariance)
        min_volatility = portfolio_volatility(gmv_weights, annual_covariance)
        max_volatility = np.sqrt(np.diag(annual_covariance).max())
        if target_volatility < min_volatility - 1e-10 or target_volatility > max_volatility + 1e-10:
            raise ValueError(
                f"Target volatility is outside the feasible long-only range "
                f"[{min_volatility:.6g}, {max_volatility:.6g}] annually"
            )
        volatility_constraint = {
            "type": "eq",
            "fun": lambda w: target_volatility ** 2 - w @ annual_covariance @ w,
            "jac": lambda w: -2 * annual_covariance @ w,
        }
        constr = (volatility_constraint, weights_constraint)
        # Exact-risk surfaces can have disconnected branches. Start from each
        # asset as well as equal weights, retaining the best verified solution.
        if np.isclose(min_volatility, max_volatility, atol=1e-12, rtol=0):
            constr = weights_constraint  # All allocations have the same risk.
    else:
        constr = weights_constraint

    def neg_portfolio_sharpe_ratio(
        weights, rets, covmatrix, risk_free_rate, periods_per_year
    ):
        """
        Computes the negative annualized sharpe ratio for minimization problem of optimal portfolios.
        The variable periods_per_year can be, e.g., 12, 52, 252, in case of yearly, weekly, and daily data.
        The variable risk_free_rate is the annual one.
        """
        # annualized portfolio returns
        portfolio_ret = portfolio_return(weights, rets)
        if target_volatility is not None:
            return -(portfolio_ret - risk_free_rate) / target_volatility
        # annualized portfolio volatility
        portfolio_vol = annualize_vol(
            portfolio_volatility(weights, covmatrix), periods_per_year
        )
        return -sharpe_ratio(
            portfolio_ret, risk_free_rate, periods_per_year, v=portfolio_vol
        )
        # i.e., simply returns  -(portfolio_ret - risk_free_rate)/portfolio_vol

    candidates = []
    last_error = None
    for guess in initial_guesses:
        result = minimize(
            neg_portfolio_sharpe_ratio,
            guess,
            args=(rets, covmatrix, risk_free_rate, periods_per_year),
            jac=(lambda w, *args: -rets / target_volatility) if target_volatility is not None else None,
            method="SLSQP",
            options={"disp": False, "ftol": 1e-12, "maxiter": 1000},
            constraints=constr,
            bounds=((0.0, 1.0),) * n_assets,
        )
        try:
            weights = _checked_long_only_weights(result, n_assets)
            if target_volatility is not None:
                actual_volatility = annualize_vol(portfolio_volatility(weights, covmatrix), periods_per_year)
                if not np.isclose(actual_volatility, target_volatility, atol=1e-7, rtol=0):
                    raise RuntimeError("Portfolio optimizer did not meet the target volatility")
        except RuntimeError as error:
            last_error = error
            continue
        candidates.append(weights)
    if not candidates:
        raise last_error
    return min(candidates, key=lambda w: neg_portfolio_sharpe_ratio(
        w, rets, covmatrix, risk_free_rate, periods_per_year
    ))


def weigths_max_sharpe_ratio(covmat, mu_exc, scale=True):
    """
    Optimal (Tangent/Max Sharpe Ratio) portfolio weights using the Markowitz Optimization Procedure:
    - mu_exc is the vector of Excess expected Returns (has to be a column vector as a pd.Series)
    - covmat is the covariance N x N matrix as a pd.DataFrame
    Look at pag. 188 eq. (5.2.28) of "The econometrics of financial markets", by Campbell, Lo, Mackinlay.
    """
    w = inverse_df(covmat).dot(mu_exc)
    if scale:
        # normalize weigths
        w = w / sum(w)
    return w


# ---------------------------------------------------------------------------------
# CPPI backtest strategy
# ---------------------------------------------------------------------------------
def cppi(
    risky_rets,
    safe_rets=None,
    start_value=1000,
    floor=0.8,
    m=3,
    drawdown=None,
    risk_free_rate=0.03,
    periods_per_year=12,
):
    """
    Backtest one independent, unlevered CPPI account per risky-return column.
    Weights, cushions, and floors are beginning-of-period; wealth is period-end.
    Include the first period's return; returns after total depletion are NaN.
    floor is a fraction of initial wealth. If drawdown is supplied, retain the
    legacy rule m=1/drawdown and use a beginning-of-period high-water-mark floor.
    Default cash uses an effective annual risk_free_rate converted per period.
    Supplied safe returns must be aligned; a Series is shared across accounts.
    Floor breaches are recorded, not repaired or treated as impossible.
    """

    if isinstance(risky_rets, pd.Series):
        risky_rets = risky_rets.to_frame(name=risky_rets.name if risky_rets.name is not None else "Risky return")
    if not isinstance(risky_rets, pd.DataFrame):
        raise TypeError("Expected risky returns as a Series or DataFrame")
    risky_rets = risky_rets.astype(float)
    if risky_rets.empty or not risky_rets.index.is_unique or not risky_rets.columns.is_unique or not risky_rets.index.is_monotonic_increasing:
        raise ValueError("Expected nonempty risky returns with unique columns and ordered, unique dates")
    if not np.isfinite(start_value) or start_value <= 0:
        raise ValueError("start_value must be positive and finite")
    if not np.isfinite(floor) or not 0 <= floor <= 1:
        raise ValueError("floor must be between 0 and 1")
    if not np.isfinite(m) or m < 0:
        raise ValueError("m must be nonnegative and finite")
    if not np.isfinite(periods_per_year) or periods_per_year <= 0:
        raise ValueError("periods_per_year must be positive and finite")
    if drawdown is not None and (not np.isfinite(drawdown) or not 0 < drawdown <= 1):
        raise ValueError("drawdown must be greater than 0 and at most 1")
    if safe_rets is None:
        if not np.isfinite(risk_free_rate) or risk_free_rate <= -1:
            raise ValueError("risk_free_rate must be finite and greater than -1")
        safe_rate = np.expm1(np.log1p(risk_free_rate) / periods_per_year)
        safe_rets = pd.DataFrame(safe_rate, index=risky_rets.index, columns=risky_rets.columns)
    elif isinstance(safe_rets, pd.Series):
        safe_rets = pd.DataFrame({col: safe_rets for col in risky_rets.columns})
    if not isinstance(safe_rets, pd.DataFrame):
        raise TypeError("Expected safe returns as a Series or DataFrame")
    if not safe_rets.index.equals(risky_rets.index) or not safe_rets.columns.equals(risky_rets.columns):
        raise ValueError("Safe and risky returns must have identical dates and column order")
    safe_rets = safe_rets.astype(float)
    for returns in (risky_rets, safe_rets):
        if not np.isfinite(returns.to_numpy()).all() or (returns < -1).any().any():
            raise ValueError("Returns must be complete, finite, and at least -1")

    risky_wealth = start_value * (1 + risky_rets).cumprod()
    account_value = pd.Series(start_value, index=risky_rets.columns, dtype=float)
    floor_value = floor * start_value

    # History dataframes
    account_history = pd.DataFrame().reindex_like(risky_rets)
    cushion_history = pd.DataFrame().reindex_like(risky_rets)
    risky_w_history = pd.DataFrame().reindex_like(risky_rets)
    return_history = pd.DataFrame().reindex_like(risky_rets)
    floor_history = pd.DataFrame().reindex_like(risky_rets)

    # Extra history dataframes in presence of drawdown
    if drawdown is not None:
        peak_history = pd.DataFrame().reindex_like(risky_rets)
        peak = start_value
        # define the multiplier
        m = 1 / drawdown

    # For loop over dates
    for step in range(len(risky_rets.index)):
        if drawdown is not None:
            # current peak
            peak = np.maximum(peak, account_value)
            peak_history.iloc[step] = peak
            # current floor value
            floor_value = peak * (1 - drawdown)
        floor_history.iloc[step] = floor_value

        # computing the cushion (as a percentage of the current account value)
        cushion = (account_value - floor_value) / account_value.where(account_value > 0)

        # compute the weight for the allocation on the risky asset
        risky_w = m * cushion
        risky_w = np.minimum(risky_w, 1)
        risky_w = np.maximum(risky_w, 0).fillna(0.0)
        # the last two conditions ensure that the risky weight is in [0,1]

        # compute the weight for the allocation on the safe asset
        safe_w = 1 - risky_w
        period_return = risky_w * risky_rets.iloc[step] + safe_w * safe_rets.iloc[step]
        return_history.iloc[step] = period_return.where(account_value > 0)

        # compute the value allocation
        risky_allocation = risky_w * account_value
        safe_allocation = safe_w * account_value

        # compute the new account value: this is given by the new values from both the risky and the safe assets
        account_value = risky_allocation * (
            1 + risky_rets.iloc[step]
        ) + safe_allocation * (1 + safe_rets.iloc[step])

        # save data: current account value, cushions, weights
        account_history.iloc[step] = account_value
        cushion_history.iloc[step] = cushion
        risky_w_history.iloc[step] = risky_w

    # Returning results
    backtest_result = {
        "Risky wealth": risky_wealth,
        "CPPI wealth": account_history,
        "CPPI returns": return_history,
        "Cushions": cushion_history,
        "Risky allocation": risky_w_history,
        "Safe returns": safe_rets,
        "Floor value": floor_history,
        "Floor breaches": account_history < floor_history - 1e-10 * start_value,
        "m": m,
    }
    if drawdown is not None:
        backtest_result.update(
            {"Floor value": floor_history, "Peaks": peak_history, "m": m}
        )

    return backtest_result


# ---------------------------------------------------------------------------------
# Random walks
# ---------------------------------------------------------------------------------
def _gbm_shocks(n_years, n_scenarios, mu, sigma, periods_per_year, start, seed):
    """Validate a complete time grid and draw standard-normal interval shocks."""
    if not np.isfinite(n_years) or n_years <= 0 or not np.isfinite(periods_per_year) or periods_per_year <= 0:
        raise ValueError("n_years and periods_per_year must be positive and finite")
    if not isinstance(n_scenarios, (int, np.integer)) or isinstance(n_scenarios, (bool, np.bool_)) or n_scenarios < 1:
        raise ValueError("n_scenarios must be a positive integer")
    if not np.isfinite(mu) or not np.isfinite(sigma) or sigma < 0 or not np.isfinite(start) or start <= 0:
        raise ValueError("Expected finite drift, nonnegative volatility, and positive starting price")
    steps = n_years * periods_per_year
    if not np.isfinite(steps) or steps < 1 or not np.isclose(steps, round(steps), atol=1e-10, rtol=0):
        raise ValueError("The horizon must contain a positive integer number of periods")
    # Preserve legacy global seeding when seed is omitted; explicit seeds are local.
    rng = np.random if seed is None else np.random.default_rng(seed)
    return 1 / periods_per_year, rng.standard_normal((int(round(steps)), n_scenarios))


def simulate_gbm_from_returns(
    n_years=10, n_scenarios=20, mu=0.07, sigma=0.15, periods_per_year=12, start=100.0,
    seed=None,
):
    """
    Simulate the Euler approximation to GBM using simple returns.
    Return prices including time zero and simple returns for each interval.
    mu and sigma are annual continuous-time drift and diffusion parameters.
    Keep legacy return-row labels 0..n-1; price rows are 0..n.
    An explicit seed uses a local generator and permits paired exact/Euler paths.
    Reject nonpositive Euler prices rather than silently clip or resample them.
    """
    dt, shocks = _gbm_shocks(n_years, n_scenarios, mu, sigma, periods_per_year, start, seed)
    rets = pd.DataFrame(mu * dt + sigma * np.sqrt(dt) * shocks)
    if not np.isfinite(rets.to_numpy()).all() or (rets <= -1).any().any():
        raise ValueError("Euler approximation produced an invalid return; use a finer grid or exact GBM")
    with np.errstate(over="ignore", under="ignore", invalid="ignore"):
        prices = compound_returns(rets, start=start)
    if not np.isfinite(prices.to_numpy()).all() or (prices <= 0).any().any():
        raise ValueError("Simulation produced nonfinite or nonpositive prices")
    prices = insert_first_row_df(prices, start)

    return prices, rets


def simulate_gbm_from_prices(
    n_years=10, n_scenarios=20, mu=0.07, sigma=0.15, periods_per_year=12, start=100.0,
    seed=None,
):
    """
    Simulate exact GBM transitions on the chosen observation grid.
    Return prices including time zero and LOG returns, retaining row labels
    1..n for the log returns. Convert with np.expm1 before simple-return analytics.
    mu and sigma are annual continuous-time drift and diffusion parameters.
    An explicit seed shares interval shocks with simulate_gbm_from_returns
    at the same grid and scenario count without changing NumPy's global RNG.
    """
    dt, shocks = _gbm_shocks(n_years, n_scenarios, mu, sigma, periods_per_year, start, seed)
    log_returns = (mu - 0.5 * sigma**2) * dt + sigma * np.sqrt(dt) * shocks
    with np.errstate(over="ignore", under="ignore", invalid="ignore"):
        price_values = start * np.exp(np.cumsum(log_returns, axis=0))
    if not np.isfinite(price_values).all() or (price_values <= 0).any():
        raise ValueError("Simulation produced nonfinite or nonpositive prices")
    prices = pd.DataFrame(price_values)
    prices = insert_first_row_df(prices, start)

    rets = pd.DataFrame(log_returns, index=prices.index[1:], columns=prices.columns)

    return prices, rets


def show_gbm(
    n_years=10, n_scenarios=10, mu=0.05, sigma=0.15, periods_per_year=12, start=100
):
    """
    Plot the evolution of prices generated by a GBM.
    The method simply calls the *simulate_gbm_from_returns* function and plots the generated prices.
    This method is designed to be used together with the *interact* method from *ipywidgets*.
    """
    prices, rets = simulate_gbm_from_returns(
        n_years=n_years,
        n_scenarios=n_scenarios,
        mu=mu,
        sigma=sigma,
        periods_per_year=periods_per_year,
        start=start,
    )
    ax = prices.plot(
        figsize=(12, 5),
        grid=True,
        legend=False,
        color="sandybrown",
        alpha=0.7,
        linewidth=2,
    )
    ax.axhline(y=start, ls=":", color="black")
    if periods_per_year == 12:
        xlab = "months"
    elif periods_per_year == 52:
        xlab = "weeks"
    elif periods_per_year == 252:
        xlab = "days"
    ax.set_xlabel(xlab)
    ax.set_ylabel("price")
    ax.set_title("Prices generated by GBM")


def _publish_echarts(plot_data, text=""):
    """Send one text/chart payload through the worker bridge or ordinary stdout."""
    import __main__
    payload = text + "\n<ECHARTS_DATA>" + json.dumps(plot_data, allow_nan=False)
    emit = getattr(__main__, "_emit_echarts", None)
    if callable(emit):
        emit(payload)
    else:
        print(payload)


def _binomial_interval(count, total):
    """Approximate 95% Wilson interval for independent simulated-path events."""
    z = 1.959963984540054
    probability = count / total
    denominator = 1 + z * z / total
    center = (probability + z * z / (2 * total)) / denominator
    margin = z * np.sqrt(probability * (1 - probability) / total + z * z / (4 * total * total)) / denominator
    return [float(max(0, center - margin)), float(min(1, center + margin))]


def show_gbm_echart(
    n_years=10, n_scenarios=10, mu=0.05, sigma=0.15, periods_per_year=12, start=100,
    seed=42,
):
    """Generate GBM paths and emit an ECharts configuration for interactive plotting.

    This helper uses exact GBM transitions and a reproducible local seed.
    It serialises the simulated price paths into the JSON structure expected by the
    documentation site (see ``<ECHARTS_DATA>`` convention in ``OutputDisplay.vue``).

    The function prints a JSON payload that contains a single chart definition named
    ``gbmPrices``. Downstream consumers can parse and display it without needing to
    re-run the GBM simulation in the browser.
    """

    prices, _ = simulate_gbm_from_prices(
        n_years=n_years,
        n_scenarios=n_scenarios,
        mu=mu,
        sigma=sigma,
        periods_per_year=periods_per_year,
        start=start,
        seed=seed,
    )

    periods_map = {12: "Months", 52: "Weeks", 252: "Days"}
    x_label = periods_map.get(periods_per_year, "Periods")

    x_data = [str(int(idx)) if isinstance(idx, (int, np.integer)) else str(idx) for idx in prices.index]

    series_data = {}
    for col_idx in range(prices.shape[1]):
        series_name = f"Scenario {col_idx + 1}"
        series_values = [float(val) for val in prices.iloc[:, col_idx].tolist()]
        series_data[series_name] = series_values

    legend_conf = {"type": "scroll"} if len(series_data) > 6 else {}

    chart_config = {
        "title": "Exact GBM Paths",
        "tooltip": {"trigger": "axis"},
        "legend": legend_conf,
        "xAxis": {"type": "category", "data": x_data, "name": x_label},
        "yAxis": {"type": "value", "name": "Price"},
        "series": series_data,
        "type": "line",
    }

    plot_data = {
        "dates": x_data,
        "gbmPrices": chart_config,
    }

    _publish_echarts(plot_data, f"Exact GBM: {n_scenarios} paths; seed={seed}; drift={mu:.1%}; volatility={sigma:.1%}")


def show_cppi(
    n_years=10,
    n_scenarios=50,
    m=3,
    floor=0,
    mu=0.04,
    sigma=0.15,
    risk_free_rate=0.03,
    periods_per_year=12,
    start=100,
    ymax=100,
):
    """
    CPPI simulation using Brownian Motion generated returns with mean mu and std sigma.
    The method will plot the simulated CPPI wealths as well as an histogram of the
    CPPI wealths at the end of the given period (n_year).
    """
    # generate returs using geometric brownian motions
    _, risky_rets = simulate_gbm_from_returns(
        n_years=n_years,
        n_scenarios=n_scenarios,
        mu=mu,
        sigma=sigma,
        periods_per_year=periods_per_year,
        start=start,
    )

    # run the CPPI strategy with fixed floor (i.e., with no drawdown constraint)
    cppiw = cppi(
        risky_rets,
        start_value=start,
        floor=floor,
        m=m,
        drawdown=None,
        risk_free_rate=risk_free_rate,
        periods_per_year=periods_per_year,
    )["CPPI wealth"]

    # make sure that start price is included
    cols = [i for i in range(0, cppiw.shape[1])]
    row = {}
    for col in cols:
        row[col] = start
    cppiw = insert_first_row_df(cppiw, row)

    # Plot parameters
    fig, (wealth_ax, hist_ax) = plt.subplots(
        figsize=(20, 7),
        nrows=1,
        ncols=2,
        sharey=True,
        gridspec_kw={"width_ratios": [3, 2]},
    )
    plt.subplots_adjust(wspace=0.005)
    simclr = "sandybrown"
    floorclr = "red"
    startclr = "black"
    ymax = (cppiw.values.max() - start) / 100 * ymax + start

    # Plot the random walks
    cppiw.plot(
        ax=wealth_ax, grid=True, legend=False, color=simclr, alpha=0.5, linewidth=2
    )
    wealth_ax.axhline(y=start, ls=":", color=startclr)
    wealth_ax.axhline(y=start * floor, ls=":", color=floorclr, linewidth=2)
    if periods_per_year == 12:
        xlab = "months"
    elif periods_per_year == 52:
        xlab = "weeks"
    elif periods_per_year == 252:
        xlab = "days"
    wealth_ax.set_xlabel(xlab)
    wealth_ax.set_ylim(top=ymax)
    wealth_ax.set_title(
        "CPPI wealths due to brownian motion generated returns", fontsize=14
    )

    # Plot the histogram
    violations_per_scenarios = (
        cppiw < start * floor
    ).sum()  # number of CPPI wealth violations of the floor per each scenario
    total_violations = (
        violations_per_scenarios.sum()
    )  # overall number of CPPI wealth violations during the entire period

    terminal_wealth = cppiw.iloc[-1]  # CPPI wealth at the end of the period
    tw_mean = terminal_wealth.mean()
    tw_median = terminal_wealth.median()
    failure_mask = np.less(terminal_wealth, start * floor)
    n_failures = failure_mask.sum()
    p_fail = n_failures / n_scenarios
    e_shorfall = (
        np.dot(terminal_wealth - start * floor, failure_mask) / n_failures
        if n_failures > 0.0
        else 0.0
    )

    terminal_wealth.hist(
        grid=False, ax=hist_ax, bins=50, ec="white", fc=simclr, orientation="horizontal"
    )
    hist_ax.axhline(y=start, ls=":", color=startclr)
    hist_ax.axhline(y=start * floor, ls=":", color=floorclr, linewidth=2)
    hist_ax.axhline(y=tw_mean, ls=":", color=simclr)
    hist_ax.axhline(y=tw_median, ls=":", color=simclr)
    hist_ax.annotate(
        "Mean: ${:.2f}".format(tw_mean),
        xy=(0.5, 0.9),
        xycoords="axes fraction",
        fontsize=15,
    )
    hist_ax.annotate(
        "Median: ${:.2f}".format(tw_mean),
        xy=(0.5, 0.85),
        xycoords="axes fraction",
        fontsize=15,
    )
    if floor > 0.0:
        hist_ax.annotate(
            "Violations (overall): {}".format(total_violations),
            xy=(0.5, 0.75),
            xycoords="axes fraction",
            fontsize=15,
        )
        hist_ax.annotate(
            "Violations (end period): {} ({:.1f}%)".format(n_failures, p_fail * 100),
            xy=(0.5, 0.7),
            xycoords="axes fraction",
            fontsize=15,
        )
        hist_ax.annotate(
            "E(shortfall) (end period): ${:.2f}".format(e_shorfall),
            xy=(0.5, 0.65),
            xycoords="axes fraction",
            fontsize=15,
        )
    hist_ax.set_title(
        "Histogram of the CPPI wealth at the end of the period", fontsize=14
    )


# ---------------------------------------------------------------------------------
def show_cppi_echart(
    n_years=10, n_scenarios=50, m=3, floor=0.0, mu=0.04, sigma=0.15,
    risk_free_rate=0.03, periods_per_year=12, start=100.0, ymax=100, seed=42,
):
    """Exact-GBM fixed-floor CPPI, with sampled-path and terminal diagnostics.

    Quantile curves are pointwise across paths. Allocation at point k was used
    during interval k; time zero has no completed interval. ymax scales only
    the plotted wealth-axis limit (100 includes all displayed quantile curves).
    """
    if not np.isfinite(ymax) or ymax <= 0:
        raise ValueError("ymax must be positive and finite")
    prices, log_returns = simulate_gbm_from_prices(
        n_years=n_years, n_scenarios=n_scenarios, mu=mu, sigma=sigma,
        periods_per_year=periods_per_year, start=start, seed=seed,
    )
    results = cppi(
        np.expm1(log_returns), start_value=start, floor=floor, m=m,
        risk_free_rate=risk_free_rate, periods_per_year=periods_per_year,
    )
    cppi_array = np.vstack([np.full(n_scenarios, start), results["CPPI wealth"].to_numpy()])
    cppi_p05, cppi_p50, cppi_p95 = np.percentile(cppi_array, [5, 50, 95], axis=1)
    risky_p50 = np.percentile(prices.to_numpy(), 50, axis=1)
    allocation = results["Risky allocation"].to_numpy() * 100
    alloc_p05, alloc_p95 = np.percentile(allocation, [5, 95], axis=1)
    dates = [str(step) for step in range(len(cppi_array))]
    x_axis = {"type": "category", "data": dates,
              "name": {12: "Months", 52: "Weeks", 252: "Days"}.get(periods_per_year, "Periods")}

    terminal = cppi_array[-1]
    floor_value = start * floor
    breach_matrix = results["Floor breaches"].to_numpy()
    path_count = int(breach_matrix.any(axis=0).sum())
    terminal_mask = breach_matrix[-1]
    terminal_count = int(terminal_mask.sum())
    shortfalls = np.maximum(floor_value - terminal, 0)
    conditional_shortfall = float(shortfalls[terminal_mask].mean()) if terminal_count else None
    path_interval = _binomial_interval(path_count, n_scenarios)
    terminal_interval = _binomial_interval(terminal_count, n_scenarios)
    summary = {
        "mean_terminal": float(terminal.mean()), "median_terminal": float(np.median(terminal)),
        "floor_value": float(floor_value), "n_scenarios": int(n_scenarios),
        "path_breach_count": path_count, "terminal_breach_count": terminal_count,
        "observed_path_breach_probability": path_count / n_scenarios,
        "terminal_breach_probability": terminal_count / n_scenarios,
        "path_breach_wilson_95": path_interval, "terminal_breach_wilson_95": terminal_interval,
        "conditional_terminal_shortfall": conditional_shortfall,
        "mean_terminal_shortfall": float(shortfalls.mean()),
        "seed": int(seed) if seed is not None else None,
    }
    shortfall_text = "n/a (no terminal breaches)" if conditional_shortfall is None else f"{conditional_shortfall:.4f}"
    text = (
        f"Exact-GBM CPPI: {n_scenarios} paths; seed={seed}; floor={floor_value:.2f}\n"
        f"Mean terminal wealth: {summary['mean_terminal']:.2f}; median: {summary['median_terminal']:.2f}\n"
        f"Observed-path breaches: {path_count}/{n_scenarios} ({path_count / n_scenarios:.2%}); "
        f"95% Wilson interval [{path_interval[0]:.2%}, {path_interval[1]:.2%}]\n"
        f"Terminal breaches: {terminal_count}/{n_scenarios} ({terminal_count / n_scenarios:.2%}); "
        f"95% Wilson interval [{terminal_interval[0]:.2%}, {terminal_interval[1]:.2%}]\n"
        f"Mean terminal floor shortfall, conditional on breach: {shortfall_text}\n"
        f"Mean terminal floor shortfall across all paths: {summary['mean_terminal_shortfall']:.4f}"
    )
    wealth_top = float(max(cppi_p95.max(), risky_p50.max(), start, floor_value) * 1.05 * ymax / 100)
    plot_data = {
        "dates": dates,
        "cppiWealth": {
            "title": "CPPI vs Risky Wealth: Pointwise Quantiles", "type": "line", "xAxis": x_axis,
            "yAxis": {"type": "value", "name": "Wealth", "min": 0, "max": wealth_top},
            "series": {"CPPI P05": cppi_p05.tolist(), "CPPI Median": cppi_p50.tolist(),
                       "CPPI P95": cppi_p95.tolist(), "Risky Median": risky_p50.tolist(),
                       "Floor": [floor_value] * len(dates)},
        },
        "riskyAllocation": {
            "title": "Risky Weight Used in Each Interval", "type": "line", "xAxis": x_axis,
            "yAxis": {"type": "value", "name": "Risky allocation (%)", "min": 0, "max": 100},
            "series": {"Risky Weight Mean": [None] + allocation.mean(axis=1).tolist(),
                       "Risky Weight P05": [None] + alloc_p05.tolist(),
                       "Risky Weight P95": [None] + alloc_p95.tolist()},
        },
        "summary": summary,
    }
    _publish_echarts(plot_data, text)


# ---------------------------------------------------------------------------------
# Securities
# ---------------------------------------------------------------------------------
def _valuation_vector(values, name):
    """Normalize a scalar/vector while preserving explicit scenario labels."""
    if isinstance(values, pd.Series):
        vector = values.astype(float)
    else:
        array = np.atleast_1d(np.asarray(values, dtype=float))
        if array.ndim != 1:
            raise ValueError(f"{name} must be a scalar or one-dimensional vector")
        vector = pd.Series(array)
    if vector.empty or not vector.index.is_unique or not np.isfinite(vector.to_numpy()).all():
        raise ValueError(f"{name} must be nonempty and finite with unique labels")
    return vector


def discount(t, r):
    """Return (1+r)^(-t), with times as rows and flat-rate cases as columns.

    Times are nonnegative numeric period counts, not calendar dates. Rates are
    effective per matching period (annual when times are years) and exceed -1.
    A rate Series preserves its labels; other rate inputs use columns 0..n-1.
    """
    times = np.atleast_1d(np.asarray(t))
    if times.ndim != 1 or not times.size or times.dtype.kind not in "iuf":
        raise ValueError("Times must be nonempty numeric period counts")
    if not np.isfinite(times).all() or (times < 0).any():
        raise ValueError("Times must be finite and nonnegative")
    rates = _valuation_vector(r, "Rates")
    if (rates <= -1).any():
        raise ValueError("Effective rates must be greater than -1")
    with np.errstate(over="ignore", under="ignore", invalid="ignore"):
        factors = np.exp(-np.outer(times, np.log1p(rates.to_numpy())))
    if not np.isfinite(factors).all() or (factors <= 0).any():
        raise ValueError("Discount factors must be finite and positive")
    return pd.DataFrame(factors, index=pd.Index(times, name=getattr(t, "name", None)), columns=rates.index)


def present_value(L, r):
    """
    Value complete cash-flow streams with numeric payment times in the index.
    One rate applies to every column. One stream with multiple rates produces
    rate scenarios. Otherwise supply one rate per stream: lists/arrays pair by
    position, while a rate Series aligns by column label. Rates are flat over
    payment dates, not a term structure. Return a labeled Series of values.
    """
    if not isinstance(L, pd.DataFrame):
        raise TypeError("Expected pd.DataFrame")

    L = L.astype(float)
    if L.empty or not L.columns.is_unique or not np.isfinite(L.to_numpy(dtype=float)).all():
        raise ValueError("Cash flows must be complete and finite with unique stream labels")
    factors = discount(L.index, r)
    if factors.shape[1] == 1:
        return L.mul(factors.iloc[:, 0], axis=0).sum()
    if L.shape[1] == 1:
        return factors.mul(L.iloc[:, 0], axis=0).sum()
    if factors.shape[1] != L.shape[1]:
        raise ValueError("Supply one rate or one rate per cash-flow stream")
    if isinstance(r, pd.Series):
        if not factors.columns.isin(L.columns).all():
            raise ValueError("Rate labels must match the cash-flow columns")
        factors = factors.reindex(columns=L.columns)
    else:
        factors.columns = L.columns
    return (L * factors).sum()


def funding_ratio(asset_value, liabilities, r):
    """
    Divide current asset values by positive liability present values.
    A single asset value or liability PV broadcasts. Otherwise labeled assets
    align to the valuation labels, and unlabeled vectors pair by position.
    """
    pv = present_value(liabilities, r)
    if not np.isfinite(pv.to_numpy()).all() or (pv <= 0).any():
        raise ValueError("Funding ratios require positive, finite liability present values")
    assets = _valuation_vector(asset_value, "Asset values")
    if (assets < 0).any():
        raise ValueError("Asset values must be nonnegative")
    if len(assets) == 1:
        return assets.iloc[0] / pv
    if len(pv) == 1:
        return assets / pv.iloc[0]
    if len(assets) != len(pv):
        raise ValueError("Supply one asset value or one per liability valuation")
    if isinstance(asset_value, pd.Series):
        if not assets.index.isin(pv.index).all():
            raise ValueError("Asset labels must match the liability valuations")
        assets = assets.reindex(pv.index)
    else:
        assets.index = pv.index
    return assets / pv


def _compounding_inputs(rate, periods_per_year):
    """Validate rate quotes while retaining pandas labels and array shapes."""
    if periods_per_year is not None:
        if (isinstance(periods_per_year, (bool, np.bool_))
                or not isinstance(periods_per_year, (int, float, np.integer, np.floating))
                or not np.isfinite(periods_per_year) or periods_per_year <= 0
                or periods_per_year != int(periods_per_year)):
            raise ValueError("periods_per_year must be a positive integer")
    rates = rate.astype(float) if isinstance(rate, (pd.Series, pd.DataFrame)) else np.asarray(rate, dtype=float)
    if not np.isfinite(np.asarray(rates)).all():
        raise ValueError("Rate quotes must be finite")
    return rates


def compounding_rate(r, periods_per_year=None):
    """Convert a quoted rate to an effective annual rate.

    With frequency m, r is the nominal annual quote compounded m times a year.
    With None, r is the continuously compounded annual rate. These are distinct
    conventions. Preserve pandas labels; log1p/expm1 retain small-rate precision.
    """
    rate = _compounding_inputs(r, periods_per_year)
    if periods_per_year is None:
        exponent = rate
    else:
        if (np.asarray(rate) / periods_per_year <= -1).any():
            raise ValueError("The per-period gross return must be positive")
        exponent = periods_per_year * np.log1p(rate / periods_per_year)
    with np.errstate(over="ignore", under="ignore", invalid="ignore"):
        effective = np.expm1(exponent)
    if not np.isfinite(np.asarray(effective)).all() or (np.asarray(effective) <= -1).any():
        raise ValueError("The effective annual rate is outside representable bounds")
    return effective


def compounding_rate_inv(R, periods_per_year=None):
    """
    Convert an effective annual rate R to an equivalent annual quote.
    With frequency m, return the nominal quote m*((1+R)**(1/m)-1).
    With None, return the continuously compounded rate log(1+R).
    R must exceed -1; preserve pandas labels and array shapes.
    """
    rate = _compounding_inputs(R, periods_per_year)
    if (np.asarray(rate) <= -1).any():
        raise ValueError("Effective annual rates must be greater than -1")
    if periods_per_year is None:
        return np.log1p(rate)
    return periods_per_year * np.expm1(np.log1p(rate) / periods_per_year)


def _cir_parameters(a, b, sigma):
    """Validate CIR parameters; b is an effective-annual representation of the mean level."""
    parameters = np.asarray([a, b, sigma], dtype=float)
    if parameters.shape != (3,) or not np.isfinite(parameters).all() or a <= 0 or b < 0 or sigma < 0:
        raise ValueError("CIR requires finite a > 0, b >= 0, and sigma >= 0")
    return float(np.log1p(b))


def _cir_zcb_price(ttm, short_rate, a, mean_level, sigma):
    """Affine risk-neutral price with continuous short rates and a stable deterministic limit."""
    if sigma == 0:
        integral = mean_level * ttm + (short_rate - mean_level) * (-np.expm1(-a * ttm)) / a
        return np.exp(-integral)
    h = np.hypot(a, np.sqrt(2) * sigma)
    a_minus_h = -2 * sigma ** 2 / (a + h)
    u = -np.expm1(-h * ttm)
    denominator = 2 * h + a_minus_h * u
    B = 2 * u / denominator
    log_A = (2 * a * mean_level / sigma ** 2) * (
        -np.log1p(a_minus_h * u / (2 * h)) + a_minus_h * ttm / 2
    )
    return np.exp(log_A - B * short_rate)


def cir_zero_coupon_price(ttm, r, a=0.05, b=0.03, sigma=0.05):
    """Price one unit at maturity using CIR risk-neutral parameters.

    ttm is remaining time in years; r and b use effective annual quote units.
    Internally the short rate and mean level are log1p(r) and log1p(b).
    Scalar/array inputs broadcast; sigma=0 uses deterministic mean reversion.
    """
    mean_level = _cir_parameters(a, b, sigma)
    time = np.asarray(ttm, dtype=float)
    quoted_rate = np.asarray(r, dtype=float)
    if not np.isfinite(time).all() or (time < 0).any() or not np.isfinite(quoted_rate).all() or (quoted_rate < 0).any():
        raise ValueError("CIR pricing requires finite, nonnegative times and rate quotes")
    price = _cir_zcb_price(time, np.log1p(quoted_rate), a, mean_level, sigma)
    if not np.isfinite(price).all() or (price <= 0).any():
        raise ValueError("CIR bond prices must be finite and positive")
    return price


def simulate_cir(
    n_years=10, n_scenarios=10, a=0.05, b=0.03, sigma=0.05, periods_per_year=12, r0=None,
    seed=None,
):
    """Exact-grid CIR rate paths and prices of a zero-coupon bond maturing at n_years.

    b and r0 are effective annual quotes; both are converted to continuous rates.
    Return annualized effective short-rate quotes (not realized annual returns)
    and unit bond prices, with rows 0..n including the initial observation.
    Parameters describe the risk-neutral dynamics used for the affine prices.
    Explicit seeds are local. With b=0, the exact transition includes mass at zero.
    """
    mean_level = _cir_parameters(a, b, sigma)
    initial_quote = b if r0 is None else r0
    if not np.isscalar(initial_quote) or not np.isfinite(initial_quote) or initial_quote < 0:
        raise ValueError("r0 must be a finite, nonnegative annual quote")
    _compounding_inputs(0.0, periods_per_year)
    if periods_per_year is None or not np.isfinite(n_years) or n_years <= 0:
        raise ValueError("CIR requires a positive horizon and an observation frequency")
    steps = n_years * periods_per_year
    if not np.isfinite(steps) or steps < 1 or not np.isclose(steps, round(steps), atol=1e-10, rtol=0):
        raise ValueError("The horizon must contain a positive integer number of periods")
    if not isinstance(n_scenarios, (int, np.integer)) or isinstance(n_scenarios, (bool, np.bool_)) or n_scenarios < 1:
        raise ValueError("n_scenarios must be a positive integer")
    n_steps = int(round(steps))
    times = np.arange(n_steps + 1) / periods_per_year
    initial_rate = np.log1p(initial_quote)
    if sigma == 0:
        path = mean_level + (initial_rate - mean_level) * np.exp(-a * times)
        short_rates = np.repeat(path[:, None], n_scenarios, axis=1)
    else:
        rng = np.random if seed is None else np.random.default_rng(seed)
        decay = np.exp(-a / periods_per_year)
        scale = sigma ** 2 * (-np.expm1(-a / periods_per_year)) / (4 * a)
        degrees = 4 * a * mean_level / sigma ** 2
        short_rates = np.empty((n_steps + 1, n_scenarios))
        short_rates[0] = initial_rate
        for step in range(1, n_steps + 1):
            noncentrality = decay * short_rates[step - 1] / scale
            if degrees == 0:
                counts = rng.poisson(noncentrality / 2)
                short_rates[step] = scale * rng.gamma(counts, 2.0)
            else:
                short_rates[step] = scale * rng.noncentral_chisquare(degrees, noncentrality)
    remaining = np.maximum(n_years - times, 0)[:, None]
    prices = _cir_zcb_price(remaining, short_rates, a, mean_level, sigma)
    prices[-1] = 1.0
    if not np.isfinite(prices).all() or (prices <= 0).any():
        raise ValueError("CIR bond prices must be finite and positive")
    return pd.DataFrame(compounding_rate(short_rates)), pd.DataFrame(prices)


def show_cir_echart(n_years=5, n_scenarios=5, a=0.5, b=0.03, sigma=0.10,
                    periods_per_year=12, r0=0.05, seed=42):
    """Emit linked CIR short-rate and zero-coupon-price paths for the lesson widget."""
    rates, prices = simulate_cir(n_years=n_years, n_scenarios=n_scenarios, a=a, b=b,
                                sigma=sigma, periods_per_year=periods_per_year, r0=r0, seed=seed)
    times = rates.index.to_numpy() / periods_per_year
    continuous_rates = compounding_rate_inv(rates)
    initial_quote = b if r0 is None else r0
    mean_level = np.log1p(b)
    conditional_mean = mean_level + (np.log1p(initial_quote) - mean_level) * np.exp(-a * times)
    plots = {}
    for key, title, label, values in (
        ("cirRates", "CIR Short Rates: Pricing-Measure Paths", "Continuous short rate (%)", continuous_rates * 100),
        ("cirBondPrices", "Zero-Coupon Bond: Same Maturity, Same Rate Paths", "Price per 1 paid at maturity", prices),
    ):
        plots[key] = {
            "type": "line", "title": title,
            "xAxis": {"type": "value", "name": "Elapsed years", "min": 0, "max": n_years},
            "yAxis": {"type": "value", "name": label, "scale": True},
            "series": {f"Scenario {column + 1}": np.column_stack([times, values[column]]).tolist()
                       for column in values.columns},
        }
    plots["cirRates"]["yAxis"]["min"] = 0
    plots["cirBondPrices"]["yAxis"]["max"] = 1
    plots["cirRates"]["series"]["Conditional mean"] = np.column_stack([times, conditional_mean * 100]).tolist()
    feller = "satisfied" if 2 * a * mean_level >= sigma ** 2 else "not satisfied; zero is accessible"
    condition = "Deterministic rate path (sigma=0)" if sigma == 0 else f"Feller condition: {feller}"
    text = (f"Risk-neutral CIR; seed={seed}. Inputs b={b:.2%}, r0={initial_quote:.2%} are effective annual quotes.\n"
            f"Continuous mean level: {mean_level:.4%}; initial continuous rate: {np.log1p(initial_quote):.4%}.\n"
            f"{condition}. Initial unit bond price: {prices.iloc[0, 0]:.6f}; maturity payoff: 1.")
    _publish_echarts(plots, text)


def cir_cash_wealth(rates, initial_assets=1.0, a=0.05, b=0.03, sigma=0.05, periods_per_year=12):
    """Cash proxy: roll default-free one-period bonds priced in the CIR model.

    rates is a time-by-scenario DataFrame of effective annual short-rate quotes,
    including time zero, observed at equally spaced intervals 1/periods_per_year.
    Use each beginning quote to price the next interval's bond; its redemption
    funds the next purchase. Return wealth at roll dates, preserving labels.
    This is discrete bond rollover, not exact integration of a short-rate path.
    """
    _compounding_inputs(0.0, periods_per_year)
    if periods_per_year is None:
        raise ValueError("Cash rollover requires an observation frequency")
    if not np.isscalar(initial_assets) or not np.isfinite(initial_assets) or initial_assets < 0:
        raise ValueError("initial_assets must be finite and nonnegative")
    if not isinstance(rates, pd.DataFrame) or rates.empty or len(rates) < 2:
        raise ValueError("rates must be a DataFrame including time zero and at least one interval")
    if not rates.index.is_unique or not rates.index.is_monotonic_increasing or not rates.columns.is_unique:
        raise ValueError("Rate dates must be ordered and unique, with unique scenario labels")
    quotes = rates.to_numpy(dtype=float)
    if not np.isfinite(quotes).all() or (quotes < 0).any():
        raise ValueError("CIR rate quotes must be finite and nonnegative")
    short_prices = cir_zero_coupon_price(1 / periods_per_year, quotes[:-1], a=a, b=b, sigma=sigma)
    log_growth = np.vstack([np.zeros(rates.shape[1]), np.cumsum(-np.log(short_prices), axis=0)])
    with np.errstate(over="ignore", invalid="ignore"):
        wealth = initial_assets * np.exp(log_growth)
    if not np.isfinite(wealth).all():
        raise ValueError("Cash wealth is outside representable bounds")
    return pd.DataFrame(wealth, index=rates.index, columns=rates.columns)


def show_liability_hedging_echart(n_years=10, n_scenarios=500, initial_assets=0.75, liability=1.0,
                                 a=0.05, b=0.03, sigma=0.08, periods_per_year=12, r0=0.03, seed=42):
    """Compare rolled cash with a maturity-matched zero coupon on shared Q paths.

    Amounts are in millions. Plot five cash funding paths, the constant matched
    ratio, and empirical terminal CDFs on one probability scale. A matching bond
    removes rate risk relative to this fixed liability, not a capital deficit.
    """
    if not np.isscalar(initial_assets) or not np.isfinite(initial_assets) or initial_assets < 0:
        raise ValueError("initial_assets must be finite and nonnegative")
    if not np.isscalar(liability) or not np.isfinite(liability) or liability <= 0:
        raise ValueError("liability must be finite and positive")
    rates, prices = simulate_cir(n_years=n_years, n_scenarios=n_scenarios, a=a, b=b,
                                sigma=sigma, periods_per_year=periods_per_year, r0=r0, seed=seed)
    cash = cir_cash_wealth(rates, initial_assets, a=a, b=b, sigma=sigma, periods_per_year=periods_per_year)
    initial_price = float(prices.iloc[0, 0])
    matched_ratio = initial_assets / (liability * initial_price)
    cash_ratios = cash / (liability * prices)
    times = rates.index.to_numpy() / periods_per_year
    paths = {f"Cash {column + 1}": np.column_stack([times, cash_ratios[column]]).tolist()
             for column in rates.columns[:5]}
    paths["Matching bond"] = [[0, matched_ratio], [n_years, matched_ratio]]
    paths["Target"] = [[0, 1], [n_years, 1]]

    # Duplicate x values draw genuine CDF steps, including the bond's point mass.
    terminal = np.sort(cash_ratios.iloc[-1].to_numpy())
    xmin = max(0.0, min(terminal[0], matched_ratio, 1.0) * 0.95)
    xmax = max(terminal[-1], matched_ratio, 1.0) * 1.05
    heights = np.column_stack([np.arange(n_scenarios), np.arange(1, n_scenarios + 1)])
    cash_cdf = np.column_stack([np.repeat(terminal, 2), heights.ravel() * 100 / n_scenarios])
    cash_cdf = np.vstack([[xmin, 0], cash_cdf, [xmax, 100]])
    plots = {
        "hedgingFunding": {
            "type": "line", "title": "Funding Ratios: Cash and a Matching Bond",
            "xAxis": {"type": "value", "name": "Elapsed years", "min": 0, "max": n_years},
            "yAxis": {"type": "value", "name": "Funding ratio", "scale": True}, "series": paths,
        },
        "hedgingTerminal": {
            "type": "line", "title": "Terminal Funding: Empirical Cumulative Distributions",
            "xAxis": {"type": "value", "name": "Terminal funding ratio", "min": xmin, "max": xmax},
            "yAxis": {"type": "value", "name": "Scenarios at or below x (%)", "min": 0, "max": 100},
            "series": {
                "Cash": cash_cdf.tolist(),
                "Matching bond": [[xmin, 0], [matched_ratio, 0], [matched_ratio, 100], [xmax, 100]],
                "Target": [[1, 0], [1, 100]],
            },
        },
    }
    # Ignore floating-point noise at exactly full funding; no economic buffer.
    cash_failures = int((terminal < 1 - 1e-10).sum())
    bond_status = "underfunded" if matched_ratio < 1 - 1e-10 else "fully funded or in surplus"
    text = (f"Risk-neutral scenario exercise (not a real-world forecast); seed={seed}.\n"
            f"Same starting assets: {initial_assets:.6f} million; liability at year {n_years:g}: {liability:.6f} million.\n"
            f"Initial unit bond price: {initial_price:.6f}; full matching cost: {liability * initial_price:.6f} million.\n"
            f"Matching bond: funding ratio {matched_ratio:.6f}, {bond_status}; terminal assets {liability * matched_ratio:.6f} million.\n"
            f"Cash terminal shortfalls (FR < 1): {cash_failures}/{n_scenarios} ({cash_failures / n_scenarios:.1%}).\n"
            f"First {min(5, n_scenarios)} cash paths shown; terminal CDF uses all {n_scenarios}. "
            "CDF includes equality; a jump at 1 is not a shortfall.")
    _publish_echarts(plots, text)


def bond_cash_flows(principal=100, maturity=10, coupon_rate=0.03, coupons_per_year=2):
    """Regular payments indexed in coupon periods, including final face value.

    principal is face value, not purchase price. Coupon rate is annual nominal;
    each coupon is principal*coupon_rate/coupons_per_year. No stub periods.
    """
    _compounding_inputs(0.0, coupons_per_year)
    if coupons_per_year is None or not np.isfinite([principal, maturity, coupon_rate]).all():
        raise ValueError("Bond terms and coupon frequency must be finite")
    if principal <= 0 or maturity <= 0 or coupon_rate < 0:
        raise ValueError("Require positive face value and maturity, and a nonnegative coupon rate")
    periods = maturity * coupons_per_year
    if not np.isclose(periods, round(periods), atol=1e-10, rtol=0) or periods < 1:
        raise ValueError("Maturity must contain an integer number of coupon periods")
    flows = pd.DataFrame(principal * coupon_rate / coupons_per_year,
                         index=np.arange(1, int(round(periods)) + 1), columns=[0])
    flows.iloc[-1, 0] += principal
    return flows


def _bond_grid(frame, maturity, coupons_per_year, periods_per_year):
    """Validate steps 0..n, with every coupon on an observation date."""
    _compounding_inputs(0.0, periods_per_year)
    if periods_per_year is None or periods_per_year % coupons_per_year:
        raise ValueError("Observation frequency must be a positive multiple of coupon frequency")
    if not isinstance(frame, pd.DataFrame) or frame.empty or not frame.columns.is_unique:
        raise ValueError("Expected a nonempty time-by-scenario DataFrame with unique columns")
    if not np.array_equal(frame.index.to_numpy(), np.arange(len(frame))):
        raise ValueError("Observation index must be consecutive steps starting at zero")
    values = frame.to_numpy(dtype=float)
    times = np.arange(len(frame)) / periods_per_year
    if not np.isfinite(values).all() or times[-1] > maturity + 1e-10:
        raise ValueError("Observations must be finite and cannot extend beyond maturity")
    return values, times


def bond_price(principal=100, maturity=10, coupon_rate=0.02, coupons_per_year=2,
               ytm=0.03, cf=None, periods_per_year=None):
    """Price at a flat nominal annual YTM compounded at coupon frequency.

    Scalar ytm returns the time-zero price. A DataFrame contains YTM scenarios
    at steps 0..n; observation frequency defaults to coupon frequency. Full
    (dirty) prices exclude payments at each observation, ending at zero after
    redemption. Optional cf is one column indexed in coupon periods, with its
    final payment at the stated maturity.
    """
    flows = bond_cash_flows(principal, maturity, coupon_rate, coupons_per_year)
    if cf is not None:
        if not isinstance(cf, pd.DataFrame) or cf.shape[1] != 1 or cf.empty:
            raise ValueError("cf must contain one nonempty cash-flow column")
        dates = np.asarray(cf.index, dtype=float)
        if (not np.isfinite(dates).all() or (dates <= 0).any() or (np.diff(dates) <= 0).any()
                or not np.isclose(dates[-1], maturity * coupons_per_year, atol=1e-10, rtol=0)
                or not np.isfinite(cf.to_numpy()).all() or (cf.to_numpy() < 0).any()):
            raise ValueError("cf must have ordered positive dates, nonnegative payments, and the stated maturity")
        flows = cf
    if np.isscalar(ytm):
        return float(present_value(flows, float(ytm) / coupons_per_year).iloc[0])
    frequency = coupons_per_year if periods_per_year is None else periods_per_year
    yields, times = _bond_grid(ytm, maturity, coupons_per_year, frequency)
    if (yields <= -coupons_per_year).any():
        raise ValueError("Nominal YTM divided by coupon frequency must exceed -1")
    prices = np.zeros_like(yields)
    for period, payment in flows.iloc[:, 0].items():
        remaining = period - times * coupons_per_year
        pending = remaining > 1e-10
        prices[pending] += payment * np.exp(-np.log1p(yields[pending] / coupons_per_year) * remaining[pending, None])
    if not np.isfinite(prices).all():
        raise ValueError("Bond prices are outside representable bounds")
    result = pd.DataFrame(prices, index=ytm.index, columns=ytm.columns)
    result.attrs.update(maturity=maturity, periods_per_year=frequency)
    return result


def bond_returns(
    principal,
    bond_prices,
    coupon_rate,
    coupons_per_year,
    periods_per_year,
    maturity=None,
):
    """Total returns from post-payment full prices, counting each payment once.

    Maturity is explicit or comes from price-frame attrs; a truncated frame
    does not imply early redemption. Compounding these returns assumes coupon
    reinvestment in the bond. For a scalar purchase price, return annualized
    terminal-wealth growth with coupons held at ZERO interest, not YTM.
    """
    if isinstance(bond_prices, pd.DataFrame):
        maturity = bond_prices.attrs.get("maturity") if maturity is None else maturity
        if maturity is None:
            raise ValueError("Maturity is required to schedule redemption")
        flows = bond_cash_flows(principal, maturity, coupon_rate, coupons_per_year)
        prices, times = _bond_grid(bond_prices, maturity, coupons_per_year, periods_per_year)
        if len(prices) < 2 or (prices[:-1] <= 0).any() or (prices[-1] < 0).any():
            raise ValueError("Returns require at least two dates and positive prices before redemption")
        if bond_prices.attrs.get("periods_per_year", periods_per_year) != periods_per_year:
            raise ValueError("Return frequency must match the price observations")
        at_maturity = np.isclose(times[-1], maturity, atol=1e-10, rtol=0)
        if (at_maturity and (prices[-1] != 0).any()) or (not at_maturity and (prices[-1] <= 0).any()):
            raise ValueError("Post-payment price must be zero at maturity and positive before it")
        payments = np.zeros(len(prices))
        for period, payment in flows.iloc[:, 0].items():
            step = int(round(period * periods_per_year / coupons_per_year))
            if step < len(payments):
                payments[step] = payment
        returns = (prices[1:] + payments[1:, None]) / prices[:-1] - 1
        return pd.DataFrame(returns, index=bond_prices.index[1:], columns=bond_prices.columns)
    if maturity is None or not np.isscalar(bond_prices) or not np.isfinite(bond_prices) or bond_prices <= 0:
        raise ValueError("A scalar purchase price must be positive and finite, with maturity supplied")
    flows = bond_cash_flows(principal, maturity, coupon_rate, coupons_per_year)
    return float((flows.iloc[:, 0].sum() / bond_prices) ** (1 / maturity) - 1)


def cir_bond_price(rates, principal=100, maturity=3, coupon_rate=0.03, coupons_per_year=2,
                   periods_per_year=12, a=0.05, b=0.03, sigma=0.05):
    """Value remaining payments on the CIR curve, not at a short-rate YTM.

    rates contains effective annual short-rate quotes at steps 0..n. Use the
    same risk-neutral parameters as the simulated curve. Full prices exclude
    payments made at the observation date, including final redemption.
    """
    flows = bond_cash_flows(principal, maturity, coupon_rate, coupons_per_year)
    quotes, times = _bond_grid(rates, maturity, coupons_per_year, periods_per_year)
    _cir_parameters(a, b, sigma)
    if (quotes < 0).any():
        raise ValueError("CIR short-rate quotes must be nonnegative")
    prices = np.zeros_like(quotes)
    for period, payment in flows.iloc[:, 0].items():
        remaining = period / coupons_per_year - times
        pending = remaining > 1e-10
        prices[pending] += payment * cir_zero_coupon_price(
            remaining[pending, None], quotes[pending], a=a, b=b, sigma=sigma)
    result = pd.DataFrame(prices, index=rates.index, columns=rates.columns)
    result.attrs.update(maturity=maturity, periods_per_year=periods_per_year)
    return result


def show_coupon_bond_echart(principal=100, maturity=3, coupon_rate=0.03, coupons_per_year=2,
                            ytm=0.05, reinvestment_rate=0.0):
    """Explore nominal YTM pricing and effective-annual coupon reinvestment."""
    flows = bond_cash_flows(principal, maturity, coupon_rate, coupons_per_year)
    price = bond_price(principal, maturity, coupon_rate, coupons_per_year, ytm)
    if not np.isfinite(reinvestment_rate) or reinvestment_rate <= -1:
        raise ValueError("Effective annual reinvestment rate must exceed -1")
    effective_ytm = np.expm1(coupons_per_year * np.log1p(ytm / coupons_per_year))
    yield_grid = np.linspace(min(-0.02, ytm), max(0.10, ytm + 0.02, coupon_rate + 0.02), 101)
    price_curve = [bond_price(principal, maturity, coupon_rate, coupons_per_year, y) for y in yield_grid]
    reinvestment_grid = np.linspace(min(-0.02, reinvestment_rate, effective_ytm),
                                   max(0.10, reinvestment_rate + 0.02, effective_ytm + 0.02), 101)
    remaining = maturity - flows.index.to_numpy() / coupons_per_year
    payments = flows.iloc[:, 0].to_numpy()
    terminal_curve = ((1 + reinvestment_grid[:, None]) ** remaining * payments).sum(axis=1)
    terminal = float(((1 + reinvestment_rate) ** remaining * payments).sum())
    realized = (terminal / price) ** (1 / maturity) - 1
    plots = {
        "couponYield": {
            "type": "line", "title": "Coupon Bond: Price and Yield to Maturity",
            "xAxis": {"type": "value", "name": "Nominal annual YTM (%)", "scale": True},
            "yAxis": {"type": "value", "name": "Full bond price (dollars)", "scale": True},
            "series": {"Bond price": np.column_stack([yield_grid * 100, price_curve]).tolist(),
                       "Face value": [[yield_grid[0] * 100, principal], [yield_grid[-1] * 100, principal]],
                       "Selected bond": [[ytm * 100, price]]},
            "seriesOptions": {"Selected bond": {"type": "scatter", "symbol": "diamond", "symbolSize": 11},
                              "Face value": {"lineStyle": {"type": "dashed"}}},
        },
        "couponReinvestment": {
            "type": "line", "title": "Terminal Wealth Depends on Coupon Reinvestment",
            "xAxis": {"type": "value", "name": "Effective reinvestment rate (%)", "scale": True},
            "yAxis": {"type": "value", "name": "Terminal wealth (dollars)", "scale": True},
            "series": {"Terminal wealth": np.column_stack([reinvestment_grid * 100, terminal_curve]).tolist(),
                       "Selected reinvestment": [[reinvestment_rate * 100, terminal]]},
            "seriesOptions": {"Selected reinvestment": {"type": "scatter", "symbol": "diamond", "symbolSize": 11}},
        },
    }
    text = (f"Face value {principal:.2f}; coupon {principal * coupon_rate / coupons_per_year:.2f}, "
            f"paid {coupons_per_year} times/year for {maturity:g} years. Full purchase price: {price:.6f}.\n"
            f"Nominal YTM: {ytm:.4%}; effective annual equivalent: {effective_ytm:.4%}.\n"
            f"Coupon reinvestment at {reinvestment_rate:.4%} effective annually: terminal wealth {terminal:.6f}; "
            f"annualized realized return {realized:.4%}.\n"
            "Fixed promised payments, no default, and purchase on a coupon date after payment. "
            "YTM is a cash-flow IRR; reinvesting interim coupons at its effective annual equivalent reproduces that compounded return.")
    _publish_echarts(plots, text)


def mac_duration(cash_flows, discount_rate):
    """PV-weighted payment time, in the units of the numeric cash-flow index.

    Use effective rates per index unit: y/m for coupon periods, or (1+y/m)**m-1
    for years when y is a nominal annual YTM. Nonnegative payments must have
    positive PV. Rate/stream alignment follows present_value. Return a float
    for one valuation, otherwise a labeled Series of durations.
    """
    if not isinstance(cash_flows, pd.DataFrame):
        raise ValueError("Expected a pd.DataFrame of cash_flows")
    flows = cash_flows.astype(float)
    price = present_value(flows, discount_rate)
    if (flows.to_numpy() < 0).any() or not np.isfinite(price).all() or (price <= 0).any():
        raise ValueError("Duration requires nonnegative cash flows with positive, finite present values")
    weighted_pv = present_value(flows.mul(flows.index.to_numpy(dtype=float), axis=0), discount_rate)
    result = weighted_pv / price
    if not np.isfinite(result).all():
        raise ValueError("Duration must be finite")
    return float(result.iloc[0]) if len(result) == 1 else result


def bond_sensitivity(principal=100, maturity=3, coupon_rate=0.03, coupons_per_year=2,
                     ytm=0.05, quote="nominal"):
    """Price and local derivatives with respect to the specified annual yield quote.

    quote='nominal' compounds ytm at coupon frequency; 'continuous' discounts
    by exp(-ytm*t). Duration is in years and convexity in years squared.
    Dollar duration is -dPrice/dQuote; DV01 is its positive 1-bp loss estimate.
    Cash flows and valuation date stay fixed. No optionality or curve twists.
    """
    flows = bond_cash_flows(principal, maturity, coupon_rate, coupons_per_year)
    if quote not in ("nominal", "continuous"):
        raise ValueError("Yield quote must be nominal or continuous")
    if not np.isscalar(ytm) or not np.isfinite(ytm):
        raise ValueError("The annual yield quote must be a finite scalar")
    times = flows.index.to_numpy() / coupons_per_year
    if quote == "continuous":
        exponent, sensitivity_times, curvature = ytm * times, times, times ** 2
    else:
        base = 1 + ytm / coupons_per_year
        if base <= 0:
            raise ValueError("Nominal YTM divided by coupon frequency must exceed -1")
        exponent = coupons_per_year * np.log1p(ytm / coupons_per_year) * times
        sensitivity_times = times / base
        curvature = times * (times + 1 / coupons_per_year) / base ** 2
    with np.errstate(over="ignore", under="ignore", invalid="ignore"):
        present_values = flows.iloc[:, 0].to_numpy() * np.exp(-exponent)
        price = present_values.sum()
    if not np.isfinite(present_values).all() or not np.isfinite(price) or price <= 0:
        raise ValueError("Bond present value must be positive and finite")
    weights = present_values / price
    mac, modified, convexity = (float(weights @ values) for values in (times, sensitivity_times, curvature))
    result = {"Price": float(price), "Macaulay duration": mac, "Modified duration": modified,
              "Convexity": convexity, "Dollar duration": float(price * modified), "DV01": float(price * modified * 1e-4)}
    if not np.isfinite(list(result.values())).all():
        raise ValueError("Bond sensitivities must be finite")
    return result


def show_duration_echart(principal=100, maturity=3, coupon_rate=0.03, coupons_per_year=2,
                         ytm=0.05, shift_bps=50, quote="nominal"):
    """PV timing and exact versus first-order repricing under an explicit quote.

    One bp is 0.0001 of the chosen nominal or continuous annual yield. Changing
    quote without converting its numeric value changes the discount curve.
    """
    flows = bond_cash_flows(principal, maturity, coupon_rate, coupons_per_year)
    measures = bond_sensitivity(principal, maturity, coupon_rate, coupons_per_year, ytm, quote)
    price, mac, modified = measures["Price"], measures["Macaulay duration"], measures["Modified duration"]
    if not np.isscalar(shift_bps) or not np.isfinite(shift_bps):
        raise ValueError("Yield shift must be a finite number of basis points")
    times = flows.index.to_numpy() / coupons_per_year
    exponent = ytm * times if quote == "continuous" else coupons_per_year * np.log1p(ytm / coupons_per_year) * times
    weights = flows[0].to_numpy() * np.exp(-exponent) / price
    width = max(100, abs(shift_bps))
    shifts = np.linspace(-width, width, 81)
    repriced = np.array([bond_sensitivity(principal, maturity, coupon_rate, coupons_per_year,
                                         ytm + shift / 10000, quote)["Price"] for shift in shifts])
    exact = (repriced / price - 1) * 100
    approximate = -modified * shifts / 100
    selected_price = bond_sensitivity(principal, maturity, coupon_rate, coupons_per_year, ytm + shift_bps / 10000, quote)["Price"]
    selected_exact = (selected_price / price - 1) * 100
    selected_approximate = -modified * shift_bps / 100
    plots = {
        "durationWeights": {
            "type": "bar", "title": "Macaulay Duration: Present-Value Timing Weights",
            "xAxis": {"type": "value", "name": "Payment year", "min": 0, "max": maturity + 0.5 / coupons_per_year,
                      "axisLabel": {"showMaxLabel": False}},
            "yAxis": {"type": "value", "name": "Share of bond present value (%)", "min": 0, "max": 100},
            "series": {"PV weight": np.column_stack([times, weights * 100]).tolist()},
        },
        "durationSensitivity": {
            "type": "line", "title": "Yield Shift: Exact Repricing and Duration Approximation",
            "xAxis": {"type": "value", "name": "Continuous yield change (bp)" if quote == "continuous" else "Nominal YTM change (bp)", "min": -width, "max": width},
            "yAxis": {"type": "value", "name": "Price change (%)", "scale": True},
            "series": {"Exact": np.column_stack([shifts, exact]).tolist(),
                       "Duration approximation": np.column_stack([shifts, approximate]).tolist(),
                       "Selected exact": [[shift_bps, selected_exact]],
                       "Selected approximation": [[shift_bps, selected_approximate]]},
            "seriesOptions": {"Duration approximation": {"lineStyle": {"type": "dashed"}},
                              "Selected exact": {"type": "scatter", "symbol": "diamond", "symbolSize": 11},
                              "Selected approximation": {"type": "scatter", "symbolSize": 9}},
        },
    }
    convention = "continuous annual yield" if quote == "continuous" else f"nominal annual YTM compounded {coupons_per_year} times/year"
    error = selected_price - (price - measures["Dollar duration"] * shift_bps / 10000)
    text = (f"Full price: {price:.6f}; {convention}: {ytm:.4%}.\n"
            f"Macaulay duration: {mac:.6f} years; modified duration: {modified:.6f} years.\n"
            f"Selected yield shift: {shift_bps:+g} bp. Exact price change: {selected_exact:+.6f}%; "
            f"duration approximation: {selected_approximate:+.6f}%.\n"
            f"DV01 for this quote: {measures['DV01']:.6f}; exact minus linear price: {error:+.6f}.\n"
            "Payment dates and amounts are fixed. Duration is a weighted-average time, not a payback date. "
            "Modified duration is a local slope; finite shifts introduce approximation error.")
    _publish_echarts(plots, text)


# ---------------------------------------------------------------------------------
# Liability driven strategies
# ---------------------------------------------------------------------------------
def duration_match_weight(d1, d2, d_liab):
    """Long-only market-value weights matching a target duration in common units.

    Durations must be measured against the same rate convention. Distinct
    asset durations must bracket the liability duration; do not silently
    replace an infeasible match with a leveraged or short position.
    """
    durations = np.asarray([d1, d2, d_liab], dtype=float)
    if durations.shape != (3,) or not np.isfinite(durations).all() or (durations < 0).any():
        raise ValueError("Durations must be finite, nonnegative scalars")
    if np.isclose(d1, d2, atol=1e-12, rtol=0):
        raise ValueError("Distinct asset durations are required for a unique two-bond match")
    weight = float((d_liab - d2) / (d1 - d2))
    if weight < -1e-12 or weight > 1 + 1e-12:
        raise ValueError("The target duration must lie between the two asset durations for a long-only match")
    weight = float(np.clip(weight, 0, 1))  # Roundoff at a feasible endpoint only.
    return weight, 1 - weight


def show_duration_matching_echart(asset_value=130000, discount_rate=0.04, short_maturity=10,
                                  long_maturity=20, short_frequency=1, long_frequency=1, liability_delay=0):
    """Match two 5%-coupon bonds against two 100,000-dollar obligations.

    All dates are years and all discount rates are effective annual rates.
    Purchase at the selected base curve; hold bond quantities fixed when
    repricing. The second panel compares contractual cash flows, not wealth.
    """
    if not np.isfinite([asset_value, discount_rate, liability_delay]).all() or asset_value <= 0 or liability_delay < 0:
        raise ValueError("Require positive finite capital, a finite rate, and a nonnegative liability delay")
    liabilities = pd.DataFrame({"Liability": [100000.0, 100000.0]}, index=[10 + liability_delay, 12 + liability_delay])
    short = bond_cash_flows(1000, short_maturity, 0.05, short_frequency).rename(columns={0: "Short"})
    long = bond_cash_flows(1000, long_maturity, 0.05, long_frequency).rename(columns={0: "Long"})
    short.index = short.index / short_frequency
    long.index = long.index / long_frequency
    bonds = pd.concat([short, long], axis=1).fillna(0).sort_index()
    prices = present_value(bonds, discount_rate)
    durations = mac_duration(bonds, discount_rate)
    liability_pv = float(present_value(liabilities, discount_rate).iloc[0])
    liability_duration = mac_duration(liabilities, discount_rate)
    try:
        weights = duration_match_weight(durations["Short"], durations["Long"], liability_duration)
    except ValueError as error:
        _publish_echarts({}, f"No unique long-only duration match. {error}\n"
                         f"Short: {durations['Short']:.6f}; long: {durations['Long']:.6f}; "
                         f"liability: {liability_duration:.6f} years. Change the maturities or liability delay.")
        return
    units = pd.Series(weights, index=bonds.columns) * asset_value / prices
    matched = bonds.mul(units, axis=1).sum(axis=1).to_frame("Matched")
    portfolios = {"Short only": short * (asset_value / prices["Short"]),
                  "Long only": long * (asset_value / prices["Long"]), "Duration matched": matched}
    rates = np.unique(np.append(np.linspace(max(-0.99, discount_rate - 0.03), discount_rate + 0.03, 121), discount_rate))
    liability_values = present_value(liabilities, rates)
    ratios = {name: np.column_stack([rates * 100, present_value(flows, rates) / liability_values]).tolist()
              for name, flows in portfolios.items()}
    ratios["Target"] = [[rates[0] * 100, 1], [rates[-1] * 100, 1]]
    ratios["Initial matched"] = [[discount_rate * 100, asset_value / liability_pv]]
    payments = pd.concat([matched, liabilities], axis=1).fillna(0).sort_index()
    plots = {
        "matchingFunding": {
            "type": "line", "title": "Fixed Holdings: Funding Ratios Under Parallel Rate Changes",
            "xAxis": {"type": "value", "name": "Effective annual rate (%)",
                      "min": round(float(rates[0] * 100), 10), "max": round(float(rates[-1] * 100), 10)},
            "yAxis": {"type": "value", "name": "Funding ratio", "scale": True}, "series": ratios,
            "seriesOptions": {"Initial matched": {"type": "scatter", "symbol": "diamond", "symbolSize": 11}},
        },
        "matchingPayments": {
            "type": "bar", "title": "Duration Matching Does Not Match Every Payment",
            "xAxis": {"type": "value", "name": "Payment year", "min": 0, "max": float(payments.index.max()) + 0.5,
                      "axisLabel": {"showMaxLabel": False}},
            "yAxis": {"type": "value", "name": "Contractual payment (thousand dollars)", "min": 0},
            "series": {name: np.column_stack([payments.index, payments[name] / 1000]).tolist() for name in payments},
        },
    }
    text = (f"Base effective annual rate: {discount_rate:.2%}. Liability PV: {liability_pv:,.2f}; assets: {asset_value:,.2f}.\n"
            f"Initial funding ratio: {asset_value / liability_pv:.6f}; PV surplus / deficit: {asset_value - liability_pv:,.2f}.\n"
            f"Market-value weights: short {weights[0]:.4%}, long {weights[1]:.4%}. "
            f"Bond quantities: {units['Short']:.6f}, {units['Long']:.6f}.\n"
            f"Asset duration: {mac_duration(matched, discount_rate):.6f}; liability duration: {liability_duration:.6f} years.\n"
            "Holdings are fixed across the rate scenarios. Duration matching makes the funding ratio locally flat; "
            "it neither supplies missing capital nor guarantees payment under arbitrary yield-curve changes.")
    _publish_echarts(plots, text)


def _ldi_return_frame(rets):
    """Complete simple returns with unique, chronological dates and scenario labels."""
    if (not isinstance(rets, pd.DataFrame) or rets.empty or not rets.index.is_unique
            or not rets.index.is_monotonic_increasing or not rets.columns.is_unique):
        raise ValueError("Returns require a nonempty DataFrame with ordered unique dates and unique scenarios")
    frame = rets.astype(float)
    if not np.isfinite(frame.to_numpy()).all() or (frame.to_numpy() < -1).any():
        raise ValueError("Simple returns must be complete, finite, and at least -1")
    return frame


def ldi_mixer(psp_rets, lhp_rets, allocator, **kwargs):
    """Mix aligned SIMPLE returns using beginning-of-interval long-only weights.

    The allocator returns a labeled weight frame for the first sleeve and must
    use only information available before each return. A fixed weight implies
    periodic rebalancing, not buy-and-hold. No fees or external cash flows.
    """
    psp = _ldi_return_frame(psp_rets)
    lhp = _ldi_return_frame(lhp_rets)
    if not psp.index.equals(lhp.index) or not psp.columns.equals(lhp.columns):
        raise ValueError("Return dates and scenario labels must match in the same order")
    weights = allocator(psp, lhp, **kwargs)
    if (not isinstance(weights, pd.DataFrame) or not weights.index.equals(psp.index)
            or not weights.columns.equals(psp.columns)):
        raise ValueError("Allocator weights must match the return dates and scenarios")
    weights = weights.astype(float)
    if not np.isfinite(weights.to_numpy()).all() or ((weights < 0) | (weights > 1)).to_numpy().any():
        raise ValueError("Long-only allocation weights must be finite and between zero and one")
    return weights * psp + (1 - weights) * lhp


def ldi_fixed_allocator(psp_rets, lhp_rets, w1, **kwargs):
    """Constant beginning-period fraction in the first sleeve; reset each interval."""
    if not np.isscalar(w1) or not np.isfinite(w1) or not 0 <= w1 <= 1:
        raise ValueError("The fixed weight must be a finite scalar between zero and one")
    return pd.DataFrame(data=w1, index=psp_rets.index, columns=psp_rets.columns)


def simulate_psp_lhp(n_years=10, n_scenarios=1000, periods_per_year=2, mu=0.07,
                     sigma=0.10, rate_sigma=0.02, short_weight=0.6, psp_weight=0.7, seed=42):
    """Paired illustrative stock/bond scenarios for fixed-mix comparisons.

    Rate dynamics equal pricing dynamics (zero modeled short-rate risk premium).
    Equity total-return GBM is a real-world scenario assumption, with independent
    stock/rate shocks. These parameters are not calibrated forecasts. The short
    bond matures at year 10, the long bond at year 20; stop no later than year 10.
    """
    if not np.isfinite(n_years) or not 0 < n_years <= 10:
        raise ValueError("The experiment horizon must be positive and no longer than the short bond's 10 years")
    _compounding_inputs(0.0, periods_per_year)
    if periods_per_year is None or periods_per_year % 2:
        raise ValueError("Observations must include the semiannual coupon dates")
    rate_seed, stock_seed = np.random.SeedSequence(seed).spawn(2)
    rates, _ = simulate_cir(n_years, n_scenarios, a=0.05, b=0.03, sigma=rate_sigma,
                            periods_per_year=periods_per_year, r0=0.03, seed=rate_seed)
    bond_prices, bond_returns_by_maturity = {}, {}
    for maturity, coupon in ((10, 0.028), (20, 0.035)):
        prices = cir_bond_price(rates, principal=100, maturity=maturity, coupon_rate=coupon,
                                coupons_per_year=2, periods_per_year=periods_per_year,
                                a=0.05, b=0.03, sigma=rate_sigma)
        bond_prices[maturity] = prices
        bond_returns_by_maturity[maturity] = bond_returns(100, prices, coupon, 2, periods_per_year, maturity)
    bonds = ldi_mixer(bond_returns_by_maturity[10], bond_returns_by_maturity[20], ldi_fixed_allocator, w1=short_weight)
    stock_prices, stock_logs = simulate_gbm_from_prices(n_years, n_scenarios, mu, sigma,
                                                       periods_per_year, start=100, seed=stock_seed)
    stocks = np.expm1(stock_logs)
    mixed = ldi_mixer(stocks, bonds, ldi_fixed_allocator, w1=psp_weight)
    return {"Rates": rates, "Short prices": bond_prices[10], "Long prices": bond_prices[20],
            "Short returns": bond_returns_by_maturity[10], "Long returns": bond_returns_by_maturity[20],
            "Stock prices": stock_prices, "Stock log returns": stock_logs,
            "Stocks": stocks, "Bonds": bonds, "Fixed mix": mixed}


def show_psp_lhp_echart(n_years=10, n_scenarios=1000, periods_per_year=2, mu=0.07,
                       sigma=0.10, rate_sigma=0.02, short_weight=0.6, psp_weight=0.7, floor=0.8, seed=42):
    """Paired wealth and terminal-outcome charts for a periodically rebalanced mix."""
    sample = simulate_psp_lhp(n_years, n_scenarios, periods_per_year, mu, sigma,
                              rate_sigma, short_weight, psp_weight, seed)
    stats = pd.concat([summary_stats_terminal(sample[name], floor, periods_per_year, name)
                       for name in ("Stocks", "Bonds", "Fixed mix")], axis=1)
    times = np.arange(len(sample["Stocks"]) + 1) / periods_per_year
    paths, terminal = {}, {}
    for name in ("Stocks", "Bonds", "Fixed mix"):
        wealth = np.vstack([np.ones(n_scenarios), (1 + sample[name]).cumprod().to_numpy()])
        paths[f"{name} median"] = np.column_stack([times, np.median(wealth, axis=1)]).tolist()
        terminal[name] = wealth[-1]
        if name == "Fixed mix":
            for percentile in (5, 95):
                paths[f"Mix {percentile}th percentile"] = np.column_stack([times, np.percentile(wealth, percentile, axis=1)]).tolist()
    paths["Terminal threshold"] = [[0, floor], [n_years, floor]]
    xmin = max(0.0, min(floor, *(values.min() for values in terminal.values())) * 0.95)
    xmax = max(1, floor, *(values.max() for values in terminal.values())) * 1.05
    cdfs = {}
    heights = np.column_stack([np.arange(n_scenarios), np.arange(1, n_scenarios + 1)]).ravel() * 100 / n_scenarios
    for name, values in terminal.items():
        points = np.column_stack([np.repeat(np.sort(values), 2), heights])
        cdfs[name] = np.vstack([[xmin, 0], points, [xmax, 100]]).tolist()
    cdfs["Terminal threshold"] = [[floor, 0], [floor, 100]]
    threshold_style = {"Terminal threshold": {"lineStyle": {"type": "dashed"}}}
    plots = {
        "pspLhpWealth": {"type": "line", "title": "Paired Scenarios: Wealth per Unit Invested",
                         "xAxis": {"type": "value", "name": "Elapsed years", "min": 0, "max": n_years},
                         "yAxis": {"type": "value", "name": "Wealth per initial 1", "min": 0},
                         "series": paths, "seriesOptions": threshold_style},
        "pspLhpTerminal": {"type": "line", "title": "Terminal Wealth: Empirical Cumulative Distributions",
                            "xAxis": {"type": "value", "name": "Terminal wealth per initial 1", "min": xmin, "max": xmax},
                            "yAxis": {"type": "value", "name": "Scenarios at or below x (%)", "min": 0, "max": 100},
                            "series": cdfs, "seriesOptions": threshold_style},
    }
    misses = int((terminal["Fixed mix"] < floor - 1e-10 * max(1, floor)).sum())
    low, high = _binomial_interval(misses, n_scenarios)
    display_stats = stats.rename(index={"Mean ann. ret.": "Mean scenario CAGR (%)", "Mean wealth std": "Terminal wealth std",
                                       "Prob breach": "Terminal shortfalls (%)", "Exp shortfall": "Conditional shortfall"})
    display_stats.loc[["Mean scenario CAGR (%)", "Terminal shortfalls (%)"]] *= 100
    text = (f"Uncalibrated scenarios; seed={seed}. Zero modeled short-rate risk premium; independent stock/rate shocks.\n"
            f"Rebalance {periods_per_year} times/year: PSP {psp_weight:.1%}; bond sleeve short/long {short_weight:.1%}/{1-short_weight:.1%}.\n"
            "Medians and percentiles are pointwise summaries, not individual paths. The threshold is tested at the experiment horizon only.\n"
            + display_stats.to_string(float_format=lambda value: f"{value:.4f}")
            + f"\nMixed terminal shortfalls: {misses}/{n_scenarios}; 95% Wilson interval {low:.2%} to {high:.2%}. "
            "This interval reflects Monte Carlo sampling, not model uncertainty. CDF includes equality; shortfall means below the threshold.")
    _publish_echarts(plots, text)


def ldi_glidepath_allocator(psp_rets, lhp_rets, start=1, end=0):
    """Calendar schedule of beginning-interval PSP weights on equally spaced dates.

    start applies to the first return and end to the last, not to a trade after
    the horizon. For one interval use start alone. The same schedule applies
    to every scenario; no realized return determines an allocation.
    """
    psp, lhp = _ldi_return_frame(psp_rets), _ldi_return_frame(lhp_rets)
    if not psp.index.equals(lhp.index) or not psp.columns.equals(lhp.columns):
        raise ValueError("Return dates and scenario labels must match in the same order")
    for weight in (start, end):
        if not np.isscalar(weight) or not np.isfinite(weight) or not 0 <= weight <= 1:
            raise ValueError("Glide-path endpoints must be finite scalars between zero and one")
    schedule = np.linspace(start, end, len(psp))
    return pd.DataFrame(np.repeat(schedule[:, None], psp.shape[1], axis=1), index=psp.index, columns=psp.columns)


def show_glidepath_echart(start=0.8, end=0.2, n_years=10, n_scenarios=1000,
                          periods_per_year=2, floor=0.8, seed=42):
    """Compare a scheduled glide path with fixed 70% and mean-target allocations.

    Reuse the baseline stock/CIR scenario model and bond sleeve. Targets apply
    before each interval; step lines depict targets, not realized weights.
    """
    sample = simulate_psp_lhp(n_years=n_years, n_scenarios=n_scenarios,
                              periods_per_year=periods_per_year, seed=seed)
    stocks, bonds = sample["Stocks"], sample["Bonds"]
    weights = ldi_glidepath_allocator(stocks, bonds, start, end)
    average = float(weights.iloc[:, 0].mean())
    glide = ldi_mixer(stocks, bonds, ldi_glidepath_allocator, start=start, end=end)
    constant = ldi_mixer(stocks, bonds, ldi_fixed_allocator, w1=average)
    returns = {"Glide path": glide, "Constant mean target": constant, "Fixed 70/30": sample["Fixed mix"]}
    times = np.arange(len(stocks) + 1) / periods_per_year
    targets = np.r_[weights.iloc[:, 0].to_numpy(), weights.iloc[-1, 0]] * 100
    wealth_series, terminal = {}, {}
    for name, rets in returns.items():
        wealth = np.vstack([np.ones(n_scenarios), (1 + rets).cumprod().to_numpy()])
        wealth_series[name] = np.column_stack([times, np.median(wealth, axis=1)]).tolist()
        terminal[name] = wealth[-1]
    stats = pd.concat([summary_stats_terminal(rets, floor, periods_per_year, name) for name, rets in returns.items()], axis=1)
    stats = stats.rename(index={"Mean ann. ret.": "Mean scenario CAGR (%)", "Mean wealth std": "Terminal wealth std",
                               "Prob breach": "Terminal shortfalls (%)", "Exp shortfall": "Conditional shortfall"})
    stats.loc[["Mean scenario CAGR (%)", "Terminal shortfalls (%)"]] *= 100
    plots = {
        "glideTargets": {
            "type": "line", "title": "Glide Path: Beginning-Period Stock Targets",
            "xAxis": {"type": "value", "name": "Elapsed years", "min": 0, "max": n_years},
            "yAxis": {"type": "value", "name": "Target stock allocation (%)", "min": 0, "max": 100},
            "series": {"Glide path": np.column_stack([times, targets]).tolist(),
                       "Constant mean target": [[0, average * 100], [n_years, average * 100]],
                       "Fixed 70/30": [[0, 70], [n_years, 70]]},
            "seriesOptions": {"Glide path": {"step": "end"}},
        },
        "glideWealth": {
            "type": "line", "title": "Same Scenarios: Pointwise Median Wealth",
            "xAxis": {"type": "value", "name": "Elapsed years", "min": 0, "max": n_years},
            "yAxis": {"type": "value", "name": "Wealth per initial 1", "min": 0},
            "series": {**wealth_series, "Terminal threshold": [[0, floor], [n_years, floor]]},
            "seriesOptions": {"Terminal threshold": {"lineStyle": {"type": "dashed"}}},
        },
    }
    difference = terminal["Glide path"] - terminal["Constant mean target"]
    text = (f"Uncalibrated baseline stock/CIR model; seed={seed}; shared scenarios and a 60/40 bond sleeve.\n"
            f"First stock target {start:.1%}; last applied target {weights.iloc[-1, 0]:.1%} at year {times[-2]:g}; "
            f"mean target {average:.1%}. A single interval uses the start target only.\n"
            + stats.to_string(float_format=lambda value: f"{value:.4f}")
            + f"\nPaired terminal difference (glide minus constant mean target): mean {difference.mean():+.6f}; "
            f"glide higher in {(difference > 1e-10).mean():.1%} of scenarios.\n"
            "Equal average target weight does not imply equal risk. Median curves are not individual paths. "
            "The threshold measures terminal outcomes; the schedule does not guarantee a floor.")
    _publish_echarts(plots, text)


def ldi_floor_allocator(psp_rets, lhp_rets, zcb_price, floor, m=3):
    """Beginning-interval stock weights; pass the FULL unit-ZCB price path.

    Prices include time zero and redemption, one more row than returns.
    lhp_rets must be this bond's holding-period returns. Starting wealth is 1;
    floor is the promised amount at maturity. For account histories and
    undefined returns after depletion, use ldi_floor_backtest directly.
    """
    return ldi_floor_backtest(psp_rets, lhp_rets, zcb_price, floor, m)["Risky allocation"]


def ldi_floor_backtest(psp_rets, lhp_rets, zcb_price, floor=0.8, m=3):
    """Self-financing stock/ZCB policy with contemporaneous floor PV f*P(t,T).

    Choose exposure from W_t and P_t BEFORE applying interval t+1 returns.
    Nonnegative stock values and an initially funded, default-free matching
    bond support the m<=1 reserve argument; m>1 can breach between rebalances.
    Depleted accounts remain zero and subsequent account returns are NaN.
    """
    risky, hedge = _ldi_return_frame(psp_rets), _ldi_return_frame(lhp_rets)
    if not risky.index.equals(hedge.index) or not risky.columns.equals(hedge.columns):
        raise ValueError("Return dates and scenario labels must match in the same order")
    if (not isinstance(zcb_price, pd.DataFrame) or len(zcb_price) != len(risky) + 1
            or not zcb_price.index.is_unique or not zcb_price.index.is_monotonic_increasing
            or not zcb_price.index[1:].equals(risky.index) or not zcb_price.columns.equals(risky.columns)):
        raise ValueError("Unit bond prices must include time zero and every return endpoint, with matching scenarios")
    prices = zcb_price.to_numpy(dtype=float)
    if not np.isfinite(prices).all() or (prices <= 0).any() or not np.allclose(prices[-1], 1, atol=1e-12, rtol=0):
        raise ValueError("Unit bond prices must be finite and positive, with redemption value one")
    if not np.allclose(1 + hedge.to_numpy(), prices[1:] / prices[:-1], atol=1e-12, rtol=1e-10):
        raise ValueError("Hedge returns must match the supplied zero-coupon bond price path")
    for value in (floor, m):
        if not np.isscalar(value) or not np.isfinite(value) or value < 0:
            raise ValueError("The terminal floor and multiplier must be finite nonnegative scalars")
    floors = floor * prices
    if not np.isfinite(floors).all():
        raise ValueError("Floor present values must be finite")
    wealth = np.ones_like(prices)
    weights = np.zeros(risky.shape)
    cushions = np.zeros(risky.shape)
    returns = np.full(risky.shape, np.nan)
    risky_values, hedge_values = risky.to_numpy(), hedge.to_numpy()
    for step in range(len(risky)):
        before = wealth[step]
        cushions[step] = before - floors[step]
        fraction = np.divide(cushions[step], before, out=np.zeros_like(before), where=before > 0)
        weights[step] = np.clip(m * fraction, 0, 1)
        with np.errstate(over="ignore", invalid="ignore"):
            wealth[step + 1] = before * (weights[step] * (1 + risky_values[step]) + (1 - weights[step]) * (1 + hedge_values[step]))
        if not np.isfinite(wealth[step + 1]).all():
            raise ValueError("Account wealth is outside representable bounds")
        returns[step] = np.divide(wealth[step + 1], before, out=np.full_like(before, np.nan), where=before > 0) - 1
    result = {name: pd.DataFrame(values, index=risky.index, columns=risky.columns)
              for name, values in (("Returns", returns), ("Risky allocation", weights), ("Cushions", cushions))}
    for name, values in (("Wealth", wealth), ("Floor value", floors),
                         ("Floor breaches", wealth < floors - 1e-10 * np.maximum(1, floors))):
        result[name] = pd.DataFrame(values, index=zcb_price.index, columns=risky.columns)
    return result


def show_floor_echart(floor=0.8, m=1, n_years=10, n_scenarios=1000, periods_per_year=12,
                      sigma=0.15, scenario=1, seed=42):
    """Compare a terminal-floor policy with matching bonds and fixed 70/30.

    Use the uncalibrated, zero-rate-risk-premium CIR scenario assumption and
    independent stock shocks. The selected path is illustrative; statistics
    cover every scenario and distinguish sampled PV breaches from terminal misses.
    """
    rate_seed, stock_seed = np.random.SeedSequence(seed).spawn(2)
    _, prices = simulate_cir(n_years, n_scenarios, a=0.05, b=0.03, sigma=0.02,
                             periods_per_year=periods_per_year, r0=0.03, seed=rate_seed)
    _, logs = simulate_gbm_from_prices(n_years, n_scenarios, mu=0.07, sigma=sigma,
                                       periods_per_year=periods_per_year, seed=stock_seed)
    stocks, bonds = np.expm1(logs), prices.pct_change(fill_method=None).iloc[1:]
    result = ldi_floor_backtest(stocks, bonds, prices, floor, m)
    if not isinstance(scenario, (int, np.integer)) or isinstance(scenario, (bool, np.bool_)) or not 1 <= scenario <= n_scenarios:
        raise ValueError("The selected scenario must be an integer between one and n_scenarios")
    fixed = ldi_mixer(stocks, bonds, ldi_fixed_allocator, w1=0.7)
    strategies = {"Floor allocator": result["Returns"], "Fixed 70/30": fixed, "ZCB only": bonds, "Stocks": stocks}
    stats = pd.concat([summary_stats_terminal(rets, floor, periods_per_year, name) for name, rets in strategies.items()], axis=1)
    stats = stats.rename(index={"Mean ann. ret.": "Mean scenario CAGR (%)", "Mean wealth std": "Terminal wealth std",
                               "Prob breach": "Terminal shortfalls (%)", "Exp shortfall": "Conditional shortfall"})
    stats.loc[["Mean scenario CAGR (%)", "Terminal shortfalls (%)"]] *= 100
    column = scenario - 1
    times = np.arange(len(prices)) / periods_per_year
    values = {"Floor allocator": result["Wealth"].iloc[:, column].to_numpy(),
              "Fixed 70/30": np.r_[1, (1 + fixed.iloc[:, column]).cumprod()],
              "ZCB only": prices.iloc[:, column].to_numpy() / prices.iloc[0, column],
              "Floor PV": result["Floor value"].iloc[:, column].to_numpy()}
    applied = result["Risky allocation"].iloc[:, column].to_numpy()
    plots = {
        "floorWealth": {"type": "line", "title": f"Scenario {scenario}: Wealth and Current Floor Value",
                        "xAxis": {"type": "value", "name": "Elapsed years", "min": 0, "max": n_years},
                        "yAxis": {"type": "value", "name": "Value per initial 1", "min": 0},
                        "series": {name: np.column_stack([times, path]).tolist() for name, path in values.items()}},
        "floorWeights": {"type": "line", "title": f"Scenario {scenario}: Beginning-Period Stock Allocation",
                         "xAxis": {"type": "value", "name": "Elapsed years", "min": 0, "max": n_years},
                         "yAxis": {"type": "value", "name": "Stock allocation (%)", "min": 0, "max": 100},
                         "series": {"Floor allocator": np.column_stack([times, np.r_[applied, applied[-1]] * 100]).tolist(),
                                    "Fixed 70/30": [[0, 70], [n_years, 70]], "ZCB only": [[0, 0], [n_years, 0]]},
                         "seriesOptions": {"Floor allocator": {"step": "end"}}},
    }
    cost = float(result["Floor value"].iloc[0, 0])
    status = "initially funded" if cost <= 1 + 1e-10 else "initially underfunded; the promise cannot be locked in with this capital"
    breaches = int(result["Floor breaches"].any(axis=0).sum())
    text = (f"Uncalibrated paired scenarios; seed={seed}; zero modeled short-rate risk premium and independent stock shocks.\n"
            f"Terminal promise: {floor:.4f}; initial matching cost: {cost:.6f}; {status}. Multiplier: {m:g}.\n"
            f"Floor-allocator sampled PV breaches (including time zero): {breaches}/{n_scenarios}.\n"
            + stats.to_string(float_format=lambda value: f"{value:.4f}")
            + "\nDecisions use beginning prices. With an initially funded default-free matching bond, nonnegative stock values, "
            "and no costs, m<=1 retains the floor reserve; larger multipliers expose it to gap risk. "
            "The plotted path is one scenario, not a quantile or a forecast.")
    _publish_echarts(plots, text)


def ldi_drawdown_allocator(psp_rets, lhp_rets, maxdd=0.2):
    """Beginning-period weights for the high-water rule m=1/maxdd.

    maxdd is a requested drawdown limit, not a guarantee. Each account uses
    its own prior wealth peak. Use ldi_drawdown_backtest for full diagnostics.
    """
    return ldi_drawdown_backtest(psp_rets, lhp_rets, maxdd)["Risky allocation"]


def ldi_drawdown_backtest(psp_rets, lhp_rets, maxdd=0.2):
    """Reuse CPPI's causal high-water accounting, starting each account at 1.

    All frames retain return-endpoint labels. 'Prior peaks', 'Floor value',
    and weights are beginning-period values; 'Wealth', 'Peaks', 'Next floor',
    and negative 'Drawdown' are ending values. Initial wealth is included in
    the peak calculation. Returns after depletion are undefined (NaN).
    """
    risky, defensive = _ldi_return_frame(psp_rets), _ldi_return_frame(lhp_rets)
    if not np.isscalar(maxdd) or not np.isfinite(maxdd) or not 0 < maxdd <= 1:
        raise ValueError("The requested drawdown must be greater than zero and at most one")
    account = cppi(risky, safe_rets=defensive, start_value=1, drawdown=maxdd)
    wealth = account["CPPI wealth"]
    if not np.isfinite(wealth.to_numpy()).all():
        raise ValueError("Account wealth is outside representable bounds")
    all_values = np.vstack([np.ones(risky.shape[1]), wealth.to_numpy()])
    peaks = pd.DataFrame(np.maximum.accumulate(all_values, axis=0)[1:], index=risky.index, columns=risky.columns)
    drawdowns = wealth / peaks - 1
    return {"Wealth": wealth, "Returns": account["CPPI returns"], "Risky allocation": account["Risky allocation"],
            "Prior peaks": account["Peaks"], "Floor value": account["Floor value"],
            "Peaks": peaks, "Next floor": (1 - maxdd) * peaks, "Drawdown": drawdowns,
            "Drawdown breaches": drawdowns < -maxdd - 1e-10, "m": account["m"]}


def show_drawdown_echart(maxdd=0.2, hedge="cash", n_years=10, n_scenarios=1000,
                         periods_per_year=12, sigma=0.15, scenario=1, seed=42):
    """Compare long-ZCB and rolled-cash defensive sleeves on paired stock paths."""
    if hedge not in ("cash", "zcb"):
        raise ValueError("The displayed hedge must be cash or zcb")
    rate_seed, stock_seed = np.random.SeedSequence(seed).spawn(2)
    rates, prices = simulate_cir(n_years, n_scenarios, a=0.05, b=0.03, sigma=0.02,
                                 periods_per_year=periods_per_year, r0=0.03, seed=rate_seed)
    _, logs = simulate_gbm_from_prices(n_years, n_scenarios, mu=0.07, sigma=sigma,
                                       periods_per_year=periods_per_year, seed=stock_seed)
    stocks = np.expm1(logs)
    cash_wealth = cir_cash_wealth(rates, a=0.05, b=0.03, sigma=0.02, periods_per_year=periods_per_year)
    defensive = {"cash": cash_wealth.pct_change(fill_method=None).iloc[1:],
                 "zcb": prices.pct_change(fill_method=None).iloc[1:]}
    runs = {name: ldi_drawdown_backtest(stocks, rets, maxdd) for name, rets in defensive.items()}
    if not isinstance(scenario, (int, np.integer)) or isinstance(scenario, (bool, np.bool_)) or not 1 <= scenario <= n_scenarios:
        raise ValueError("The selected scenario must be an integer between one and n_scenarios")
    selected, column = runs[hedge], scenario - 1
    times = np.arange(len(stocks) + 1) / periods_per_year
    wealth = np.r_[1, selected["Wealth"].iloc[:, column]]
    peaks = np.r_[1, selected["Peaks"].iloc[:, column]]
    drawdown_series = {f"Policy + {name.upper() if name == 'zcb' else name}":
                      np.column_stack([times, np.r_[0, run["Drawdown"].iloc[:, column]] * 100]).tolist()
                      for name, run in runs.items()}
    stock_wealth = np.vstack([np.ones(n_scenarios), (1 + stocks).cumprod().to_numpy()])
    stock_drawdowns = stock_wealth / np.maximum.accumulate(stock_wealth, axis=0) - 1
    drawdown_series["Stocks"] = np.column_stack([times, stock_drawdowns[:, column] * 100]).tolist()
    drawdown_series["Drawdown limit"] = [[0, -maxdd * 100], [n_years, -maxdd * 100]]
    plots = {
        "drawdownWealth": {"type": "line", "title": f"Scenario {scenario}: {hedge.upper()} Policy Wealth and Peak",
                           "xAxis": {"type": "value", "name": "Elapsed years", "min": 0, "max": n_years},
                           "yAxis": {"type": "value", "name": "Value per initial 1", "min": 0},
                           "series": {"Policy wealth": np.column_stack([times, wealth]).tolist(),
                                      "High-water mark": np.column_stack([times, peaks]).tolist(),
                                      "High-water floor": np.column_stack([times, (1 - maxdd) * peaks]).tolist()},
                           "seriesOptions": {"High-water floor": {"step": "end"}}},
        "drawdownLoss": {"type": "line", "title": f"Scenario {scenario}: Drawdowns from Each Strategy's Own Peak",
                         "xAxis": {"type": "value", "name": "Elapsed years", "min": 0, "max": n_years},
                         "yAxis": {"type": "value", "name": "Drawdown (%)", "max": 0}, "series": drawdown_series},
    }
    stats = pd.DataFrame({name: {
        "Mean terminal wealth": run["Wealth"].iloc[-1].mean(),
        "Mean worst drawdown (%)": run["Drawdown"].min().mean() * 100,
        "Paths beyond limit (%)": run["Drawdown breaches"].any().mean() * 100,
        "Terminal below 0.8 (%)": (run["Wealth"].iloc[-1] < 0.8 - 1e-10).mean() * 100,
    } for name, run in runs.items()})
    text = (f"Uncalibrated paired stock/CIR scenarios; seed={seed}; independent shocks and zero modeled short-rate risk premium.\n"
            f"Requested drawdown: {maxdd:.1%}; rule multiplier: {1 / maxdd:g}. The initial stock weight is 100%.\n"
            + stats.to_string(float_format=lambda value: f"{value:.4f}")
            + "\nPeaks include initial wealth. Decisions use prior peaks; the plotted updated floor is the next decision's reference. "
            "Rolled cash uses the same CIR curve. Its nonnegative returns at roll dates do not remove stock gap risk. "
            "Terminal wealth below 0.8 and drawdowns beyond the requested limit are different events.")
    _publish_echarts(plots, text)


def historical_drawdown(start_year=1990, end_year=2018, maxdd=0.2, cash_rate=0.03):
    """Restart a monthly policy on the bundled lagged 30-industry proxy.

    Cash is a constant effective-annual assumption, not historical bill data.
    Require complete calendar years. Initial wealth is one immediately before
    the first selected return; lagged industry weights are computed beforehand.
    """
    for year in (start_year, end_year):
        if not isinstance(year, (int, np.integer)) or isinstance(year, (bool, np.bool_)):
            raise ValueError("Window years must be integers")
    if start_year > end_year:
        raise ValueError("The start year cannot exceed the end year")
    if not np.isscalar(cash_rate) or not np.isfinite(cash_rate) or cash_rate <= -1:
        raise ValueError("The assumed effective annual cash rate must exceed -1")
    proxy = get_total_market_index_returns()
    begin, end = pd.Period(year=start_year, month=1, freq="M"), pd.Period(year=end_year, month=12, freq="M")
    market = proxy.loc[begin:end].to_frame("Market proxy")
    if len(market) != 12 * (end_year - start_year + 1) or market.index[0] != begin or market.index[-1] != end:
        raise ValueError("The requested whole-year window is not fully covered by the bundled snapshot")
    monthly_cash = np.expm1(np.log1p(cash_rate) / 12)
    cash = pd.DataFrame(monthly_cash, index=market.index, columns=market.columns)
    policy = ldi_drawdown_backtest(market, cash, maxdd)
    fixed = ldi_mixer(market, cash, ldi_fixed_allocator, w1=0.7)
    returns = pd.concat([market.iloc[:, 0], policy["Returns"].iloc[:, 0].rename("Drawdown policy"),
                         fixed.iloc[:, 0].rename("Fixed 70/30"), cash.iloc[:, 0].rename("Assumed cash")], axis=1)
    dates = market.index.insert(0, market.index[0] - 1)
    wealth = pd.DataFrame(np.vstack([np.ones(returns.shape[1]), (1 + returns).cumprod().to_numpy()]),
                          index=dates, columns=returns.columns)
    drawdowns = wealth / wealth.cummax() - 1
    stats = pd.DataFrame({"CAGR (%)": annualize_rets(returns, 12) * 100,
                          "Annualized vol (%)": annualize_vol(returns, 12) * 100,
                          "Sharpe vs assumed cash": sharpe_ratio(returns, cash_rate, 12),
                          "Worst drawdown (%)": drawdowns.min() * 100,
                          "Months beyond limit": (drawdowns < -maxdd - 1e-10).sum()})
    return {"Market returns": market, "Cash returns": cash, "Policy": policy,
            "Returns": returns, "Wealth": wealth, "Drawdown": drawdowns, "Statistics": stats}


def show_historical_drawdown_echart(start_year=1990, end_year=2018, maxdd=0.2, cash_rate=0.03):
    """Historical proxy illustration with a synthetic cash benchmark and explicit reset date."""
    result = historical_drawdown(start_year, end_year, maxdd, cash_rate)
    wealth, drawdowns = result["Wealth"], result["Drawdown"]
    dates = wealth.index.astype(str).tolist()
    wealth_series = {name: wealth[name].tolist() for name in wealth}
    if maxdd < 1:
        wealth_series["High-water floor"] = ((1 - maxdd) * wealth["Drawdown policy"].cummax()).tolist()
    plots = {
        "dates": dates,
        "historicalWealth": {"type": "line", "title": "Historical Proxy: Wealth from the Same Starting Capital",
                             "xAxis": {"type": "category", "name": "Month"},
                             "yAxis": {"type": "log", "name": "Wealth per initial 1",
                                       "min": min(min(path) for path in wealth_series.values()) * 0.95,
                                       "max": max(max(path) for path in wealth_series.values()) * 1.05},
                             "series": wealth_series, "seriesOptions": {"High-water floor": {"step": "end"}}},
        "historicalDrawdowns": {"type": "line", "title": "Observed Month-End Drawdowns from Each Portfolio's Peak",
                                 "xAxis": {"type": "category", "name": "Month"},
                                 "yAxis": {"type": "value", "name": "Drawdown (%)", "max": 0},
                                 "series": {**{name: (drawdowns[name] * 100).tolist() for name in ("Market proxy", "Drawdown policy", "Fixed 70/30")},
                                            "Drawdown limit": [-maxdd * 100] * len(dates)}},
    }
    market = result["Market returns"]
    text = (f"Bundled, one-month-lagged 30-industry proxy: {market.index[0]} to {market.index[-1]}, {len(market)} monthly returns.\n"
            f"Restart wealth and peaks at 1 in {dates[0]}; that initial marker is not another return. "
            f"Assumed cash: {cash_rate:.2%} effective annually; requested drawdown: {maxdd:.1%}.\n"
            + result["Statistics"].to_string(float_format=lambda value: f"{value:.4f}", na_rep="—")
            + "\nOne observed history: counts of months are not forecast probabilities. Cash is hypothetical, "
            "costs are omitted, and lagging does not establish point-in-time investability. "
            "Changing the start year restarts the policy rather than zooming an existing account.")
    _publish_echarts(plots, text)


# ---------------------------------------------------------------------------------
# Factor and Style analysis
# ---------------------------------------------------------------------------------
def _factor_inputs(dep_var, exp_vars):
    """Validate one response and an explicitly aligned complete design matrix."""
    if isinstance(dep_var, pd.DataFrame):
        if dep_var.shape[1] != 1:
            raise ValueError("Expected exactly one dependent return series")
        dep_var = dep_var.iloc[:, 0]
    if isinstance(dep_var, pd.Series) and isinstance(exp_vars, pd.DataFrame):
        if not dep_var.index.equals(exp_vars.index):
            raise ValueError("Dependent returns and explanatory returns must have identical ordered dates")
    for obj in (dep_var, exp_vars):
        if isinstance(obj, (pd.Series, pd.DataFrame)):
            if not obj.index.is_unique or not obj.index.is_monotonic_increasing:
                raise ValueError("Observation dates must be unique and ordered")
    if isinstance(exp_vars, pd.DataFrame) and not exp_vars.columns.is_unique:
        raise ValueError("Explanatory variable names must be unique")
    y, x = np.asarray(dep_var, dtype=float), np.asarray(exp_vars, dtype=float)
    if y.ndim != 1 or x.ndim != 2 or not len(y) or x.shape[0] != len(y) or x.shape[1] == 0:
        raise ValueError("Expected one response and a nonempty matching two-dimensional design")
    if not np.isfinite(y).all() or not np.isfinite(x).all():
        raise ValueError("Regression observations must be complete and finite")
    return dep_var, exp_vars


def linear_regression(dep_var, exp_vars, alpha=True):
    """Fit OLS to complete aligned observations, adding an 'Alpha' intercept.

    Inputs share a horizon and units; excess-return conversion is the caller's
    responsibility. Preserve labeled results. Require an identified design
    and positive residual degrees of freedom. Default inference is classical
    OLS; use get_robustcov_results explicitly for another covariance estimator.
    """
    dep_var, exp_vars = _factor_inputs(dep_var, exp_vars)
    if alpha:
        if isinstance(exp_vars, pd.DataFrame):
            if "Alpha" in exp_vars.columns:
                raise ValueError("Alpha is reserved for the intercept; use alpha=False for an existing design")
            exp_vars = exp_vars.copy()
            exp_vars["Alpha"] = 1
        else:
            exp_vars = np.column_stack([exp_vars, np.ones(len(dep_var))])
    design = np.asarray(exp_vars, dtype=float)
    if len(dep_var) <= design.shape[1] or np.linalg.matrix_rank(design) < design.shape[1]:
        raise ValueError("OLS requires a full-rank design and positive residual degrees of freedom")
    return sm.OLS(dep_var, exp_vars).fit()


def capm_betas(ri, rm):
    """
    Returns the CAPM factor exposures beta for each asset in the ri pd.DataFrame,
    where rm is the pd.DataFrame (or pd.Series) of the market return (not excess return).
    The betas are defined as:
      beta_i = Cov(r_i, rm) / Var(rm)
    with r_i being the ith column (i.e., asset) of DataFrame ri.
    """
    market_var = (rm.std() ** 2)[0]
    betas = []
    for name in ri.columns:
        cov_im = pd.concat([ri[name], rm], axis=1).cov().iloc[0, 1]
        betas.append(cov_im / market_var)
    return pd.Series(betas, index=ri.columns)


def tracking_error(r_a, r_b):
    """Legacy Euclidean fit distance sqrt(sum(active_return**2)).

    This is not conventional tracking-error volatility (the sample standard
    deviation of active returns). It includes mean bias and scales with sqrt(n).
    """
    if isinstance(r_a, pd.Series) and isinstance(r_b, pd.Series) and not r_a.index.equals(r_b.index):
        raise ValueError("Return series must have identical ordered dates")
    a, b = np.asarray(r_a, dtype=float), np.asarray(r_b, dtype=float)
    if a.ndim != 1 or a.shape != b.shape or not a.size:
        raise ValueError("Expected two matching nonempty one-dimensional return series")
    if not np.isfinite(a).all() or not np.isfinite(b).all():
        raise ValueError("Return series must be complete and finite")
    return float(np.linalg.norm(a - b))


def style_analysis_tracking_error(weights, ref_r, bb_r):
    """
    Sharpe style analysis objective function.
    Returns the tracking error between the reference returns
    and a portfolio of building block returns held with given weights.
    """
    return tracking_error(ref_r, (weights * bb_r).sum(axis=1))


def style_analysis(dep_var, exp_vars):
    """Long-only fully invested least-squares return replication, no intercept.

    Minimize mean squared active return, not demeaned tracking-error variance.
    Require explicitly aligned complete pandas inputs. Correlated benchmarks
    can yield nonunique weights; a successful fit does not identify holdings.
    """
    if not isinstance(dep_var, (pd.Series, pd.DataFrame)) or not isinstance(exp_vars, pd.DataFrame):
        raise TypeError("Style analysis requires labeled pandas return inputs")
    dep_var, exp_vars = _factor_inputs(dep_var, exp_vars)
    y, x = dep_var.to_numpy(dtype=float), exp_vars.to_numpy(dtype=float)
    n = x.shape[1]
    init_guess = np.repeat(1 / n, n)
    # Scaling preserves the solution while keeping optimizer tolerances useful
    # for decimal monthly returns. The squared objective has a smooth gradient.
    scale = max(float(np.mean(y ** 2)), float(np.mean(x ** 2)), np.finfo(float).tiny)
    def objective(weights):
        return np.mean((x @ weights - y) ** 2) / scale
    def gradient(weights):
        return 2 * x.T @ (x @ weights - y) / (len(y) * scale)
    weights_const = {"type": "eq", "fun": lambda weights: 1 - np.sum(weights)}
    solution = minimize(
        objective,
        init_guess,
        jac=gradient,
        method="SLSQP",
        options={"disp": False, "ftol": 1e-12, "maxiter": 1000},
        constraints=(weights_const,),
        bounds=((0.0, 1.0),) * n,
    )
    weights = pd.Series(_checked_long_only_weights(solution, n), index=exp_vars.columns)
    return weights


# ---------------------------------------------------------------------------------
# Covariance matrix estimators
# ---------------------------------------------------------------------------------
def _covariance_returns(r):
    """Require a common complete sample so covariance estimates remain PSD."""
    if not isinstance(r, pd.DataFrame):
        raise TypeError("Expected a DataFrame of common-period returns")
    if len(r) < 2 or r.shape[1] == 0 or not r.columns.is_unique or not r.index.is_unique:
        raise ValueError("Covariance requires at least two observations and unique row/asset labels")
    if not np.isfinite(r.to_numpy(dtype=float)).all():
        raise ValueError("Covariance observations must be complete and finite on a common sample")
    return r.astype(float)


def sample_cov(r, **kwargs):
    """Sample covariance (ddof=1) at the input horizon; no pairwise deletion."""
    return _covariance_returns(r).cov()


def cc_cov(r, **kwargs):
    """Constant-correlation target retaining sample variances (ddof=1).

    Average distinct correlations among nonconstant assets. Constant assets
    have zero covariance rows/columns, not a fabricated correlation. With
    fewer than two variable assets the target is simply diagonal.
    """
    r = _covariance_returns(r)
    std = r.std(ddof=1)
    active = r.nunique() > 1
    std = std.where(active, 0.0)
    n = int(active.sum())
    rho = 0.0
    if n > 1:
        correlations = r.loc[:, active].corr().to_numpy()
        rho = correlations[np.triu_indices(n, k=1)].mean()
        rho = float(np.clip(rho, -1 / (n - 1), 1))
    covariance = rho * np.outer(std, std)
    np.fill_diagonal(covariance, std.to_numpy() ** 2)
    return pd.DataFrame(covariance, index=r.columns, columns=r.columns)


def shrinkage_cov(r, delta=0.5, **kwargs):
    """Convex blend delta*constant-correlation + (1-delta)*sample covariance.

    delta is specified by the caller, not an estimated Ledoit-Wolf intensity.
    Both estimates use the same complete sample and input return horizon.
    """
    if not np.isscalar(delta) or not np.isfinite(delta) or not 0 <= delta <= 1:
        raise ValueError("delta must be a finite fraction in [0, 1]")
    samp_cov = sample_cov(r, **kwargs)
    const_cov = cc_cov(r, **kwargs)
    return delta * const_cov + (1 - delta) * samp_cov


# ---------------------------------------------------------------------------------
# Back-test weigthing schemes
# ---------------------------------------------------------------------------------
def _capitalization_weights(r, cap_ws):
    """End-of-training-window cap weights, for the following return period."""
    if not isinstance(r, pd.DataFrame) or r.empty or not r.columns.is_unique:
        raise ValueError("Expected a nonempty return window with unique asset names")
    if (not isinstance(cap_ws, pd.DataFrame) or not cap_ws.index.is_unique
            or not cap_ws.columns.is_unique or set(cap_ws.columns) != set(r.columns)
            or r.index[-1] not in cap_ws.index):
        raise ValueError("Capitalization weights must cover the last training date and the same assets")
    cw = cap_ws.loc[r.index[-1], r.columns].astype(float)
    if not np.isfinite(cw).all() or (cw < 0).any() or not np.isclose(cw.sum(), 1, atol=1e-10, rtol=0):
        raise ValueError("Capitalization weights must be finite, nonnegative, and sum to one")
    return cw


def weight_ew(r, cap_ws=None, max_cw_mult=None, microcap_thr=None, **kwargs):
    """Equal weights, optionally excluding small components and capping weights.

    Use the last training row's capitalization. The legacy microcap_thr means
    a component's cap fraction (an industry threshold for industry data).
    Capped equal weights solve w_i=min(lambda, max_cw_mult*cw_i) on eligible
    assets, with lambda chosen to sum to one; infeasible bounds raise an error.
    """
    if not isinstance(r, pd.DataFrame) or r.empty or not r.columns.is_unique:
        raise ValueError("Expected a nonempty return window with unique asset names")
    ew = pd.Series(1 / len(r.columns), index=r.columns)
    if cap_ws is not None:
        cw = _capitalization_weights(r, cap_ws)
        threshold = 0 if microcap_thr is None else microcap_thr
        if not np.isfinite(threshold) or not 0 <= threshold < 1:
            raise ValueError("microcap_thr must be a finite fraction in [0, 1)")
        eligible = cw >= threshold
        if not eligible.any():
            raise ValueError("No assets remain after the capitalization threshold")
        ew = eligible.astype(float) / eligible.sum()
        if max_cw_mult is not None:
            if not np.isfinite(max_cw_mult) or max_cw_mult <= 0:
                raise ValueError("max_cw_mult must be positive and finite")
            caps = (cw * max_cw_mult).where(eligible, 0.0).clip(upper=1)
            if caps.sum() < 1 - 1e-12:
                raise ValueError("Capitalization caps are infeasible for a fully invested portfolio")
            lower, upper = 0.0, 1.0
            for _ in range(60):
                level = (lower + upper) / 2
                if np.minimum(level, caps).sum() < 1:
                    lower = level
                else:
                    upper = level
            ew = np.minimum(upper, caps)
    elif max_cw_mult is not None or microcap_thr is not None:
        raise ValueError("Capitalization weights are required for exclusions or caps")
    return ew


def weight_cw(r, cap_ws, **kwargs):
    """Use last training-date capitalization fractions for the next period."""
    return _capitalization_weights(r, cap_ws)


def weight_rp(r, cov_estimator=sample_cov, **kwargs):
    """Labeled equal-risk-contribution weights from one complete training window."""
    r = _covariance_returns(r)
    est_cov = _bl_matrix(cov_estimator(r, **kwargs), r.columns, "Risk-parity covariance")
    return risk_parity_weigths(est_cov)


def backtest_weight_scheme(r, window=36, weight_scheme=weight_ew, **kwargs):
    """Apply each training-window allocation to the NEXT observed return row.

    Preserve the index with NaN during warm-up. Require complete asset returns
    and finite labeled weights summing to one. The callable is responsible for
    using only information available by the training endpoint. Costs omitted.
    """
    r = _ldi_return_frame(r)
    if not isinstance(window, (int, np.integer)) or isinstance(window, bool) or not 1 <= window < len(r):
        raise ValueError("window must be an integer between one and the number of observations minus one")
    n_periods = r.shape[0]
    windows = [(start, start + window) for start in range(0, n_periods - window)]
    weights = [weight_scheme(r.iloc[win[0] : win[1]], **kwargs) for win in windows]
    for w in weights:
        if not isinstance(w, pd.Series) or not w.index.is_unique or set(w.index) != set(r.columns):
            raise ValueError("Weight schemes must return a Series with exactly the asset labels")
        if not np.isfinite(w).all() or not np.isclose(w.sum(), 1, atol=1e-7, rtol=0):
            raise ValueError("Portfolio weights must be finite and sum to one")
    weights = pd.DataFrame(weights, index=r.iloc[window:].index, columns=r.columns)
    returns = (weights * r).sum(
        axis=1, min_count=r.shape[1]
    )  # mincount is to generate NAs if all inputs are NAs
    return returns


def annualize_vol_ewa(r, decay=0.95, periods_per_year=12):
    """Finite-history exponentially weighted dispersion about the sample mean.

    Retain the legacy arithmetic-mean centering, normalized weights, and no
    degrees-of-freedom correction. decay=1 equals std(ddof=0). This is not a
    recursively estimated conditional variance or a weighted-mean estimator.
    Series return a float; DataFrame columns return a labeled Series.
    """
    if not np.isfinite(decay) or not 0 < decay <= 1:
        raise ValueError("decay must be finite and in (0, 1]")
    if not np.isfinite(periods_per_year) or periods_per_year <= 0:
        raise ValueError("periods_per_year must be positive and finite")
    if not isinstance(r, (pd.Series, pd.DataFrame)):
        raise TypeError("Expected an ordered Series or DataFrame of returns")
    if r.empty or not r.index.is_unique or not r.index.is_monotonic_increasing or not np.isfinite(r.to_numpy(dtype=float)).all():
        raise ValueError("EWA requires complete finite returns with unique ordered observations")
    if isinstance(r, pd.DataFrame):
        return r.apply(annualize_vol_ewa, decay=decay, periods_per_year=periods_per_year)
    values = r.to_numpy(dtype=float)
    weights = decay ** np.arange(len(values) - 1, -1, -1)
    variance = np.average((values - values.mean()) ** 2, weights=weights)
    return float(np.sqrt(variance * periods_per_year))


def weight_minvar(r, cov_estimator=sample_cov, periods_per_year=12, **kwargs):
    """Labeled fully invested long-only minimum-variance weights.

    No expected-return estimate is needed. Common annualization changes the
    risk report, not these weights. Minimize scaled variance with its analytic
    gradient; validate covariance ordering/PSD and the solver allocation.
    """
    r = _covariance_returns(r)
    if not np.isfinite(periods_per_year) or periods_per_year <= 0:
        raise ValueError("periods_per_year must be positive and finite")
    est_cov = cov_estimator(r, **kwargs)
    _, covariance = _optimization_inputs(pd.Series(0.0, index=r.columns), est_cov)
    n = r.shape[1]
    equal = np.repeat(1 / n, n)
    scale = np.max(np.abs(covariance))
    if scale == 0:
        return pd.Series(equal, index=r.columns)
    covariance = covariance / scale
    solution = minimize(lambda w: w @ covariance @ w, equal,
                        jac=lambda w: 2 * covariance @ w, method="SLSQP",
                        bounds=((0.0, 1.0),) * n,
                        constraints={"type": "eq", "fun": lambda w: w.sum() - 1,
                                     "jac": lambda w: np.ones(n)},
                        options={"ftol": 1e-12, "maxiter": 1000, "disp": False})
    return pd.Series(_checked_long_only_weights(solution, n), index=r.columns)


def weight_maxsharpe(
    r, cov_estimator=sample_cov, periods_per_year=12, risk_free_rate=0.03, **kwargs
):
    """
    Produces the weights of the Maximum Sharpe Ratio Portfolio given a covariance matrix of the returns
    """
    est_cov = cov_estimator(r, **kwargs)
    ann_ret = annualize_rets(r, periods_per_year=12)
    return maximize_sharpe_ratio(
        ann_ret,
        est_cov,
        risk_free_rate=risk_free_rate,
        periods_per_year=periods_per_year,
    )


# ---------------------------------------------------------------------------------
# Black-Litterman model
# ---------------------------------------------------------------------------------
def _bl_matrix(matrix, labels, name):
    """Align a labeled symmetric PSD matrix without dropping or inventing labels."""
    if not isinstance(matrix, pd.DataFrame):
        raise TypeError(f"{name} must be a labeled DataFrame")
    if (not labels.is_unique or not matrix.index.is_unique or not matrix.columns.is_unique
            or set(matrix.index) != set(labels) or set(matrix.columns) != set(labels)):
        raise ValueError(f"{name} must have exactly the required unique row and column labels")
    result = matrix.reindex(index=labels, columns=labels).astype(float)
    values = result.to_numpy()
    if not np.isfinite(values).all():
        raise ValueError(f"{name} must be finite")
    if len(labels):
        tolerance = 1e-10 * max(float(np.max(np.abs(values))), np.finfo(float).tiny)
        if not np.allclose(values, values.T, rtol=0, atol=tolerance):
            raise ValueError(f"{name} must be symmetric")
        values = (values + values.T) / 2
        if np.linalg.eigvalsh(values).min() < -tolerance:
            raise ValueError(f"{name} must be positive semidefinite")
        result = pd.DataFrame(values, index=labels, columns=labels)
    return result


def _bl_vector(vector, labels, name):
    """Accept a labeled Series or one-column frame, including a one-asset case."""
    if isinstance(vector, pd.DataFrame) and vector.shape[1] == 1:
        vector = vector.iloc[:, 0]
    if not isinstance(vector, pd.Series):
        raise TypeError(f"{name} must be a Series or one-column DataFrame")
    if not vector.index.is_unique or set(vector.index) != set(labels):
        raise ValueError(f"{name} must have exactly the required unique labels")
    result = vector.reindex(labels).astype(float)
    if not np.isfinite(result).all():
        raise ValueError(f"{name} must be finite")
    return result


def _bl_views(P, assets):
    """Validate named view exposures; zero views are allowed, zero rows are not."""
    if not isinstance(P, pd.DataFrame):
        raise TypeError("P must be a labeled DataFrame")
    if not P.index.is_unique or not P.columns.is_unique or set(P.columns) != set(assets):
        raise ValueError("P must have unique view labels and exactly the covariance asset labels")
    P = P.reindex(columns=assets).astype(float)
    if not np.isfinite(P.to_numpy()).all() or (P.eq(0).all(axis=1)).any():
        raise ValueError("Each view must have finite, nonzero exposures")
    return P


def implied_returns(covmat, weigths, delta=2.5):
    """Reverse-optimize expected EXCESS returns Pi=delta*Sigma*w.

    Keep the historical 'weigths' keyword. The reference weights sum to one;
    signed reference weights are allowed. All inputs use the same horizon.
    This is a model-implied prior, not a sample mean or a forecast guarantee.
    """
    if not isinstance(covmat, pd.DataFrame) or covmat.empty:
        raise ValueError("A nonempty labeled covariance matrix is required")
    covmat = _bl_matrix(covmat, covmat.index, "Covariance")
    weights = _bl_vector(weigths, covmat.index, "Reference weights")
    if not np.isfinite(delta) or delta <= 0:
        raise ValueError("delta must be positive and finite")
    if not np.isclose(weights.sum(), 1, atol=1e-10, rtol=0):
        raise ValueError("Reference weights must sum to one")
    return (delta * covmat.dot(weights)).rename("Implied Returns")


def omega_uncertain_prior(covmat, tau, P):
    """Default diagonal view-error covariance diag(P*(tau*Sigma)*P.T).

    This is a modeling heuristic, not an estimated probability of correctness.
    Because Omega scales with tau, tau cancels from the posterior mean.
    """
    if not isinstance(covmat, pd.DataFrame) or covmat.empty:
        raise ValueError("A nonempty labeled covariance matrix is required")
    covmat = _bl_matrix(covmat, covmat.index, "Covariance")
    if not np.isfinite(tau) or tau <= 0:
        raise ValueError("tau must be positive and finite")
    P = _bl_views(P, covmat.index)
    return pd.DataFrame(np.diag(np.diag(P @ (tau * covmat) @ P.T)), index=P.index, columns=P.index)


def black_litterman(w_prior, Sigma_prior, P, Q, Omega=None, delta=2.5, tau=0.02):
    """Return (posterior excess mean, posterior PREDICTIVE return covariance).

    Prior mean uncertainty is C=tau*Sigma. Q specifies P*mu in excess-return
    units, and Omega is the view-error covariance, not return covariance.
    The returned covariance is Sigma+M, where M is posterior mean uncertainty.
    Match assets/views by labels. Support empty views and independent exact
    views (Omega=0); reject singular conditioning systems rather than jittering
    or silently using a pseudoinverse. All moments share a return horizon.
    """
    Pi = implied_returns(Sigma_prior, w_prior, delta)
    Sigma_prior = _bl_matrix(Sigma_prior, Pi.index, "Covariance")
    if not np.isfinite(tau) or tau <= 0:
        raise ValueError("tau must be positive and finite")
    P = _bl_views(P, Pi.index)
    Q = _bl_vector(Q, P.index, "View returns")
    Omega = omega_uncertain_prior(Sigma_prior, tau, P) if Omega is None else _bl_matrix(Omega, P.index, "Omega")
    covariance = Sigma_prior.to_numpy()
    C = tau * covariance
    exposures = P.to_numpy()
    cross = C @ exposures.T
    system = exposures @ cross + Omega.to_numpy()
    if len(P):
        try:
            if np.linalg.matrix_rank(system) < len(P):
                raise np.linalg.LinAlgError("Rank-deficient view system")
            solved = np.linalg.solve(system, np.column_stack([Q.to_numpy() - exposures @ Pi.to_numpy(), cross.T]))
        except np.linalg.LinAlgError as error:
            raise ValueError("Singular view system: remove redundant exact views or specify positive view uncertainty") from error
        mean = Pi.to_numpy() + cross @ solved[:, 0]
        M = C - cross @ solved[:, 1:]
    else:
        mean, M = Pi.to_numpy(), C
    predictive = covariance + (M + M.T) / 2
    return (pd.Series(mean, index=Pi.index, name="Posterior excess returns"),
            pd.DataFrame(predictive, index=Pi.index, columns=Pi.index))


def bl_portfolio_weights(mu, covmat, delta=2.5):
    """Maximize mean-variance utility with long-only weights summing to one.

    mu contains expected excess returns. Choose conditional or predictive
    covariance explicitly; the function does not silently swap risk models.
    """
    if not isinstance(covmat, pd.DataFrame) or covmat.empty:
        raise ValueError("A nonempty labeled covariance matrix is required")
    covmat = _bl_matrix(covmat, covmat.index, "Allocation covariance")
    mu = _bl_vector(mu, covmat.index, "Expected excess returns")
    if not np.isfinite(delta) or delta <= 0:
        raise ValueError("delta must be positive and finite")
    means, covariance = mu.to_numpy(), covmat.to_numpy()
    n = len(mu)
    scale = max(float(np.max(np.abs(means))), float(delta * np.max(np.abs(covariance))), np.finfo(float).tiny)
    solution = minimize(lambda w: (delta / 2 * w @ covariance @ w - w @ means) / scale,
                        np.repeat(1 / n, n), jac=lambda w: (delta * covariance @ w - means) / scale,
                        method="SLSQP", bounds=((0.0, 1.0),) * n,
                        constraints={"type": "eq", "fun": lambda w: w.sum() - 1, "jac": lambda w: np.ones(n)},
                        options={"ftol": 1e-12, "maxiter": 1000, "disp": False})
    return pd.Series(_checked_long_only_weights(solution, n), index=mu.index, name="Weight")


def show_black_litterman_echart(view_return=0.08, confidence=0.5, tau=0.05, delta=2.5, risk_model="prior"):
    """Two-asset, one-relative-view experiment; confidence is a gain parameter."""
    if not np.isfinite(view_return) or not np.isfinite(confidence) or not 0 <= confidence <= 1:
        raise ValueError("View return must be finite and confidence must be in [0, 1]")
    if risk_model not in ("prior", "predictive"):
        raise ValueError("risk_model must be prior or predictive")
    assets = pd.Index(["Equity", "Bonds"])
    covariance = pd.DataFrame([[0.04, 0.006], [0.006, 0.01]], index=assets, columns=assets)
    benchmark = pd.Series([0.6, 0.4], index=assets)
    P = pd.DataFrame([[1.0, -1.0]], columns=assets, index=["Equity minus bonds"])
    Q = pd.Series([view_return], index=P.index)
    prior = implied_returns(covariance, benchmark, delta)
    base_omega = omega_uncertain_prior(covariance, tau, P)
    if confidence == 0:
        mean, predictive = black_litterman(benchmark, covariance, P.iloc[:0], Q.iloc[:0], delta=delta, tau=tau)
    else:
        omega = base_omega * (1 - confidence) / confidence
        mean, predictive = black_litterman(benchmark, covariance, P, Q, omega, delta=delta, tau=tau)
    weights = bl_portfolio_weights(mean, covariance if risk_model == "prior" else predictive, delta)
    spread = P.iloc[0].to_numpy()
    mean_sd = np.sqrt(max(float(spread @ (predictive - covariance).to_numpy() @ spread), 0))
    return_sd = np.sqrt(float(spread @ predictive.to_numpy() @ spread))
    text = (f"One-year hypothetical inputs; confidence is a single-view update weight, not a probability.\n"
            f"Prior spread: {float(spread @ prior):.3%}; stated view: {view_return:.3%}; posterior spread: {float(spread @ mean):.3%}.\n"
            f"Posterior mean-spread uncertainty: {mean_sd:.3%}; predictive spread volatility: {return_sd:.3%}.\n"
            f"Allocation covariance: {risk_model}; long-only, fully invested utility; delta={delta:g}, tau={tau:g}.")
    plots = {
        "blMeans": {"type": "bar", "title": "Black–Litterman: Expected Excess Returns",
                    "xAxis": {"type": "category", "data": assets.tolist()}, "yAxisName": "Expected annual excess return (%)",
                    "series": {"Prior": (prior * 100).tolist(), "Posterior": (mean * 100).tolist()}},
        "blWeights": {"type": "bar", "title": "Black–Litterman: Constrained Allocation",
                      "xAxis": {"type": "category", "data": assets.tolist()}, "yAxisName": "Portfolio weight (%)",
                      "series": {"Reference": (benchmark * 100).tolist(), "Updated": (weights * 100).tolist()}},
    }
    _publish_echarts(plots, text)


# ---------------------------------------------------------------------------------
# Risk contributions analysis
# ---------------------------------------------------------------------------------
def _unit_shares(values, name):
    """Validate nonnegative finite shares summing to one without renormalizing."""
    values = np.asarray(values, dtype=float)
    if (values.ndim != 1 or not values.size or not np.isfinite(values).all()
            or (values < 0).any() or not np.isclose(values.sum(), 1, atol=1e-8, rtol=0)):
        raise ValueError(f"{name} must be finite nonnegative shares summing to one")
    return values


def enc(weigths):
    """Inverse weight Herfindahl for a fully invested long-only allocation.

    This measures capital concentration, not independent sources of risk.
    Keep the historical 'weigths' keyword; do not apply to leveraged/signed weights.
    """
    values = _unit_shares(weigths, "Portfolio weights")
    return float(1 / (values @ values))


def encb(risk_contrib):
    """Legacy name: inverse concentration of NONNEGATIVE relative risk shares.

    It is not a count of independent bets or factors. Signed hedge contributions
    are valid risk attribution but do not have this effective-count interpretation.
    """
    values = _unit_shares(risk_contrib, "Relative risk contributions")
    return float(1 / (values @ values))


def risk_contribution_report(weights, matcov):
    """Euler volatility attribution on the covariance horizon.

    Return Weight, Marginal volatility, Component volatility, and Relative risk.
    Labeled weights align by asset name; arrays are positional. Signed exposure
    and negative hedge contributions are allowed. Zero-risk portfolios have
    undefined marginal/relative volatility attribution and raise an error.
    """
    if not isinstance(matcov, pd.DataFrame) or matcov.empty:
        raise ValueError("A nonempty labeled covariance matrix is required")
    covariance = _bl_matrix(matcov, matcov.index, "Risk-contribution covariance")
    if isinstance(weights, (pd.Series, pd.DataFrame)):
        weights = _bl_vector(weights, covariance.index, "Portfolio weights").to_numpy()
    else:
        weights = np.asarray(weights, dtype=float)
    if weights.shape != (len(covariance),) or not np.isfinite(weights).all():
        raise ValueError("Weights must be finite and match the covariance assets")
    matrix = covariance.to_numpy()
    marginal_variance = matrix @ weights
    variance = float(weights @ marginal_variance)
    scale = float(np.abs(weights) @ np.abs(matrix) @ np.abs(weights))
    if variance <= 64 * np.finfo(float).eps * scale:
        raise ValueError("Risk contributions require positive portfolio variance")
    volatility = np.sqrt(variance)
    return pd.DataFrame({"Weight": weights, "Marginal volatility": marginal_variance / volatility,
                         "Component volatility": weights * marginal_variance / volatility,
                         "Relative risk": weights * marginal_variance / variance}, index=covariance.index)


def portfolio_risk_contributions(weigths, matcov):
    """Relative Euler risk shares w_i*(Sigma*w)_i/(w.T*Sigma*w); may be negative."""
    return risk_contribution_report(weigths, matcov)["Relative risk"]


def msd_risk_contrib(weights, target_risk, mat_cov):
    """Legacy SUM of squared differences from target relative risk shares."""
    w_risk_contribs = portfolio_risk_contributions(weights, mat_cov)
    if isinstance(target_risk, (pd.Series, pd.DataFrame)):
        target_risk = _bl_vector(target_risk, w_risk_contribs.index, "Risk budgets").to_numpy()
    target_risk = _unit_shares(target_risk, "Risk budgets")
    if len(target_risk) != len(w_risk_contribs):
        raise ValueError("Risk budgets must match the covariance assets")
    msd = (w_risk_contribs - target_risk) ** 2
    return float(msd.sum())


def _risk_budget_solution(matrix, budgets):
    """Damped Newton solve of the strictly convex positive risk-budget problem."""
    x = np.sqrt(budgets / np.diag(matrix))
    def objective(value):
        return 0.5 * value @ matrix @ value - budgets @ np.log(value)
    for _ in range(100):
        marginal = matrix @ x
        if np.max(np.abs(x * marginal - budgets)) <= 1e-10:
            return x
        gradient = marginal - budgets / x
        hessian = matrix + np.diag(budgets / x ** 2)
        direction = np.linalg.solve(hessian, -gradient)
        falling = direction < 0
        step = min(1.0, 0.99 * np.min(-x[falling] / direction[falling])) if falling.any() else 1.0
        current = objective(x)
        for _ in range(60):
            candidate = x + step * direction
            tolerance = 1e-14 * max(1, abs(current))
            if objective(candidate) <= current + 1e-4 * step * (gradient @ direction) + tolerance:
                x = candidate
                break
            step *= 0.5
        else:
            raise RuntimeError("Risk-budget Newton line search failed")
    raise RuntimeError("Risk-budget optimization did not converge")


def portfolio_risk_contrib_optimizer(target_risk_contrib, mat_cov):
    """Positive long-only risk budgets via convex log-barrier optimization.

    Require a numerically positive-definite covariance and strictly positive
    budgets summing to one. Exclude zero-budget assets before calling. Solve
    min_x .5*x.T*Sigma*x - sum(b_i*log(x_i)), then normalize positive x.
    Return positional weights only after checking achieved relative budgets.
    """
    if not isinstance(mat_cov, pd.DataFrame) or mat_cov.empty:
        raise ValueError("A nonempty labeled covariance matrix is required")
    covariance = _bl_matrix(mat_cov, mat_cov.index, "Risk-budget covariance")
    if isinstance(target_risk_contrib, (pd.Series, pd.DataFrame)):
        target_risk_contrib = _bl_vector(target_risk_contrib, covariance.index, "Risk budgets").to_numpy()
    budgets = _unit_shares(target_risk_contrib, "Risk budgets")
    if len(budgets) != len(covariance) or (budgets <= 0).any():
        raise ValueError("Risk budgets must be strictly positive and match the assets; exclude zero-budget assets")
    matrix = covariance.to_numpy()
    scale = float(np.max(np.abs(matrix)))
    if scale == 0 or np.linalg.eigvalsh(matrix / scale).min() <= 1e-12:
        raise ValueError("Risk budgeting requires positive-definite covariance; use shrinkage or remove redundant assets")
    matrix = matrix / scale
    x = np.asarray(_risk_budget_solution(matrix, budgets))
    if x.shape != budgets.shape or not np.isfinite(x).all() or (x <= 0).any():
        raise RuntimeError("Risk-budget optimizer returned invalid exposures")
    weights = x / x.sum()
    achieved = weights * (matrix @ weights) / (weights @ matrix @ weights)
    if not np.allclose(achieved, budgets, atol=1e-7, rtol=0):
        raise RuntimeError("Risk-budget optimizer did not meet the requested risk shares")
    return weights


def risk_parity_weigths(mat_cov):
    """Equal positive relative risk budgets; retain the historical API spelling."""
    if not isinstance(mat_cov, pd.DataFrame) or mat_cov.empty:
        raise ValueError("A nonempty labeled covariance matrix is required")
    n = mat_cov.shape[0]
    weigths = portfolio_risk_contrib_optimizer(
        target_risk_contrib=np.repeat(1 / n, n), mat_cov=mat_cov
    )
    return pd.Series(weigths, index=mat_cov.index)


def show_risk_parity_echart(vol_equity=0.20, vol_bond=0.10, correlation=0.25, equity_budget=0.5):
    """Compare capital and Euler risk allocations in a two-asset annual model."""
    if not np.isfinite([vol_equity, vol_bond, correlation, equity_budget]).all():
        raise ValueError("Risk experiment inputs must be finite")
    if vol_equity <= 0 or vol_bond <= 0 or not -1 < correlation < 1 or not 0 < equity_budget < 1:
        raise ValueError("Use positive volatilities, correlation in (-1, 1), and a risk budget in (0, 1)")
    assets = pd.Index(["Equity", "Bonds"])
    cross = correlation * vol_equity * vol_bond
    covariance = pd.DataFrame([[vol_equity ** 2, cross], [cross, vol_bond ** 2]], index=assets, columns=assets)
    gmv_equity = np.clip((vol_bond ** 2 - cross) / (vol_equity ** 2 + vol_bond ** 2 - 2 * cross), 0, 1)
    budgets = pd.Series([equity_budget, 1 - equity_budget], index=assets)
    weights = pd.DataFrame({"EW": [0.5, 0.5], "GMV": [gmv_equity, 1 - gmv_equity],
                            "Risk budget": portfolio_risk_contrib_optimizer(budgets, covariance)}, index=assets)
    shares = weights.apply(lambda w: portfolio_risk_contributions(w, covariance))
    stats = pd.DataFrame({"Volatility (%)": weights.apply(lambda w: portfolio_volatility(w, covariance) * 100),
                          "Effective holdings": weights.apply(enc)})
    text = (f"Hypothetical annual covariance; requested Equity risk share: {equity_budget:.1%}.\n"
            "Capital weights and relative risk shares answer different questions. Negative shares indicate hedging.\n"
            + stats.to_string(float_format=lambda value: f"{value:.4f}"))
    plots = {
        "riskParityWeights": {"type": "bar", "title": "Capital Allocation",
                              "xAxis": {"type": "category", "data": assets.tolist()}, "yAxisName": "Portfolio weight (%)",
                              "series": {name: (weights[name] * 100).tolist() for name in weights}},
        "riskParityShares": {"type": "bar", "title": "Euler Risk Allocation",
                             "xAxis": {"type": "category", "data": assets.tolist()}, "yAxisName": "Relative volatility contribution (%)",
                             "series": {name: (shares[name] * 100).tolist() for name in shares}},
    }
    _publish_echarts(plots, text)


# ---------------------------------------------------------------------------------
# Auxiliary methods
# ---------------------------------------------------------------------------------
def as_colvec(x):
    """
    In order to consistently use column vectors, this method takes either a np.array or a np.column
    matrix (i.e., a column vector) and returns the input data as a column vector.
    """
    if x.ndim == 2:
        return x
    else:
        return np.expand_dims(x, axis=1)


def inverse_df(d):
    """
    Inverse of a pd.DataFrame (i.e., inverse of dataframe.values)
    """
    return pd.DataFrame(inv(d.values), index=d.columns, columns=d.index)


def insert_first_row_df(df, row):
    """
    The method inserts a row at the beginning of a given dataframe and shift by one existing rows.
    The input row has to be either a single element (in case of 1-column dataframe) or
    a dictionary in case of multi-column dataframe.

    Example:
        df  = pd.DataFrame([1, 2, 3])
        row = 0.5
        df  = insert_first_row_df(df, row)
    Example:
        df  = pd.DataFrame([[1,2],[34,12]], columns=["A","B"])
        row = {"A":-34, "B":443}
        df  = insert_first_row_df(df, row)
    """
    df.loc[-1] = row
    df.index = df.index + 1
    return df.sort_index()
