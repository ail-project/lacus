import os
from functools import lru_cache
from pathlib import Path

from lacus.default import get_homedir


def src_request_ip(request) -> str:
    """
    Get the source IP address from the request object.

    Args:
        request: The request object containing the headers and remote address.

    Returns
    -------
        The source IP address as a string.
    """
    # NOTE: X-Real-IP is the IP passed by the reverse proxy in the headers.
    real_ip = request.headers.get("X-Real-IP")
    if not real_ip:
        real_ip = request.remote_addr
    return real_ip


@lru_cache(64)
def get_secret_key() -> bytes:
    """
    Get the secret key used for encryption.

    Returns
    -------
        The secret key as bytes.
    """
    secret_file_path: Path = get_homedir() / "secret_key"
    if not secret_file_path.exists() or secret_file_path.stat().st_size < 64:
        if not secret_file_path.exists() or secret_file_path.stat().st_size < 64:
            with secret_file_path.open("wb") as f:
                f.write(os.urandom(64))
    with secret_file_path.open("rb") as f:
        return f.read()
