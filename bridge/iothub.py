"""
Function breaks down connection string into dictionary. Used by mqtt connector
"""

import base64
import hashlib
import hmac
import time
from urllib.parse import quote


def parse_connection_string(connection_string: str) -> dict:
    connection_string_dict = {}
    for connecrion_string_part in connection_string.split(";"):
        name, value = connecrion_string_part.split("=", maxsplit=1)
        connection_string_dict[name] = value
    return connection_string_dict


def generate_sas_token(host, device_id, key, ttl_seconds=3600):
    expiry = int(time.time()) + ttl_seconds
    uri = quote(host + "/" + "devices" + "/" + device_id, safe="")
    note = f"{uri}\n{expiry}"
    sig = hmac.new(base64.b64decode(key), note.encode(), hashlib.sha256).digest()
    sig = base64.b64encode(sig)
    sig = quote(sig.decode(), safe="")
    return f"SharedAccessSignature sr={uri}&sig={sig}&se={expiry}"