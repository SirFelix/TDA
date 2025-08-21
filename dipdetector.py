# detector_stream_plot.py
import numpy as np
import math
import matplotlib.pyplot as plt
from collections import deque

class DipDetector:
    def __init__(self, fs=30.0, L=5, alpha=0.02, beta=0.02,
                 thr_k=1.6, refractory_s=1.5):
        self.fs = fs
        self.L = L
        # Negative Hann template -> zero-mean, unit-energy
        t = -0.5*(1 - np.cos(2*np.pi*np.arange(L)/(L-1)))
        t -= t.mean()
        self.t = t / max(np.linalg.norm(t), 1e-9)

        # sliding buffer
        self.buf = deque([0.0]*L, maxlen=L)
        # EWMA baseline & scale
        self.m = 0.0
        self.s = 1.0
        self.alpha = alpha
        self.beta = beta

        # detection thresholding
        self.thr_k = thr_k
        self.rho_std = 1.0
        self.rho_beta = 0.02

        # refractory period (samples)
        self.refractory = int(round(refractory_s*fs))
        self.cooldown = 0
        self.started = False  # becomes True after the buffer has useful data

    def update(self, x):
        # EWMA mean and scale (robust-ish)
        self.m = (1 - self.alpha)*self.m + self.alpha*x
        dev = abs(x - self.m)
        self.s = (1 - self.beta)*self.s + self.beta*max(dev, 1e-6)
        xn = (x - self.m) / max(self.s, 1e-6)

        # slide buffer
        self.buf.append(xn)
        buf_list = list(self.buf)

        # only consider started once buffer has had a chance to contain real data
        if not self.started and any(abs(v) > 1e-12 for v in buf_list):
            self.started = True

        if not self.started:
            # not enough info yet
            return None, False, 0.0

        # compute dot product with template and local stats (small L so OK to recompute)
        sumxt = 0.0
        sumx = 0.0
        sumx2 = 0.0
        for j, v in enumerate(buf_list):
            sumxt += v * self.t[j]
            sumx += v
            sumx2 += v*v

        meanx = sumx / self.L
        varx = max(sumx2 - self.L*meanx*meanx, 1e-9)
        rho = sumxt / math.sqrt(varx)

        # update rho noise proxy
        self.rho_std = (1 - self.rho_beta)*self.rho_std + self.rho_beta*abs(rho)

        detected = False
        if self.cooldown > 0:
            self.cooldown -= 1
        else:
            if rho < -self.thr_k * self.rho_std:  # negative because template is negative
                detected = True
                self.cooldown = self.refractory

        return rho, detected, sumxt    # sumxt is matched-filter dot (normalized units)


def simulate_stream_array(duration_s=60.0, fs=30.0,
                          mean_level=4000.0, dip_depth=20.0,
                          dip_duration_s=0.125, period_s_jitter=(3.0, 5.0),
                          noise_sigma=200.0, seed=42):
    rng = np.random.default_rng(seed)
    n_total = int(round(duration_s * fs))
    dt = 1.0 / fs
    times = np.arange(n_total) * dt

    # schedule dips with jittered periods
    dip_starts = []
    t_next = rng.uniform(*period_s_jitter)
    while t_next < duration_s:
        dip_starts.append(t_next)
        t_next += rng.uniform(*period_s_jitter)

    xs = np.empty(n_total)
    for i, t in enumerate(times):
        x = mean_level + rng.normal(0.0, noise_sigma)
        # check if inside any dip window
        in_dip = any((t >= s) and (t < s + dip_duration_s) for s in dip_starts)
        if in_dip:
            # Hann-shaped local envelope inside the dip window for realism
            s0 = max(s for s in dip_starts if s <= t)
            phase = (t - s0) / max(dip_duration_s, 1e-9)
            phase = min(max(phase, 0.0), 0.999999)
            env = 0.5*(1 - math.cos(2*math.pi*phase))
            x -= dip_depth * env
        xs[i] = x

    return times, xs, dip_starts


if __name__ == "__main__":
    fs = 30.0
    duration = 60.0
    times, xs, dip_starts = simulate_stream_array(duration_s=duration, fs=fs,
                                                  mean_level=4000.0, dip_depth=20.0,
                                                  dip_duration_s=0.125, period_s_jitter=(3.0,5.0),
                                                  noise_sigma=200.0, seed=7)

    det = DipDetector(fs=fs, L=6, alpha=0.02, beta=0.02, thr_k=2.8, refractory_s=1.5)

    rhos = np.full_like(xs, np.nan, dtype=float)
    filter_out = np.zeros_like(xs)
    detections_idx = []
    for i, x in enumerate(xs):
        rho, detected, sumxt = det.update(x)
        rhos[i] = rho if rho is not None else np.nan
        filter_out[i] = sumxt
        if detected:
            detections_idx.append(i)

    # For plotting: scale the normalized matched-filter output to rough psi units
    # by multiplying by a local rolling std (approximate)
    window = int(round(0.5 * fs))  # 0.5 s local window
    local_std = np.array([np.std(xs[max(0,i-window+1):i+1]) if i>0 else np.std(xs[:1]) for i in range(len(xs))])
    local_std[local_std < 1e-6] = 1.0
    filter_psi = filter_out * local_std

    # Plot raw with scaled filter overlay and detection markers
    plt.figure(figsize=(12,5))
    ax1 = plt.gca()
    ax1.plot(times, xs, label="raw pressure (psi)", linewidth=0.8)
    # overlay scaled matched-filter, offset so it's visible
    offset = np.percentile(xs, 90) + 20
    ax1.plot(times, offset + 0.5*filter_psi, label="matched filter (scaled & offset)", linewidth=1.2)
    # true dip starts (green lines)
    for s in dip_starts:
        ax1.axvline(s, color='green', linestyle=':', alpha=0.6, label='true dip start' if s==dip_starts[0] else "")
    # detections (red X)
    if detections_idx:
        det_times = times[detections_idx]
        det_vals  = xs[detections_idx]
        ax1.scatter(det_times, det_vals, marker='x', color='red', s=60, label="detections")
    ax1.set_xlabel("time (s)")
    ax1.set_ylabel("pressure (psi)")
    ax1.set_title("Raw pressure with matched-filter overlay and detections (red X)")
    ax1.legend(loc='upper right')

    # Plot rho below
    plt.figure(figsize=(12,2.8))
    plt.plot(times, rhos, label="rho (NCC)", linewidth=0.9)
    # show threshold (approx): -thr_k * avg rho_std (the rho_std is dynamic; show last value scaled)
    thr_line = -det.thr_k * det.rho_std
    plt.axhline(thr_line, color='red', linestyle='--', label=f"threshold ~ {thr_line:.2f}")
    for idx in detections_idx:
        plt.axvline(times[idx], color='red', alpha=0.4)
    plt.xlabel("time (s)")
    plt.ylabel("rho")
    plt.title("Detector statistic (rho)")
    plt.ylim(-4, 4)
    plt.legend(loc='upper right')

    plt.show()

    print("Detected times (s):", np.round(times[detections_idx], 3).tolist())
    print("Number of detections:", len(detections_idx))
