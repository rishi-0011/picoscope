"""
Lightning Impulse Parameter Analyzer  (IEC 60060-1)
----------------------------------------------------
Measures, from a recorded impulse voltage/current waveform:

    - Front (rise) time            T1
    - Time to half-value (tail)    T2
    - Virtual origin                O1
    - Peak (extreme) value          Vext
    - Base-curve peak               Upmc
    - Overshoot magnitude           beta
    - Relative overshoot magnitude  beta'   ("beta dash")
    - Frequency of the crest oscillation   f

Usage
-----
    python lightning_impulse_analyzer.py
        -> prompts you to type/paste the path to your data file

    python lightning_impulse_analyzer.py path/to/file.txt
        -> runs directly on that file (no prompt)

Input file format
------------------
Two columns: time, voltage (or current). Delimiter can be tab, comma,
or whitespace; a header row is fine (it is auto-skipped). Time can be
in seconds (e.g. 1.2e-6) or already in microseconds (e.g. 1.2) -- the
script auto-detects which.

Output
------
Prints a results table to the terminal and saves an annotated PNG plot
("<inputfile>_analysis.png") next to your input file.
"""

import os
import sys
import csv

import numpy as np
from scipy.optimize import curve_fit
from scipy.signal import find_peaks


# ----------------------------------------------------------------------
# 1. Loading
# ----------------------------------------------------------------------
def load_waveform(path):
    """Load a 2-column (time, voltage) file, auto-detecting delimiter,
    header row, and time units. Returns t (s), v (raw units)."""

    if not os.path.isfile(path):
        raise FileNotFoundError(f"No such file: {path}")

    # Sniff delimiter from the first non-empty line
    with open(path, "r", newline="") as f:
        sample = f.read(4096)
    try:
        dialect = csv.Sniffer().sniff(sample, delimiters="\t,; ")
        delim = dialect.delimiter
    except csv.Error:
        delim = None  # fall back to "any whitespace"

    # Try loading; skip a header row if the first line isn't numeric
    def try_load(skip):
        kwargs = dict(skiprows=skip)
        if delim and delim != " ":
            kwargs["delimiter"] = delim
        return np.loadtxt(path, **kwargs)

    try:
        data = try_load(0)
    except ValueError:
        data = try_load(1)

    if data.ndim == 1:
        raise ValueError("Could not find two numeric columns in the file.")
    if data.shape[1] > 2:
        print(f"Note: file has {data.shape[1]} columns; "
              f"using the first two as (time, voltage).")
    t_raw, v_raw = data[:, 0], data[:, 1]

    # Auto-detect time units: assume seconds if values are tiny,
    # otherwise assume the file is already in microseconds.
    if np.nanmax(np.abs(t_raw)) < 1e-2:
        t = t_raw.astype(float)
        unit_note = "seconds (as given)"
    else:
        t = t_raw.astype(float) * 1e-6
        unit_note = "microseconds -> converted to seconds"
    print(f"Detected time column units: {unit_note}")

    return t, v_raw.astype(float)


# ----------------------------------------------------------------------
# 2. Core IEC 60060-1 measurements
# ----------------------------------------------------------------------
def _crossing_time(target, tt, vv):
    """Linear-interpolated time at which vv first reaches `target`."""
    idx = np.where(vv >= target)[0]
    if len(idx) == 0:
        raise ValueError("Signal never reaches the requested level.")
    idx = idx[0]
    if idx == 0:
        return tt[0]
    t0, t1 = tt[idx - 1], tt[idx]
    v0, v1 = vv[idx - 1], vv[idx]
    frac = (target - v0) / (v1 - v0)
    return t0 + frac * (t1 - t0)


def _double_exp(tt, A, alpha, beta, t0):
    tau = np.clip(tt - t0, 0, None)
    return A * (np.exp(-alpha * tau) - np.exp(-beta * tau))


def analyze(t, v_raw):
    """Compute all IEC 60060-1 lightning-impulse parameters.
    Returns a dict of results plus the fitted base curve (same length as t)."""

    # --- Work in "positive-going" magnitude space ---
    polarity = -1 if abs(np.min(v_raw)) > abs(np.max(v_raw)) else 1
    v = v_raw * polarity

    idx_peak = int(np.argmax(v))
    Vext = v[idx_peak]
    tp = t[idx_peak]

    # --- Front timing: 30% / 90% crossings -> O1, T1 ---
    front_t, front_v = t[: idx_peak + 1], v[: idx_peak + 1]
    v30, v90 = 0.30 * Vext, 0.90 * Vext
    t30 = _crossing_time(v30, front_t, front_v)
    t90 = _crossing_time(v90, front_t, front_v)
    T1 = 1.67 * (t90 - t30)
    O1 = t30 - 0.3 * (t90 - t30)

    # --- Tail timing: 50% crossing after the peak -> T2 ---
    tail_t, tail_v = t[idx_peak:], v[idx_peak:]
    v50 = 0.50 * Vext
    idx50 = np.where(tail_v <= v50)[0]
    if len(idx50) == 0:
        raise ValueError(
            "Record ends before the signal decays to 50% of peak; "
            "cannot compute T2. Provide a longer record."
        )
    idx50 = idx50[0]
    t0_, t1_ = tail_t[idx50 - 1], tail_t[idx50]
    v0_, v1_ = tail_v[idx50 - 1], tail_v[idx50]
    frac = (v50 - v0_) / (v1_ - v0_)
    t50 = t0_ + frac * (t1_ - t0_)
    T2 = t50 - O1

    # --- Base-curve fit (double exponential), excluding the crest
    #     oscillation window so overshoot doesn't bias the fit ---
    tail_start = tp + 4 * T1          # heuristic: oscillation has died
                                       # out a few front-times after peak
    mask_fit = ((t >= O1) & (t < t90)) | (t > tail_start)
    if mask_fit.sum() < 5:
        mask_fit = t >= O1  # fallback: fit everything

    A0 = Vext * 1.3
    alpha0 = np.log(2) / max(T2, 1e-9)
    beta0 = 3 / max(T1, 1e-9)
    try:
        popt, _ = curve_fit(
            lambda tt, A, a, b: _double_exp(tt, A, a, b, O1),
            t[mask_fit], v[mask_fit],
            p0=[A0, alpha0, beta0], maxfev=50000,
        )
        base = _double_exp(t, popt[0], popt[1], popt[2], O1)
    except RuntimeError:
        print("Warning: base-curve fit did not converge; "
              "overshoot/beta values may be unreliable.")
        base = np.full_like(v, np.nan)

    base_peak = np.nanmax(base)
    beta_os = Vext - base_peak
    beta_prime = beta_os / Vext * 100.0

    # --- Oscillation frequency: local extrema of the RAW signal near the
    #     crest (peak -> dip -> secondary peak ...). Using the raw curve
    #     directly (rather than the fit residual) is more robust, since
    #     it doesn't depend on how well the base-curve fit happened to
    #     track the crest region. ---
    f_osc = np.nan
    win = (t >= tp - 0.3 * T1) & (t <= tp + 10 * T1)
    t_seg, v_seg = t[win], v[win]
    if len(v_seg) > 5:
        prom = 0.01 * Vext  # 1% of peak value
        pk, _ = find_peaks(v_seg, prominence=prom)
        tr, _ = find_peaks(-v_seg, prominence=prom)
        extrema_t = np.sort(np.concatenate([t_seg[pk], t_seg[tr]]))
        if len(extrema_t) >= 2:
            half_periods = np.diff(extrema_t)
            period = 2 * np.mean(half_periods)
            f_osc = 1.0 / period

    return {
        "polarity": "negative" if polarity == -1 else "positive",
        "Vext": Vext,
        "tp_us": tp * 1e6,
        "t30_us": t30 * 1e6,
        "t90_us": t90 * 1e6,
        "O1_us": O1 * 1e6,
        "T1_us": T1 * 1e6,
        "t50_us": t50 * 1e6,
        "T2_us": T2 * 1e6,
        "base_peak": base_peak,
        "beta": beta_os,
        "beta_prime_pct": beta_prime,
        "f_osc_MHz": f_osc * 1e-6 if not np.isnan(f_osc) else None,
    }, base, polarity


# ----------------------------------------------------------------------
# 3. Reporting
# ----------------------------------------------------------------------
def print_report(r):
    print("\n" + "=" * 60)
    print("  LIGHTNING IMPULSE PARAMETERS  (IEC 60060-1)")
    print("=" * 60)
    print(f"  Polarity                         : {r['polarity']}")
    print(f"  Peak (extreme) voltage, Vext      : {r['Vext']:.4f}")
    print(f"  Virtual origin, O1                : {r['O1_us']:.4f} us")
    is_chopped = (r['T2_us'] < 15.0)
    t2_label = "Chopping time, Tc" if is_chopped else "Time to half-value, T2"
    
    print(f"  Front time, T1                    : {r['T1_us']:.4f} us")
    print(f"      (30% pt: {r['t30_us']:.4f} us, 90% pt: {r['t90_us']:.4f} us)")
    print(f"  {t2_label:<34}: {r['T2_us']:.4f} us")
    if not is_chopped:
        print(f"      (50% pt on tail: {r['t50_us']:.4f} us)")
    else:
        print(f"      (50% pt on tail: {r['t50_us']:.4f} us - treated as chopped)")
        
    print(f"  Base-curve peak, Upmc             : {r['base_peak']:.4f}")
    print(f"  Overshoot magnitude, beta         : {r['beta']:.4f}")
    print(f"  Relative overshoot, beta' (dash)  : {r['beta_prime_pct']:.2f} %")
    if r["f_osc_MHz"] is not None:
        print(f"  Crest oscillation frequency, f    : {r['f_osc_MHz']:.4f} MHz")
    else:
        print(f"  Crest oscillation frequency, f    : not detected (smooth crest)")
    print("=" * 60)

    # Informational tolerance check vs standard 1.2/50 impulse
    print("\n  Reference check vs standard 1.2/50 impulse tolerances:")
    ok1 = 0.84 <= r["T1_us"] <= 1.56
    ok2 = 40.0 <= r["T2_us"] <= 60.0
    okb = r["beta_prime_pct"] <= 10.0
    print(f"    T1 within 1.2us +/-30%  : {'OK' if ok1 else 'OUT OF RANGE'}")
    if not is_chopped:
        print(f"    T2 within 50us +/-20%   : {'OK' if ok2 else 'OUT OF RANGE'}")
    else:
        print(f"    Tc chopped typically 2-5: {'OK' if r['T2_us'] <= 5.0 else 'CHECK'}")
    print(f"    beta' <= 10%            : {'OK' if okb else 'EXCEEDS LIMIT'}")
    print("  (Ignore this block if your impulse isn't meant to be 1.2/50.)\n")


def save_plot(t, v_raw, base, r, polarity, out_path):
    import matplotlib
    matplotlib.use("Agg")
    import matplotlib.pyplot as plt

    v = v_raw * polarity
    t_us = t * 1e6

    fig, axes = plt.subplots(1, 2, figsize=(13, 5))

    ax = axes[0]
    ax.plot(t_us, v, lw=1.2, label="Recorded (|V|)")
    ax.plot(t_us, base, lw=1.2, ls="--", label="Base curve (fit)")
    ax.axvline(r["O1_us"], color="gray", ls=":", lw=1)
    ax.plot(r["tp_us"], r["Vext"], "o", ms=6, zorder=5)
    ax.plot(r["t50_us"], r["Vext"] * 0.5, "s", ms=6, zorder=5)
    ax.set_xlabel("Time (us)"); ax.set_ylabel("|Voltage|")
    ax.set_title("Full impulse waveform")
    ax.legend(fontsize=9)

    ax2 = axes[1]
    lo, hi = max(0, r["tp_us"] - 10), r["tp_us"] + 10
    mask = (t_us >= lo) & (t_us <= hi)
    ax2.plot(t_us[mask], v[mask], lw=1.4, label="Recorded")
    ax2.plot(t_us[mask], base[mask], lw=1.4, ls="--", label="Base curve")
    ax2.plot(r["t30_us"], r["Vext"] * 0.3, "D", ms=5, color="k")
    ax2.plot(r["t90_us"], r["Vext"] * 0.9, "D", ms=5, color="k")
    ax2.plot(r["tp_us"], r["Vext"], "o", ms=7, label=f"Vext={r['Vext']:.2f}")
    ax2.set_xlabel("Time (us)"); ax2.set_ylabel("|Voltage|")
    ax2.set_title("Front / crest detail")
    ax2.legend(fontsize=8)

    plt.tight_layout()
    plt.savefig(out_path, dpi=150)
    print(f"Annotated plot saved to: {out_path}")


# ----------------------------------------------------------------------
# 4. Entry point
# ----------------------------------------------------------------------
def prompt_file_path():
    """Open a native 'Open File' dialog (Windows Explorer / Finder /
    file manager) so the user can browse to their data file. Falls back
    to a typed path if no GUI/display is available."""
    try:
        import tkinter as tk
        from tkinter import filedialog

        root = tk.Tk()
        root.withdraw()                     # don't show the empty root window
        root.attributes("-topmost", True)   # bring the dialog to the front
        path = filedialog.askopenfilename(
            title="Select your impulse data file",
            filetypes=[
                ("Text/CSV/Data files", "*.txt *.csv *.dat *.asc"),
                ("All files", "*.*"),
            ],
        )
        root.destroy()
        if path:
            return path
        print("No file selected.")
        return None
    except Exception:
        # No display / tkinter unavailable -> fall back to typing a path
        return input(
            "Enter/paste the path to your impulse data file "
            "(2 columns: time, voltage): "
        ).strip().strip('"').strip("'")


def main():
    if len(sys.argv) > 1:
        path = sys.argv[1]
    else:
        path = prompt_file_path()
        if not path:
            sys.exit(1)

    t, v_raw = load_waveform(path)
    results, base, polarity = analyze(t, v_raw)
    print_report(results)

    base_name = os.path.splitext(os.path.basename(path))[0]
    out_dir = os.path.dirname(os.path.abspath(path))
    out_path = os.path.join(out_dir, f"{base_name}_analysis.png")
    try:
        save_plot(t, v_raw, base, results, polarity, out_path)
    except Exception as e:
        print(f"(Could not save plot: {e})")


if __name__ == "__main__":
    main()