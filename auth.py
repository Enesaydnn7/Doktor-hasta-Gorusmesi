# -*- coding: utf-8 -*-
"""
Basit oturum (session) yönetimi — imzalı çerez.
Tarayıcının çirkin "Basic auth" kutusu yerine kendi giriş sayfamızı kullanırız.
Ek bağımlılık yok (yalnızca standart kütüphane).
"""
import os
import hmac
import time
import base64
import hashlib
import secrets

COOKIE = "klinik_admin"
MAX_AGE = int(os.getenv("SESSION_HOURS", "12")) * 3600

ADMIN_USER = os.getenv("ADMIN_USER", "admin")
ADMIN_PASS = os.getenv("ADMIN_PASS", "admin")

# Sunucu her yeniden başladığında değişir (o zaman herkes yeniden giriş yapar).
SECRET = os.getenv("SESSION_SECRET", secrets.token_hex(32)).encode()


def _sign(msg: str) -> str:
    return base64.urlsafe_b64encode(
        hmac.new(SECRET, msg.encode(), hashlib.sha256).digest()
    ).decode().rstrip("=")


def dogrula_giris(user: str, password: str) -> bool:
    return (secrets.compare_digest(user or "", ADMIN_USER)
            and secrets.compare_digest(password or "", ADMIN_PASS))


def token_uret(user: str) -> str:
    msg = f"{user}|{int(time.time())}"
    return f"{base64.urlsafe_b64encode(msg.encode()).decode().rstrip('=')}.{_sign(msg)}"


def token_gecerli(token: str) -> bool:
    if not token or "." not in token:
        return False
    body, sig = token.rsplit(".", 1)
    try:
        pad = "=" * (-len(body) % 4)
        msg = base64.urlsafe_b64decode(body + pad).decode()
    except Exception:
        return False
    if not hmac.compare_digest(_sign(msg), sig):
        return False
    try:
        _, ts = msg.rsplit("|", 1)
        return (time.time() - int(ts)) < MAX_AGE
    except Exception:
        return False
