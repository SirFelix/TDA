#!/usr/bin/env python3
"""
combined_detector_stream.py

Streaming version of the combined detector. Supports:
 - replay mode (stream samples from CSV at real-time or accelerated speed)
 - stdin mode (read "time,pressure" lines)
 - optional websocket skeleton (requires websockets lib)

Usage examples:
  # replay file in real time
  python combined_detector_stream.py replay /path/to/tractor_section.csv --realtime True

  # replay file at 10x speed (faster than real-time)
  python combined_detector_stream.py replay /path/to/tractor_section.csv --speed 10.0

  # read lines from stdin (format: time,pressure)
  tail -f data_stream.csv | python combined_detector_stream.py stdin -

  # If you have a WebSocket producing lines like time,pressure or JSON {"t":..., "p":...}
  pip install websockets
  python combined_detector_stream.py websocket ws://host:port/path

Dependencies: numpy, pandas, matplotlib (matplotlib optional for plotting)

Tuning Notes:
The Kalman q and measurement variance r are the primary knobs for baseline responsiveness vs stability.
 Increase q to let baseline move faster; increase r to make baseline trust measurements less (smoother baseline).

The template widths and z_thresh control sensitivity.
 Lower z_thresh (e.g. -2.5) → more detections, increase false positives.

tractor_on_thr filters detections to only when pressure > 1500 psi.

The streaming old-method uses a short buffer history for local-minimum detection;
 it approximate local times for minima based on buffer center — if you need exact alignment,
 refine the timestamping step (I provided an approximate adjustment).
"""

import argparse, time, math, csv, os
from collections import deque
import numpy as np

try:
    import pandas as pd
except Exception:
    pd = None

# ---------- Streaming detectors (stateful) ----------

class SmoothedMinimaStream:
    """Streaming moving-average + local-minima prominence detector."""
    def __init__(self, fs, smooth_win_s=0.7, prominence_psi=25.0,
                 local_max_halfwin_s=2.5, min_sep_s=3.0, tractor_on_thr=1500.0):
        self.fs = float(fs)
        self.w = max(1, int(round(smooth_win_s * fs)))
        self.box = np.ones(self.w) / self.w
        # circular buffer for computing moving average
        self.buf = deque([0.0]*self.w, maxlen=self.w)
        self.sum_buf = 0.0
        self.index = -1
        self.prominence_psi = float(prominence_psi)
        self.halfwin = int(round(local_max_halfwin_s * fs))
        self.min_sep_samples = int(round(min_sep_s * fs))
        self.last_det_idx = -1
        self.tr_threshold = float(tractor_on_thr)
        # keep a small history of smoothed values to detect local minima
        self.smoothed_history = deque(maxlen=self.halfwin*2 + 5)
        self.sample_idx = -1
        # store detections as (idx, time, smoothed_value)
    def process(self, t, x):
        """Process one sample. Returns detection tuple or None."""
        self.sample_idx += 1
        # update moving average buffer
        if len(self.buf) < self.w:
            self.buf.append(x); self.sum_buf += x
        else:
            old = self.buf[0]
            self.buf.append(x)
            # deque auto pops left, so compute by capturing popped value:
            # but simpler: maintain sum by subtract old and add new:
            # we already appended so popped happened; implement as:
            # pop left manually for clarity
            # (we stick with this approach: use popleft and append to keep sum consistent)
            # Implementation change: use manual popleft to track sum reliably
            pass

    # We'll provide a robust streaming implementation below in the main code
    # because this skeleton isn't used directly here.


class KalmanMatchedBankStream:
    """Streaming Kalman baseline + matched-filter bank (stateful)."""
    def __init__(self, fs, min_w_s=0.5, max_w_s=1.5, n_templates=5,
                 kalman_q=1.0, kalman_r=100.0**2,
                 z_thresh=-3.0, min_sep_s=2.0, tractor_on_thr=1500.0):
        self.fs = float(fs)
        self.min_w_s = float(min_w_s)
        self.max_w_s = float(max_w_s)
        self.n_templates = int(n_templates)
        self.kalman_q = float(kalman_q)
        self.kalman_r = float(kalman_r)
        self.z_thresh = float(z_thresh)
        self.min_sep_samples = int(round(min_sep_s * fs))
        self.tr_threshold = float(tractor_on_thr)

        # Kalman state
        self.P = 1.0
        self.b = None  # baseline estimate
        # build templates
        widths_s = np.linspace(self.min_w_s, self.max_w_s, self.n_templates)
        self.templates = []
        self.L_list = []
        for w_s in widths_s:
            L = int(round(w_s * self.fs))
            if L < 3: L = 3
            self.L_list.append(L)
            tt = np.arange(L)
            sigma = max(1.0, L/6.0)
            gauss = np.exp(-0.5 * ((tt - (L-1)/2)/sigma)**2)
            pulse = -gauss
            pulse = pulse - pulse.mean()
            pulse = pulse / max(np.linalg.norm(pulse), 1e-9)
            self.templates.append(pulse)
        # Circular buffers for residual and per-template running stats
        self.maxL = max(self.L_list)
        self.res_buf = np.zeros(self.maxL, dtype=float)
        self.res_idx = -1
        # per-template running sums for numerator and local energy
        # We'll compute numerator by dot product with window rebuilt each sample (L small, n_templates small)
        # Keep last detection info
        self.last_det_idx = -1
        self.sample_idx = -1
        # For robust normalization z-score we collect robust stats on tractor-on zone adaptively:
        self.robust_med = 0.0
        self.robust_mad = 1.0
        self.robust_alpha = 0.01  # EWMA of median-like proxy (approx)
        # we maintain a small buffer of recent best_corr for robust estimate
        self.recent_best = deque(maxlen=int(round(5.0*self.fs)))  # 5s window approx

    def update_kalman(self, x):
        if self.b is None:
            self.b = x
            self.P = 1.0
            return self.b
        q = self.kalman_q; r = self.kalman_r
        # predict
        b_pred = self.b
        P_pred = self.P + q
        # update
        K = P_pred / (P_pred + r)
        self.b = b_pred + K * (x - b_pred)
        self.P = (1 - K) * P_pred
        return self.b

    def process(self, t, x):
        """Process single sample. Return (detection_tuple or None, best_corr_value)."""
        self.sample_idx += 1
        # 1) baseline
        b = self.update_kalman(x)
        residual = x - b
        # 2) push into circular buffer
        self.res_idx = (self.res_idx + 1) % self.maxL
        self.res_buf[self.res_idx] = residual

        # 3) compute per-template normalized correlation at this time
        best_corr = np.nan
        best_k = -1
        for k, h in enumerate(self.templates):
            L = self.L_list[k]
            # reconstruct ordered window corresponding to template (align center)
            # we will take last L samples ending at current index (common "same" alignment)
            if self.sample_idx < L-1:
                continue
            # get window from circular buffer
            idx0 = (self.res_idx - (L-1)) % self.maxL
            if idx0 <= self.res_idx:
                win = self.res_buf[idx0:self.res_idx+1].copy()
            else:
                win = np.concatenate([self.res_buf[idx0:], self.res_buf[:self.res_idx+1]])
            # numerator
            num = float(np.dot(win, h[::-1]))  # convolution alignment
            local_energy = float(np.sum(win*win))
            denom = math.sqrt(max(local_energy * (np.linalg.norm(h)**2), 1e-12))
            corr = num / denom
            if (best_k == -1) or (corr < best_corr):
                best_corr = corr; best_k = k

        # update robust z stats window (only when pressure > threshold we'll keep updating median-like EWMA)
        if x > self.tr_threshold and not np.isnan(best_corr):
            self.recent_best.append(best_corr)
            # compute running median and MAD approximately every few samples
            if len(self.recent_best) >= 5:
                arr = np.array(self.recent_best)
                med = np.median(arr); mad = np.median(np.abs(arr - med)) + 1e-9
                # smooth update
                self.robust_med = (1 - self.robust_alpha) * self.robust_med + self.robust_alpha * med
                self.robust_mad = (1 - self.robust_alpha) * self.robust_mad + self.robust_alpha * mad

        # z_score
        if not np.isnan(best_corr):
            z = (best_corr - self.robust_med) / (1.4826 * max(self.robust_mad, 1e-9))
        else:
            z = np.nan

        # peak picking (we detect when z < z_thresh and enforce min_sep)
        detect = None
        if (not np.isnan(z)) and (x > self.tr_threshold) and (z < self.z_thresh):
            if (self.last_det_idx < 0) or ((self.sample_idx - self.last_det_idx) >= self.min_sep_samples):
                # declare detection at current sample
                self.last_det_idx = self.sample_idx
                detect = (self.sample_idx, t, x, best_k, best_corr, z)
        return detect, best_corr

# ---------- Helper to stream from CSV as replay ----------

def replay_csv_stream(csv_path, speed=1.0, realtime=True, callback=None, time_col='Stopwatch', pressure_col='Pressure'):
    """
    Replay CSV, calling callback(t, x) for each sample.
    speed >1.0 -> accelerate (sleep shorter).
    realtime True -> use timestamps in file; realtime False -> ignore timestamps and stream by fixed dt derived from median sampling.
    """
    import pandas as pd
    df = pd.read_csv(csv_path)
    if time_col in df.columns:
        tcol = pd.to_numeric(df[time_col], errors='coerce').to_numpy()
    elif 'DateTime' in df.columns:
        tcol = pd.to_datetime(df['DateTime']).astype('int64').to_numpy() / 1e9
    else:
        tcol = np.arange(len(df)).astype(float)
    if pressure_col in df.columns:
        xcol = pd.to_numeric(df[pressure_col], errors='coerce').to_numpy()
    else:
        # fallback to first numeric column
        xcol = pd.to_numeric(df.iloc[:, 0], errors='coerce').to_numpy()

    mask = np.isfinite(tcol) & np.isfinite(xcol)
    tcol = tcol[mask]; xcol = xcol[mask]
    if len(tcol) < 2:
        raise RuntimeError("Not enough samples in CSV")

    # compute dt array
    dts = np.diff(tcol)
    median_dt = float(np.median(dts[dts>0])) if np.any(dts>0) else (1.0/30.0)

    prev_time = None
    for i, (t, x) in enumerate(zip(tcol, xcol)):
        if callback is not None:
            callback(t, float(x))
        if i < len(tcol)-1:
            if realtime:
                sleep_time = (tcol[i+1] - tcol[i]) / max(speed, 1e-9)
                if sleep_time > 0:
                    time.sleep(sleep_time)
            else:
                # simulate fixed-rate streaming at median_dt/speed
                time.sleep(median_dt / max(speed, 1e-9))

# ---------- Main streaming application ----------

def run_streaming_mode(args):
    # determine fs estimate from csv if in replay mode
    if args.mode == 'replay':
        if pd is None:
            raise RuntimeError("pandas required for replay mode; pip install pandas")
        df = pd.read_csv(args.source)
        if 'Stopwatch' in df.columns:
            tvals = pd.to_numeric(df['Stopwatch'], errors='coerce').to_numpy()
        elif 'DateTime' in df.columns:
            tvals = pd.to_datetime(df['DateTime']).astype('int64').to_numpy() / 1e9
        else:
            tvals = np.arange(len(df)).astype(float)
        tvals = tvals[np.isfinite(tvals)]
        if len(tvals) >= 2:
            est_fs = 1.0 / np.median(np.diff(tvals))
        else:
            est_fs = 100.0
    else:
        est_fs = args.fs

    # instantiate streaming detectors
    old_stream = None  # we will use a simpler incremental MA minima as a function below
    new_stream = KalmanMatchedBankStream(est_fs,
                                         min_w_s=args.min_w_s, max_w_s=args.max_w_s,
                                         n_templates=args.n_templates,
                                         kalman_q=args.kalman_q, kalman_r=args.kalman_r,
                                         z_thresh=args.z_thresh, min_sep_s=args.min_sep_s,
                                         tractor_on_thr=args.tractor_on_thr)

    # For old method streaming, implement a simple circular MA + local minima detection:
    w = max(1, int(round(args.smooth_win_s * est_fs)))
    ma_buf = deque([0.0]*w, maxlen=w)
    ma_sum = 0.0
    halfwin = int(round(args.local_max_halfwin_s * est_fs))
    smoothed_history = deque(maxlen=halfwin*2 + 5)
    sample_idx = -1
    last_old_det = -1

    # Output CSV writers (append)
    out_old_path = args.out_old or 'tractor_detections_old_method_stream.csv'
    out_new_path = args.out_new or 'tractor_detections_new_method_stream.csv'
    f_old = open(out_old_path, 'w', newline='')
    f_new = open(out_new_path, 'w', newline='')
    w_old = csv.writer(f_old); w_new = csv.writer(f_new)
    w_old.writerow(['sample_idx', 'time_s', 'smoothed_psi'])
    w_new.writerow(['sample_idx', 'time_s', 'pressure_psi', 'template_idx', 'corr', 'z'])

    # callback invoked per sample
    def callback(t, x):
        nonlocal sample_idx, ma_buf, ma_sum, smoothed_history, last_old_det
        sample_idx += 1
        # OLD streaming MA
        # update ma buffer & sum
        if len(ma_buf) < ma_buf.maxlen or ma_buf.maxlen == 0:
            # if initial fill use append and sum
            if len(ma_buf) < ma_buf.maxlen:
                ma_buf.append(x); ma_sum += x
        else:
            # pop left and append
            left = ma_buf.popleft(); ma_sum -= left
            ma_buf.append(x); ma_sum += x
        # compute smoothed value when buffer full (use partial smoothing before full)
        smoothed = ma_sum / len(ma_buf) if len(ma_buf) > 0 else x
        smoothed_history.append(smoothed)
        # detect local minima in smoothed_history center
        N = len(smoothed_history)
        # we only detect if we have at least 3 points and we're not at start
        if N >= 3:
            center_idx = N//2
            center = list(smoothed_history)[center_idx]
            # ensure tractor-on
            if x > args.tractor_on_thr:
                left = max(0, center_idx - halfwin); right = min(N, center_idx + halfwin + 1)
                seq = list(smoothed_history)
                local_max = max(seq[left:right])
                depth = local_max - center
                if depth >= args.prominence_psi:
                    # global sample index of candidate is sample_idx - (N - 1 - center_idx)
                    cand_idx = sample_idx - (N - 1 - center_idx)
                    if (last_old_det < 0) or ((cand_idx - last_old_det) >= int(round(args.min_sep_s * est_fs))):
                        # record detection; time approximated as t (current) shifted back to cand time
                        cand_time = t - ( (N - 1 - center_idx) * (1.0/est_fs) )
                        w_old.writerow([cand_idx, cand_time, center])
                        last_old_det = cand_idx

        # NEW method (Kalman + matched bank)
        detect, corr = new_stream.process(t, x)
        if detect is not None:
            idx, tt, val, template_idx, corr_val, z = detect
            w_new.writerow([idx, tt, val, template_idx, corr_val, z])
            # flush so immediate persist
            f_new.flush()

    # Choose stream source
    if args.mode == 'replay':
        replay_csv_stream(args.source, speed=args.speed, realtime=args.realtime, callback=callback)
    elif args.mode == 'stdin':
        # Expect lines "time,pressure"
        import sys
        for line in sys.stdin:
            line = line.strip()
            if not line: continue
            parts = line.split(',')
            if len(parts) >= 2:
                t = float(parts[0]); x = float(parts[1])
                callback(t, x)
    elif args.mode == 'websocket':
        # Simple skeleton for websocket client; requires "websockets" package.
        try:
            import asyncio, websockets
        except Exception as e:
            raise RuntimeError("websocket mode requires 'websockets' package (pip install websockets)") from e
        async def ws_run():
            async with websockets.connect(args.source) as ws:
                async for msg in ws:
                    # assume message is "time,pressure" or JSON {"t":..., "p":...}
                    msg = msg.strip()
                    if not msg: continue
                    if msg.startswith('{'):
                        import json
                        j = json.loads(msg)
                        t = float(j.get('t') or j.get('time') or j.get('timestamp'))
                        x = float(j.get('p') or j.get('pressure'))
                    else:
                        parts = msg.split(',')
                        t = float(parts[0]); x = float(parts[1])
                    callback(t, x)
        asyncio.get_event_loop().run_until_complete(ws_run())
    else:
        raise ValueError("Unknown mode")

    f_old.close(); f_new.close()
    print("Streaming finished. Saved streams to:", out_old_path, out_new_path)
    # plotting if requested
    if args.plot and pd is not None:
        # read saved files and plot summary
        try:
            det_old = pd.read_csv(out_old_path)
            det_new = pd.read_csv(out_new_path)
            if args.mode == 'replay':
                df = pd.read_csv(args.source)
                if 'Stopwatch' in df.columns:
                    tcol = pd.to_numeric(df['Stopwatch'], errors='coerce').to_numpy()
                elif 'DateTime' in df.columns:
                    tcol = pd.to_datetime(df['DateTime']).astype('int64').to_numpy() / 1e9
                else:
                    tcol = np.arange(len(df)).astype(float)
                if 'Pressure' in df.columns:
                    xcol = pd.to_numeric(df['Pressure'], errors='coerce').to_numpy()
                else:
                    xcol = pd.to_numeric(df.iloc[:, 0], errors='coerce').to_numpy()
                mask = np.isfinite(tcol) & np.isfinite(xcol)
                tcol = tcol[mask]; xcol = xcol[mask]
                import matplotlib.pyplot as plt
                plt.figure(figsize=(12,5))
                plt.plot(tcol, xcol, label='pressure', linewidth=0.6)
                if len(det_old):
                    plt.scatter(det_old['time_s'], det_old['smoothed_psi'], marker='x', color='C3', label='old dets')
                if len(det_new):
                    plt.scatter(det_new['time_s'], det_new['pressure_psi'], marker='o', facecolors='none', edgecolors='r', label='new dets')
                plt.legend(); plt.title('Stream detections (end-of-run)'); plt.show()
        except Exception as e:
            print("Plotting failed:", e)


# ---------- CLI ----------

def parse_args():
    p = argparse.ArgumentParser(description="Combined detector (streaming).")
    p.add_argument('mode', choices=['replay', 'stdin', 'websocket'], help="stream source")
    p.add_argument('source', help="CSV path for replay, '-' for stdin, or ws:// URL for websocket")
    p.add_argument('--speed', type=float, default=1.0, help="replay speed multiplier (>1 faster)")
    p.add_argument('--realtime', type=lambda x: bool(str(x).lower() in ('1','true','yes')), default=True, help="use file timestamps for replay")
    p.add_argument('--fs', type=float, default=100.0, help="sampling rate guess (for stdin/websocket)")
    p.add_argument('--plot', action='store_true', help="plot results at end (replay mode only)")

    # old method args
    p.add_argument('--smooth_win_s', type=float, default=0.7)
    p.add_argument('--prominence_psi', type=float, default=25.0)
    p.add_argument('--local_max_halfwin_s', type=float, default=2.5)
    p.add_argument('--min_sep_s', type=float, default=3.0)
    p.add_argument('--tractor_on_thr', type=float, default=1500.0)

    # new method args
    p.add_argument('--min_w_s', type=float, default=0.5)
    p.add_argument('--max_w_s', type=float, default=1.5)
    p.add_argument('--n_templates', type=int, default=5)
    p.add_argument('--kalman_q', type=float, default=1.0)
    p.add_argument('--kalman_r', type=float, default=100.0**2)
    p.add_argument('--z_thresh', type=float, default=-3.0)
    # p.add_argument('--min_sep_s', type=float, default=2.0)

    p.add_argument('--out_old', type=str, default=None)
    p.add_argument('--out_new', type=str, default=None)
    return p.parse_args()

if __name__ == '__main__':
    args = parse_args()
    run_streaming_mode(args)
