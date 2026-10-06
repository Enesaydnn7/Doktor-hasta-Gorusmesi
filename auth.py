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
import json
import secrets
import re
import threading
from datetime import datetime

COOKIE = "klinik_session"
MAX_AGE = int(os.getenv("SESSION_HOURS", "12")) * 3600
MOBILE_API_MAX_AGE = int(os.getenv("MOBILE_SESSION_DAYS", "30")) * 86400

ADMIN_USER = os.getenv("ADMIN_USER", "admin")
ADMIN_PASS = os.getenv("ADMIN_PASS", "admin")
_DEFAULT_DOCTOR_ACCOUNTS = {
    "adnan.kaya;enes.aydin1|tracer": {
        "password": "1",
        "display_name": "Prof. Dr. Adnan Kaya",
    },
    "sami.sokucu;enes.aydin1|tracer": {
        "password": "1",
        "display_name": "Dr. Sami Sökücü",
    },
}
_DEFAULT_PATIENT_ACCOUNTS = {
    "476644": {
        "password": "1",
        "display_name": "Dursun Kılıçarslan",
        "patient_no": "476644",
    },
}


def _doctor_accounts() -> dict[str, dict[str, str]]:
    """Doktor hesaplarını ortam değişkeninden veya güvenli test varsayılanından oku."""
    raw = os.getenv("DOCTOR_ACCOUNTS_JSON", "").strip()
    accounts: dict[str, dict[str, str]] = {}
    if raw:
        try:
            parsed = json.loads(raw)
            for username, value in parsed.items():
                if isinstance(value, str):
                    accounts[str(username)] = {
                        "password": value,
                        "display_name": str(username).split(";", 1)[0],
                    }
                elif isinstance(value, dict) and value.get("password") is not None:
                    accounts[str(username)] = {
                        "password": str(value["password"]),
                        "display_name": str(value.get("display_name") or username),
                    }
        except (TypeError, ValueError, json.JSONDecodeError):
            accounts = {}
    if not accounts:
        accounts = {key: dict(value) for key, value in _DEFAULT_DOCTOR_ACCOUNTS.items()}
    return accounts


def doktor_bilgisi(user: str) -> dict[str, str] | None:
    account = _doctor_accounts().get(user or "")
    return {"username": user, **account} if account else None


def _patient_accounts() -> dict[str, dict[str, str]]:
    """Hasta hesaplarını ortam değişkeninden veya MVP test hesabından oku."""
    raw = os.getenv("PATIENT_ACCOUNTS_JSON", "").strip()
    accounts: dict[str, dict[str, str]] = {}
    if raw:
        try:
            parsed = json.loads(raw)
            for username, value in parsed.items():
                if isinstance(value, str):
                    accounts[str(username)] = {
                        "password": value,
                        "display_name": str(username),
                        "patient_no": str(username),
                    }
                elif isinstance(value, dict) and value.get("password") is not None:
                    accounts[str(username)] = {
                        "password": str(value["password"]),
                        "display_name": str(value.get("display_name") or username),
                        "patient_no": str(value.get("patient_no") or username),
                    }
        except (TypeError, ValueError, json.JSONDecodeError):
            accounts = {}
    if not accounts:
        accounts = {key: dict(value) for key, value in _DEFAULT_PATIENT_ACCOUNTS.items()}
    return accounts


def hasta_bilgisi(user: str) -> dict[str, str] | None:
    account = _patient_accounts().get(user or "")
    return {"username": user, **account} if account else None


def kullanici_adi(user: str, role: str) -> str:
    if role == "admin":
        return "Yönetici"
    account = hasta_bilgisi(user) if role == "patient" else doktor_bilgisi(user)
    return account.get("display_name", user) if account else user

# Render yeniden başlasa da aynı yönetici bilgileri aynı imza anahtarını üretir.
_configured_secret = os.getenv("SESSION_SECRET", "").strip()
_fallback_secret = hashlib.sha256(
    f"klinik-admin-session\0{ADMIN_USER}\0{ADMIN_PASS}".encode()
).hexdigest()
SECRET = (_configured_secret or _fallback_secret).encode()

PATIENT_TEST_OTP_ENABLED = os.getenv("PATIENT_TEST_OTP_ENABLED", "false").strip().lower() in {
    "1", "true", "yes", "on",
}
PATIENT_TEST_OTP = "000000"
PATIENT_OTP_TTL_SECONDS = int(os.getenv("PATIENT_OTP_TTL_SECONDS", "300"))
PATIENT_OTP_MAX_ATTEMPTS = int(os.getenv("PATIENT_OTP_MAX_ATTEMPTS", "5"))
_PATIENT_OTP_LOCK = threading.Lock()
_PATIENT_OTP_CHALLENGES: dict[str, dict] = {}


def normalize_tckn(value: str) -> str:
    return re.sub(r"\D", "", value or "")


def valid_tckn(value: str) -> bool:
    """T.C. kimlik numarasının biçim ve resmi kontrol basamaklarını doğrula."""
    digits = normalize_tckn(value)
    if len(digits) != 11 or digits[0] == "0":
        return False
    values = [int(char) for char in digits]
    tenth = ((sum(values[0:9:2]) * 7) - sum(values[1:8:2])) % 10
    eleventh = sum(values[:10]) % 10
    return values[9] == tenth and values[10] == eleventh


def normalize_birth_date(value: str) -> str:
    raw = (value or "").strip()
    for fmt in ("%d.%m.%Y", "%Y-%m-%d", "%d/%m/%Y"):
        try:
            return datetime.strptime(raw, fmt).date().isoformat()
        except ValueError:
            pass
    raise ValueError("Doğum tarihi geçersiz")


def patient_identity_hash(tckn: str, birth_date: str) -> str:
    normalized = f"{normalize_tckn(tckn)}|{normalize_birth_date(birth_date)}"
    return hmac.new(SECRET, normalized.encode("utf-8"), hashlib.sha256).hexdigest()


def patient_otp_create(patient_no: str) -> tuple[str, str, int]:
    """Tek kullanımlık OTP üret; düz kodu yalnız SMS göndericisine döndür."""
    challenge_id = secrets.token_urlsafe(24)
    code = f"{secrets.randbelow(1_000_000):06d}"
    now = int(time.time())
    with _PATIENT_OTP_LOCK:
        for key, item in list(_PATIENT_OTP_CHALLENGES.items()):
            if int(item.get("expires_at", 0)) <= now:
                _PATIENT_OTP_CHALLENGES.pop(key, None)
        _PATIENT_OTP_CHALLENGES[challenge_id] = {
            "patient_no": str(patient_no),
            "code_hash": hmac.new(SECRET, code.encode(), hashlib.sha256).hexdigest(),
            "expires_at": now + PATIENT_OTP_TTL_SECONDS,
            "attempts": 0,
            "used": False,
        }
    return challenge_id, code, PATIENT_OTP_TTL_SECONDS


def patient_otp_verify(challenge_id: str, code: str) -> str | None:
    candidate = re.sub(r"\D", "", code or "")
    now = int(time.time())
    with _PATIENT_OTP_LOCK:
        item = _PATIENT_OTP_CHALLENGES.get(challenge_id or "")
        if not item or item["used"] or int(item["expires_at"]) <= now:
            return None
        item["attempts"] += 1
        if item["attempts"] > PATIENT_OTP_MAX_ATTEMPTS:
            return None
        expected = hmac.new(SECRET, candidate.encode(), hashlib.sha256).hexdigest()
        valid = hmac.compare_digest(expected, item["code_hash"])
        if PATIENT_TEST_OTP_ENABLED and secrets.compare_digest(candidate, PATIENT_TEST_OTP):
            valid = True
        if not valid:
            return None
        item["used"] = True
        return str(item["patient_no"])


def _sign(msg: str) -> str:
    return base64.urlsafe_b64encode(
        hmac.new(SECRET, msg.encode(), hashlib.sha256).digest()
    ).decode().rstrip("=")


def dogrula_giris(user: str, password: str) -> bool:
    return (secrets.compare_digest(user or "", ADMIN_USER)
            and secrets.compare_digest(password or "", ADMIN_PASS))


def _b64_encode(value: str) -> str:
    return base64.urlsafe_b64encode(value.encode()).decode().rstrip("=")


def _b64_decode(value: str) -> str:
    return base64.urlsafe_b64decode(value + "=" * (-len(value) % 4)).decode()


def token_uret(user: str, role: str = "admin") -> str:
    if role not in {"doctor", "admin"}:
        raise ValueError("Geçersiz kullanıcı rolü")
    msg = f"web2|{_b64_encode(user)}|{role}|{int(time.time())}"
    return f"{base64.urlsafe_b64encode(msg.encode()).decode().rstrip('=')}.{_sign(msg)}"


def token_bilgisi(token: str) -> dict | None:
    if not token or "." not in token:
        return None
    body, sig = token.rsplit(".", 1)
    try:
        pad = "=" * (-len(body) % 4)
        msg = base64.urlsafe_b64decode(body + pad).decode()
    except Exception:
        return None
    if not hmac.compare_digest(_sign(msg), sig):
        return None
    try:
        if msg.startswith("web2|"):
            marker, encoded_user, role, ts = msg.split("|", 3)
            if marker != "web2" or role not in {"doctor", "admin"}:
                return None
            user = _b64_decode(encoded_user)
        else:
            # v2.8.x yönetici çerezleri için geriye uyumluluk.
            user, ts = msg.rsplit("|", 1)
            role = "admin"
        if (time.time() - int(ts)) >= MAX_AGE:
            return None
        return {"user": user, "role": role, "display_name": kullanici_adi(user, role)}
    except Exception:
        return None


def token_gecerli(token: str) -> bool:
    return token_bilgisi(token) is not None


def api_giris_rolu(user: str, password: str) -> str | None:
    """Mobil API kullanıcısını doğrula ve yetki rolünü döndür."""
    if dogrula_giris(user, password):
        return "admin"
    account = doktor_bilgisi(user)
    if account and secrets.compare_digest(password or "", account["password"]):
        return "doctor"
    legacy_patient_login = os.getenv("PATIENT_LEGACY_LOGIN_ENABLED", "false").strip().lower() in {
        "1", "true", "yes", "on",
    }
    account = hasta_bilgisi(user) if legacy_patient_login else None
    if account and secrets.compare_digest(password or "", account["password"]):
        return "patient"
    return None


def api_token_uret(user: str, role: str) -> str:
    """Mobil istemciler için süreli ve imzalı Bearer token üret."""
    if role not in {"doctor", "patient", "admin"}:
        raise ValueError("Geçersiz kullanıcı rolü")
    # Kullanıcı adları COMED tarafında `|tracer` içerebildiği için
    # kullanıcıyı ayrı bir base64url alanında taşıyoruz.
    msg = f"api2|{_b64_encode(user)}|{role}|{int(time.time())}"
    body = base64.urlsafe_b64encode(msg.encode()).decode().rstrip("=")
    return f"{body}.{_sign(msg)}"


def api_token_bilgisi(token: str) -> dict | None:
    """Geçerli Bearer token içindeki kullanıcı ve rol bilgisini döndür."""
    if not token or "." not in token:
        return None
    body, sig = token.rsplit(".", 1)
    try:
        pad = "=" * (-len(body) % 4)
        msg = base64.urlsafe_b64decode(body + pad).decode()
    except Exception:
        return None
    if not hmac.compare_digest(_sign(msg), sig):
        return None
    try:
        marker, user_field, role, ts = msg.split("|", 3)
        if marker == "api2":
            user = _b64_decode(user_field)
        elif marker == "api":
            user = user_field
        else:
            return None
        if role not in {"doctor", "patient", "admin"}:
            return None
        if (time.time() - int(ts)) >= MOBILE_API_MAX_AGE:
            return None
        result = {
            "user": user,
            "role": role,
            "display_name": kullanici_adi(user, role),
        }
        if role == "patient":
            account = hasta_bilgisi(user)
            result["patient_no"] = (account or {}).get("patient_no", user)
        return result
    except Exception:
        return None
