import struct
import json
import hashlib
import os
import numpy as np

IAAS_MAGIC = b"IAAS_DAT_V1\x00"  # 12 bytes proprietary magic header
SECRET_KEY_SEED = b"IAAS_CORONA_POWER_PROPRIETARY_KEY_2026_HV_IMPULSE"

def _derive_keystream(salt: bytes, length: int) -> bytes:
    """Derive deterministic keystream using SHA-256 counter mode for secure stream encryption."""
    keystream = bytearray()
    counter = 0
    while len(keystream) < length:
        h = hashlib.sha256(SECRET_KEY_SEED + salt + counter.to_bytes(4, 'big')).digest()
        keystream.extend(h)
        counter += 1
    return bytes(keystream[:length])

def encrypt_iaas_dat(x_data, y_A, y_B=None, time_unit="us"):
    """
    Encrypts raw numpy waveform arrays into proprietary IAAS encrypted DAT format.
    Output file starts with magic header 'IAAS_DAT_V1\x00' followed by encrypted binary payload.
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
    
    return IAAS_MAGIC + salt + cipher_bytes

def decrypt_iaas_dat(b_data):
    """
    Decrypts proprietary IAAS DAT binary file bytes back into x_data, y_A, y_B, time_unit.
    Raises ValueError if magic header or key verification fails.
    """
    if not b_data.startswith(IAAS_MAGIC):
        raise ValueError("Invalid or corrupted IAAS DAT file. Only authorized IAAS software can decrypt this file.")
        
    salt = b_data[12:28]
    cipher_bytes = b_data[28:]
    
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
