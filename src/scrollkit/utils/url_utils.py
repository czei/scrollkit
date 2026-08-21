"""
URL utilities for handling URL encoding and decoding.
Copyright (c) 2024-2026 Michael Czeiszperger
"""


__all__ = ['url_decode', 'load_credentials']

def url_decode(input_string):
    """
    Decode URL-encoded strings

    Percent-escapes are BYTES, and browsers percent-encode form fields as
    UTF-8, so a single accented character arrives as several escapes: 'é' is
    '%C3%A9'. Turning each escape straight into a character with chr() (which
    this did until 2026-08) yields 'Ã©' — two wrong characters, silently, in
    whatever the user typed. For a WiFi password that means the board stores
    something the user never entered and can never join their network; the
    setup portal still reports success, because the corruption happens before
    anything checks. Collect the bytes first, decode once at the end.

    Args:
        input_string: The URL-encoded string to decode

    Returns:
        The decoded string
    """
    input_string = input_string.replace('+', ' ')
    hex_chars = "0123456789abcdef"
    out = bytearray()
    i = 0
    while i < len(input_string):
        ch = input_string[i]
        if ch == "%" and i < len(input_string) - 2:
            hex_value = input_string[i + 1:i + 3].lower()
            if all(c in hex_chars for c in hex_value):
                out.append(int(hex_value, 16))
                i += 3
                continue
        out.extend(ch.encode("utf-8"))
        i += 1
    try:
        return bytes(out).decode("utf-8")
    except Exception:
        # Not valid UTF-8 — a stray literal '%' followed by hex, or a client
        # posting some other encoding. Keep the old byte-wise reading rather
        # than dropping the value: a mangled password beats no password.
        return "".join(chr(b) for b in out)


def load_credentials():
    """
    Load WiFi credentials from secrets.py
    
    Returns:
        A tuple of (ssid, password)
    """
    try:
        from secrets import secrets
        return secrets['ssid'], secrets['password']
    except ImportError:
        return "", ""