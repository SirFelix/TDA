#!/usr/bin/env python3
"""
dip_detector_montecarlo.py

Monte Carlo evaluation of a streaming matched-filter dip detector.
Saves a summary table and plots TPR vs false positives per minute.

Usage:
    python dip_detector_montecarlo.py

Tweak parameters in the CONFIG section below.
"""

import numpy as np
import math
from collections import deque
import matplotlib.pyplot as plt
import pandas as pd
import time

# ---------------- CONFIG ----------------
FS = 30.0
DURATION_S = 120.0        # seconds per trial
TRIALS = 200             # Monte Carlo trials per configuration (reduce to 50 for quick runs)
LS = [4, 5, 6, 7, 8]           # template lengths (samples)
THR_KS = [1.6, 1.7, 1.75, 1.8, 1.85, 1.9, 1.95, 2.0, 2.05, 2.1, 2.15, 2.2, 2.25, 2.3, 2.35, 2.4, 2.45, 2.5, 2.55, 2.6, 2.65, 2.7, 2.75, 2.8, 2.85, 2.9, 2.95, 3.0]  # detection thresholds (multiples of rho_std)
NOISE_SIGMA = 200.0
DIP_DEPTH = 20.0
DIP_DURATION_S = 0.125
PERIOD_JITTER = (3.0, 6.0)
SEED_BASE = 12345
TP_TOL_S = 0.5           # allowed time window to match a detection to a true dip (seconds)
VERBOSE = True
# ----------------------------------------

class DipDetector:
    def __init__(self, fs=30.0, L=6, alpha=0.02, beta=0.02,
                 thr_k=2.5, refractory_s=1.5):
        self.fs = fs
        self.L = L
        # Negative Hann template -> zero-mean, unit-energy
        t = -0.5*(1 - np.cos(2*np.pi*np.arange(L)/(L-1)))
        t -= t.mean()
        self.t = t / max(np.linalg.norm(t), 1e-9)
        # sliding buffer & adaptive stats
        self.buf = deque([0.0]*L, maxlen=L)
        self.m = 0.0
        self.s = 1.0
        self.alpha = alpha
        self.beta = beta
        self.thr_k = thr_k
        self.rho_std = 1.0
        self.rho_beta = 0.02
        self.refractory = int(round(refractory_s*fs))
        self.cooldown = 0
        self.started = False

    def update(self, x):
        # ewma baseline + scale
        self.m = (1 - self.alpha)*self.m + self.alpha*x
        dev = abs(x - self.m)
        self.s = (1 - self.beta)*self.s + self.beta*max(dev, 1e-6)
        xn = (x - self.m) / max(self.s, 1e-6)

        self.buf.append(xn)
        buf_list = list(self.buf)
        if not self.started and any(abs(v) > 1e-12 for v in buf_list):
            self.started = True
        if not self.started:
            return None, False, 0.0

        # compute correlation and normalization (small L -> recompute is cheap)
        sumxt = 0.0; sumx = 0.0; sumx2 = 0.0
        for j, v in enumerate(buf_list):
            sumxt += v * self.t[j]; sumx += v; sumx2 += v*v
        meanx = sumx / self.L
        varx = max(sumx2 - self.L*meanx*meanx, 1e-9)
        rho = sumxt / math.sqrt(varx)
        self.rho_std = (1 - self.rho_beta)*self.rho_std + self.rho_beta*abs(rho)

        detected = False
        if self.cooldown > 0:
            self.cooldown -= 1
        else:
            if rho < -self.thr_k * self.rho_std:
                detected = True
                self.cooldown = self.refractory

        return rho, detected, sumxt


def simulate_stream_array(duration_s=60.0, fs=30.0,
                          mean_level=4000.0, dip_depth=20.0,
                          dip_duration_s=0.125, period_s_jitter=(3.0, 5.0),
                          noise_sigma=200.0, seed=42):
    rng = np.random.default_rng(seed)
    n_total = int(round(duration_s * fs))
    dt = 1.0 / fs
    times = np.arange(n_total) * dt
    dip_starts = []
    t_next = rng.uniform(*period_s_jitter)
    while t_next < duration_s:
        dip_starts.append(t_next)
        t_next += rng.uniform(*period_s_jitter)

    xs = np.empty(n_total)
    for i, t in enumerate(times):
        x = mean_level + rng.normal(0.0, noise_sigma)
        in_dip = any((t >= s) and (t < s + dip_duration_s) for s in dip_starts)
        if in_dip:
            s0 = max(s for s in dip_starts if s <= t)
            phase = (t - s0) / max(dip_duration_s, 1e-9)
            phase = min(max(phase, 0.0), 0.999999)
            env = 0.5*(1 - math.cos(2*math.pi*phase))
            x -= dip_depth * env
        xs[i] = x
    return times, xs, np.array(dip_starts)


def evaluate_detector(fs=30.0, L=6, thr_k=2.5, trials=100, seed0=0, verbose=False):
    rng = np.random.default_rng(seed0)
    results = []
    for tr in range(trials):
        seed = int(rng.integers(1, 1_000_000))
        times, xs, dip_starts = simulate_stream_array(duration_s=DURATION_S, fs=fs,
                                                      mean_level=4000.0, dip_depth=DIP_DEPTH,
                                                      dip_duration_s=DIP_DURATION_S,
                                                      period_s_jitter=PERIOD_JITTER,
                                                      noise_sigma=NOISE_SIGMA, seed=seed)
        det = DipDetector(fs=fs, L=L, thr_k=thr_k, refractory_s=1.5)
        detections = []
        for i, x in enumerate(xs):
            rho, detected, _ = det.update(x)
            if detected:
                detections.append(times[i])
        detections = np.array(detections)
        # Match detections to dip_starts using tolerance TP_TOL_S
        tol_s = TP_TOL_S
        tp = 0
        matched = set()
        for d in detections:
            idx = np.where(np.abs(dip_starts - d) <= tol_s)[0]
            if idx.size > 0:
                matched_idx = None
                for j in idx:
                    if j not in matched:
                        matched_idx = j; break
                if matched_idx is not None:
                    tp += 1; matched.add(matched_idx)
        fp = max(0, len(detections) - tp)
        fn = max(0, len(dip_starts) - tp)
        results.append({'tp': tp, 'fp': fp, 'fn': fn, 'n_dips': len(dip_starts), 'n_detections': len(detections)})
        if verbose and (tr+1) % 50 == 0:
            print(f"  trial {tr+1}/{trials} done for L={L}, thr={thr_k}")
    # aggregate
    tp_sum = sum(r['tp'] for r in results)
    fp_sum = sum(r['fp'] for r in results)
    fn_sum = sum(r['fn'] for r in results)
    dips_sum = sum(r['n_dips'] for r in results)
    detections_sum = sum(r['n_detections'] for r in results)
    return {'trials': trials, 'tp': tp_sum, 'fp': fp_sum, 'fn': fn_sum,
            'dips': dips_sum, 'detections': detections_sum, 'per_trial': results}


def main():
    start_time = time.time()
    summary = {}
    total_configs = len(LS) * len(THR_KS)
    config_index = 0
    print(f"Running Monte Carlo: {TRIALS} trials per config, {total_configs} configs ({len(LS)} Ls x {len(THR_KS)} thr).")
    for L in LS:
        for thr in THR_KS:
            config_index += 1
            print(f"\n[{config_index}/{total_configs}] L={L}, thr={thr} ...", end="\n", flush=True)
            res = evaluate_detector(fs=FS, L=L, thr_k=thr, trials=TRIALS, seed0=SEED_BASE + int(L*10 + thr*100), verbose=VERBOSE)
            summary[(L, thr)] = res
            print("done")
    # Summarize into DataFrame
    rows = []
    for (L,thr), res in summary.items():
        tpr = res['tp'] / res['dips'] if res['dips']>0 else 0.0
        # false positives per minute: total FP / total minutes simulated
        total_minutes = res['trials'] * (DURATION_S/60.0)
        fpr_per_min = res['fp'] / total_minutes
        rows.append({'L':L, 'thr':thr, 'TPR':tpr, 'FPR_per_min': fpr_per_min,
                     'TP':res['tp'], 'FP':res['fp'], 'FN':res['fn'], 'Dips':res['dips']})
    df = pd.DataFrame(rows).sort_values(['L','thr']).reset_index(drop=True)
    print("\nSummary (by config):")
    print(df.to_string(index=False))

    # Plot TPR vs FPR_per_min
    plt.figure(figsize=(8,5))
    markers = {4:'o',6:'s',8:'^'}
    for _, row in df.iterrows():
        plt.scatter(row['FPR_per_min'], row['TPR'], label=f"L={int(row['L'])},thr={row['thr']}", marker=markers[int(row['L'])], s=80)
    plt.xlabel("False positives per minute")
    plt.ylabel("True positive rate (recall)")
    plt.title(f"Detector tradeoff (TRIALS={TRIALS}, duration per trial={DURATION_S}s)")
    plt.legend(bbox_to_anchor=(1.05,1), loc='upper left')
    plt.grid(True)
    plt.tight_layout()
    plt.show()

    # Print top configs by simple score (TPR - 0.02*FPR_per_min)
    scored = []
    for _, row in df.iterrows():
        score = row['TPR'] - 0.02 * row['FPR_per_min']
        scored.append((score, row))
    scored_sorted = sorted(scored, key=lambda x: x[0], reverse=True)
    print("\nTop configs (TPR penalized by FPR):")
    for score, r in scored_sorted[:6]:
        print(f" L={int(r['L'])}, thr={r['thr']}: TPR={r['TPR']:.3f}, FPR/min={r['FPR_per_min']:.3f}, TP={r['TP']}, FP={r['FP']} (score={score:.3f})")

    print(f"\nTotal run time: {time.time()-start_time:.1f}s")
    # Save df
    df.to_csv("detector_montecarlo_summary.csv", index=False)
    print("Saved summary CSV: detector_montecarlo_summary.csv")


if __name__ == "__main__":
    main()
