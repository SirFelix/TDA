#!/usr/bin/env python3
\"\"\"combined_detector_script.py

Loads a CSV with columns DateTime/Stopwatch/Pressure (Stopwatch in seconds preferred),
runs two dip-detection methods (smoothed-minima and Kalman+matched-filter-bank),
plots results, and saves detection CSVs and period/speed CSVs.

Usage:
    python combined_detector_script.py /path/to/tractor_section.csv

Outputs (saved in current working directory):
 - tractor_detections_old_method.csv
 - tractor_detections_new_method.csv
 - tractor_periods_old.csv (if available)
 - tractor_periods_new.csv (if available)

Requires: numpy, pandas, matplotlib
\"\"\"

import sys, os, math
import numpy as np, pandas as pd, matplotlib.pyplot as plt
from collections import deque

def load_csv(path):
    df = pd.read_csv(path)
    # Prefer 'Stopwatch' column (seconds). Fall back to DateTime if needed.
    if 'Stopwatch' in df.columns:
        t = pd.to_numeric(df['Stopwatch'], errors='coerce').to_numpy()
    elif 'DateTime' in df.columns:
        try:
            t = pd.to_datetime(df['DateTime']).astype('int64').to_numpy() / 1e9
        except Exception:
            t = np.arange(len(df)).astype(float)
    else:
        t = np.arange(len(df)).astype(float)
    # Pressure
    if 'Pressure' in df.columns:
        x = pd.to_numeric(df['Pressure'], errors='coerce').to_numpy()
    else:
        # if single-column CSV, assume it's pressure
        if df.shape[1] == 1:
            x = pd.to_numeric(df.iloc[:,0], errors='coerce').to_numpy()
        else:
            raise ValueError("CSV must contain a 'Pressure' column (or be a single-column file)")
    mask = np.isfinite(t) & np.isfinite(x)
    return t[mask], x[mask], df

def smoothed_minima_method(t, x, fs, tractor_on_thr=1500.0,
                           smooth_win_s=0.7, prominence_psi=25.0,
                           local_max_halfwin_s=2.5, min_sep_s=3.0):
    # Moving-average smoothing
    w = max(1, int(round(smooth_win_s * fs)))
    pad = w//2
    xpad = np.pad(x, (pad,pad), mode='edge')
    box = np.ones(w)/w
    y = np.convolve(xpad, box, mode='same')[pad:-pad]
    tractor_on = x > tractor_on_thr
    halfwin = int(round(local_max_halfwin_s * fs))
    mins_idx = []
    N = len(x)
    i = 1
    while i < N-1:
        if tractor_on[i] and y[i] < y[i-1] and y[i] <= y[i+1]:
            left = max(0, i-halfwin); right = min(N, i+halfwin+1)
            local_max = np.max(y[left:right])
            depth = local_max - y[i]
            if depth >= prominence_psi:
                if not mins_idx or (i - mins_idx[-1]) >= int(round(min_sep_s * fs)):
                    mins_idx.append(i)
                else:
                    prev = mins_idx[-1]
                    leftp = max(0, prev-halfwin); rightp = min(N, prev+halfwin+1)
                    local_max_prev = np.max(y[leftp:rightp])
                    depth_prev = local_max_prev - y[prev]
                    if depth > depth_prev:
                        mins_idx[-1] = i
        i += 1
    return np.array(mins_idx, dtype=int), y

def kalman_matched_bank_method(t, x, fs, tractor_on_thr=1500.0,
                               kalman_q=1.0, kalman_r=100.0**2,
                               min_w_s=0.5, max_w_s=1.5, n_templates=5,
                               z_thresh=-3.0, min_sep_s=2.0):
    # Kalman baseline (random-walk)
    baseline = np.zeros_like(x)
    P = 1.0
    b = x[0]
    baseline[0] = b
    q = kalman_q; r = kalman_r
    for i in range(1, len(x)):
        b_pred = b
        P_pred = P + q
        K = P_pred / (P_pred + r)
        b = b_pred + K * (x[i] - b_pred)
        P = (1 - K) * P_pred
        baseline[i] = b
    residual = x - baseline
    # Build templates (Gaussian-like negative pulses)
    widths_s = np.linspace(min_w_s, max_w_s, n_templates)
    templates = []
    L_list = []
    for w_s in widths_s:
        L = int(round(w_s * fs))
        if L < 3: L = 3
        L_list.append(L)
        tt = np.arange(L)
        sigma = max(1.0, L/6.0)
        gauss = np.exp(-0.5 * ((tt - (L-1)/2)/sigma)**2)
        pulse = -gauss
        pulse = pulse - pulse.mean()
        pulse = pulse / max(np.linalg.norm(pulse), 1e-9)
        templates.append(pulse)
    # Compute normalized correlation per template (same-mode conv)
    n_templates = len(templates)
    corrs = np.full((n_templates, len(x)), np.nan)
    for k, h in enumerate(templates):
        L = len(h)
        num = np.convolve(residual, h[::-1], mode='same')
        sq = residual**2
        kernel = np.ones(L)
        local_energy = np.convolve(sq, kernel, mode='same')
        denom = np.sqrt(np.maximum(local_energy * (np.linalg.norm(h)**2), 1e-12))
        corr = num / denom
        corrs[k] = corr
    # Pick most negative (strongest negative match) across templates
    best_corr = np.nanmin(corrs, axis=0)
    best_template_idx = np.nanargmin(corrs, axis=0)
    tractor_on = x > tractor_on_thr
    on_idx = tractor_on & np.isfinite(best_corr)
    if np.any(on_idx):
        med = np.median(best_corr[on_idx]); mad = np.median(np.abs(best_corr[on_idx] - med)) + 1e-9
    else:
        med = np.nanmedian(best_corr[np.isfinite(best_corr)]); mad = np.nanmedian(np.abs(best_corr[np.isfinite(best_corr)] - med)) + 1e-9
    z_corr = (best_corr - med) / (1.4826 * mad)
    # Peak-pick negative z crossings with min separation
    candidates = np.where((z_corr < z_thresh) & tractor_on & np.isfinite(z_corr))[0]
    dets = []
    i = 0
    min_sep_samples = int(round(min_sep_s * fs))
    while i < len(candidates):
        idx = candidates[i]; j = i; best_idx = idx; best_val = z_corr[idx]
        while j+1 < len(candidates) and candidates[j+1] - candidates[j] <= 1:
            j += 1
            if z_corr[candidates[j]] < best_val:
                best_val = z_corr[candidates[j]]; best_idx = candidates[j]
        if not dets or (best_idx - dets[-1]) >= min_sep_samples:
            dets.append(best_idx)
        else:
            if z_corr[best_idx] < z_corr[dets[-1]]:
                dets[-1] = best_idx
        i = j + 1
    dets = np.array(dets, dtype=int)
    matched_template = best_template_idx[dets] if dets.size else np.array([])
    matched_corr = best_corr[dets] if dets.size else np.array([])
    return dets, baseline, corrs, L_list, matched_template, matched_corr

def compute_periods_times(indices, times):
    if len(indices) < 2:
        return np.array([]), np.array([]), np.array([])
    det_times = times[indices]
    periods = np.diff(det_times)
    mid_t = 0.5 * (det_times[1:] + det_times[:-1])
    speeds = 1.0 / periods
    return periods, speeds, det_times

def main(csv_path):
    t, x, df = load_csv(csv_path)
    dt = np.diff(t); dt = dt[(dt>0) & np.isfinite(dt)]
    fs = 1.0/np.median(dt) if dt.size else 100.0
    print(f\"Loaded {len(x)} samples, fs ≈ {fs:.2f} Hz\")
    # Old method
    mins_idx, y_smooth = smoothed_minima_method(t, x, fs)
    # New method
    dets_new, baseline, corrs, L_list, matched_template, matched_corr = kalman_matched_bank_method(t, x, fs)
    # Periods/speeds
    periods_old, speeds_old, det_times_old = compute_periods_times(mins_idx, t)
    periods_new, speeds_new, det_times_new = compute_periods_times(dets_new, t)
    # Plots (3 figures)
    plt.figure(figsize=(14,6))
    plt.plot(t, x, label='raw pressure', linewidth=0.6)
    plt.plot(t, baseline, label='Kalman baseline', linewidth=1.2)
    plt.plot(t, y_smooth, label='MA smooth', linewidth=1.0, alpha=0.9)
    if mins_idx.size:
        plt.scatter(t[mins_idx], y_smooth[mins_idx], marker='x', color='C3', s=50, label='old minima dets')
    if dets_new.size:
        plt.scatter(t[dets_new], x[dets_new], marker='o', facecolors='none', edgecolors='r', s=60, label='new matched dets')
    plt.axhline(1500.0, linestyle='--', color='k', alpha=0.6, label='tractor-on threshold')
    plt.xlabel('time (s)'); plt.ylabel('psi'); plt.title('Raw pressure with baseline, smooth, and detections (both methods)')
    plt.legend(loc='upper right'); plt.tight_layout(); plt.show()
    # Zoomed matched-filter responses (center on middle tractor-on region)
    tractor_on = x > 1500.0
    on_idxs = np.where(tractor_on)[0]
    if on_idxs.size:
        mid = on_idxs[len(on_idxs)//2]
        wsec = 80.0
        wpts = int(round(wsec * fs))
        z0 = max(on_idxs[0], mid - wpts//2)
        z1 = min(on_idxs[-1], z0 + wpts)
    else:
        z0 = 0; z1 = min(len(x), int(round(60*fs)))
    plt.figure(figsize=(14,6))
    plt.plot(t[z0:z1], x[z0:z1], label='pressure', linewidth=0.6)
    offset = np.nanpercentile(x[z0:z1], 98); scale = np.nanstd(x[z0:z1]) * 0.06
    for k, L in enumerate(L_list):
        plt.plot(t[z0:z1], offset + scale * corrs[k, z0:z1], label=f'corr L={L}')
    if dets_new.size:
        plt.scatter(t[dets_new], offset + scale * np.nanmin(corrs[:, dets_new], axis=0), marker='o', edgecolors='r', facecolors='none', s=80, label='new dets')
    plt.xlabel('time (s)'); plt.ylabel('psi or scaled corr'); plt.title('Matched-filter bank responses (zoom)')
    plt.legend(loc='upper right'); plt.tight_layout(); plt.show()
    # Period plots
    if len(periods_old):
        midt_old = 0.5*(det_times_old[1:] + det_times_old[:-1])
        plt.figure(figsize=(12,3)); plt.plot(midt_old, periods_old, label='period old (s)'); plt.xlabel('time (s)'); plt.ylabel('s'); plt.title('Old method instantaneous period'); plt.legend(); plt.tight_layout(); plt.show()
    if len(periods_new):
        midt_new = 0.5*(det_times_new[1:] + det_times_new[:-1])
        plt.figure(figsize=(12,3)); plt.plot(midt_new, periods_new, label='period new (s)'); plt.xlabel('time (s)'); plt.ylabel('s'); plt.title('New method instantaneous period'); plt.legend(); plt.tight_layout(); plt.show()
    # Save CSVs
    out_old = pd.DataFrame({'det_index': mins_idx, 'det_time_s': t[mins_idx], 'det_value_smoothed_psi': y_smooth[mins_idx]})
    out_new = pd.DataFrame({'det_index': dets_new, 'det_time_s': t[dets_new], 'det_value_psi': x[dets_new], 'template_idx': matched_template, 'corr': matched_corr})
    out_old.to_csv('tractor_detections_old_method.csv', index=False)
    out_new.to_csv('tractor_detections_new_method.csv', index=False)
    if len(periods_old):
        pd.DataFrame({'mid_time_s': 0.5*(t[mins_idx][1:]+t[mins_idx][:-1]), 'period_s': periods_old, 'speed_hz': speeds_old}).to_csv('tractor_periods_old.csv', index=False)
    if len(periods_new):
        pd.DataFrame({'mid_time_s': 0.5*(t[dets_new][1:]+t[dets_new][:-1]), 'period_s': periods_new, 'speed_hz': speeds_new}).to_csv('tractor_periods_new.csv', index=False)
    print('Saved CSVs: tractor_detections_old_method.csv, tractor_detections_new_method.csv, tractor_periods_old.csv, tractor_periods_new.csv (if available)')

if __name__ == '__main__':
    if len(sys.argv) < 2:
        print('Usage: python combined_detector_script.py /path/to/tractor_section.csv')
        sys.exit(1)
    csv_path = sys.argv[1]
    if not os.path.exists(csv_path):
        print('File not found:', csv_path); sys.exit(1)
    main(csv_path)
