"""Base62 encoding and short code generation utilities.

Base62 uses characters [0-9a-zA-Z]:
- 10 digits (0-9)
- 26 lowercase English letters (a-z)
- 26 uppercase English letters (A-Z)
Total: 62 characters.

Why Base62:
1. URL-safe without percent-encoding (unlike Base64 which contains '+' and '/').
2. High density: 62^7 = 3,521,614,606,208 (3.5+ Trillion) unique IDs with only 7 characters.
3. Human-readable and clean when printed or shared.
"""

import secrets
from typing import Final

BASE62_ALPHABET: Final[str] = "0123456789abcdefghijklmnopqrstuvwxyzABCDEFGHIJKLMNOPQRSTUVWXYZ"
BASE: Final[int] = len(BASE62_ALPHABET)  # 62


def encode_base62(num: int) -> str:
    """Encode an unsigned integer into a Base62 string.
    
    Used when mapping auto-incrementing database primary keys to short codes.
    """
    if num < 0:
        raise ValueError("Cannot encode negative integers in Base62.")
    if num == 0:
        return BASE62_ALPHABET[0]

    chars = []
    while num > 0:
        num, rem = divmod(num, BASE)
        chars.append(BASE62_ALPHABET[rem])

    return "".join(reversed(chars))


def decode_base62(code: str) -> int:
    """Decode a Base62 string back into an integer.
    
    Inverse of encode_base62.
    """
    if not code:
        raise ValueError("Cannot decode empty string.")

    num = 0
    for char in code:
        idx = BASE62_ALPHABET.find(char)
        if idx == -1:
            raise ValueError(f"Invalid Base62 character: '{char}'")
        num = num * BASE + idx

    return num


def generate_random_short_code(length: int = 7) -> str:
    """Generate a cryptographically secure random Base62 token.
    
    Uses `secrets` (CSPRN / os.urandom) rather than pseudo-random `random` module
    to prevent sequence predictability and token harvesting.
    """
    if length <= 0:
        raise ValueError("Length must be a positive integer.")
    return "".join(secrets.choice(BASE62_ALPHABET) for _ in range(length))
