"""Google access tokens without the google-auth package.

Service accounts (preferred: scoped to the properties the account was added
to, no consent screen, no 7-day test-mode expiry) use the JWT-bearer grant,
signed RS256 with the system `openssl` binary. OAuth refresh tokens (YouTube,
legacy Search Console) use the standard refresh grant.
"""
from __future__ import annotations

import base64
import json
import os
import shutil
import subprocess
import tempfile
import time
from pathlib import Path
from typing import Dict, Tuple

from lib.http import request_json
from lib.mcp_stdio import ToolError

TOKEN_URI = "https://oauth2.googleapis.com/token"
_cache = {}  # type: Dict[Tuple[str, str], Tuple[str, float]]


def _b64url(raw: bytes) -> str:
    return base64.urlsafe_b64encode(raw).rstrip(b"=").decode("ascii")


def _openssl() -> str:
    for candidate in (shutil.which("openssl"), "/usr/bin/openssl", "/opt/homebrew/bin/openssl"):
        if candidate and Path(candidate).exists():
            return candidate
    raise ToolError("Signing the Google service-account login needs the `openssl` program, which was not found.")


def sign_rs256(message: bytes, private_key_pem: str) -> bytes:
    tmpdir = tempfile.mkdtemp(prefix="fw-")
    key_path = os.path.join(tmpdir, "key.pem")
    try:
        fd = os.open(key_path, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600)
        with os.fdopen(fd, "w") as f:
            f.write(private_key_pem)
        proc = subprocess.run([_openssl(), "dgst", "-sha256", "-sign", key_path],
                              input=message, capture_output=True, timeout=30)
    finally:
        shutil.rmtree(tmpdir, ignore_errors=True)
    if proc.returncode != 0:
        raise ToolError("Could not sign the service-account login: the private key in the key file looks invalid.")
    return proc.stdout


def load_service_account(path: Path) -> dict:
    try:
        info = json.loads(Path(path).read_text(encoding="utf-8"))
    except FileNotFoundError:
        raise ToolError(f"Service-account key file not found: {path}. See the Google connector guide.")
    except ValueError:
        raise ToolError(f"{path} is not a valid JSON key file.")
    if info.get("type") != "service_account" or "private_key" not in info or "client_email" not in info:
        raise ToolError(f"{path} is not a Google service-account key (expected type=service_account).")
    return info


def service_account_token(info: dict, scope: str) -> str:
    key = (info["client_email"], scope)
    cached = _cache.get(key)
    if cached and time.time() < cached[1]:
        return cached[0]
    now = int(time.time())
    header = _b64url(json.dumps({"alg": "RS256", "typ": "JWT", "kid": info.get("private_key_id", "")}).encode())
    claims = _b64url(json.dumps({
        "iss": info["client_email"], "scope": scope, "aud": info.get("token_uri", TOKEN_URI),
        "iat": now, "exp": now + 3600,
    }).encode())
    signing_input = f"{header}.{claims}".encode()
    assertion = f"{header}.{claims}.{_b64url(sign_rs256(signing_input, info['private_key']))}"
    data = request_json("POST", info.get("token_uri", TOKEN_URI), service="Google sign-in", form={
        "grant_type": "urn:ietf:params:oauth:grant-type:jwt-bearer", "assertion": assertion,
    })
    token = data["access_token"]
    _cache[key] = (token, time.time() + int(data.get("expires_in", 3600)) - 120)
    return token


def expired_signin(how_to_sign_in_again: str) -> ToolError:
    return ToolError(
        "The Google sign-in has expired or was revoked. The usual cause is a Google Cloud app still in "
        "Testing mode, which ends every sign-in after 7 days. Fix it once: Google Cloud console → Google Auth "
        "Platform → Audience → Publishing status → Publish app (\"In production\"; Google's verification is not "
        "needed for the brand's own use). Then " + how_to_sign_in_again + ". Other causes: the password was "
        "changed or access was removed at myaccount.google.com → Security → Third-party connections.")


def refresh_token_access(client_id: str, client_secret: str, refresh_token: str, token_uri: str = TOKEN_URI,
                         how_to_sign_in_again: str = "sign in again") -> str:
    key = (client_id, refresh_token[-12:])
    cached = _cache.get(key)
    if cached and time.time() < cached[1]:
        return cached[0]
    try:
        data = request_json("POST", token_uri, service="Google sign-in", form={
            "grant_type": "refresh_token", "client_id": client_id,
            "client_secret": client_secret, "refresh_token": refresh_token,
        })
    except ToolError as e:
        if "invalid_grant" in str(e):
            raise expired_signin(how_to_sign_in_again) from None
        raise
    token = data["access_token"]
    _cache[key] = (token, time.time() + int(data.get("expires_in", 3600)) - 120)
    return token
