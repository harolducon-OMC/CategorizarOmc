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


def validate_security_config():
    if len(JWT_SECRET) < 32 or "REEMPLAZA" in JWT_SECRET.upper() or "CHANGE-ME" in JWT_SECRET.upper():
        raise RuntimeError("Configura JWT_SECRET con al menos 32 caracteres aleatorios antes de iniciar.")


def hash_password(password: str) -> str:
    return PASSWORD_HASHER.hash(password)


def verify_password(password: str, password_hash: str) -> bool:
    return PASSWORD_HASHER.verify(password, password_hash)


def create_access_token(subject: str, token_version: int = 0, minutes: int | None = None) -> str:
    """JWT de sesión. `tv` (versión del token) permite invalidar sesiones al banear o cambiar contraseñas."""
    now = datetime.now(timezone.utc)
    payload = {"sub": subject, "iat": now, "exp": now + timedelta(minutes=minutes or ACCESS_TOKEN_MINUTES), "tv": int(token_version)}
    return jwt.encode(payload, JWT_SECRET, algorithm=JWT_ALGORITHM)


def token_claims(token: str) -> dict | None:
    try:
        claims = jwt.decode(token, JWT_SECRET, algorithms=[JWT_ALGORITHM])
    except JWTError:
        return None
    return claims if isinstance(claims.get("sub"), str) else None


def token_subject(token: str) -> str | None:
    claims = token_claims(token)
    return claims["sub"] if claims else None


def allowed_email_domain() -> str:
    return os.getenv("OMC_EMAIL_DOMAIN", "omc").strip().lower().lstrip("@").lstrip(".")


def email_is_allowed(email: str) -> bool:
    domain = allowed_email_domain()
    return bool(domain and email.strip().lower().endswith("@" + domain))


def _api_key_cipher() -> Fernet:
    """Deriva una clave Fernet separada lógicamente del secreto JWT."""
    validate_security_config()
    digest = hashlib.sha256((JWT_SECRET + ":user-provider-api-keys:v1").encode("utf-8")).digest()
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
