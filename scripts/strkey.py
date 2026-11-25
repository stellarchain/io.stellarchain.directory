"""Validate canonical Stellar public addresses using SEP-23."""

from base64 import b32decode, b32encode
from binascii import crc_hqx


ADDRESS_TYPES = {
    6 << 3: (32, "account"),
    2 << 3: (32, "contract"),
    12 << 3: (40, "muxed_account"),
    22 << 3: (40, "muxed_contract"),
}


def address_type(address):
    if not isinstance(address, str) or len(address) not in (56, 69):
        raise ValueError("expected a canonical Stellar public address")

    try:
        decoded = b32decode(address + "=" * (-len(address) % 8))
    except ValueError:
        raise ValueError("expected uppercase Stellar Base32") from None

    payload_size, kind = ADDRESS_TYPES.get(decoded[0], (0, None))
    if kind is None or len(decoded) != payload_size + 3:
        raise ValueError("expected a Stellar account or contract address")

    checksum = crc_hqx(decoded[:-2], 0).to_bytes(2, "little")
    canonical = b32encode(decoded).decode("ascii").rstrip("=")
    if checksum != decoded[-2:] or canonical != address:
        raise ValueError("invalid Stellar address checksum or encoding")

    return kind
