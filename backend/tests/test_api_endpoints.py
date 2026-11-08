"""Pruebas de la capa HTTP (autenticación, propiedad de estudios y límites de peticiones).

No necesitan PostgreSQL: la sesión de base de datos se reemplaza por un Mock.
Se omiten solas si FastAPI/httpx no están instalados.
"""
import os
import re
import sys
import unittest
from types import SimpleNamespace
from unittest.mock import MagicMock, patch

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
os.environ.setdefault("DATABASE_URL", "sqlite:///./unused-by-tests.db")  # nunca se conecta: get_db se sustituye

try:
    from fastapi.testclient import TestClient
    from app import policies, ratelimit
    from app.db import get_db
    from app.main import app
    from app.security import create_access_token
    API_AVAILABLE = True
except ImportError:  # pragma: no cover - entorno sin dependencias de la API
    API_AVAILABLE = False

SECRET = "t" * 64
PUBLIC_PATHS = {
    "/api/health",
    "/api/auth/register",
    "/api/auth/login",
    "/api/telemetry/vitals",  # métricas web del navegador: pública a propósito (sendBeacon no envía token)
}
# Rutas de documentación autogeneradas por FastAPI: son públicas por diseño.
DOCS_PATHS = {"/docs", "/docs/oauth2-redirect", "/redoc", "/openapi.json"}
HTTP_METHODS = {"GET", "POST", "PUT", "PATCH", "DELETE"}


@unittest.skipUnless(API_AVAILABLE, "FastAPI/httpx no están instalados")
class ApiHttpLayerTests(unittest.TestCase):
    def setUp(self):
        self.secret_patch = patch("app.security.JWT_SECRET", SECRET)
        self.secret_patch.start()
        self.env_patch = patch.dict(os.environ, {"RATE_LIMIT_DISABLED": "0"})
        self.env_patch.start()
        ratelimit.limiter.reset()
        # Estado de la cuenta y políticas sin tocar la base de datos
        self.status = {"id": "user-1", "email": "ana@omc", "role": "user", "active": True, "banned": False,
                       "must_change_password": False, "token_version": 0}
        self.status_patch = patch("app.accounts.account_status", side_effect=lambda email: self.status)
        self.status_patch.start()
        self.policy_patch = patch("app.policies.get_policy", return_value=policies.default_policy())
        self.policy_patch.start()
        self.db = MagicMock()
        app.dependency_overrides[get_db] = lambda: self.db
        self.client = TestClient(app)  # sin "with": no ejecuta el evento de arranque (sin BD)
        self.headers = {"Authorization": f"Bearer {create_access_token('ana@omc')}"}

    def tearDown(self):
        app.dependency_overrides.clear()
        self.status_patch.stop()
        self.policy_patch.stop()
        self.env_patch.stop()
        self.secret_patch.stop()
        ratelimit.limiter.reset()

    # ---- autenticación
    def test_health_is_public_and_has_security_headers(self):
        response = self.client.get("/api/health")
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json()["status"], "ok")
        self.assertEqual(response.headers["X-Content-Type-Options"], "nosniff")
        self.assertTrue(response.headers.get("X-Request-ID"))

    def test_every_private_route_requires_a_token(self):
        # Se usa el esquema OpenAPI: lista las rutas reales de la API
        # y deja fuera las internas de Swagger/ReDoc.
        checked = 0
        for path, operations in app.openapi()["paths"].items():
            if path in PUBLIC_PATHS or path in DOCS_PATHS:
                continue
            for method in operations:
                method = method.upper()
                if method not in HTTP_METHODS:
                    continue
                url = re.sub(r"\{[^}]+\}", "x", path)
                response = self.client.request(method, url)
                self.assertEqual(
                    response.status_code, 401,
                    f"{method} {path} debería exigir token"
                )
                checked += 1
        self.assertGreater(checked, 25)

    def test_invalid_token_is_rejected(self):
        response = self.client.get("/api/studies", headers={"Authorization": "Bearer no-es-un-jwt"})
        self.assertEqual(response.status_code, 401)

    def test_valid_token_lists_only_the_users_studies(self):
        self.db.scalar.return_value = SimpleNamespace(id="user-1")
        self.db.scalars.return_value.all.return_value = []
        response = self.client.get("/api/studies", headers=self.headers)
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json(), [])
        statement = str(self.db.scalars.call_args.args[0])
        self.assertIn("studies.owner_id", statement)

    # ---- propiedad de los datos
    def test_study_of_another_user_returns_404(self):
        self.db.scalar.side_effect = [SimpleNamespace(id="user-1"), None]  # usuario válido, estudio ajeno
        response = self.client.get("/api/studies/estudio-ajeno", headers=self.headers)
        self.assertEqual(response.status_code, 404)

    # ---- validación y límites
    # ---- cuentas y roles
    def test_regular_users_cannot_use_admin_endpoints(self):
        self.db.scalar.return_value = SimpleNamespace(id="u1", email="ana@omc", role="user", banned_at=None, is_active=True)
        for method, url in (("GET", "/api/admin/users"), ("GET", "/api/admin/policies"), ("GET", "/api/admin/audit")):
            self.assertEqual(self.client.request(method, url, headers=self.headers).status_code, 403, url)

    def test_banned_account_is_blocked_even_with_a_valid_token(self):
        self.status["banned"] = True
        response = self.client.get("/api/studies", headers=self.headers)
        self.assertEqual(response.status_code, 403)
        self.assertEqual(response.json()["code"], "account_banned")

    def test_inactive_account_is_blocked(self):
        self.status["active"] = False
        response = self.client.get("/api/studies", headers=self.headers)
        self.assertEqual((response.status_code, response.json()["code"]), (403, "account_inactive"))

    def test_session_is_closed_when_the_token_version_changes(self):
        self.status["token_version"] = 3  # el administrador restableció la contraseña o baneó la cuenta
        response = self.client.get("/api/studies", headers=self.headers)
        self.assertEqual((response.status_code, response.json()["code"]), (401, "session_invalid"))

    def test_temporary_password_forces_a_change_before_anything_else(self):
        self.status["must_change_password"] = True
        blocked = self.client.get("/api/studies", headers=self.headers)
        self.assertEqual((blocked.status_code, blocked.json()["code"]), (403, "password_change_required"))
        me = self.client.get("/api/auth/me", headers=self.headers)
        self.assertEqual(me.status_code, 200)
        self.assertTrue(me.json()["must_change_password"])

    def test_me_reports_the_role(self):
        self.status["role"] = "admin"
        self.assertEqual(self.client.get("/api/auth/me", headers=self.headers).json()["role"], "admin")

    def test_login_rejects_short_passwords(self):
        response = self.client.post("/api/auth/login", json={"email": "ana@omc", "password": "corta"})
        self.assertEqual(response.status_code, 422)

    def test_register_rejects_non_corporate_email(self):
        self.db.scalar.return_value = None
        response = self.client.post(
            "/api/auth/register", json={"email": "alguien@gmail.com", "password": "una-clave-larga-123"},
        )
        self.assertEqual(response.status_code, 403)

    def test_help_ask_answers_from_the_local_guide_without_ai(self):
        response = self.client.post(
            "/api/help/ask", json={"question": "¿Cómo subo mi encuesta?", "page": "home"}, headers=self.headers,
        )
        self.assertEqual(response.status_code, 200)
        body = response.json()
        self.assertTrue(body["confident"])
        self.assertEqual(body["article"], "importar-archivo")

    def test_help_ask_reports_when_the_guide_has_no_answer(self):
        response = self.client.post("/api/help/ask", json={"question": "receta de arepas"}, headers=self.headers)
        self.assertEqual(response.status_code, 200)
        self.assertFalse(response.json()["confident"])

    def test_login_is_throttled_per_email_after_repeated_failures(self):
        self.db.scalar.return_value = None  # usuario inexistente -> 401
        body = {"email": "victima@omc", "password": "clave-incorrecta-123"}
        for _ in range(8):
            self.assertEqual(self.client.post("/api/auth/login", json=body).status_code, 401)
        blocked = self.client.post("/api/auth/login", json=body)
        self.assertEqual(blocked.status_code, 429)
        self.assertGreaterEqual(int(blocked.headers["Retry-After"]), 1)
        other = self.client.post("/api/auth/login", json={**body, "email": "otra@omc"})
        self.assertEqual(other.status_code, 401)  # otro correo no queda bloqueado

    def test_ai_endpoint_is_throttled_per_user(self):
        self.db.scalar.return_value = SimpleNamespace(id="user-1")
        # El último mensaje es del asistente: el endpoint responde 422 sin llamar a ningún modelo,
        # pero el límite se cuenta igual, que es lo que se comprueba aquí.
        payload = {"provider": "gemini", "model": "m", "messages": [{"role": "assistant", "content": "hola"}]}
        statuses = [
            self.client.post("/api/help/chat", json=payload, headers=self.headers).status_code
            for _ in range(21)
        ]
        self.assertEqual(statuses[-1], 429)
        self.assertNotIn(429, statuses[:20])


if __name__ == "__main__":
    unittest.main(verbosity=2)