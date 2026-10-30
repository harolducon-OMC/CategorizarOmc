# -*- coding: utf-8 -*-
"""Cliente LLM para APIs directas y gateways compatibles con Chat Completions."""
import json
import re
from typing import Any, Optional

DEFAULT_PROVIDER = "gemini"
DEFAULT_MODEL = "gemini-3.5-flash-lite"
# Endpoints directos de los servicios de inferencia. Directorios API no son proveedores.
PROVIDER_CONFIG = {
    "gemini": {"name": "Google AI Studio · Gemini", "base_url": "https://generativelanguage.googleapis.com/v1beta/openai/", "key_env": "GEMINI_API_KEY", "default_model": "gemini-3.5-flash-lite", "models": ["gemini-3.5-flash-lite", "gemini-3.8-flash", "gemini-3.6-flash", "gemini-3.1-flash-lite"], "free_note": "Free tier real para los modelos indicados, con cuotas que dependen del modelo y pueden cambiar. En este tier Google puede usar prompts y respuestas para mejorar sus productos."},
    "groq": {"name": "Groq", "base_url": "https://api.groq.com/openai/v1", "key_env": "GROQ_API_KEY", "default_model": "openai/gpt-oss-20b", "models": ["openai/gpt-oss-20b", "openai/gpt-oss-120b", "openai/gpt-oss-safeguard-20b", "qwen/qwen3.8-27b"], "free_note": "Plan Free real con límites por modelo y organización. Qwen está en Preview; los modelos disponibles pueden cambiar."},
    "cohere": {"name": "Cohere", "base_url": "https://api.cohere.ai/compatibility/v1", "key_env": "COHERE_API_KEY", "default_model": "command-a-plus-05-2026", "models": ["command-a-plus-05-2026"], "free_note": "Command A+ figura sin coste con Trial y production keys, sujeto a límites. Trial limitado y no es para uso comercial/producción; verifica las condiciones de Cohere."},
    "openrouter": {"name": "OpenRouter", "base_url": "https://openrouter.ai/api/v1", "key_env": "OPENROUTER_API_KEY", "default_model": "xingchen-agi/xing4.0-29b-a4b:free", "models": ["xingchen-agi/xing4.0-29b-a4b:free", "liquid/lfm-2.5-2.6b:free", "nvidia/nemotron-3.5-super-vl:free"], "free_note": "Gratis solo para variantes con :free, con disponibilidad volátil y cuota limitada (habitualmente 50 solicitudes/día). No enruta automáticamente a modelos de pago."},
    "anthropic": {"name": "Anthropic · Claude", "base_url": None, "key_env": "ANTHROPIC_API_KEY", "default_model": "claude-haiku-5-5", "models": [], "free_note": "API de pago; sin cuota gratuita general. Ingresa un ID de modelo Claude disponible en tu cuenta."},
}

class LLMError(RuntimeError):
    """Error controlado al llamar o interpretar la respuesta del LLM."""

def parse_json(raw: str) -> Any:
    """Extrae y parsea JSON de una respuesta, tolerando bloques markdown."""
    text = raw.strip()
    text = re.sub(r"^```(?:json)?\s*|\s*```$", "", text, flags=re.IGNORECASE).strip()
    try:
        return json.loads(text)
    except json.JSONDecodeError:
        pass
    for open_c, close_c in (("{", "}"), ("[", "]")):
        i, j = text.find(open_c), text.rfind(close_c)
        if i != -1 and j > i:
            try:
                return json.loads(text[i:j + 1])
            except json.JSONDecodeError:
                continue
    raise ValueError("La respuesta del modelo no contiene JSON válido.")

class LLM:
    def __init__(self, api_key: str, fast: str = DEFAULT_MODEL, smart: str = DEFAULT_MODEL,
                 provider: str = DEFAULT_PROVIDER):
        if not api_key:
            raise LLMError("Falta la API key del proveedor de IA.")
        if provider not in PROVIDER_CONFIG:
            raise LLMError("Proveedor de IA no reconocido.")
        self.provider = provider
        self.api_key = api_key
        self.fast, self.smart = fast, smart
        cfg = PROVIDER_CONFIG[provider]
        if provider == "anthropic":
            try:
                import anthropic
            except ImportError as exc:
                raise LLMError("Falta la dependencia Anthropic. Instala los requisitos del proyecto.") from exc
            self._anthropic = anthropic
            self.client = anthropic.Anthropic(api_key=api_key, max_retries=3, timeout=120.0)
        else:
            try:
                from openai import OpenAI
            except ImportError as exc:
                raise LLMError("Falta la dependencia OpenAI-compatible. Ejecuta: pip install openai") from exc
            self.client = OpenAI(api_key=api_key, base_url=cfg["base_url"], max_retries=2, timeout=120.0)

    def text(self, system: str, user: str, model: Optional[str] = None,
             max_tokens: int = 2000, temperature: Optional[float] = 0.0,
             json_mode: bool = False) -> str:
        model_name = model or self.fast
        if self.provider == "anthropic":
            kwargs = {"model": model_name, "max_tokens": max_tokens, "system": system,
                      "messages": [{"role": "user", "content": user}]}
            try:
                resp = self.client.messages.create(temperature=temperature, **kwargs) if temperature is not None else self.client.messages.create(**kwargs)
                return "".join(block.text for block in resp.content if getattr(block, "type", "") == "text")
            except self._anthropic.APIError as exc:
                status = getattr(exc, "status_code", None)
                raise LLMError(_friendly_api_error(self.provider, status, model_name)) from exc
        messages = [{"role": "system", "content": system}, {"role": "user", "content": user}]
        if self.provider == "cohere":
            try:
                import requests
                payload = {"model": model_name, "messages": messages, "max_tokens": max_tokens}
                if temperature is not None:
                    payload["temperature"] = temperature
                if json_mode:
                    payload["response_format"] = {"type": "json_object"}
                response = requests.post(
                    "https://api.cohere.ai/v2/chat", json=payload,
                    headers={"Authorization": f"Bearer {self.api_key}", "Content-Type": "application/json"},
                    timeout=120,
                )
                if response.status_code >= 400:
                    raise _ProviderHTTPError(response.status_code)
                content = response.json().get("message", {}).get("content", [])
                return "".join(item.get("text", "") for item in content if isinstance(item, dict))
            except _ProviderHTTPError as exc:
                raise LLMError(_friendly_api_error(self.provider, exc.status, model_name)) from exc
            except Exception as exc:
                status = getattr(exc, "status_code", None)
                raise LLMError(_friendly_api_error(self.provider, status, model_name)) from exc
        kwargs = {"model": model_name, "messages": messages, "max_tokens": max_tokens}
        # Gemini 3.x funciona mejor con su temperatura predeterminada (1.0).
        if temperature is not None and not (self.provider == "gemini" and model_name.startswith("gemini-3")):
            kwargs["temperature"] = temperature
        # Para Gemini se solicita JSON en el prompt y se valida con parse_json;
        # la salida estructurada de su capa compatible requiere un esquema.
        if json_mode and self.provider in ("groq", "openrouter"):
            kwargs["response_format"] = {"type": "json_object"}
        if json_mode and self.provider == "openrouter":
            kwargs["provider"] = {"require_parameters": True}
        try:
            resp = self.client.chat.completions.create(**kwargs)
            content = resp.choices[0].message.content
            if isinstance(content, str):
                return content
            if isinstance(content, list):
                return "".join(part.get("text", "") for part in content if isinstance(part, dict))
            return ""
        except Exception as exc:
            status = getattr(exc, "status_code", None)
            detail = _api_error_detail(exc, self.api_key)
            raise LLMError(_friendly_api_error(self.provider, status, model_name, detail)) from exc

    def json(self, system: str, user: str, model: Optional[str] = None, max_tokens: int = 2000) -> Any:
        """Pide JSON y reintenta una vez si la salida no se puede parsear."""
        system += "\n\nResponde ÚNICAMENTE con JSON válido, sin texto adicional ni markdown."
        raw = self.text(system, user, model=model, max_tokens=max_tokens, json_mode=True)
        try:
            return parse_json(raw)
        except ValueError:
            raw = self.text(system + "\nIMPORTANTE: tu respuesta anterior no fue JSON válido. Devuelve solo JSON.",
                            user, model=model, max_tokens=max_tokens, json_mode=True)
            try:
                return parse_json(raw)
            except ValueError as exc:
                raise LLMError("El modelo no devolvió JSON válido tras reintentar.") from exc

def _api_error_detail(exc: Exception, secret: str = "") -> str:
    """Extrae el mensaje del proveedor, ocultando la clave si apareciera en el texto."""
    body = getattr(exc, "body", None)
    detail = ""
    if isinstance(body, dict):
        error = body.get("error", body)
        if isinstance(error, dict):
            detail = str(error.get("message") or error.get("detail") or "")
    if not detail:
        detail = str(getattr(exc, "message", "") or exc)
    if secret:
        detail = detail.replace(secret, "[API key oculta]")
    return detail[:500]


def _friendly_api_error(provider: str, status: Optional[int], model: str, detail: str = "") -> str:
    label = PROVIDER_CONFIG[provider]["name"]
    if status in (401, 403):
        return f"{label} rechazó la clave. Revisa que sea una API key/token de ese proveedor y que siga activo."
    if status == 404:
        return f"{label} no encontró el modelo '{model}'. Comprueba que el ID esté disponible para tu cuenta."
    if status == 400:
        suffix = f" Detalle de Google: {detail}" if detail else " Revisa los parámetros enviados y el modelo seleccionado."
        return f"{label} rechazó la solicitud (HTTP 400) para '{model}'.{suffix}"
    if status == 429:
        return f"{label} alcanzó el límite de uso/cuota. Espera un momento o revisa los límites de tu plan."
    if status:
        return f"La API de {label} devolvió un error HTTP {status}. Revisa clave, modelo, cuota y soporte de endpoint."
    return f"No se pudo conectar con {label}. Revisa conexión, clave y disponibilidad del modelo."

class _ProviderHTTPError(RuntimeError):
    def __init__(self, status: int):
        self.status = status
