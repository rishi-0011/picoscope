import struct
import json
import hashlib
import os
import base64
import numpy as np

IAAS_MAGIC_ENC = b"IAAS_DAT_V1\x00"  # 12 bytes proprietary magic header for encrypted DAT
IAAS_MAGIC_BIN = b"IAAS"             # 4 bytes magic header for standard 70-byte binary DAT
SECRET_KEY_SEED = b"IAAS_CORONA_POWER_PROPRIETARY_KEY_2026_HV_IMPULSE"

HEADER_TAG = "-----BEGIN IAAS ENCRYPTED DAT WAVEFORM-----\n"
FOOTER_TAG = "-----END IAAS ENCRYPTED DAT WAVEFORM-----\n"

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
    Packs raw waveform data into industrial 70-byte header + binary int16 sample payload DAT format.
    Header Size: 70 bytes (Magic, Version, SampleCount, dt, t_start, Scale_A, Scale_B, Flags).
    Payload: Sequentially packed int16 ADC samples.
    """
    n_samples = len(x_data)
    dt = (x_data[-1] - x_data[0]) / (n_samples - 1) if n_samples > 1 else 1e-6
    t_start = x_data[0]
    
    max_A = np.max(np.abs(y_A)) if (y_A is not None and len(y_A) > 0) else 1.0
    if max_A == 0: max_A = 1.0
    scale_A = max_A / 32767.0
    
    has_B = y_B is not None and len(y_B) > 0
    if has_B:
        max_B = np.max(np.abs(y_B))
        if max_B == 0: max_B = 1.0
        scale_B = max_B / 32767.0
    else:
        scale_B = 1.0
        
    unit_flag = 0 if time_unit == "us" else (1 if time_unit == "ms" else 2)
    
    header = struct.pack('>4sHIddddBBB25s',
        IAAS_MAGIC_BIN, 1, n_samples, dt, t_start, scale_A, scale_B,
        1 if y_A is not None else 0,
        1 if has_B else 0,
        unit_flag,
        b'\x00' * 25
    )
    
    int_A = (y_A / scale_A).astype(np.int16)
    if has_B:
        int_B = (y_B / scale_B).astype(np.int16)
        interleaved = np.empty((n_samples * 2,), dtype=np.int16)
        interleaved[0::2] = int_A
        interleaved[1::2] = int_B
        payload = interleaved.tobytes()
    else:
        payload = int_A.tobytes()
        
    return header + payload

def encrypt_iaas_dat(x_data, y_A, y_B=None, time_unit="us"):
    """
    Encrypts raw numpy waveform arrays into proprietary IAAS encrypted DAT format.
    Formats payload as line-broken Base64 text so Windows Notepad opens instantly without freezing.
    """
    salt = os.urandom(16)  # 16-byte random salt
    
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
    Supports 70-byte binary DAT files, raw binary DAT files, and encrypted Base64 DAT files.
    """
    if isinstance(b_data, str):
        b_data = b_data.encode('utf-8', errors='ignore')

    # Check 1: Standard 70-byte Binary DAT Header
    if len(b_data) >= 70 and b_data.startswith(IAAS_MAGIC_BIN):
        try:
            magic, ver, n_samples, dt, t_start, scale_A, scale_B, has_A, has_B, unit_flag, _ = struct.unpack('>4sHIddddBBB25s', b_data[:70])
            time_unit = "us" if unit_flag == 0 else ("ms" if unit_flag == 1 else "s")
            x_rec = t_start + np.arange(n_samples) * dt
            
            payload = b_data[70:]
            if has_B:
                samples = np.frombuffer(payload, dtype=np.int16)
                y_A_rec = samples[0::2].astype(np.float64) * scale_A
                y_B_rec = samples[1::2].astype(np.float64) * scale_B
            else:
                y_A_rec = np.frombuffer(payload, dtype=np.int16).astype(np.float64) * scale_A
                y_B_rec = None
            return x_rec, y_A_rec, y_B_rec, time_unit
        except Exception:
            pass

    # Check 2: Encrypted IAAS DAT (raw binary or Base64 wrapped)
    raw_bytes = None
    if b_data.startswith(IAAS_MAGIC_ENC):
        raw_bytes = b_data
    else:
        try:
            text = b_data.decode('utf-8', errors='ignore')
            lines = [line.strip() for line in text.splitlines() if line.strip() and not line.startswith("---")]
            clean_b64 = "".join(lines)
            raw_bytes = base64.b64decode(clean_b64)
        except Exception:
            pass

    if not raw_bytes or not raw_bytes.startswith(IAAS_MAGIC_ENC):
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
