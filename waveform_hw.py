import ctypes
import time
import threading
from waveform_utils import PicoScopeProxy, read_control_info

def hide_splash():
    try:
        EnumWindows = ctypes.windll.user32.EnumWindows
        EnumWindowsProc = ctypes.WINFUNCTYPE(ctypes.c_bool, ctypes.POINTER(ctypes.c_int), ctypes.POINTER(ctypes.c_int))
        GetClassName = ctypes.windll.user32.GetClassNameW
        IsWindowVisible = ctypes.windll.user32.IsWindowVisible
        ShowWindow = ctypes.windll.user32.ShowWindow

        def foreach_window(hwnd, lParam):
            if IsWindowVisible(hwnd):
                buff = ctypes.create_unicode_buffer(256)
                GetClassName(hwnd, buff, 256)
                if 'PicoScope' in buff.value:
                    ShowWindow(hwnd, 0)
            return True

        for _ in range(1000):
            EnumWindows(EnumWindowsProc(foreach_window), 0)
            time.sleep(0.005)
    except Exception:
        pass

def init_scope(app, config):
    if getattr(app, 'is_demo_mode', False):
        app.chandle = -1
        app.status = {"openunit": 0}
        print("Demo mode initialized.")
        return

    if getattr(app, 'chandle', None) is not None and app.chandle != -1:
        print("Scope handle already open:", app.chandle)
        app.is_scope_connected = True
        return
    try:
        from picosdk.functions import assert_pico_ok, mV2adc
        
        c_info = read_control_info()
        scope_model = c_info.get('Scope', 'ps5000a')
        serial_no_str = c_info.get('Serial no.')
        serial_no = serial_no_str.encode('utf-8') if serial_no_str else None
        hw_res_str = c_info.get('Hardware resolution', '14BIT')
        
        ps = PicoScopeProxy(scope_model)
        
        threading.Thread(target=hide_splash, daemon=True).start()
        
        chandle = ctypes.c_int16()
        try:
            res_enum = ps.PS5000A_DEVICE_RESOLUTION[f"PS5000A_DR_{hw_res_str}"]
        except KeyError:
            res_enum = ps.PS5000A_DEVICE_RESOLUTION["PS5000A_DR_14BIT"]
            
        status = ps.ps5000aOpenUnit(ctypes.byref(chandle), serial_no, res_enum)
        
        if status == 282 or status == 286:
            status = ps.ps5000aChangePowerSource(chandle, status)
            
        try:
            assert_pico_ok(status)
        except Exception:
            pass
            
        if status != 0:
            print("Failed to open scope, status:", status)
            app.chandle = None
        else:
            app.chandle = chandle.value
            
            wavetype = ctypes.c_int32(0) 
            sweepType = ctypes.c_int32(0) 
            triggertype = ctypes.c_int32(0) 
            triggerSource = ctypes.c_int32(0) 
            
            try:
                app.status["setSigGen"] = ps.ps5000aSetSigGenBuiltInV2(
                    app.chandle, 0, 1600000, wavetype, ctypes.c_double(1000.0), ctypes.c_double(1000.0), 0, 0, sweepType, 0, 0, 0, triggertype, triggerSource, 0
                )
            except Exception as e:
                print("AWG Error:", e)
                
            try:
                ch1_active = config.get('ch1_active', True)
                ch2_active = config.get('ch2_active', False)
                
                app.status["setChA"] = ps.ps5000aSetChannel(
                    app.chandle, ps.PS5000A_CHANNEL["PS5000A_CHANNEL_A"], 1 if ch1_active else 0, 1, ps.PS5000A_RANGE["PS5000A_1V"], 0.0
                )
                app.status["setChB"] = ps.ps5000aSetChannel(
                    app.chandle, ps.PS5000A_CHANNEL["PS5000A_CHANNEL_B"], 1 if ch2_active else 0, 1, ps.PS5000A_RANGE["PS5000A_1V"], 0.0
                )
                
                polarity = config.get('polarity', 'Positive')
                is_positive = (polarity == 'Positive')
                
                maxADC = ctypes.c_int16(32767)
                trig_thresh_mv = 50 if is_positive else -50
                trig_adc = mV2adc(trig_thresh_mv, ps.PS5000A_RANGE["PS5000A_1V"], maxADC)
                trig_ch = ps.PS5000A_CHANNEL["PS5000A_CHANNEL_A"] if ch1_active else ps.PS5000A_CHANNEL["PS5000A_CHANNEL_B"]
                trig_dir = ps.PS5000A_THRESHOLD_DIRECTION["PS5000A_RISING"] if is_positive else ps.PS5000A_THRESHOLD_DIRECTION["PS5000A_FALLING"]
                
                # Trigger disabled (0) to match Official Software "Trigger: None"
                app.status["setTrigger"] = ps.ps5000aSetSimpleTrigger(
                    app.chandle, 0, trig_ch, trig_adc, trig_dir, 0, 1000                                               
                )
            except Exception as e:
                print("ChA/ChB/Trigger Error:", e)
                
    except Exception as e:
        print("Failed to init scope:", e)
        import traceback
        traceback.print_exc()
        if getattr(app, 'chandle', None):
            try:
                scope_m = read_control_info().get('Scope', 'ps5000a')
                ps_close = PicoScopeProxy(scope_m)
                ps_close.ps5000aCloseUnit(app.chandle)
            except: pass
            app.chandle = None

def run_hardware_block(app, config, total_time_ns, max_mv_A, max_mv_B, time_str, range_enum_A, range_enum_B, timebase, noSamples, res_str):
    c_info = read_control_info()
    pre_trig_percent = float(c_info.get('Pre-trigger [%]', 0)) / 100.0
    thresh_percent = float(c_info.get('Threshold [%]', 18)) / 100.0

    if getattr(app, 'is_demo_mode', False):
        app.update_hardware_requested = False
        adc_max_val = 32512 if res_str == "8 bits" else 32767
        pre_trig = int(noSamples * pre_trig_percent)
        
        ch1_active = config.get('ch1_active', True)
        ch2_active = config.get('ch2_active', False)
        if ch1_active:
            trig_ch_name = "CHANNEL_A"
        elif ch2_active and not ch1_active:
            trig_ch_name = "CHANNEL_B"
        else:
            trig_ch_name = "CHANNEL_A"
            
        polarity = config.get('polarity', 'Negative')
        trig_dir_name = "RISING" if polarity == 'Positive' else "FALLING"
        print(f"\n[DEMO MODE] Hardware Trigger Configured -> Source: {trig_ch_name} | Direction: {trig_dir_name}\n")
        
        app.capture_context = (range_enum_A, range_enum_B, noSamples, 10.0, max_mv_A, max_mv_B, time_str, adc_max_val, pre_trig)
        return True

    scope_m = c_info.get('Scope', 'ps5000a')
    ps = PicoScopeProxy(scope_m)
    from picosdk.functions import mV2adc
    
    ch1_active = config.get('ch1_active', True)
    ch2_active = config.get('ch2_active', False)
    
    try:
        if res_str == "8 bits":
            res_enum = ps.PS5000A_DEVICE_RESOLUTION["PS5000A_DR_8BIT"]
            maxADC = ctypes.c_int16(32512)
        else:
            res_enum = ps.PS5000A_DEVICE_RESOLUTION["PS5000A_DR_14BIT"]
            maxADC = ctypes.c_int16(32767)
            
        try:
            ps.ps5000aSetDeviceResolution(app.chandle, res_enum)
        except Exception as e:
            print("SetDeviceResolution error:", e)

        # Source selection logic
        if ch1_active:
            trig_ch = ps.PS5000A_CHANNEL["PS5000A_CHANNEL_A"]
        elif ch2_active and not ch1_active:
            trig_ch = ps.PS5000A_CHANNEL["PS5000A_CHANNEL_B"]
        else:
            trig_ch = ps.PS5000A_CHANNEL["PS5000A_CHANNEL_A"] # Default fallback
        
        polarity = config.get('polarity', 'Negative')
        
        # Use Channel A's or Channel B's expected value based on the trigger channel
        if trig_ch == ps.PS5000A_CHANNEL["PS5000A_CHANNEL_A"]:
            exp_val_str = config.get('Expected Voltage [kV]' if getattr(app, 'ch1_type', 'Voltage') == 'Voltage' else 'Expected Current [A]', 150)
            att = float(config.get('ch1_int', 1)) * float(config.get('ch1_ext', 1))
            is_voltage = getattr(app, 'ch1_type', 'Voltage') == 'Voltage'
        else:
            exp_val_str = config.get('Expected Voltage [kV]' if getattr(app, 'ch2_type', 'Voltage') == 'Voltage' else 'Expected Current [A]', 150)
            att = float(config.get('ch2_int', 1)) * float(config.get('ch2_ext', 1))
            is_voltage = getattr(app, 'ch2_type', 'Voltage') == 'Voltage'
            
        exp_val = float(exp_val_str) if str(exp_val_str).strip() != '' else 150.0
        exp_v = exp_val * 1000.0 if is_voltage else exp_val
        
        scope_input_v = exp_v / att if att != 0 else exp_v
        
        trig_thresh_mv = int((scope_input_v * thresh_percent) * 1000)
        if abs(trig_thresh_mv) < 250:
            trig_thresh_mv = 250 if polarity == 'Positive' else -250
        
        # Trigger direction and threshold negation for negative polarity
        if polarity == 'Positive':
            trig_dir = ps.PS5000A_THRESHOLD_DIRECTION["PS5000A_RISING"]
            trig_thresh_mv = abs(trig_thresh_mv)
        else:
            trig_dir = ps.PS5000A_THRESHOLD_DIRECTION["PS5000A_FALLING"]
            trig_thresh_mv = -abs(trig_thresh_mv)
        
        ps.ps5000aSetChannel(app.chandle, ps.PS5000A_CHANNEL["PS5000A_CHANNEL_A"], 1 if ch1_active else 0, 1, range_enum_A, 0)
        ps.ps5000aSetChannel(app.chandle, ps.PS5000A_CHANNEL["PS5000A_CHANNEL_B"], 1 if ch2_active else 0, 1, range_enum_B, 0)

        trig_adc_val = int(mV2adc(trig_thresh_mv, range_enum_A if ch1_active else range_enum_B, maxADC))
        if trig_adc_val > 32000: trig_adc_val = 32000
        if trig_adc_val < -32000: trig_adc_val = -32000
        trig_adc = ctypes.c_int16(trig_adc_val)
        
        trig_ch_name = "CHANNEL_A" if trig_ch == ps.PS5000A_CHANNEL["PS5000A_CHANNEL_A"] else "CHANNEL_B"
        trig_dir_name = "RISING" if polarity == 'Positive' else "FALLING"
        print(f"\n[HARDWARE] Trigger Configured -> Source: {trig_ch_name} | Direction: {trig_dir_name} | Threshold: {trig_thresh_mv} mV (ADC: {trig_adc_val})\n")
        
        # Enable Trigger (1) with auto_trigger_ms = 0 (WAIT INDEFINITELY FOR REAL IMPULSE TO FIRE!)
        ps.ps5000aSetSimpleTrigger(app.chandle, 1, trig_ch, trig_adc, trig_dir, 0, 0)
        
        app.update_hardware_requested = False
    except Exception as e:
        print("Hardware Config Error:", e)
        app.update_hardware_requested = False

    timeIntervalns = ctypes.c_float()
    returnedMaxSamples = ctypes.c_int32()
    
    status_tb = ps.ps5000aGetTimebase2(app.chandle, timebase, noSamples, ctypes.byref(timeIntervalns), ctypes.byref(returnedMaxSamples), 0)
    while status_tb != 0 and timebase < 10000:
        timebase += 1
        status_tb = ps.ps5000aGetTimebase2(app.chandle, timebase, noSamples, ctypes.byref(timeIntervalns), ctypes.byref(returnedMaxSamples), 0)
    
    pre_trig = int(noSamples * pre_trig_percent)
    post_trig = noSamples - pre_trig
    
    status_run = ps.ps5000aRunBlock(app.chandle, pre_trig, post_trig, timebase, None, 0, None, None)
    
    if status_run != 0:
        print("Failed to start run block, status:", status_run)
        return False
        
    adc_max_val = 32512 if res_str == "8 bits" else 32767
    app.capture_context = (range_enum_A, range_enum_B, noSamples, timeIntervalns.value, max_mv_A, max_mv_B, time_str, adc_max_val, pre_trig)
    return True

def is_hardware_ready(app):
    if getattr(app, 'is_demo_mode', False):
        import time
        time.sleep(0.5)
        return True
    if not getattr(app, 'chandle', None): return False
    c_info = read_control_info()
    scope_m = c_info.get('Scope', 'ps5000a')
    ps = PicoScopeProxy(scope_m)
    ready = ctypes.c_int16(0)
    try:
        status = ps.ps5000aIsReady(app.chandle, ctypes.byref(ready))
        if status != 0:
            print(f"Scope disconnected or not responding! Status: {status}")
            app.is_scope_connected = False
            try:
                ps.ps5000aCloseUnit(app.chandle)
            except: pass
            app.chandle = None
            return False
        return ready.value != 0
    except Exception as e:
        print(f"Hardware error during polling: {e}")
        app.is_scope_connected = False
        try:
            ps.ps5000aCloseUnit(app.chandle)
        except: pass
        app.chandle = None
        return False

def fetch_hardware_data(app, config):
    import numpy as np
    
    if getattr(app, 'is_demo_mode', False):
        ch1_active = config.get('ch1_active', True)
        ch2_active = config.get('ch2_active', False)
        r_enum_A, r_enum_B, nSamp, tInt, mx_mv_A, mx_mv_B, t_str, adc_max_val, pre_trig_samples = app.capture_context
        
        x = np.linspace(0, 10, nSamp)
        polarity = config.get('polarity', 'Positive')
        sign = 1 if polarity == 'Positive' else -1
        
        ch1_type = getattr(app, 'ch1_type', 'Voltage')
        ch2_type = getattr(app, 'ch2_type', 'Current')
        
        exp_v = float(config.get('Expected Voltage [kV]' if ch1_type == 'Voltage' else 'Expected Current [A]', 150))
        exp_i = float(config.get('Expected Current [A]' if ch2_type == 'Current' else 'Expected Voltage [kV]', 300))
        
        y_data_A = (sign * (exp_v * 0.8) * np.sin(x)) if ch1_active else None
        y_data_B = (sign * (exp_i * 0.8) * np.cos(x)) if ch2_active else None
        
        return y_data_A, y_data_B, tInt, pre_trig_samples, mx_mv_A, mx_mv_B, nSamp, t_str
    c_info = read_control_info()
    scope_m = c_info.get('Scope', 'ps5000a')
    ps = PicoScopeProxy(scope_m)
    from picosdk.functions import adc2mV
    
    ch1_active = config.get('ch1_active', True)
    ch2_active = config.get('ch2_active', False)
    
    r_enum_A, r_enum_B, nSamp, tInt, mx_mv_A, mx_mv_B, t_str, adc_max_val, pre_trig_samples = app.capture_context
    
    overflow = ctypes.c_int16()
    cmaxSamples = ctypes.c_int32(nSamp)
    
    current_max_adc = ctypes.c_int16(adc_max_val)
    
    y_data_A = None
    y_data_B = None
    
    if ch1_active:
        bufferAMax = (ctypes.c_int16 * nSamp)()
        ps.ps5000aSetDataBuffer(app.chandle, ps.PS5000A_CHANNEL["PS5000A_CHANNEL_A"], ctypes.byref(bufferAMax), nSamp, 0, 0)
    if ch2_active:
        bufferBMax = (ctypes.c_int16 * nSamp)()
        ps.ps5000aSetDataBuffer(app.chandle, ps.PS5000A_CHANNEL["PS5000A_CHANNEL_B"], ctypes.byref(bufferBMax), nSamp, 0, 0)
    
    ps.ps5000aGetValues(app.chandle, 0, ctypes.byref(cmaxSamples), 1, 0, 0, ctypes.byref(overflow))
    
    ch1_type = getattr(app, 'ch1_type', 'Voltage')
    ch2_type = getattr(app, 'ch2_type', 'Current')

    c1_att = float(config.get('ch1_int', 1.0)) * float(config.get('ch1_ext', 1.0))
    c2_att = float(config.get('ch2_int', 1.0)) * float(config.get('ch2_ext', 1.0))

    if ch1_active:
        v_raw_A = np.array(adc2mV(bufferAMax, r_enum_A, current_max_adc)) / 1000.0
        v_actual_A = v_raw_A * c1_att
        y_data_A = (v_actual_A / 1000.0) if ch1_type == 'Voltage' else v_actual_A

    if ch2_active:
        v_raw_B = np.array(adc2mV(bufferBMax, r_enum_B, current_max_adc)) / 1000.0
        v_actual_B = v_raw_B * c2_att
        y_data_B = (v_actual_B / 1000.0) if ch2_type == 'Voltage' else v_actual_B
        
    return y_data_A, y_data_B, tInt, pre_trig_samples, mx_mv_A, mx_mv_B, nSamp, t_str
