#!/usr/bin/env python3
"""
combined_detector_stream_live.py

Streaming combined detector with live plotting (replay / stdin / websocket).

Usage:
  python combined_detector_stream_live.py replay path/to/tractor_section.csv --realtime True --plot_interval 0.5

Options:
  replay  : replay CSV file (expects Stopwatch or DateTime and Pressure columns)
  stdin   : read lines "time,pressure" from stdin
  websocket: websocket source (skeleton; needs `websockets`)

Outputs:
  two CSVs with detections: tractor_detections_old_stream.csv and tractor_detections_new_stream.csv
"""

import argparse, time, math, csv, os, sys
from collections import deque
import numpy as np

try:
    import pandas as pd
except Exception:
    pd = None

# -------------------- Kalman + matched bank (streaming) --------------------

class KalmanMatchedBankStream:
    def __init__(self, fs, min_w_s=0.5, max_w_s=1.5, n_templates=5,
                 kalman_q=1.0, kalman_r=100.0**2, z_thresh=-3.0,
                 min_sep_s=2.0, tractor_on_thr=1500.0):
        self.fs = float(fs)
        self.min_w_s = float(min_w_s); self.max_w_s = float(max_w_s)
        self.n_templates = int(n_templates)
        self.kalman_q = float(kalman_q); self.kalman_r = float(kalman_r)
        self.z_thresh = float(z_thresh)
        self.min_sep_samples = int(round(min_sep_s * fs))
        self.tr_threshold = float(tractor_on_thr)

        # Kalman
        self.P = 1.0
        self.b = None

        # Templates
        widths_s = np.linspace(self.min_w_s, self.max_w_s, self.n_templates)
        self.templates = []
        self.L_list = []
        for w_s in widths_s:
            L = int(round(w_s * self.fs))
            if L < 3: L = 3
            self.L_list.append(L)
            tt = np.arange(L)
            sigma = max(1.0, L / 6.0)
            gauss = np.exp(-0.5 * ((tt - (L - 1) / 2) / sigma) ** 2)
            pulse = -gauss
            pulse = pulse - pulse.mean()
            pulse = pulse / max(np.linalg.norm(pulse), 1e-9)
            self.templates.append(pulse)

        self.maxL = max(self.L_list)
        self.res_buf = np.zeros(self.maxL, dtype=float)
        self.res_idx = -1
        self.sample_idx = -1
        self.last_det_idx = -1

        # robust stats for normalization (EWMA-like)
        self.robust_med = 0.0
        self.robust_mad = 1.0
        self.robust_alpha = 0.02
        self.recent_best = deque(maxlen=int(round(5.0 * self.fs)))

    def update_kalman(self, x):
        if self.b is None:
            self.b = x
            self.P = 1.0
            return self.b
        q = self.kalman_q; r = self.kalman_r
        b_pred = self.b
        P_pred = self.P + q
        K = P_pred / (P_pred + r)
        self.b = b_pred + K * (x - b_pred)
        self.P = (1 - K) * P_pred
        return self.b

    def process(self, t, x):
        """
        Process one sample. Returns detection tuple (sample_idx, time, pressure, template_idx, corr, z)
        or None, and the current baseline and best_corr for plotting/inspection.
        """
        self.sample_idx += 1
        b = self.update_kalman(x)
        residual = x - b

        # circular buffer
        self.res_idx = (self.res_idx + 1) % self.maxL
        self.res_buf[self.res_idx] = residual

        best_corr = np.nan
        best_k = -1

        for k, h in enumerate(self.templates):
            L = self.L_list[k]
            if self.sample_idx < L - 1:
                continue
            # reconstruct last L samples (ordered)
            idx0 = (self.res_idx - (L - 1)) % self.maxL
            if idx0 <= self.res_idx:
                win = self.res_buf[idx0:self.res_idx + 1].copy()
            else:
                win = np.concatenate([self.res_buf[idx0:], self.res_buf[:self.res_idx + 1]])
            num = float(np.dot(win, h[::-1]))
            local_energy = float(np.sum(win * win))
            denom = math.sqrt(max(local_energy * (np.linalg.norm(h) ** 2), 1e-12))
            corr = num / denom
            if (best_k == -1) or (corr < best_corr):
                best_corr = corr; best_k = k

        # update robust stats (only when on threshold)
        if (not np.isnan(best_corr)) and (x > self.tr_threshold):
            self.recent_best.append(best_corr)
            if len(self.recent_best) >= 5:
                arr = np.array(self.recent_best)
                med = np.median(arr)
                mad = np.median(np.abs(arr - med)) + 1e-9
                self.robust_med = (1 - self.robust_alpha) * self.robust_med + self.robust_alpha * med
                self.robust_mad = (1 - self.robust_alpha) * self.robust_mad + self.robust_alpha * mad

        z = np.nan
        if not np.isnan(best_corr):
            z = (best_corr - self.robust_med) / (1.4826 * max(self.robust_mad, 1e-9))

        detect = None
        if (not np.isnan(z)) and (x > self.tr_threshold) and (z < self.z_thresh):
            if (self.last_det_idx < 0) or ((self.sample_idx - self.last_det_idx) >= self.min_sep_samples):
                self.last_det_idx = self.sample_idx
                detect = (self.sample_idx, t, x, best_k, best_corr, z)

        return detect, b, best_corr, z

# -------------------- Replay helper --------------------

def replay_csv_stream(csv_path, speed=1.0, realtime=True, callback=None,
                      time_col='Stopwatch', pressure_col='Pressure'):
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
        xcol = pd.to_numeric(df.iloc[:, 0], errors='coerce').to_numpy()

    mask = np.isfinite(tcol) & np.isfinite(xcol)
    tcol = tcol[mask]; xcol = xcol[mask]
    if len(tcol) < 2:
        raise RuntimeError("Not enough samples in CSV")

    for i, (t, x) in enumerate(zip(tcol, xcol)):
        if callback is not None:
            callback(t, float(x))
        if i < len(tcol) - 1:
            if realtime:
                sleep_time = (tcol[i + 1] - tcol[i]) / max(speed, 1e-9)
                if sleep_time > 0:
                    time.sleep(sleep_time)
            else:
                median_dt = float(np.median(np.diff(tcol)))
                time.sleep(median_dt / max(speed, 1e-9))

# -------------------- Streaming app with live plotting --------------------

def run_streaming_with_live_plot(args):
    # estimate fs from file when replay mode
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
            est_fs = args.fs
    else:
        est_fs = args.fs

    print(f"Estimated sampling fs ≈ {est_fs:.2f} Hz")

    # instantiate detectors
    new_stream = KalmanMatchedBankStream(est_fs,
                                         min_w_s=args.min_w_s, max_w_s=args.max_w_s,
                                         n_templates=args.n_templates,
                                         kalman_q=args.kalman_q, kalman_r=args.kalman_r,
                                         z_thresh=args.z_thresh, min_sep_s=args.min_sep_s,
                                         tractor_on_thr=args.tractor_on_thr)

    # simple moving-average for old method (streaming)
    w = max(1, int(round(args.smooth_win_s * est_fs)))
    ma_buf = deque(maxlen=w)
    ma_sum = 0.0
    halfwin = int(round(args.local_max_halfwin_s * est_fs))
    smoothed_history = deque(maxlen=halfwin*2 + 5)
    sample_idx = -1
    last_old_det = -1

    # output files
    out_old = args.out_old or 'tractor_detections_old_stream.csv'
    out_new = args.out_new or 'tractor_detections_new_stream.csv'
    f_old = open(out_old, 'w', newline=''); w_old = csv.writer(f_old); w_old.writerow(['sample_idx', 'time_s', 'smoothed_psi'])
    f_new = open(out_new, 'w', newline=''); w_new = csv.writer(f_new); w_new.writerow(['sample_idx', 'time_s', 'pressure_psi', 'template_idx', 'corr', 'z'])

    # collecting arrays for plotting
    times_buf = []
    x_buf = []
    baseline_buf = []
    rho_buf = []
    dets_old = []
    dets_new = []

    # plotting setup
    if args.plot:
        try:
            import matplotlib.pyplot as plt
        except Exception:
            print("matplotlib not available; disabling plotting.")
            args.plot = False

    # callback that handles a single sample
    def callback(t, x):
        nonlocal sample_idx, ma_buf, ma_sum, smoothed_history, last_old_det
        sample_idx += 1

        # ----- OLD streaming MA minima detection -----
        if len(ma_buf) < ma_buf.maxlen:
            ma_buf.append(x); ma_sum += x
        else:
            left = ma_buf.popleft(); ma_sum -= left
            ma_buf.append(x); ma_sum += x
        smoothed = ma_sum / len(ma_buf) if len(ma_buf) > 0 else x
        smoothed_history.append(smoothed)

        # detect in smoothed_history center if enough samples
        if len(smoothed_history) >= 3:
            seq = list(smoothed_history)
            center_idx = len(seq) // 2
            center = seq[center_idx]
            if x > args.tractor_on_thr:
                left = max(0, center_idx - halfwin); right = min(len(seq), center_idx + halfwin + 1)
                local_max = max(seq[left:right])
                depth = local_max - center
                if depth >= args.prominence_psi:
                    cand_idx = sample_idx - (len(seq) - 1 - center_idx)
                    if (last_old_det < 0) or ((cand_idx - last_old_det) >= int(round(args.min_sep_s * est_fs))):
                        # approximate cand_time by shifting current t back
                        cand_time = t - ((len(seq) - 1 - center_idx) * (1.0 / est_fs))
                        w_old.writerow([cand_idx, cand_time, center])
                        f_old.flush()
                        last_old_det = cand_idx
                        dets_old.append((cand_idx, cand_time))
                        print(f"[OLD] Detected dip at ~{cand_time:.3f}s (sample {cand_idx})")

        # ----- NEW method processing -----
        detect, baseline, best_corr, z = new_stream.process(t, x)
        times_buf.append(t); x_buf.append(x); baseline_buf.append(baseline); rho_buf.append(best_corr if not np.isnan(best_corr) else 0.0)

        if detect is not None:
            idx, tt, val, template_idx, corr_val, zval = detect
            w_new.writerow([idx, tt, val, template_idx, corr_val, zval])
            f_new.flush()
            dets_new.append((idx, tt))
            print(f"[NEW] Detected dip at {tt:.3f}s (sample {idx}) template={template_idx} corr={corr_val:.3f} z={zval:.2f}")

        # update live plot occasionally
        if args.plot and (len(times_buf) % max(1, int(round(args.plot_interval * est_fs))) == 0):
            # rolling window length in seconds
            win_s = args.plot_window_s
            win_samples = int(round(win_s * est_fs))
            if win_samples < 10: win_samples = min(200, len(times_buf))
            plt.clf()
            plt.subplot(2,1,1)
            tb = np.array(times_buf[-win_samples:])
            xb = np.array(x_buf[-win_samples:])
            bb = np.array(baseline_buf[-win_samples:])
            plt.plot(tb, xb, label='pressure', linewidth=0.6)
            plt.plot(tb, bb, label='kalman baseline', linewidth=1.0)
            # mark detections occurring in window
            new_in_window = [d for d in dets_new if tb[0] <= d[1] <= tb[-1]]
            old_in_window = [d for d in dets_old if tb[0] <= d[1] <= tb[-1]]
            if old_in_window:
                times_old = [d[1] for d in old_in_window]; vals_old = np.interp(times_old, tb, xb)
                plt.scatter(times_old, vals_old, marker='x', color='C3', s=40, label='old dets')
            if new_in_window:
                times_new = [d[1] for d in new_in_window]; vals_new = np.interp(times_new, tb, xb)
                plt.scatter(times_new, vals_new, marker='o', facecolors='none', edgecolors='r', s=60, label='new dets')
            plt.axhline(args.tractor_on_thr, linestyle='--', color='k', alpha=0.5)
            plt.legend(loc='upper right')
            plt.title("Live stream (rolling)")

            plt.subplot(2,1,2)
            rb = np.array(rho_buf[-win_samples:])
            plt.plot(tb, rb, label='best_corr (scaled)', linewidth=0.8)
            plt.axhline(0, color='k', linewidth=0.4)
            plt.ylabel('corr')
            plt.xlabel('time (s)')
            plt.tight_layout()
            plt.pause(0.001)

    # Choose source
    try:
        if args.mode == 'replay':
            replay_csv_stream(args.source, speed=args.speed, realtime=args.realtime, callback=callback)
        elif args.mode == 'stdin':
            for line in sys.stdin:
                line = line.strip()
                if not line: continue
                parts = line.split(',')
                if len(parts) >= 2:
                    tt = float(parts[0]); xx = float(parts[1])
                    callback(tt, xx)
        elif args.mode == 'websocket':
            import asyncio, websockets, json
            async def ws_run():
                async with websockets.connect(args.source) as ws:
                    async for msg in ws:
                        msg = msg.strip()
                        if not msg: continue
                        if msg.startswith('{'):
                            j = json.loads(msg)
                            tt = float(j.get('t') or j.get('time') or j.get('timestamp'))
                            xx = float(j.get('p') or j.get('pressure'))
                        else:
                            parts = msg.split(',')
                            tt = float(parts[0]); xx = float(parts[1])
                        callback(tt, xx)
            asyncio.get_event_loop().run_until_complete(ws_run())
        else:
            raise ValueError("unknown mode")
    finally:
        f_old.close(); f_new.close()
        print("Streaming finished. Outputs saved:", out_old, out_new)

# -------------------- CLI --------------------

def parse_args():
    p = argparse.ArgumentParser(description="Combined detector streaming with live plot")
    p.add_argument('mode', choices=['replay','stdin','websocket'])
    p.add_argument('source', help="CSV path for replay, '-' for stdin, or ws:// URL for websocket")
    p.add_argument('--speed', type=float, default=1.0, help="replay speed multiplier")
    p.add_argument('--realtime', type=lambda x: bool(str(x).lower() in ('1','true','yes')), default=True)
    p.add_argument('--fs', type=float, default=100.0, help="sampling rate guess for stdin/ws")
    p.add_argument('--plot', action='store_true', help="enable live plotting")
    p.add_argument('--plot_interval', type=float, default=0.5, help="plot refresh interval (seconds)")
    p.add_argument('--plot_window_s', type=float, default=60.0, help="plot rolling window seconds")

    # old method params
    p.add_argument('--smooth_win_s', type=float, default=0.7)
    p.add_argument('--prominence_psi', type=float, default=25.0)
    p.add_argument('--local_max_halfwin_s', type=float, default=2.5)
    p.add_argument('--min_sep_s', type=float, default=3.0)
    p.add_argument('--tractor_on_thr', type=float, default=1500.0)

    # new method params
    p.add_argument('--min_w_s', type=float, default=0.5)
    p.add_argument('--max_w_s', type=float, default=1.5)
    p.add_argument('--n_templates', type=int, default=5)
    p.add_argument('--kalman_q', type=float, default=1.0)
    p.add_argument('--kalman_r', type=float, default=100.0**2)
    p.add_argument('--z_thresh', type=float, default=-3.0)
    p.add_argument('--min_sep_s', type=float, default=2.0)

    p.add_argument('--out_old', type=str, default=None)
    p.add_argument('--out_new', type=str, default=None)
    return p.parse_args()

if __name__ == '__main__':
    args = parse_args()
    run_streaming_with_live_plot(args)
