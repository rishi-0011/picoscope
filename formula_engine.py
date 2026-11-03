"""
formula_engine.py
Dynamic Formula Evaluation Engine for IEC 60060-1 Impulse Calculator.
Loads, parses, and evaluates formulas defined in an external plain-text file.
"""

import os
import math
import numpy as np

class FormulaEngine:
    def __init__(self, filepath=None):
        if filepath is None:
            base_dir = os.path.dirname(os.path.abspath(__file__))
            filepath = os.path.join(base_dir, "formulas.txt")
        self.filepath = filepath
        self.formulas = []  # list of (var_name, expression_str)
        self.load()

    def load(self, filepath=None):
        """Reads and parses the formulas text file."""
        if filepath:
            self.filepath = filepath
            
        self.formulas = []
        if not os.path.exists(self.filepath):
            return

        with open(self.filepath, "r", encoding="utf-8") as f:
            for line in f:
                line = line.strip()
                # Skip comments and empty lines
                if not line or line.startswith("#") or line.startswith("//"):
                    continue
                if "=" in line:
                    parts = line.split("=", 1)
                    var_name = parts[0].strip()
                    expr = parts[1].strip()
                    if var_name and expr:
                        self.formulas.append((var_name, expr))

    def evaluate(self, inputs):
        """
        Evaluates the sequence of formulas given a dictionary of inputs.
        Returns a dictionary containing all inputs and calculated variables.
        """
        # Safe evaluation namespace with standard math utilities
        context = {
            "abs": abs,
            "min": min,
            "max": max,
            "sqrt": math.sqrt,
            "exp": math.exp,
            "log": math.log,
            "np": np,
            "math": math,
        }

        # Seed context with inputs
        for k, v in inputs.items():
            context[k] = v

        # Sequentially evaluate each formula
        for var_name, expr in self.formulas:
            try:
                # Check if expression references any variable that is None
                # If so, the result will safely be None
                val = eval(expr, {"__builtins__": None}, context)
                context[var_name] = val
            except Exception:
                context[var_name] = None

        return context

    def get_raw_text(self):
        """Returns the full text of formulas.txt."""
        if os.path.exists(self.filepath):
            with open(self.filepath, "r", encoding="utf-8") as f:
                return f.read()
        return ""

    def save_raw_text(self, text):
        """Saves new content into formulas.txt and reloads formulas."""
        with open(self.filepath, "w", encoding="utf-8") as f:
            f.write(text)
        self.load()


# ----------------------------------------------------------------------
# ACCURATE IEC 60060-1 IMPULSE PARAMETER CALCULATION ENGINE
# ----------------------------------------------------------------------
_shared_engine = None

def get_shared_formula_engine():
    global _shared_engine
    if _shared_engine is None:
        _shared_engine = FormulaEngine()
    else:
        _shared_engine.load()
    return _shared_engine

def calculate_iec_parameters(time, raw_voltage, formula_engine=None):
    """
    Standard IEC 60060-1 Parameter Calculation Pipeline:
    - Dynamic formula evaluation via formulas.txt
    - Front timing T1, virtual origin O1
    - Chopping detection (Tc, front vs tail chopped)
    - Half-value time T2
    - Base curve double-exponential fit
    - K-factor digital filtering (Annex B)
    - Beta (raw overshoot %) and Beta Dash (β' %)
    - Virtual steepness S and crest oscillation frequency f_osc
    """
    if formula_engine is None:
        formula_engine = get_shared_formula_engine()
    else:
        formula_engine.load()

    t = np.asarray(time, dtype=float)
    v_raw = np.asarray(raw_voltage, dtype=float)

    if len(t) < 5 or len(v_raw) < 5:
        raise ValueError("Insufficient data points for IEC calculation.")

    dt = (t[-1] - t[0]) / max(len(t) - 1, 1)
    if dt <= 0:
        dt = 1e-9

    polarity = -1 if abs(np.min(v_raw)) > abs(np.max(v_raw)) else 1
    v = v_raw * polarity

    idx_peak = int(np.argmax(v))
    Vext = float(v[idx_peak])
    tp = float(t[idx_peak])

    def _crossing_time(target, tt, vv):
        idx = np.where(vv >= target)[0]
        if len(idx) == 0:
            raise ValueError("Signal never reaches the requested level.")
        idx = idx[0]
        if idx == 0:
            return float(tt[0])
        t0, t1 = tt[idx - 1], tt[idx]
        v0, v1 = vv[idx - 1], vv[idx]
        frac = (target - v0) / (v1 - v0) if (v1 - v0) != 0 else 0
        return float(t0 + frac * (t1 - t0))

    def _double_exp(tt, A, alpha, beta_p, t0):
        tau = np.clip(tt - t0, 0, None)
        return A * (np.exp(np.clip(-alpha * tau, -700, 700)) - np.exp(np.clip(-beta_p * tau, -700, 700)))

    # Evaluate threshold levels from formulas.txt
    thresh_eval = formula_engine.evaluate({'Vext': Vext})
    v30 = thresh_eval.get('v30')
    v90 = thresh_eval.get('v90')
    v50 = thresh_eval.get('v50')
    if v30 is None: v30 = 0.30 * Vext
    if v90 is None: v90 = 0.90 * Vext
    if v50 is None: v50 = 0.50 * Vext

    front_t, front_v = t[: idx_peak + 1], v[: idx_peak + 1]

    try:
        t30 = _crossing_time(v30, front_t, front_v)
        t90 = _crossing_time(v90, front_t, front_v)
        calc_front = formula_engine.evaluate({
            'Vext': Vext,
            't30': t30,
            't90': t90,
            'tp': tp
        })
        T1 = calc_front.get('T1')
        O1 = calc_front.get('O1')
        if T1 is None:
            T1 = (t90 - t30) / 0.6
        if O1 is None:
            O1 = t30 - 0.3 * T1
    except Exception:
        t30, t90, T1, O1 = None, None, None, None

    # Chopping Detection (Tc) per IEC 60060-1
    win_len = max(3, int(0.05e-6 / dt))
    kernel = np.ones(win_len) / win_len
    v_smooth = np.convolve(v, kernel, mode='same')
    dv_dt = np.gradient(v_smooth, dt)

    chop_thresh = -1.0 * Vext / 1e-6
    steepest_idx = int(np.argmin(dv_dt))
    min_slope = dv_dt[steepest_idx]

    is_chopped = False
    is_front_chopped = False
    is_tail_chopped = False
    idx_chop = None
    t_chop = None
    Tc = None

    if min_slope < chop_thresh:
        window_pts = max(5, int(1.5e-6 / dt))
        v_before = v[max(0, steepest_idx - window_pts // 2)]
        v_after = v[min(len(v) - 1, steepest_idx + window_pts)]
        if (v_before - v_after) > 0.40 * Vext:
            is_chopped = True
            idx_s = steepest_idx
            while idx_s > 0 and dv_dt[idx_s] < 0.15 * min_slope:
                idx_s -= 1
            idx_chop = idx_s
            t_chop = float(t[idx_chop])
            if O1 is not None:
                calc_chop = formula_engine.evaluate({
                    'Vext': Vext,
                    't30': t30,
                    't90': t90,
                    't_chop': t_chop,
                    'O1': O1,
                    'T1': T1,
                    'tp': tp
                })
                Tc = calc_chop.get('Tc')
                if Tc is None:
                    Tc = t_chop - O1

            if t90 is not None and t_chop < (t90 - 0.05 * (t90 - t30)):
                is_front_chopped = True
            elif t90 is None:
                is_front_chopped = True
            else:
                is_tail_chopped = True

    # Tail Timing (T2 for full, Tc for chopped)
    t50, T2 = None, None
    if not is_chopped:
        tail_t, tail_v = t[idx_peak:], v[idx_peak:]
        idx50 = np.where(tail_v <= v50)[0]
        if len(idx50) > 0 and O1 is not None:
            idx50 = idx50[0]
            if idx50 > 0:
                t0_, t1_ = tail_t[idx50 - 1], tail_t[idx50]
                v0_, v1_ = tail_v[idx50 - 1], tail_v[idx50]
                frac = (v50 - v0_) / (v1_ - v0_) if (v1_ - v0_) != 0 else 0
                t50 = float(t0_ + frac * (t1_ - t0_))

                calc_tail = formula_engine.evaluate({
                    'Vext': Vext,
                    't30': t30,
                    't90': t90,
                    't50': t50,
                    'O1': O1,
                    'T1': T1,
                    'tp': tp
                })
                T2 = calc_tail.get('T2')
                if T2 is None:
                    T2 = t50 - O1
    else:
        T2 = Tc

    # Base curve fit for full & chopped waves
    base = np.zeros_like(v)
    base_peak = Vext

    def _get_alpha_for_tau_p(beta_val, tau_p_val):
        target = beta_val * np.exp(-beta_val * tau_p_val)
        a_max = 1.0 / tau_p_val - 1e-9
        a_min = 1e-6
        try:
            from scipy.optimize import brentq
            return brentq(lambda a: a * np.exp(-a * tau_p_val) - target, a_min, a_max)
        except Exception:
            return 14600.0

    if O1 is not None and T1 is not None:
        try:
            from scipy.optimize import curve_fit, minimize
            alpha_nom = np.log(2) / 50e-6
            beta0 = 3.0 / max(T1, 1e-9)
            tau_p = max(1e-7, tp - O1)

            if not is_chopped:
                tail_start = tp + 3 * T1
                mask_fit = ((t >= O1) & (t < tp)) | (t >= tail_start)
                if mask_fit.sum() < 5:
                    mask_fit = t >= O1

                if T2 is not None:
                    alpha0 = np.log(2) / max(T2, 1e-9)
                else:
                    mask_tail = t >= tail_start
                    if mask_tail.sum() >= 5:
                        t_tail = t[mask_tail]
                        v_tail = v[mask_tail]
                        poly = np.polyfit(t_tail - O1, np.log(np.maximum(1e-3, v_tail)), 1)
                        alpha0 = max(100.0, min(1e5, -poly[0]))
                    else:
                        alpha0 = alpha_nom

                A0 = Vext * 1.05

                popt, _ = curve_fit(
                    lambda tt, A, a, b: _double_exp(tt, A, a, b, O1),
                    t[mask_fit], v[mask_fit],
                    p0=[A0, alpha0, beta0],
                    bounds=([0.7 * Vext, 100.0, 1e5], [2.0 * Vext, 5e5, 1e8]),
                    maxfev=50000,
                )
                base = _double_exp(t, popt[0], popt[1], popt[2], O1)
                base_peak = float(np.nanmax(base))
                if base_peak > Vext:
                    base *= (Vext / base_peak)
                    base_peak = Vext
                if T2 is None and popt[1] > 0:
                    T2 = np.log(2) / popt[1]
            elif is_tail_chopped and idx_chop is not None:
                t_fit_end = max(tp, t_chop)
                mask_fit = (t >= O1) & (t <= t_fit_end)
                t_fit = t[mask_fit]
                v_fit = v[mask_fit]
                tau_fit = t_fit - O1

                if len(t_fit) >= 5:
                    def loss(params):
                        U_b, b_val = params
                        a_val = _get_alpha_for_tau_p(b_val, tau_p)
                        denom = np.exp(-a_val * tau_p) - np.exp(-b_val * tau_p)
                        if denom <= 1e-6:
                            return 1e12
                        A = U_b / denom
                        u_model = A * (np.exp(-a_val * tau_fit) - np.exp(-b_val * tau_fit))
                        return np.sum((u_model - v_fit)**2)

                    res = minimize(
                        loss,
                        x0=[Vext * 0.98, 2.5 / tau_p],
                        bounds=[(0.70 * Vext, 1.00 * Vext), (0.5 / tau_p, 20.0 / tau_p)],
                        method='L-BFGS-B'
                    )
                    U_base_opt, beta_opt = res.x
                    alpha_opt = _get_alpha_for_tau_p(beta_opt, tau_p)
                    denom = np.exp(-alpha_opt * tau_p) - np.exp(-beta_opt * tau_p)
                    A_opt = U_base_opt / max(1e-6, denom)

                    tau_all = np.maximum(0.0, t - O1)
                    base = np.zeros_like(t)
                    m_front = (t >= O1) & (t <= tp)
                    base[m_front] = A_opt * (np.exp(-alpha_opt * tau_all[m_front]) - np.exp(-beta_opt * tau_all[m_front]))

                    m_tail = t > tp
                    base[m_tail] = U_base_opt * np.exp(-alpha_nom * (t[m_tail] - tp))
                    base_peak = float(U_base_opt)
                else:
                    raise ValueError("Insufficient points for chopped fit")
            else:
                t_peak_est = np.log(beta0 / alpha_nom) / (beta0 - alpha_nom)
                A_est = Vext / max(1e-6, np.exp(-alpha_nom * t_peak_est) - np.exp(-beta0 * t_peak_est))
                base = _double_exp(t, A_est, alpha_nom, beta0, O1)
                base_peak = float(np.nanmax(base))
                if base_peak > Vext:
                    base *= (Vext / base_peak)
                    base_peak = Vext
        except Exception:
            alpha_fallback = np.log(2) / 50e-6
            beta_fallback = 3.0 / max(T1 if T1 else 1.2e-6, 1e-9)
            t_p_est = np.log(beta_fallback / alpha_fallback) / (beta_fallback - alpha_fallback)
            A_fallback = Vext / max(1e-6, np.exp(-alpha_fallback * t_p_est) - np.exp(-beta_fallback * t_p_est))
            base = _double_exp(t, A_fallback, alpha_fallback, beta_fallback, O1 if O1 else t[0])
            base_peak = float(np.nanmax(base))
            if base_peak > Vext:
                base *= (Vext / base_peak)
                base_peak = Vext

    # K-factor filtering (Annex B)
    v_kfilt = np.copy(v)
    Up_kfilt = Vext
    beta_raw_pct = None
    beta_dash_pct = None

    if not is_front_chopped:
        try:
            residual = v - base
            if is_tail_chopped and idx_chop is not None:
                taper_len = min(idx_chop, max(5, int(0.3e-6 / dt)))
                taper = np.linspace(1.0, 0.0, taper_len)
                residual[idx_chop - taper_len:idx_chop] *= taper
                residual[idx_chop:] = 0.0

            n_pts = len(t)
            dt_s = dt if dt > 0 else 1e-9
            r_fft = np.fft.rfft(residual)
            freqs_mhz = np.fft.rfftfreq(n_pts, d=dt_s) * 1e-6

            k_filter_h = 1.0 / (1.0 + 2.2 * (freqs_mhz ** 2))
            r_filt = np.fft.irfft(r_fft * k_filter_h, n=n_pts)

            v_kfilt = base + r_filt
            if is_tail_chopped and idx_chop is not None:
                v_kfilt[idx_chop:] = v[idx_chop:]
                Up_kfilt = float(np.nanmax(v_kfilt[:idx_chop]))
            else:
                Up_kfilt = float(np.nanmax(v_kfilt))

            ref_Up = base_peak if (base_peak is not None and base_peak > 0) else Vext
            calc_overshoot = formula_engine.evaluate({
                'Vext': Vext,
                'Ubase': ref_Up,
                'Up_kfilt': Up_kfilt,
                'T1': T1,
                'O1': O1,
                't30': t30,
                't90': t90,
                't50': t50,
                't_chop': t_chop,
                'tp': tp
            })
            beta_raw_pct = calc_overshoot.get('beta')
            beta_dash_pct = calc_overshoot.get('beta_dash')
            if beta_raw_pct is None:
                beta_raw_pct = max(0.0, ((Vext - ref_Up) / ref_Up) * 100.0) if ref_Up > 0 else 0.0
            else:
                beta_raw_pct = max(0.0, float(beta_raw_pct))

            if beta_dash_pct is None:
                beta_dash_pct = max(0.0, ((Up_kfilt - ref_Up) / ref_Up) * 100.0) if ref_Up > 0 else 0.0
            else:
                beta_dash_pct = max(0.0, float(beta_dash_pct))
        except Exception:
            v_kfilt = np.copy(base)
            Up_kfilt = base_peak
            beta_raw_pct = 0.0
            beta_dash_pct = 0.0

    steepness_kv_us = None
    if T1 is not None and T1 > 0:
        calc_s = formula_engine.evaluate({'Vext': Vext, 'T1': T1 * 1e6})
        s_val = calc_s.get('S')
        if s_val is not None:
            steepness_kv_us = float(s_val)
        else:
            steepness_kv_us = Vext / (T1 * 1e6)

    # Oscillation Frequency
    f_osc = np.nan
    if T1 is not None and not is_front_chopped:
        from scipy.signal import find_peaks
        win_end = min(t_chop if (is_tail_chopped and t_chop) else t[-1], tp + 10 * T1)
        win = (t >= tp - 0.3 * T1) & (t <= win_end)
        t_seg, v_seg = t[win], v[win]
        if len(v_seg) > 5:
            prom = 0.05 * Vext
            pk, _ = find_peaks(v_seg, prominence=prom)
            tr, _ = find_peaks(-v_seg, prominence=prom)
            extrema_t = np.sort(np.concatenate([t_seg[pk], t_seg[tr]]))
            if len(extrema_t) >= 2:
                half_periods = np.diff(extrema_t)
                period = 2 * np.mean(half_periods)
                f_osc = 1.0 / period

    v_peak_plot = Vext * polarity
    base_plot = base * polarity
    base_peak_plot = base_peak * polarity
    v_kfilt_plot = v_kfilt * polarity
    Up_kfilt_plot = Up_kfilt * polarity

    if is_chopped and idx_chop is not None:
        idx_stop = max(idx_peak, idx_chop)
        base_plot[idx_stop + 1:] = np.nan

    return {
        'time_us': t * 1e6,
        'raw_v': v_raw,
        'smooth_v': base_plot,
        'v_kfilt': v_kfilt_plot,
        'u_pkfilt': Up_kfilt_plot,
        'v_peak': v_peak_plot,
        'v_base_peak': base_peak_plot,
        'v30': v30 * polarity if 'v30' in locals() else 0,
        'v50': v50 * polarity if 'v50' in locals() else 0,
        'v90': v90 * polarity if 'v90' in locals() else 0,
        't30_us': t30 * 1e6 if t30 else None,
        't90_us': t90 * 1e6 if t90 else None,
        't50_us': t50 * 1e6 if t50 else None,
        't1_us': T1 * 1e6 if T1 else None,
        't2_us': T2 * 1e6 if T2 else None,
        'o1_us': O1 * 1e6 if O1 else None,
        'is_chopped': is_chopped,
        'is_front_chopped': is_front_chopped,
        'is_tail_chopped': is_tail_chopped,
        'tc_us': Tc * 1e6 if Tc else None,
        'steepness_kv_us': steepness_kv_us,
        'beta_raw_pct': beta_raw_pct,
        'beta_dash_pct': beta_dash_pct,
        'beta_pct': beta_dash_pct,
        'osc_freq_khz': f_osc * 1e-3 if not np.isnan(f_osc) else 0
    }
