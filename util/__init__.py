import asyncio
import json
import base64
import hmac
import hashlib
import logging
from typing import Callable, Any
from urllib.parse import urlencode


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


def base64url_encode(data):
    return base64.urlsafe_b64encode(data).rstrip(b"=").decode('utf-8')


def base64url_decode(data):
    return base64.urlsafe_b64decode(data + '==').decode('utf-8')


def json_base64_decode(data):
    return json.loads(base64url_decode(data))


def json_base64_encode(data):
    return base64url_encode(json.dumps(data).encode('utf-8'))


def jwt_validate_debug(token, secret, algorithm: str = 'HS256'):
    """Validates a JWT token against a secret key."""
    if len(secret.encode()) < 32:
        secret = secret.ljust(32, ' ')

    payload, header, signature = jwt_decode(token)
    expected_payload, expected_header, expected_signature = jwt_decode(jwt_encode(payload, secret, algorithm))

    return signature == expected_signature, signature, expected_signature


def jwt_validate(token, secret, algorithm: str = 'HS256'):
    result, signature, expected = jwt_validate_debug(token, secret, algorithm)
    return result


def jwt_encode(payload: dict, secret: str, algorithm: str = 'HS256'):
    """Creates a JWT token without using external libraries."""
    if algorithm != 'HS256':
        raise NotImplementedError("Only HS256 algorithms are supported")

    if len(secret.encode()) < 32:
        secret = secret.ljust(32, ' ')

    # Create header
    header = {"alg": algorithm, "typ": "JWT"}
    encoded_header = json_base64_encode(header)

    # Encode payload
    encoded_payload = json_base64_encode(payload)

    # Create signature
    message = f"{encoded_header}.{encoded_payload}".encode()
    signature = hmac.new(secret.encode(), message, hashlib.sha256).digest()
    encoded_signature = base64url_encode(signature)

    # Return final token
    return f"{encoded_header}.{encoded_payload}.{encoded_signature}"


def jwt_decode(token):
    token = str(token)
    """Decode the JWT token and return the payload as a dictionary."""
    header_b64, payload_b64, signature_b64 = token.split('.')

    header = json_base64_decode(header_b64)
    payload = json_base64_decode(payload_b64)

    return payload, header, str(signature_b64)
