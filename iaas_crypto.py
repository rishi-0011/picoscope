import struct
import json
import hashlib
import os
import base64
import datetime
import numpy as np

IAAS_MAGIC_ENC = b"IAAS_DAT_V1\x00"  # 12 bytes proprietary magic header for encrypted DAT
IAAS_MAGIC_BIN = b"IAAS"             # 4 bytes magic header for standard binary DAT
SECRET_KEY_SEED = b"IAAS_CORONA_POWER_PROPRIETARY_KEY_2026_HV_IMPULSE"

HEADER_TAG = "-----BEGIN IAAS BINARY DAT WAVEFORM-----\n"
FOOTER_TAG = "-----END IAAS BINARY DAT WAVEFORM-----\n"

def _derive_keystream(salt: bytes, length: int) -> bytes:
    """Derive deterministic keystream using SHA-256 counter mode for secure stream encryption."""
    keystream = bytearray()
    counter = 0
    while len(keystream) < length:
        h = hashlib.sha256(SECRET_KEY_SEED + salt + counter.to_bytes(4, 'big')).digest()
        keystream.extend(h)
        counter += 1
    return bytes(keystream[:length])

def pack_binary_dat(x_data, y_A, y_B=None, time_unit="us"):
    """
    Packs raw waveform data matching FCHW1-ch1_V-n 1.dat binary format.
    Formats payload as line-broken Base64 text so Windows Notepad opens instantly without freezing.
    """
    n_samples = len(x_data)
    dt = (x_data[-1] - x_data[0]) / (n_samples - 1) if n_samples > 1 else 1e-6
    t_start = x_data[0]
    
    header = struct.pack('>4sHIdd', IAAS_MAGIC_BIN, 1, n_samples, dt, t_start)
    
    body_A = y_A.astype(np.float64).tobytes() if y_A is not None else b""
    body_B = y_B.astype(np.float64).tobytes() if y_B is not None else b""
    
    timestamp_str = datetime.datetime.now().strftime("%d  %b  %Y  %H:%M")
    ch_label = "Voltage[kV]" if time_unit == "us" else "Current[A]"
    time_label = f"Time [{time_unit}]"
    
    footer_buf = bytearray()
    for lbl in [ch_label, time_label, timestamp_str]:
        b_lbl = lbl.encode('ascii')
        footer_buf.extend(struct.pack('>I', len(b_lbl)))
        footer_buf.extend(b_lbl)
        
    raw_binary_dat = header + body_A + body_B + bytes(footer_buf)
    
    # Wrap in 76-character Base64 lines so Windows Notepad opens instantly without freezing
    b64_str = base64.b64encode(raw_binary_dat).decode('ascii')
    wrapped_lines = [b64_str[i:i+76] for i in range(0, len(b64_str), 76)]
    
    formatted_text = HEADER_TAG + "\n".join(wrapped_lines) + "\n" + FOOTER_TAG
    return formatted_text.encode('utf-8')

def encrypt_iaas_dat(x_data, y_A, y_B=None, time_unit="us"):
    """
    Encrypts raw numpy waveform arrays into proprietary IAAS encrypted DAT format.
    Formats payload as line-broken Base64 text so Windows Notepad opens instantly without freezing.
    """
    salt = os.urandom(16)
    
    meta = {
        "time_unit": time_unit,
        "has_A": y_A is not None,
        "has_B": y_B is not None,
        "n_samples": len(x_data)
    }
    meta_bytes = json.dumps(meta).encode('utf-8')
    
    payload_buf = bytearray()
    payload_buf.extend(struct.pack(">I", len(meta_bytes)))
    payload_buf.extend(meta_bytes)
    payload_buf.extend(x_data.astype(np.float64).tobytes())
    
    if y_A is not None:
        payload_buf.extend(y_A.astype(np.float64).tobytes())
    if y_B is not None:
        payload_buf.extend(y_B.astype(np.float64).tobytes())
        
    plain_bytes = bytes(payload_buf)
    keystream = _derive_keystream(salt, len(plain_bytes))
    
    cipher_bytes = bytes(p ^ k for p, k in zip(plain_bytes, keystream))
    raw_encrypted = IAAS_MAGIC_ENC + salt + cipher_bytes
    
    b64_str = base64.b64encode(raw_encrypted).decode('ascii')
    wrapped_lines = [b64_str[i:i+76] for i in range(0, len(b64_str), 76)]
    
    formatted_text = HEADER_TAG + "\n".join(wrapped_lines) + "\n" + FOOTER_TAG
    return formatted_text.encode('utf-8')

def decrypt_iaas_dat(b_data):
    """
    Decrypts or unpacks DAT binary file bytes back into x_data, y_A, y_B, time_unit.
    Supports IEEE-754 float64 DAT files (FCHW1-ch1_V-n 1.dat format), raw binary DAT files, and encrypted Base64 DAT files.
    """
    if isinstance(b_data, str):
        b_data = b_data.encode('utf-8', errors='ignore')

    # Step 1: Decode Base64 line-broken wrapper if present
    raw_bytes = None
    if b_data.startswith(IAAS_MAGIC_BIN) or b_data.startswith(IAAS_MAGIC_ENC):
        raw_bytes = b_data
    else:
        try:
            text = b_data.decode('utf-8', errors='ignore')
            lines = [line.strip() for line in text.splitlines() if line.strip() and not line.startswith("---")]
            clean_b64 = "".join(lines)
            raw_bytes = base64.b64decode(clean_b64)
        except Exception:
            pass

    if not raw_bytes:
        raw_bytes = b_data

    # Step 2: Binary DAT Header Parsing
    if len(raw_bytes) >= 26 and raw_bytes.startswith(IAAS_MAGIC_BIN):
        try:
            magic, ver, n_samples, dt, t_start = struct.unpack('>4sHIdd', raw_bytes[:26])
            x_rec = t_start + np.arange(n_samples) * dt
            
            body_bytes = n_samples * 8
            y_A_rec = np.frombuffer(raw_bytes[26:26+body_bytes], dtype=np.float64)
            y_B_rec = None
            
            time_unit = "us"
            footer = raw_bytes[26+body_bytes:]
            if b"Time [s]" in footer: time_unit = "s"
            elif b"Time [ms]" in footer: time_unit = "ms"
            elif b"Time [us]" in footer: time_unit = "us"

            return x_rec, y_A_rec, y_B_rec, time_unit
        except Exception:
            pass

    # Step 3: Encrypted IAAS DAT Parsing
    if not raw_bytes.startswith(IAAS_MAGIC_ENC):
        raise ValueError("Invalid or corrupted IAAS DAT file.")
        
    salt = raw_bytes[12:28]
    cipher_bytes = raw_bytes[28:]
    
    keystream = _derive_keystream(salt, len(cipher_bytes))
    plain_bytes = bytes(c ^ k for c, k in zip(cipher_bytes, keystream))
    
    meta_len = struct.unpack(">I", plain_bytes[:4])[0]
    meta_bytes = plain_bytes[4 : 4 + meta_len]
    meta = json.loads(meta_bytes.decode('utf-8'))
    
    offset = 4 + meta_len
    n_samples = meta["n_samples"]
    
    x_bytes = plain_bytes[offset : offset + n_samples * 8]
    x_data = np.frombuffer(x_bytes, dtype=np.float64)
    offset += n_samples * 8
    
    y_A = None
    if meta["has_A"]:
        y_bytes = plain_bytes[offset : offset + n_samples * 8]
        y_A = np.frombuffer(y_bytes, dtype=np.float64)
        offset += n_samples * 8
        
    y_B = None
    if meta["has_B"]:
        y_bytes = plain_bytes[offset : offset + n_samples * 8]
        y_B = np.frombuffer(y_bytes, dtype=np.float64)
        
    time_unit = meta.get("time_unit", "us")
    return x_data, y_A, y_B, time_unit
