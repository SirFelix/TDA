import numpy as np
from collections import deque
from smoothn import smoothn  # import smoothn as smoothn
import matplotlib.pyplot as plt
# from your_module import smoothn  # ensure smoothn(...) is available (from previous message)

class LiveSmoothN:
    """
    Streaming fixed-lag smoother for 1D data using Damien Garcia's smoothn on a rolling window.
    At each new sample, it smooths the current window and emits the center sample of the smoothed window.
    """
    def __init__(self,
                 fs=30.0,
                 window_seconds=1.0,   # 1.0 s window -> 0.5 s lag at 30 Hz (recommended)
                 s=None,               # None = auto GCV
                 robust=True,
                 max_iter=100,
                 tol_z=1e-3):
        self.fs = float(fs)
        win = int(round(window_seconds * self.fs))
        win = max(3, win)                         # minimum length
        if win % 2 == 0:
            win += 1                              # enforce odd length for a clean "center"
        self.window_len = win
        self.center_idx = win // 2
        self.lag_seconds = (win // 2) / self.fs

        # Hann-tapered weights for the window (helps boundary behavior)
        # normalized to peak 1 so center is near-fully trusted
        w = 0.5 * (1 - np.cos(2 * np.pi * np.arange(win) / (win - 1)))
        w /= w.max()
        self.W = w

        # smoothn params
        self._s = s
        self._robust = robust
        self._max_iter = max_iter
        self._tol_z = tol_z

        # buffer
        self.buf = deque(maxlen=win)
        self._ready = False

    def process_sample(self, x):
        """
        Push one new sample, return (y_hat, is_valid).
        is_valid is False until enough data have accumulated to fill the first window.
        """
        self.buf.append(float(x))
        if len(self.buf) < self.window_len:
            return np.nan, False

        # we have a full window
        window = np.asarray(self.buf, dtype=float)

        # Treat non-finite as missing (smoothn handles that). (shouldn't happen for surface P usually)
        y = window.copy()
        # Build weights with Hann taper; set weight 0 at missing if any
        W = self.W.copy()
        finite = np.isfinite(y)
        W = W * finite

        # Run smoothn on the current window
        z, _, _ = smoothn(y, s=self._s, W=W, robust=self._robust,
                          MaxIter=self._max_iter, TolZ=self._tol_z)

        # Emit the center (fixed-lag)
        yhat = float(z[self.center_idx])
        self._ready = True
        return yhat, True

    def process(self, x_array):
        """
        Vectorized convenience: process a batch of samples and return an array of smoothed outputs.
        Entries are NaN until the first full window is available; after that each element is the
        smoothed value aligned with input time minus lag_seconds.
        """
        x_array = np.asarray(x_array, dtype=float).ravel()
        out = np.empty_like(x_array)
        valid_mask = np.zeros_like(x_array, dtype=bool)
        for i, xi in enumerate(x_array):
            yhat, ok = self.process_sample(xi)
            out[i] = yhat
            valid_mask[i] = ok
        return out, valid_mask

    def status(self):
        return {
            "window_len": self.window_len,
            "center_index": self.center_idx,
            "lag_seconds": self.lag_seconds,
            "fs": self.fs,
            "ready": self._ready
        }

# --------- Example usage (30 Hz surface pressure) ----------
if __name__ == "__main__":
    fs = 30.0
    filt = LiveSmoothN(fs=fs, window_seconds=1.0, robust=True)  # ~0.5 s latency

    # Simulate 10 seconds of noisy surface pressure with a step & spikes
    t = np.arange(0, 10, 1/fs)
    p = 1500 + 5*np.sin(2*np.pi*0.2*t) + np.random.randn(t.size)*0.8
    p[int(3.2*fs)] += 20  # spike
    p[int(6.7*fs)] -= 15  # spike

    print(p)
    print()
    yhat, valid = filt.process(p)
    print(yhat)
    # yhat[~valid] are NaN until the first window is filled


    y1 = p
    y2 = yhat
    plt.plot(y1, label="raw")
    plt.plot(y2, label="smoothed")
    plt.legend()
    plt.title("Surface Pressure (raw vs smoothed)")
    plt.show()