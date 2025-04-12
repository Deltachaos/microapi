import asyncio
import collections
import json
import base64
import hmac
import hashlib
import logging
from typing import Callable, Any
from urllib.parse import urlencode

# From https://github.com/kennethreitz/requests/blob/v1.2.3/requests/structures.py
# Copyright 2013 Kenneth Reitz
# Licensed under the Apache License, Version 2.0 (the "License")
class CaseInsensitiveDict:
    def __init__(self, data=None, **kwargs):
        self._store = dict()
        if data is None:
            data = {}
        for k, v in data.items():
            self[k] = v

    def __setitem__(self, key, value):
        # Use the lowercased key for lookups, but store the actual
        # key alongside the value.
        self._store[key.lower()] = (key, value)

    def __getitem__(self, key):
        return self._store[key.lower()][1]

    def __delitem__(self, key):
        del self._store[key.lower()]

    def __iter__(self):
        return (casedkey for casedkey, mappedvalue in self._store.values())

    def as_dict(self) -> dict:
        return dict(self.items())

    def as_lower_dict(self) -> dict:
        return dict(self.lower_items())

    def __len__(self):
        return len(self._store)

    def get(self, key, default=None):
        if key in self:
            return self[key]
        return default

    def items(self):
        return (
            (keyval[0], keyval[1])
            for (lowerkey, keyval)
            in self._store.items()
        )

    def lower_items(self):
        """Like iteritems(), but with all lowercase keys."""
        return (
            (lowerkey, keyval[1])
            for (lowerkey, keyval)
            in self._store.items()
        )

    def __eq__(self, other):
        if isinstance(other, collections.Mapping):
            other = CaseInsensitiveDict(other)
        else:
            return NotImplemented
        # Compare insensitively
        return dict(self.lower_items()) == dict(other.lower_items())

    # Copy is required
    def copy(self):
         return CaseInsensitiveDict(self._store)

    def __repr__(self):
        return '%s(%r)' % (self.__class__.__name__, dict(self.items()))


def logger(name="app"):
    _ = logging.getLogger(name)
    logging.basicConfig(level=logging.DEBUG)
    return _


async def call_async(listener: Callable, *args, **kwargs) -> Any:
    if asyncio.iscoroutinefunction(listener):
        return await listener(*args, **kwargs)
    else:
        #return await asyncio.to_thread(listener, *args, **kwargs)
        return listener(*args, **kwargs)


def path(p, query=None):
    result = p.lstrip("/")

    if query is not None:
        result = result + f"?{urlencode(query)}"

    return result


def base64_encode(data) -> str:
    if isinstance(data, str):
        data = data.encode("utf-8")
    return base64.b64encode(data).decode('utf-8')


def base64_decode(data) -> str:
    if isinstance(data, str):
        data = data.encode("utf-8")
    return base64.b64decode(data).decode('utf-8')


def base64url_encode(data) -> str:
    if isinstance(data, str):
        data = data.encode("utf-8")
    return base64.urlsafe_b64encode(data).rstrip(b"=").decode('utf-8')


def base64url_decode(data) -> str:
    if isinstance(data, str):
        data = data.encode("utf-8")
    return base64.urlsafe_b64decode(data + '=='.encode('utf-8')).decode('utf-8')


def json_base64_decode(data) -> Any:
    return json.loads(base64url_decode(data))


def json_base64_encode(data) -> str:
    return base64url_encode(json.dumps(data).encode('utf-8'))


def jwt_validate_debug(token, secret):
    """Validates a JWT token against a secret key."""
    if len(secret.encode()) < 32:
        secret = secret.ljust(32, ' ')

    _, header_data, _ = jwt_decode(token)
    if "typ" not in header_data or header_data["typ"] != "JWT":
        return False, RuntimeError(f"jwt header type {header_data['typ']} not supported")
    if "alg" not in header_data:
        return False, RuntimeError(f"jwt header alg {header_data['alg']} not supported")

    header, payload, signature = jwt_parse(token)
    expected_signature = jwt_signature(f"{header}.{payload}", secret, header_data["alg"])

    if signature == expected_signature:
        return True, None

    return False, RuntimeError(f"{signature} did not match expected signature")


def jwt_validate(token, secret):
    result, exception = jwt_validate_debug(token, secret)
    return result


def jwt_signature(message: str, secret: str, algorithm: str = 'HS256'):
    """Creates a raw JWT token without using external libraries."""
    if algorithm != 'HS256':
        raise NotImplementedError("Only HS256 algorithms are supported")

    if len(secret.encode()) < 32:
        secret = secret.ljust(32, ' ')

    signature = hmac.new(secret.encode(), message.encode(), hashlib.sha256).digest()
    return base64url_encode(signature)


def jwt_encode(payload: dict, secret: str, algorithm: str = 'HS256'):
    """Creates a JWT token without using external libraries."""
    # Create header
    header = {"alg": algorithm, "typ": "JWT"}
    encoded_header = json_base64_encode(header)

    # Encode payload
    encoded_payload = json_base64_encode(payload)

    # Create signature
    message = f"{encoded_header}.{encoded_payload}"
    encoded_signature = jwt_signature(message, secret, algorithm)

    # Return final token
    return f"{encoded_header}.{encoded_payload}.{encoded_signature}"


def jwt_parse(token):
    token = str(token)
    """Decode the JWT token and return the payload as a dictionary."""
    header_b64, payload_b64, signature_b64 = token.split('.')
    return str(header_b64), str(payload_b64), str(signature_b64)


def jwt_decode(token, secret: str = None):
    """Decode the JWT token and return the payload as a dictionary."""
    if secret is not None and not jwt_validate(token, secret):
        raise RuntimeError(f"jwt token {token} does not match secret")

    header_b64, payload_b64, signature_b64 = jwt_parse(token)

    header = json_base64_decode(header_b64)
    payload = json_base64_decode(payload_b64)

    return payload, header, signature_b64
