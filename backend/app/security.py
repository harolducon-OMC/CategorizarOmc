"""Autenticación JWT y utilidades de seguridad de la plataforma."""
from datetime import datetime, timedelta, timezone
import os
import base64
import hashlib
from cryptography.fernet import Fernet, InvalidToken
from jose import JWTError, jwt
from pwdlib import PasswordHash

JWT_SECRET = os.getenv("JWT_SECRET", "")
JWT_ALGORITHM = "HS256"
ACCESS_TOKEN_MINUTES = int(os.getenv("ACCESS_TOKEN_MINUTES", "60"))
PASSWORD_HASHER = PasswordHash.recommended()
_PLACEHOLDER_MARKERS = ("REEMPLAZA", "CHANGE-ME", "CHANGE-THIS", "CAMBIA-ESTE")


def _is_weak_secret(value: str) -> bool:
    upper = value.upper()
    return len(value) < 32 or any(marker in upper for marker in _PLACEHOLDER_MARKERS)


def validate_security_config():
    if _is_weak_secret(JWT_SECRET):
        raise RuntimeError("Configura JWT_SECRET con al menos 32 caracteres aleatorios antes de iniciar.")
    # Clave de cifrado de API keys independiente (opcional). Si se define, también debe ser robusta.
    dedicated = os.getenv("API_KEY_ENCRYPTION_SECRET", "")
    if dedicated and _is_weak_secret(dedicated):
        raise RuntimeError("API_KEY_ENCRYPTION_SECRET debe tener al menos 32 caracteres aleatorios.")


def hash_password(password: str) -> str:
    return PASSWORD_HASHER.hash(password)


def verify_password(password: str, password_hash: str) -> bool:
    return PASSWORD_HASHER.verify(password, password_hash)


# Hash de relleno: se verifica cuando el correo no existe para que el tiempo de respuesta no delate qué cuentas existen.
_DUMMY_HASH = PASSWORD_HASHER.hash("contraseña-de-relleno-no-valida")


def verify_password_constant_time(password: str, password_hash: str | None) -> bool:
    """Verifica la contraseña y, si no hay hash (usuario inexistente), gasta el mismo tiempo de cálculo."""
    if password_hash is None:
        PASSWORD_HASHER.verify(password, _DUMMY_HASH)
        return False
    return PASSWORD_HASHER.verify(password, password_hash)


def create_access_token(subject: str, token_version: int = 0, minutes: int | None = None) -> str:
    """JWT de sesión. `tv` (versión del token) permite invalidar sesiones al banear o cambiar contraseñas."""
    now = datetime.now(timezone.utc)
    payload = {"sub": subject, "iat": now, "exp": now + timedelta(minutes=minutes or ACCESS_TOKEN_MINUTES), "tv": int(token_version)}
    return jwt.encode(payload, JWT_SECRET, algorithm=JWT_ALGORITHM)


def token_claims(token: str) -> dict | None:
    if not token or len(token) > 4096:
        return None
    try:
        claims = jwt.decode(
            token, JWT_SECRET, algorithms=[JWT_ALGORITHM],
            options={"require_exp": True, "require_iat": True, "require_sub": True},
        )
    except (JWTError, ValueError):
        return None
    if not isinstance(claims.get("sub"), str):
        return None
    try:
        claims["tv"] = int(claims.get("tv", 0))
    except (TypeError, ValueError):
        return None
    return claims
<<<<<<< HEAD
=======


def token_subject(token: str) -> str | None:
    claims = token_claims(token)
    return claims["sub"] if claims else None
>>>>>>> cb3a1cb179251adae7eb3d93ad086a25a7e02b09


def allowed_email_domain() -> str:
    return os.getenv("OMC_EMAIL_DOMAIN", "omc").strip().lower().lstrip("@").lstrip(".")


def email_is_allowed(email: str) -> bool:
    domain = allowed_email_domain()
    local, _, host = email.strip().lower().rpartition("@")
    return bool(domain and local and host == domain)


def _api_key_cipher() -> Fernet:
    """Deriva una clave Fernet separada lógicamente del secreto JWT."""
    validate_security_config()
    # API_KEY_ENCRYPTION_SECRET permite rotar JWT_SECRET sin perder las API keys guardadas.
    base_secret = os.getenv("API_KEY_ENCRYPTION_SECRET") or JWT_SECRET
    digest = hashlib.sha256((base_secret + ":user-provider-api-keys:v1").encode("utf-8")).digest()
    return Fernet(base64.urlsafe_b64encode(digest))


def encrypt_api_key(api_key: str) -> str:
    if not api_key.strip():
        raise ValueError("La API key no puede estar vacía.")
    return _api_key_cipher().encrypt(api_key.strip().encode("utf-8")).decode("ascii")


def decrypt_api_key(ciphertext: str) -> str:
    try:
        return _api_key_cipher().decrypt(ciphertext.encode("ascii")).decode("utf-8")
    except (InvalidToken, ValueError, UnicodeError) as exc:
        raise RuntimeError("No se pudo descifrar la API key guardada. Comprueba que JWT_SECRET no haya cambiado.") from exc
