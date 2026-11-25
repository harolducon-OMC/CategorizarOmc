"""
Lógica reusable de escucha social: Xpoz (MCP remoto) + análisis de sentimiento Gemini/Groq.

Instalación:
    python -m pip install mcp openai pydantic truststore langdetect

Variables de entorno:
    XPOZ_API_KEY       (clave gratuita en xpoz.ai)
    LLM_PROVIDER       groq | gemini        (por defecto: groq)
    GROQ_API_KEY       (console.groq.com)
    GEMINI_API_KEY     (aistudio.google.com/app/apikey)
    LLM_MODEL          (opcional, para cambiar el modelo por defecto)

Uso:
    python social_listening.py --list-tools
    python social_listening.py "Koaj" --max 60 --lang es
    LLM_PROVIDER=gemini python social_listening.py "Koaj"
"""
# Usa el almacén de certificados de Windows (necesario en redes corporativas con proxy SSL).
# Debe ir ANTES de importar mcp / httpx / openai.
try:
    import truststore

    truststore.inject_into_ssl()
except ImportError:
    pass

import json
import os
import re
import time
import unicodedata
from collections import Counter
from typing import Literal

from mcp import ClientSession
from mcp.client.streamable_http import streamablehttp_client
from openai import (
    APIConnectionError,
    APITimeoutError,
    InternalServerError,
    OpenAI,
    RateLimitError,
)
from pydantic import BaseModel, Field

# Detección de idioma propia (para posts que Xpoz devuelve sin dato de idioma)
try:
    from langdetect import DetectorFactory, detect

    DetectorFactory.seed = 0  # resultados reproducibles
except ImportError:
    detect = None

XPOZ_URL = "https://mcp.xpoz.ai/mcp"

# Groq y Gemini exponen endpoints compatibles con el SDK de OpenAI.
# Los nombres de modelo cambian con el tiempo: si uno falla, cámbialo con LLM_MODEL.
PROVIDERS = {
    "groq": {
        "base_url": "https://api.groq.com/openai/v1",
        "key_env": "GROQ_API_KEY",
        "model": "llama-3.3-70b-versatile",
        "models": ["llama-3.3-70b-versatile", "llama-3.1-8b-instant"],
    },
    "gemini": {
        "base_url": "https://generativelanguage.googleapis.com/v1beta/openai/",
        "key_env": "GEMINI_API_KEY",
        "model": "gemini-3.5-flash-lite",
        "models": ["gemini-3.5-flash-lite", "gemini-3.6-flash", "gemini-2.5-flash-lite"],
    },
}
PROVIDER = os.getenv("LLM_PROVIDER", "groq").lower()
CFG = PROVIDERS[PROVIDER]
MODEL = os.getenv("LLM_MODEL", CFG["model"])
TEXT_KEYS = ("text", "body", "content", "selftext", "caption", "title", "description")


# ---------- 1. Extracción vía MCP ----------
def _find_records(obj):
    """Busca recursivamente la primera lista de dicts dentro de la respuesta."""
    if isinstance(obj, list) and obj and isinstance(obj[0], dict):
        return obj
    if isinstance(obj, dict):
        for v in obj.values():
            found = _find_records(v)
            if found:
                return found
    return []


# Xpoz responde en formato tabular tipo TOON, no en JSON:
#   data:
#     results[100]{id,text,authorUsername,...}:
#       "2102...","texto con, comas",usuario,806,es,"2026-09-21T00:00:00.000Z"
_HEADER = re.compile(r"^(\s*)[\w\-]*\[(\d+)\]\{([^}]*)\}:\s*$")


def _split_row(line: str) -> list[str]:
    """Separa una fila por comas respetando comillas y escapes (\\n, \\", \\\\)."""
    fields, cur, in_q, esc = [], [], False, False
    for ch in line:
        if esc:
            cur.append({"n": "\n", "t": "\t", "r": "\r"}.get(ch, ch))
            esc = False
        elif ch == "\\" and in_q:
            esc = True
        elif ch == '"':
            in_q = not in_q
        elif ch == "," and not in_q:
            fields.append("".join(cur))
            cur = []
        else:
            cur.append(ch)
    fields.append("".join(cur))
    return fields


def _parse_toon(text: str) -> list[dict]:
    """Convierte la primera tabla `nombre[N]{col1,col2}:` en una lista de dicts."""
    lines = text.splitlines()
    records: list[dict] = []
    i = 0
    while i < len(lines):
        m = _HEADER.match(lines[i])
        i += 1
        if not m:
            continue
        indent = len(m.group(1))
        declared = int(m.group(2))
        cols = [c.strip() for c in m.group(3).split(",")]
        while i < len(lines) and lines[i].strip() and (len(lines[i]) - len(lines[i].lstrip())) > indent:
            vals = _split_row(lines[i].strip())
            if len(vals) == len(cols):
                records.append(dict(zip(cols, vals)))
            i += 1
        if records:
            if len(records) != declared:
                print(f"[aviso] la tabla declara {declared} filas y se leyeron {len(records)} (filas con columnas desalineadas se descartan)")
            break
    return records


LOCATION_HINTS = ("location", "country", "place", "geo", "city")
LANG_KEYS = ("lang", "language", "languageCode", "lang_code", "tweetLang")


def _pick_location(r: dict) -> str:
    """Junta cualquier campo del post cuyo nombre sugiera ubicación."""
    vals = [
        str(v)
        for k, v in r.items()
        if any(h in k.lower() for h in LOCATION_HINTS)
        and v
        and str(v).strip().lower() not in ("null", "none", "undefined")
    ]
    return " | ".join(vals)[:120]


def _pick_lang(r: dict) -> str:
    """Toma el idioma del post si viene en alguno de los campos conocidos (es-419 -> es)."""
    for k in LANG_KEYS:
        v = str(r.get(k) or "").strip().lower()
        if v and v not in ("null", "none", "und", "undefined"):
            return v.split("-")[0].split("_")[0]
    return ""


URL_SKIP = ("avatar", "image", "img", "media", "profile", "thumbnail", "photo",
            "picture", "video", "cover", "icon", "banner")


_IG_ALPHABET = "ABCDEFGHIJKLMNOPQRSTUVWXYZabcdefghijklmnopqrstuvwxyz0123456789-_"


def _ig_shortcode(strong_id) -> str:
    """'3923334600170977402_13243072318' -> shortcode del link /p/<shortcode>/."""
    try:
        n = int(str(strong_id).split("_")[0])
    except ValueError:
        return ""
    out = ""
    while n:
        n, r = divmod(n, 64)
        out = _IG_ALPHABET[r] + out
    return out


def _pick_url(platform: str, r: dict, kind: str = "post") -> str:
    """Link a la publicación/comentario. Busca campos url/link/permalink y,
    si no hay, arma el de Twitter/X con el id y el usuario."""
    plat = platform.lower()
    # permalink primero (en Reddit 'url' puede ser un enlace externo)
    for k, v in sorted(r.items(), key=lambda kv: 0 if "permalink" in kv[0].lower() else 1):
        kl = k.lower()
        if any(h in kl for h in ("url", "link", "permalink")) and not any(s in kl for s in URL_SKIP):
            v = str(v or "").strip()
            if v.lower() in ("", "null", "none", "undefined"):
                continue
            if v.startswith("/") and "reddit" in plat:
                v = "https://www.reddit.com" + v
            if v.startswith("http"):
                return v
    if kind == "post":
        if "tiktok" in plat and r.get("id") and r.get("username"):
            return f"https://www.tiktok.com/@{r['username']}/video/{r['id']}"
        if "instagram" in plat:
            sc = _ig_shortcode(r.get("id"))
            if sc:
                return f"https://www.instagram.com/p/{sc}/"
        if "reddit" in plat and r.get("id"):
            return f"https://www.reddit.com/comments/{r['id']}"
    if "twitter" in plat:
        pid = r.get("id")
        user = r.get("authorUsername") or r.get("username")
        if pid and user:
            return f"https://x.com/{user}/status/{pid}"
        if pid:
            return f"https://x.com/i/status/{pid}"
    return ""


def _clean_for_detect(text: str) -> str:
    """Quita URLs, menciones, hashtags y emojis para que langdetect acierte más."""
    text = re.sub(r"https?://\S+|@\w+|#\w+", " ", text)
    text = re.sub(r"[^\w\sáéíóúüñÁÉÍÓÚÜÑ¿¡?!.,]", " ", text)
    return re.sub(r"\s+", " ", text).strip()


def _detect_lang(text: str) -> str:
    """Detecta el idioma por el texto. Devuelve '' si no se puede."""
    if not detect:
        return ""
    clean = _clean_for_detect(text)
    if len(clean) < 12:  # muy corto: la detección no es confiable
        return ""
    try:
        return detect(clean)
    except Exception:
        return ""


def _to_mentions(platform: str, payload_text: str, kind: str = "post") -> list[dict]:
    try:
        records = _find_records(json.loads(payload_text))
    except json.JSONDecodeError:
        records = _parse_toon(payload_text)
    out = []
    for r in records:
        text = next((str(r[k]) for k in TEXT_KEYS if r.get(k)), "")
        if r.get("title") and r.get("selftext"):  # Reddit: título + cuerpo
            text = f"{r['title']}. {r['selftext']}"
        if text.strip():
            out.append(
                {
                    "platform": platform,
                    "text": text.strip()[:1000],
                    "lang": _pick_lang(r),
                    "location": _pick_location(r),
                    "url": _pick_url(platform, r, kind),
                    "kind": kind,
                    "raw": r,
                }
            )
    return out


async def list_tools():
    headers = {"Authorization": f"Bearer {os.environ['XPOZ_API_KEY'].strip()}"}
    async with streamablehttp_client(XPOZ_URL, headers=headers) as (r, w, _):
        async with ClientSession(r, w) as s:
            await s.initialize()
            for t in (await s.list_tools()).tools:
                print(f"- {t.name}: {(t.description or '')[:90]}")


# Campos extra a pedir por red (Xpoz devuelve pocas columnas por defecto).
# None/ausente = columnas por defecto. Rellena Reddit/Instagram/TikTok cuando confirmes
# los nombres exactos en el esquema de cada herramienta (parámetro "fields").
FIELDS: dict[str, list[str]] = {
    "Twitter": ["id", "text", "authorUsername", "impressionCount", "lang",
                "createdAtDate", "placeCountry", "placeName"],
}
LAST_DISCARDED: list[dict] = []  # menciones descartadas en la última corrida de collect(), con el motivo


COMMENT_TOOLS = {
    "Instagram": "getInstagramCommentsByPostId",
    "Tiktok": "getTiktokCommentsByPostId",
    "Twitter": "getTwitterPostComments",
}


def _norm(s: str) -> str:
    return unicodedata.normalize("NFKD", s).encode("ascii", "ignore").decode().lower()


def _mentions_brand(brand: str, text: str) -> bool:
    """La marca aparece como palabra completa (sin acentos ni mayúsculas)."""
    return re.search(rf"(?<!\w){re.escape(_norm(brand))}(?!\w)", _norm(text)) is not None


def _lang_ok(m: dict, wanted: list[str]) -> bool:
    """Acepta si el idioma de origen O el detectado por texto coincide.
    El idioma de origen falla en textos cortos (p. ej. 'ht' para español con emojis)."""
    src = m["lang"]
    m.setdefault("lang_src", src)
    if src in wanted:
        return True
    det = _detect_lang(m["text"])
    if det:
        m["lang"] = det
        return det in wanted
    return src in ("", "und")  # texto muy corto sin dato fiable: se conserva


def _slim(m: dict) -> dict:
    return {
        "red": m["platform"],
        "tipo": m.get("kind", "post"),
        "idioma_origen": m.get("lang_src", m.get("lang", "")),
        "idioma_detectado": m.get("lang", ""),
        "texto": m["text"],
        "link": m.get("url", ""),
    }


def _apply_lang(found: list[dict], wanted: list[str]) -> list[dict]:
    kept = [m for m in found if _lang_ok(m, wanted)]
    ids = {id(m) for m in kept}
    LAST_DISCARDED.extend({**_slim(m), "motivo": "idioma"} for m in found if id(m) not in ids)
    return kept


async def _call(s, name: str, args: dict, fallback: dict | None = None) -> str:
    """Llama a una herramienta; si falla con args extra (fields/fechas), reintenta con lo básico."""
    err = ""
    for a in (args, fallback):
        if a is None:
            continue
        try:
            res = await s.call_tool(name, a)
        except Exception as e:  # una red caída no debe tumbar el reporte
            err = f"{type(e).__name__}: {e}"
            continue
        text = "".join(getattr(b, "text", "") for b in res.content if getattr(b, "type", "") == "text")
        if getattr(res, "isError", False):
            err = text[:200]
            continue
        return text
    print(f"[aviso] {name} falló: {err}")
    return ""


async def collect(
    brand: str,
    limit: int,
    platforms: list[str] | None = None,
    xpoz_key: str | None = None,
    langs: list[str] | None = None,
    with_comments: bool = False,
    comment_platforms: tuple[str, ...] = ("Instagram", "Tiktok"),
    comments_posts: int = 5,
    comments_per_post: int = 40,
    strict_brand: bool = True,
    days: int | None = None,
    on_log=None,
) -> list[dict]:
    """Extrae menciones. Embudo por herramienta: filas crudas -> marca -> idioma -> tope."""

    def log(msg: str):
        print(msg)
        if on_log:
            on_log(msg)

    headers = {"Authorization": f"Bearer {(xpoz_key or os.environ['XPOZ_API_KEY']).strip()}"}
    wanted_langs = [l.lower().split("-")[0] for l in langs] if langs else []
    start_date = None
    if days:
        import datetime as _dt

        start_date = (_dt.date.today() - _dt.timedelta(days=days)).isoformat()
    LAST_DISCARDED.clear()
    mentions: list[dict] = []
    posts_by_platform: dict[str, list[dict]] = {}
    async with streamablehttp_client(XPOZ_URL, headers=headers) as (r, w, _):
        async with ClientSession(r, w) as s:
            await s.initialize()
            tools = {t.name for t in (await s.list_tools()).tools}
            names = sorted(n for n in tools if n.endswith("PostsByKeywords") or n == "getRedditCommentsByKeywords")
            if platforms:
                wanted = [p.lower() for p in platforms]
                names = [n for n in names if any(p in n.lower() for p in wanted)]
            per_platform = max(1, limit // max(1, len(names)))
            for name in names:
                platform = re.sub(r"^get|(Posts|Comments)ByKeywords$", "", name)
                kind = "comentario" if "Comments" in name else "post"
                basic = {"query": brand, "limit": min(300, per_platform * 3)}  # margen para los filtros
                args = dict(basic)
                if platform in FIELDS and kind == "post":
                    args["fields"] = FIELDS[platform]
                if start_date:
                    args["startDate"] = start_date
                text = await _call(s, name, args, basic)
                found = _to_mentions(platform, text, kind) if text else []
                raw_n = len(found)
                if strict_brand:
                    kept = [m for m in found if _mentions_brand(brand, m["text"])]
                    ids = {id(m) for m in kept}
                    LAST_DISCARDED.extend({**_slim(m), "motivo": "sin la marca"} for m in found if id(m) not in ids)
                    found = kept
                brand_n = len(found)
                if wanted_langs:
                    found = _apply_lang(found, wanted_langs)
                log(f"{name}: {raw_n} crudas -> {brand_n} con la marca -> {len(found)} tras idioma")
                found = found[:per_platform]
                mentions += found
                if kind == "post":
                    posts_by_platform[platform] = found

            # Comentarios de los primeros posts (opcional: consume créditos de Xpoz)
            if with_comments:
                for platform in comment_platforms:
                    tool = COMMENT_TOOLS.get(platform)
                    posts = posts_by_platform.get(platform, [])[:comments_posts]
                    if not tool or tool not in tools or not posts:
                        continue
                    got = 0
                    for post in posts:
                        pid = str(post["raw"].get("id", ""))
                        basic = {"postId": pid, "limit": comments_per_post}
                        text = await _call(s, tool, basic)
                        cs = _to_mentions(platform, text, "comentario") if text else []
                        if wanted_langs:
                            cs = _apply_lang(cs, wanted_langs)
                        for c in cs:
                            c["url"] = post.get("url", "")  # link al post de origen
                        mentions += cs[:per_platform]
                        got += len(cs[:per_platform])
                    log(f"{tool}: {got} comentarios de {len(posts)} posts")
    return mentions


# ---------- 2. Clasificación con LLM ----------
class Item(BaseModel):
    id: int
    sentiment: Literal["positivo", "neutral", "negativo"]
    score: float = Field(ge=-1, le=1)
    emotion: str
    topic: str
    pain_point: str | None = None
    risk: bool = False
    country: str = "desconocido"


class Batch(BaseModel):
    items: list[Item]


SYSTEM = (
    "Eres analista de social listening. Recibes menciones de una marca (español/inglés). "
    "Responde SOLO con JSON válido, sin texto extra ni backticks, con la forma "
    '{"items":[{"id":int,"sentiment":"positivo|neutral|negativo","score":-1..1,'
    '"emotion":str,"topic":str,"pain_point":str|null,"risk":bool,"country":str}]}. '
    "risk=true si es queja viral, amenaza reputacional o crisis. "
    "country = país del autor en español (Colombia, México, España, Argentina, Chile, Perú, "
    "Ecuador, Venezuela, Estados Unidos, etc.). Dedúcelo del campo location (si existe), de "
    "ciudades, moneda, jerga local o referencias a tiendas. Si no hay evidencia suficiente "
    'responde exactamente "desconocido"; no adivines.'
)


def list_models(provider: str, api_key: str) -> list[str]:
    """Modelos disponibles para tu llave (endpoint /models, compatible con OpenAI)."""
    cfg = PROVIDERS[provider]
    client = OpenAI(api_key=api_key, base_url=cfg["base_url"], timeout=30.0, max_retries=0)
    ids = [m.id.removeprefix("models/") for m in client.models.list().data]
    skip = ("whisper", "tts", "guard", "embed", "imagen", "veo", "aqa", "orpheus", "playai", "image")
    ids = [i for i in ids if not any(s in i.lower() for s in skip)]
    if provider == "gemini":
        ids = [i for i in ids if i.startswith("gemini")]
    return sorted(set(ids))


def describe_error(e: Exception) -> str:
    """Texto legible con código HTTP y cuerpo de la respuesta del proveedor."""
    status = getattr(e, "status_code", None)
    body = getattr(e, "body", None)
    if not body:
        try:
            body = e.response.text[:800]
        except Exception:
            body = ""
    body_s = str(body)
    if "<html" in body_s.lower() or "<script" in body_s.lower():
        if "Unsanctioned" in body_s or "Blocked" in body_s:
            return (
                f"{type(e).__name__} (HTTP {status}): la red de la empresa bloqueó este proveedor "
                "(página de bloqueo, no es un error de la API ni de tu llave). "
                "Prueba con otro proveedor o pide autorización a seguridad de la información."
            )
        return f"{type(e).__name__} (HTTP {status}): respuesta HTML inesperada (posible proxy o firewall)."
    return f"{type(e).__name__} (HTTP {status}): {e} | detalle: {body_s[:800]}"


def _call_llm(client: OpenAI, user_content: str, model: str, retries: int = 5, on_log=None) -> str:
    """Llama al LLM con backoff ante 429 y ante 5xx/caídas de conexión (503 = proveedor saturado)."""
    last_err: Exception | None = None
    for attempt in range(retries):
        try:
            resp = client.chat.completions.create(
                model=model,
                temperature=0,
                response_format={"type": "json_object"},
                messages=[
                    {"role": "system", "content": SYSTEM},
                    {"role": "user", "content": user_content},
                ],
            )
            return resp.choices[0].message.content
        except (RateLimitError, InternalServerError, APIConnectionError, APITimeoutError) as e:
            last_err = e
            wait = 5 * (2**attempt)
            msg = f"{describe_error(e)} -> reintentando en {wait}s ({attempt + 1}/{retries})"
            print(f"[aviso] {msg}")
            if on_log:
                on_log(msg[:300])
            time.sleep(wait)
    raise RuntimeError(
        "Se agotaron los reintentos con el LLM. Último error: "
        f"{describe_error(last_err) if last_err else 'desconocido'}. "
        "Cambia de proveedor/modelo (p. ej. gemini-2.5-flash-lite o llama-3.1-8b-instant), "
        "baja el máximo de menciones o espera un rato."
    )


def classify(
    brand: str,
    mentions: list[dict],
    batch_size: int = 8,
    provider: str | None = None,
    model: str | None = None,
    api_key: str | None = None,
    on_progress=None,
    on_log=None,
) -> list[dict]:
    cfg = PROVIDERS[provider or PROVIDER]
    model = model or (MODEL if provider in (None, PROVIDER) else cfg["model"])
    # timeout: una llamada colgada falla a los 60 s en vez de esperar indefinidamente.
    # max_retries=0: los reintentos los controla _call_llm (así se ven en pantalla).
    client = OpenAI(
        api_key=api_key or os.environ[cfg["key_env"]],
        base_url=cfg["base_url"],
        timeout=60.0,
        max_retries=0,
    )
    for i in range(0, len(mentions), batch_size):
        if on_progress:
            on_progress(min(i + batch_size, len(mentions)), len(mentions))
        chunk = mentions[i : i + batch_size]
        # Texto recortado para no pasarse del límite de tokens por minuto del plan gratuito
        payload = [
            {"id": j, "text": m["text"][:400], "location": m.get("location", ""), "lang": m.get("lang", "")}
            for j, m in enumerate(chunk)
        ]
        raw = _call_llm(
            client, f"Marca: {brand}\n{json.dumps(payload, ensure_ascii=False)}", model, on_log=on_log
        )
        raw = raw.replace("```json", "").replace("```", "").strip()
        try:
            items = Batch.model_validate_json(raw).items
        except Exception as e:  # un lote mal formado no debe tumbar todo el reporte
            print(f"[aviso] lote {i // batch_size} inválido: {e}")
            continue
        for item in items:
            if 0 <= item.id < len(chunk):
                chunk[item.id]["analysis"] = item.model_dump()
        time.sleep(2)  # pausa corta entre lotes
    return [m for m in mentions if "analysis" in m]


# ---------- 3. Reporte ----------
def report(brand: str, mentions: list[dict]) -> dict:
    n = len(mentions) or 1
    sent = Counter(m["analysis"]["sentiment"] for m in mentions)
    by_platform = {}
    for m in mentions:
        by_platform.setdefault(m["platform"], []).append(m["analysis"]["score"])
    summary = {
        "marca": brand,
        "total_menciones": len(mentions),
        "sentimiento_%": {k: round(100 * v / n, 1) for k, v in sent.items()},
        "score_promedio": round(sum(m["analysis"]["score"] for m in mentions) / n, 2),
        "score_por_red": {p: round(sum(v) / len(v), 2) for p, v in by_platform.items()},
        "temas_top": Counter(m["analysis"]["topic"] for m in mentions).most_common(8),
        "pain_points_top": Counter(
            m["analysis"]["pain_point"] for m in mentions if m["analysis"]["pain_point"]
        ).most_common(8),
        "alertas_riesgo": [
            {"red": m["platform"], "texto": m["text"][:200]} for m in mentions if m["analysis"]["risk"]
        ],
    }
    return summary


