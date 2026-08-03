import os
import math
import numpy as np

def read_control_info():
    config = {'Scope': 'ps5000a', 'Serial no.': None, 'Hardware resolution': '14BIT'}
    info_path = r"c:\Users\MaharshiM\Music\Picoscope\control info.txt"
    if os.path.exists(info_path):
        with open(info_path, 'r', encoding='utf-8') as f:
            for line in f:
                if ':' in line:
                    k, v = [x.strip() for x in line.split(':', 1)]
                    if v.lower() in ('none', ''): v = None
                    if k.lower().startswith('scope'): config['Scope'] = v
                    elif k.lower().startswith('serial'): config['Serial no.'] = v
                    elif k.lower().startswith('hardware'): config['Hardware resolution'] = v
    return config

class PicoScopeProxy:
    def __init__(self, scope_name):
        import importlib
        self.scope_name = scope_name
        self.scope_upper = scope_name.upper()
        self.module = getattr(importlib.import_module(f"picosdk.{scope_name}"), scope_name)
    def __getattr__(self, name):
        if name.startswith('ps5000a'): return getattr(self.module, f"{self.scope_name}{name[7:]}")
        if name.startswith('PS5000A_'):
            attr = getattr(self.module, f"{self.scope_upper}_{name[8:]}")
            if isinstance(attr, dict):
                class DictProxy:
                    def __init__(self, d, p): self.d, self.p = d, p
                    def __getitem__(self, k): return self.d[f"{self.p}_{k[8:]}"] if k.startswith('PS5000A_') else self.d[k]
                return DictProxy(attr, self.scope_upper)
            return attr
        return getattr(self.module, name)

def parse_time_label(t_str):
    s = t_str.strip()
    if s.endswith('ns'): return float(s[:-2]), "ns", 1.0
    if s.endswith('us'): return float(s[:-2]), "us", 1000.0
    if s.endswith('ms'): return float(s[:-2]), "ms", 1e6
    if s.endswith('s'): return float(s[:-1]), "s", 1e9
    return 1.0, "ms", 1e6

def parse_time_to_ns(time_str):
    val, unit, scale = parse_time_label(time_str)
    return val * scale

def parse_volts_to_mv(v_str):
    s = v_str.strip()
    if s.endswith('mV'): return float(s[:-2])
    if s.endswith('V'): return float(s[:-1]) * 1000
    return 1000.0

def get_voltage_range_enum(mv):
    if mv <= 10: return 0
    if mv <= 20: return 1
    if mv <= 50: return 2
    if mv <= 100: return 3
    if mv <= 200: return 4
    if mv <= 500: return 5
    if mv <= 1000: return 6
    if mv <= 2000: return 7
    if mv <= 5000: return 8
    if mv <= 10000: return 9
    return 10

def calc_tb(total_time_ns, target_samples=100000):
    # PicoScope rounds UP the timebase to guarantee 96.2kS per screen
    if total_time_ns <= target_samples:
        return 0, max(10, int(total_time_ns))
    interval_ns = total_time_ns / target_samples
    if interval_ns <= 1.0: return 0, int(total_time_ns)
    elif interval_ns <= 2.0: return 1, int(total_time_ns / 2)
    elif interval_ns <= 4.0: return 2, int(total_time_ns / 4)
    else:
        import math
        # Using math.ceil forces Timebase 15 (104ns) for a 1ms/div setting
        n = math.ceil(interval_ns / 8.0) + 2
        actual_interval = (n - 2) * 8
        return n, max(10, int(total_time_ns / actual_interval))

def get_nice_step(val):
    import math
    if val <= 0: return 1.0
    pwr = math.floor(math.log10(val))
    frac = val / (10**pwr)
    if frac <= 1.0: nice = 1.0
    elif frac <= 1.25: nice = 1.25
    elif frac <= 1.5: nice = 1.5
    elif frac <= 2.0: nice = 2.0
    elif frac <= 2.5: nice = 2.5
    elif frac <= 4.0: nice = 4.0
    elif frac <= 5.0: nice = 5.0
    elif frac <= 7.5: nice = 7.5
    else: nice = 10.0
    return nice * (10**pwr)

def process_channel(y_data, ch_prefix, ui_vars, noSamples, tInt_ns, unit):
    try:
        mx = np.max(y_data) 
        mn = np.min(y_data) 
        vpp = mx - mn
        
        N = max(2, noSamples // 200)
        y_smooth = np.convolve(y_data, np.ones(N)/N, mode='valid')
        mean_val = np.mean(y_smooth)
        all_crossings = np.where((y_smooth[:-1] < mean_val) & (y_smooth[1:] >= mean_val))[0]
        
        crossings = []
        if len(all_crossings) > 0:
            crossings.append(all_crossings[0])
            min_distance = (noSamples - N) / 100
            for c in all_crossings[1:]:
                if c - crossings[-1] > min_distance:
                    crossings.append(c)
                    
        num = "1" if ch_prefix == "A" else "2"
        
        if len(crossings) >= 2:
            exact_crossings = []
            for i in crossings:
                y1, y2 = y_smooth[i], y_smooth[i+1]
                frac = i + (mean_val - y1) / (y2 - y1) if y2 != y1 else i
                exact_crossings.append(frac)
                
            delta_frac = exact_crossings[-1] - exact_crossings[0]
            period_ns = (delta_frac * tInt_ns) / (len(exact_crossings) - 1)
            freq_hz = 1e9 / period_ns
            
            if freq_hz >= 1e6:
                ui_vars['freq'].set(f"CH{num} Freq: {freq_hz/1e6:.2f} MHz")
            elif freq_hz >= 1e3:
                ui_vars['freq'].set(f"CH{num} Freq: {freq_hz/1e3:.2f} kHz")
            else:
                ui_vars['freq'].set(f"CH{num} Freq: {freq_hz:.1f} Hz")
        else:
            ui_vars['freq'].set(f"CH{num} Freq: -- Hz")
    except Exception:
        mx = np.max(y_data) if y_data is not None else 0.0
        mn = np.min(y_data) if y_data is not None else 0.0
        vpp = mx - mn
        num = "1" if ch_prefix == "A" else "2"
        ui_vars['freq'].set(f"CH{num} Freq: -- Hz")
        
    ui_vars['max'].set(f"CH{num} Max: {mx:.2f} {unit}")
    ui_vars['min'].set(f"CH{num} Min: {mn:.2f} {unit}")
    ui_vars['vpp'].set(f"CH{num} Vpp: {vpp:.2f} {unit}")
