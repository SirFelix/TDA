import numpy as np
from numpy.linalg import norm
from scipy.fft import dctn, idctn
from scipy.optimize import fminbound
from scipy.ndimage import distance_transform_edt

import matplotlib.pyplot as plt
def smoothn(y, s=None, W=None, robust=False, MaxIter=100, TolZ=1e-3,
            z0=None, Weights='bisquare', return_s=False, verbose=False):
    """
    Robust spline-like smoothing for 1-D to N-D data (Python port of Damien Garcia's SMOOTHN).
    
    Parameters
    ----------
    y : array_like
        N-D uniformly sampled data. NaN/Inf are treated as missing.
    s : float or None, optional
        Smoothing parameter. If None, chosen automatically by GCV.
        Larger s -> smoother result. Must be >= 0 if provided.
    W : array_like or None, optional
        Non-negative weights, same shape as y. Zero -> missing. If None, all ones.
    robust : bool, optional
        If True, iteratively reweight residuals to reduce outlier influence.
    MaxIter : int, optional
        Maximum iterations for the inner fixed-point loop (per robust step).
    TolZ : float, optional
        Relative tolerance on Z between iterations (0 < TolZ < 1).
    z0 : array_like or None, optional
        Initial guess for Z (same shape as y).
    Weights : {'bisquare','cauchy','talworth'}, optional
        Robust weight function when robust=True.
    return_s : bool, optional
        If True, also return the final smoothing parameter s.
    verbose : bool, optional
        If True, prints a few diagnostics.
    Returns
    -------
    z : ndarray
        Smoothed array (float64).
    s : float, optional
        The smoothing parameter actually used (if return_s=True).
    exitflag : int
        1 if converged before MaxIter, 0 otherwise.
    Wtot : ndarray
        The final weights used (including robust weights if robust=True).
    Notes
    -----
    - Implements the penalized least squares formulation with N-D DCT diagonalization,
      and uses GCV to pick `s` automatically when omitted, following Garcia (2010).
    - Requires SciPy >= 1.4 for `scipy.fft.dctn/idctn`.
    References
    ----------
    Garcia D. (2010) Robust smoothing of gridded data in one and higher dimensions with missing values.
    Computational Statistics & Data Analysis, 54(4):1167–1178.  (See Matlab docs & examples).  :contentReference[oaicite:1]{index=1}
    SciPy DCTN/IDCTN documentation. :contentReference[oaicite:2]{index=2}
    """
    y = np.asarray(y, dtype=float)
    sizy = y.shape
    noe = y.size
    if noe < 2:
        z = y.copy()
        return (z, s, 1, np.ones_like(z)) if return_s else (z, 1, np.ones_like(z))
    # Prepare weights and mask of finite entries
    IsFinite = np.isfinite(y)
    if W is None:
        W = np.ones(sizy, dtype=float)
    else:
        W = np.asarray(W, dtype=float)
        if W.shape != sizy:
            raise ValueError("W must have the same shape as y")
        if np.any(W < 0):
            raise ValueError("W must be >= 0 everywhere")
    W = W * IsFinite
    if W.max() > 0:
        W /= W.max()
    isweighted = np.any(W < 1)
    # Robust mode?
    isrobust = bool(robust)
    isauto = s is None
    # Build Lambda eigenvalues of the discrete Laplacian (same as MATLAB code)
    d = y.ndim
    Lambda = np.zeros(sizy, dtype=float)
    for i, n in enumerate(sizy):
        # cos(pi*(k-1)/n) for k=1..n reshaped along axis i
        idx = np.arange(1, n + 1, dtype=float)
        lam_i = np.cos(np.pi * (idx - 1) / n)
        shp = [1] * d
        shp[i] = n
        Lambda += lam_i.reshape(shp)
    Lambda = -2.0 * (d - Lambda)
    # If s is fixed, precompute Gamma
    if not isauto:
        if not np.isscalar(s) or s < 0:
            raise ValueError("s must be a scalar >= 0")
        Gamma = 1.0 / (1.0 + s * (Lambda ** 2))
    # Bounds for s via leverage h (Eq. #12 in paper)
    N = np.sum(np.array(sizy) != 1)  # tensor rank
    hMin, hMax = 1e-6, 0.99
    sMinBnd = (((1 + np.sqrt(1 + 8 * (hMax ** (2 / N)))) / 4.0 / (hMax ** (2 / N))) ** 2 - 1) / 16.0
    sMaxBnd = (((1 + np.sqrt(1 + 8 * (hMin ** (2 / N)))) / 4.0 / (hMin ** (2 / N))) ** 2 - 1) / 16.0
    # Initial guess
    if isweighted:
        if z0 is not None:
            z = np.asarray(z0, dtype=float).copy()
            if z.shape != sizy:
                raise ValueError("z0 must have the same shape as y")
        else:
            z = _initial_guess(y, IsFinite)
    else:
        z = np.zeros(sizy, dtype=float)
    y_filled = y.copy()
    y_filled[~IsFinite] = 0.0
    z_prev = z.copy()
    tol = 1.0
    exitflag = 1
    Wtot = W.copy()
    # Relaxation factor to speed convergence (as in MATLAB)
    RF = 1.75 if isweighted else 1.0
    robust_steps = 3 if isrobust else 1
    for rstep in range(robust_steps):
        nit = 0
        # aow = "amount of weights"
        aow = Wtot.sum() / noe  # 0 < aow <= 1
        # Precompute DCT of weighted residual + current z at each iteration
        while (tol > TolZ) and (nit < MaxIter):
            nit += 1
            DCTy = dctn(Wtot * (y_filled - z) + z, norm='ortho')
            # If s is automatic, periodically (powers of 2) update it via GCV
            if isauto and (np.log2(nit).is_integer()):
                # Minimize GCV score over log10(s)
                def gcv_log10(p):
                    sval = 10.0 ** p
                    G = 1.0 / (1.0 + sval * (Lambda ** 2))
                    if aow > 0.9:  # fast path (no inverse DCT)
                        RSS = norm(DCTy.ravel() * (G.ravel() - 1.0)) ** 2
                    else:
                        yhat = idctn(G * DCTy, norm='ortho')
                        resid = np.sqrt(Wtot[IsFinite]) * (y_filled[IsFinite] - yhat[IsFinite])
                        RSS = norm(resid) ** 2
                    TrH = G.sum()
                    return RSS / IsFinite.sum() / (1.0 - TrH / noe) ** 2
                p_opt = fminbound(gcv_log10, np.log10(sMinBnd), np.log10(sMaxBnd), xtol=0.1, disp=0)
                s = 10.0 ** p_opt
            # Update z using current (or new) s
            if isauto:
                Gamma = 1.0 / (1.0 + s * (Lambda ** 2))
            z = RF * idctn(Gamma * DCTy, norm='ortho') + (1.0 - RF) * z
            # Convergence measure (if not weighted, we do one pass)
            tol = (1 if isweighted else 0) * norm((z_prev - z).ravel()) / max(norm(z.ravel()), 1e-16)
            z_prev = z.copy()
        if nit >= MaxIter and tol > TolZ:
            exitflag = 0
        if isrobust and (rstep < robust_steps - 1):
            # Compute robust weights and re-enter loop
            # average leverage h for robust scaling (same as MATLAB)
            h = np.sqrt(1 + 16 * s)
            h = np.sqrt(1 + h) / np.sqrt(2) / h
            h = h ** N
            Wrob = _robust_weights(y_filled - z, IsFinite, h, Weights)
            Wtot = W * Wrob  # combine base and robust weights
            # Re-init loop state
            tol = 1.0
            z_prev = z.copy()
    if isauto and (abs(np.log10(s) - np.log10(sMinBnd)) < 0.1 or
                   abs(np.log10(s) - np.log10(sMaxBnd)) < 0.1):
        if verbose:
            print("Warning: automatic s may be at search boundary; you can set `s` manually.")
    if return_s:
        return z, s, exitflag, Wtot
    else:
        return z, exitflag, Wtot

def _robust_weights(r, I, h, wstr):
    # Median absolute deviation (MAD), with 1.4826 scaling to std for normal data
    r_f = r[I]
    if r_f.size == 0:
        return np.zeros_like(r)
    med = np.median(r_f)
    MAD = np.median(np.abs(r_f - med))
    if MAD == 0:
        # fallback: avoid division by zero; treat all as well-fit
        return (np.ones_like(r) * I).astype(float)
    u = np.abs(r / (1.4826 * MAD) / np.sqrt(max(1e-12, (1 - h))))
    wstr = str(wstr).lower()
    if wstr == 'cauchy':
        c = 2.385
        W = 1.0 / (1.0 + (u / c) ** 2)
    elif wstr in ('talworth', 'talwar', 'talworth'):
        c = 2.795
        W = (u < c).astype(float)
    else:  # bisquare (default)
        c = 4.685
        W = (1 - (u / c) ** 2)
        W = (W ** 2) * (u < c)
    W[~np.isfinite(W)] = 0.0
    return W

def _initial_guess(y, I):
    """
    Nearest-neighbor fill (via distance transform) + coarse DCT low-pass.
    Mirrors the MATLAB strategy used for faster convergence.
    """
    z = y.copy()
    if np.any(~I):
        # distance_transform_edt returns indices of nearest True if return_indices=True
        # We emulate bwdist-like nearest neighbor:
        dist, (inds) = distance_transform_edt(I == 0, return_indices=True)
        z[~I] = y[tuple(ind[~I] for ind in inds)]
    # Coarse low-pass: keep ~1/10 of coefficients along each axis
    Z = dctn(z, norm='ortho')
    for axis, n in enumerate(z.shape):
        cutoff = int(np.ceil(n / 10.0))
        sl = [slice(None)] * z.ndim
        sl[axis] = slice(cutoff, None)
        Z[tuple(sl)] = 0
    z = idctn(Z, norm='ortho')
    return z


# # 1D
# x = np.linspace(0, 100, 256)
# y = np.cos(x/10) + (x/50.0)**2 + np.random.randn(x.size)/10
# y[[70,75,80]] = [5.5, 5.0, 6.0]  # outliers
# z, s, exitflag, _ = smoothn(y, robust=True, return_s=True)

# # 2D with missing data
# import numpy as np
# rng = np.random.default_rng(0)
# y0 = np.fromfunction(lambda i,j: np.sin(i/30)+np.cos(j/40), (256,256))
# y = y0 + rng.normal(scale=0.5, size=y0.shape)
# mask = rng.random(y.size).reshape(y.shape) < 0.5
# y[mask] = np.nan
# z, s, exitflag, _ = smoothn(y, robust=True, return_s=True)
# print(z)
