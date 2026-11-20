# -*- coding: utf-8 -*-
"""Base de conocimiento propia de Insy: responde sin IA, sin costo y sin enviar datos a terceros.

El buscador es local (BM25 simplificado sobre palabras raíz en español). Si la confianza es baja,
la interfaz ofrece —de forma explícita— preguntarle a la IA.
Para ampliar la guía basta con agregar un artículo a ARTICLES y una prueba en tests/test_help_kb.py.
"""
import math
import re
import unicodedata
from typing import Dict, List, Optional

G = lambda label, page: {"label": label, "page": page}  # noqa: E731  acción de navegación

ARTICLES: List[Dict] = [
    {"id": "importar-archivo", "title": "Importar tu encuesta", "pages": ["home"],
     "keywords": ["importar", "subir", "cargar", "archivo", "csv", "excel", "xlsx", "hoja", "crear estudio", "nuevo estudio", "25 mb", "encuesta"],
     "answer": "En Inicio sube un CSV o XLSX (hasta 25 MB y 200.000 filas). Si es Excel, elige la hoja. Al importar se crea un estudio y sus respuestas quedan guardadas en tu cuenta. Después puedes categorizar sus preguntas abiertas.",
     "actions": [G("Ir a Inicio", "home")]},
    {"id": "preguntas-abiertas", "title": "Preguntas abiertas recomendadas", "pages": ["home", "categorize"],
     "keywords": ["preguntas abiertas", "recomendadas", "texto libre", "detectar", "columnas de texto", "abiertas"],
     "answer": "Inicio muestra cuántas preguntas abiertas detectó: columnas de texto con respuestas variadas (descarta demográficos y códigos). Son una recomendación; en Categorización puedes elegir cualquier otra columna.",
     "actions": [G("Ir a Categorización", "categorize")]},
    {"id": "categorizar-temas", "title": "Categorizar por temas o motivos", "pages": ["categorize"],
     "keywords": ["categorizar", "categorias", "categorizacion", "temas", "motivos", "catalogo", "clasificar", "proponer categorias", "codificar", "codeframe"],
     "answer": "En Categorización elige la pregunta y el tipo «Temas». Pide que se propongan categorías (la IA sugiere entre 5 y 20 a partir de una muestra) o escríbelas tú, edítalas y pulsa Clasificar. Las respuestas idénticas se agrupan para clasificarlas una sola vez, las celdas vacías quedan vacías, NS/NR no cuenta como respuesta válida y lo que no encaja queda en «Otros».",
     "actions": [G("Ir a Categorización", "categorize")]},
    {"id": "categorizar-marcas", "title": "Categorizar marcas", "pages": ["categorize"],
     "keywords": ["marcas", "marca", "catalogo cerrado", "otra marca", "detectar marcas", "entidades", "alias", "menciones"],
     "answer": "En Categorización elige la pregunta y el tipo «Marcas». Puedes dejar que se detecten las marcas escritas o definir un catálogo cerrado: una marca fuera del catálogo queda como «Otra». Después revisa y corrige las etiquetas. Estas clasificaciones son las que alimenta el Awareness integrado.",
     "actions": [G("Ir a Categorización", "categorize")]},
    {"id": "sentimiento", "title": "Análisis de sentimiento", "pages": ["categorize"],
     "keywords": ["sentimiento", "positivo", "negativo", "neutral", "mixto", "ambivalente", "emociones", "opinion"],
     "answer": "El tipo «Sentimiento» clasifica cada respuesta como Positivo, Neutral, Negativo o Mixto/ambivalente. Se elige en Categorización igual que los temas y se revisa en el Dashboard.",
     "actions": [G("Ir a Categorización", "categorize")]},
    {"id": "diccionarios", "title": "Diccionarios de palabras clave", "pages": ["categorize"],
     "keywords": ["diccionario", "palabras clave", "sinonimos", "reglas", "coincidencia", "sin ia", "ahorrar"],
     "answer": "Los diccionarios aplican una categoría cuando aparece una palabra o sinónimo que tú defines, antes de llamar al modelo. Dan resultados predecibles y ahorran llamadas de IA. Lo que no coincide pasa al modelo.",
     "actions": [G("Ir a Categorización", "categorize")]},
    {"id": "etiquetas-especiales", "title": "Otros, Ninguna, Otra y NS/NR", "pages": ["categorize", "dashboard"],
     "keywords": ["otros", "ninguna", "otra", "nsnr", "ns/nr", "no sabe", "no responde", "significa", "etiqueta", "vacia", "vacias"],
     "answer": "«Otros»: la respuesta no encaja en ninguna categoría del catálogo. «Otra» (marcas): marca fuera del catálogo cerrado. «Ninguna»: la persona dijo que no recuerda o no menciona ninguna. «NS/NR»: falta de información y no cuenta como válida. Las celdas vacías permanecen vacías.",
     "actions": []},
    {"id": "revisar-corregir", "title": "Revisar y corregir etiquetas", "pages": ["dashboard"],
     "keywords": ["editar", "corregir", "revisar", "revision", "cambiar etiqueta", "guardar cambios", "manual", "correccion"],
     "answer": "En el Dashboard abre «Revisión y edición manual», marca las etiquetas correctas por respuesta y pulsa «Guardar cambios». Las correcciones se guardan, actualizan las frecuencias y las usa el Awareness integrado.",
     "actions": [G("Ir al Dashboard", "dashboard")]},
    {"id": "dashboard", "title": "Dashboard: frecuencias y segmentos", "pages": ["dashboard"],
     "keywords": ["dashboard", "frecuencias", "segmentos", "cruces", "grafico", "porcentajes", "resultados", "cruzar"],
     "answer": "En el Dashboard eliges una pregunta ya categorizada y ves sus frecuencias. Con un segmento (por ejemplo sexo o departamento) obtienes el cruce por grupos. Las cifras las calcula el sistema, no la IA.",
     "actions": [G("Ir al Dashboard", "dashboard")]},
    {"id": "insights-ia", "title": "Insights cualitativos con IA", "pages": ["dashboard"],
     "keywords": ["insights", "insight", "sintesis", "resumen", "citas", "conclusiones", "generar insights"],
     "answer": "«Generar insights» pide al modelo una síntesis a partir de una muestra de respuestas reales. Las cifras las calcula el sistema y las citas se verifican contra la muestra enviada. Consume tu clave de IA y, antes de enviar, se ocultan correos, teléfonos y documentos.",
     "actions": [G("Ir al Dashboard", "dashboard"), G("Ir a Ajustes", "settings")]},
    {"id": "calidad", "title": "Calidad de la categorización", "pages": ["dashboard"],
     "keywords": ["calidad", "categorizacion", "acuerdo", "precision", "validar", "muestra", "confiable", "error de la ia", "kappa", "revisar muestra", "medir"],
     "answer": "En el Dashboard, el panel «Calidad de la categorización» toma una muestra al azar de respuestas, te deja confirmar o corregir la etiqueta y calcula el acuerdo entre la IA y tu criterio, en total y por categoría. Con 50 respuestas o más la estimación es más estable; las categorías con menor acuerdo son las que conviene afinar.",
     "actions": [G("Ir al Dashboard", "dashboard")]},
    {"id": "api-key", "title": "Guardar o cambiar tu API key", "pages": ["settings"],
     "keywords": ["api key", "apikey", "clave", "token", "llave", "guardar clave", "cambiar clave", "eliminar clave", "reemplazar", "sesion"],
     "answer": "Ve a Ajustes, elige el proveedor y el modelo, pega la API key y pulsa «Guardar clave». Queda cifrada, vinculada a tu cuenta y no vuelve a mostrarse. Para cambiarla escribe una nueva y guarda; para quitarla pulsa «Eliminar clave». También puedes usar una clave solo para la sesión desde el selector de IA superior (esa no se guarda).",
     "actions": [G("Ir a Ajustes", "settings")]},
    {"id": "proveedores-ia", "title": "Elegir proveedor y modelo de IA", "pages": ["settings"],
     "keywords": ["proveedor", "modelo", "gemini", "groq", "cohere", "openrouter", "anthropic", "gratis", "gratuito", "free", "cual elegir", "ia"],
     "answer": "En Ajustes puedes elegir Gemini, Groq, Cohere, OpenRouter o Anthropic. Lee la nota de cada proveedor: en algunos planes gratuitos el proveedor puede usar los textos para mejorar sus productos. Con datos sensibles usa un plan que no lo permita.",
     "actions": [G("Ir a Ajustes", "settings")]},
    {"id": "awareness-tipos", "title": "TOM, espontáneo y ayudado", "pages": ["awareness"],
     "keywords": ["tom", "top of mind", "espontaneo", "espontanea", "ayudado", "ayudada", "awa", "awareness", "recordacion", "conocimiento de marca"],
     "answer": "TOM (Top of Mind) es la primera marca que la persona menciona. Espontáneo son marcas mencionadas sin ayuda que no cuentan ya en TOM. Ayudado son marcas reconocidas cuando se muestra una lista o estímulo y que no estaban en los anteriores. AWA es la suma de las tres, así que cada persona cuenta una sola vez por marca.",
     "actions": [G("Ir a Awareness", "awareness")]},
    {"id": "awareness-modos", "title": "Awareness integrado o independiente", "pages": ["awareness"],
     "keywords": ["integrado", "independiente", "diferencia", "awareness", "cual usar", "sin crear estudio"],
     "answer": "El integrado usa un estudio ya cargado y las marcas que detectaste y corregiste en Categorización. El independiente recibe su propio CSV o XLSX y no exige crear un estudio ni categorizar antes; tiene presets (Bancos, Conglomerados, Personalizado) y genera un Excel completo.",
     "actions": [G("Ir a Awareness", "awareness")]},
    {"id": "awareness-codigos", "title": "Códigos de pregunta (P1, P2…)", "pages": ["awareness"],
     "keywords": ["codigo", "codigos", "codigos de pregunta", "p1", "p2", "p3", "columna", "columnas", "no se encontro", "no encuentra", "validacion de columnas", "tom una sola"],
     "answer": "En Awareness escribes el código de la pregunta (por ejemplo P2) y la plataforma busca las columnas cuyo nombre empieza por ese código (P2 incluye P2_1, P2_2…). TOM admite una sola pregunta; en Espontáneo y Ayudado puedes poner varias. Un «0» significa «sin pregunta». La tabla «Validación de columnas» muestra qué columna encontró para cada código.",
     "actions": [G("Ir a Awareness", "awareness")]},
    {"id": "awareness-fuente", "title": "¿Awareness usa lo que categoricé?", "pages": ["awareness"],
     "keywords": ["awareness", "categorice", "categorizado", "categorizacion", "fuente de los datos", "texto original", "usa mis correcciones", "etiquetas corregidas", "integrado"],
     "answer": "El Awareness integrado usa tus etiquetas, con las correcciones manuales, en las preguntas TOM y Espontánea que clasificaste como «Marcas». Si una columna no está clasificada, usa el texto original con los alias detectados. El panel «Fuente de los datos» del resultado te dice, columna por columna, cuál de las dos cosas pasó. Las columnas de Ayudado se leen siempre del dato original.",
     "actions": [G("Ir a Awareness", "awareness"), G("Ir a Categorización", "categorize")]},
    {"id": "awareness-base", "title": "Base y filas a evaluar", "pages": ["awareness"],
     "keywords": ["base", "filas a evaluar", "recortada", "cuantas respuestas", "muestra", "segmento", "encuestados", "diferente"],
     "answer": "La base es el número de respuestas evaluadas. En Awareness independiente, «Filas a evaluar» en 0 usa todo el archivo; con un número recorta a las primeras filas y aparece un aviso amarillo. En el integrado, al elegir un segmento la base pasa a ser solo ese grupo. Si dos resultados se ven distintos, compara primero la base.",
     "actions": [G("Ir a Awareness", "awareness")]},
    {"id": "descargas", "title": "Descargar gráficos, tablas y Excel", "pages": ["awareness", "dashboard"],
     "keywords": ["descargar", "exportar", "grafico", "tabla", "imagen", "png", "excel", "reporte", "consolidado"],
     "answer": "En Awareness, cada análisis tiene «Descargar gráfico» y «Descargar tabla», ambos como imagen PNG lista para presentaciones. El Awareness independiente además genera el reporte completo en Excel. Para las categorizaciones usa «Exportar Excel consolidado».",
     "actions": [G("Ir a Awareness", "awareness")]},
    {"id": "cuenta-acceso", "title": "Cuenta, registro y contraseña", "pages": ["settings"],
     "keywords": ["registro", "registrarme", "cuenta", "contrasena", "password", "iniciar sesion", "login", "correo", "dominio"],
     "answer": "El registro exige un correo del dominio autorizado por tu organización y una contraseña de al menos 12 caracteres. Cada estudio pertenece a tu cuenta y nadie más puede verlo. Si ves «Se requiere un token de acceso válido», vuelve a iniciar sesión.",
     "actions": []},
    {"id": "limites-uso", "title": "«Demasiadas solicitudes»", "pages": [],
     "keywords": ["demasiadas solicitudes", "limite", "429", "espera", "bloqueado", "muchos intentos", "tiempo de espera"],
     "answer": "Para proteger la plataforma hay límites de frecuencia, sobre todo en el inicio de sesión y en las acciones que usan IA (clasificar, insights, chat). Espera el tiempo que indica el mensaje y vuelve a intentar. Si te pasa con frecuencia, avisa al administrador del proyecto.",
     "actions": []},
    {"id": "privacidad", "title": "Privacidad y datos personales", "pages": ["settings"],
     "keywords": ["privacidad", "datos personales", "seguridad", "confidencial", "habeas data", "ley 1581", "quien ve", "proveedor ve", "enviar datos", "anonimizar"],
     "answer": "Tus estudios se guardan por cuenta y solo tú puedes verlos. Las funciones de IA envían respuestas de la encuesta al proveedor que elegiste; antes se ocultan correos, teléfonos, enlaces y números de documento. Aun así evita incluir datos sensibles y asegúrate de contar con la autorización de los participantes para tratar sus datos (en Colombia, Ley 1581 de 2012); consulta con el responsable de datos de tu organización. El historial de Insy no se guarda.",
     "actions": [G("Ir a Ajustes", "settings")]},
    {"id": "eliminar-estudio", "title": "Eliminar un estudio", "pages": ["home"],
     "keywords": ["eliminar", "borrar", "quitar estudio", "eliminar estudio", "borrar encuesta"],
     "answer": "En Inicio, junto al estudio, usa la opción de eliminar y confirma. Se borran el estudio, sus respuestas y sus clasificaciones guardadas; esta acción no se puede deshacer.",
     "actions": [G("Ir a Inicio", "home")]},
    {"id": "olvide-contrasena", "title": "Olvidé mi contraseña", "pages": ["settings"],
     "keywords": ["olvide", "olvido", "contrasena", "recuperar", "restablecer", "resetear", "temporal", "cambiar contrasena", "no recuerdo", "acceso"],
     "answer": "La plataforma no envía correos de recuperación. Pide a un administrador que restablezca tu contraseña: te dará una contraseña temporal; entras con ella y la plataforma te pedirá crear una nueva que solo tú conozcas. Si recuerdas la actual y solo quieres cambiarla, hazlo en Ajustes, sección «Cambiar mi contraseña».",
     "actions": [G("Ir a Ajustes", "settings")]},
    {"id": "cuenta-suspendida", "title": "Mi cuenta está inactiva, suspendida o bloqueada", "pages": [],
     "keywords": ["suspendida", "baneada", "baneado", "inactiva", "bloqueada", "bloqueo", "no puedo entrar", "cuenta", "desactivada", "intentos fallidos"],
     "answer": "Inactiva: tu cuenta se desactivó (por ejemplo, porque ya no haces parte de la organización). Suspendida: se retiró el acceso por incumplir las políticas de la plataforma. En ambos casos contacta al administrador. Si el aviso dice que está bloqueada temporalmente, es por varios intentos fallidos: se levanta sola pasados los minutos indicados.",
     "actions": []},
    {"id": "roles-admin", "title": "Roles y panel de administración", "pages": ["admin"],
     "keywords": ["rol", "roles", "administrador", "admin", "super administrador", "panel", "administracion", "permisos", "que puede hacer", "usuario"],
     "answer": "Hay tres roles. Usuario: usa la plataforma. Administrador: inactiva, banea o elimina cuentas de usuarios, restablece contraseñas y edita las políticas de seguridad. Super administrador (uno solo): hace todo lo anterior y además es el único que nombra o quita administradores. Quien se registra empieza como usuario. Nadie puede actuar sobre su propia cuenta ni sobre el super administrador, y un administrador no puede actuar sobre otro administrador.",
     "actions": [G("Ir a Administración", "admin")]},
    {"id": "admin-restablecer", "title": "Restablecer la contraseña de alguien", "pages": ["admin"],
     "keywords": ["restablezco", "restablecer", "contrasena", "temporal", "olvido", "resetear", "banear", "inactivar", "eliminar cuenta", "baneo", "reactivar"],
     "answer": "En Administración → Usuarios pulsa «Restablecer» en la cuenta: el sistema genera una contraseña temporal que verás una sola vez (no se guarda ni se registra). Entrégala por un canal seguro; la persona deberá cambiarla al entrar y sus sesiones abiertas se cierran. Inactivar es para quien ya no hace parte de la organización; Banear es por incumplir políticas y deja el motivo; Eliminar borra la cuenta y todos sus estudios y pide escribir el correo para confirmar.",
     "actions": [G("Ir a Administración", "admin")]},
    {"id": "politicas-seguridad", "title": "Políticas de seguridad configurables", "pages": ["admin"],
     "keywords": ["politicas", "politica", "seguridad", "longitud", "complejidad", "sesion", "intentos", "dominios", "proveedores permitidos", "registro", "configurar"],
     "answer": "En Administración → Políticas de seguridad puedes definir: longitud mínima y complejidad de la contraseña, duración de la sesión, intentos fallidos y minutos de bloqueo, si el registro está abierto, los dominios de correo permitidos, si se ocultan datos personales antes de enviar texto a la IA y qué proveedores de IA se pueden usar. Cada cambio queda en la auditoría.",
     "actions": [G("Ir a Administración", "admin")]},
    {"id": "insy-ia", "title": "¿Insy usa IA?", "pages": [],
     "keywords": ["insy", "asistente", "bot", "ayuda", "usa ia", "consume ia", "consume", "responde"],
     "answer": "Insy responde primero con la guía propia de la plataforma: es instantáneo, gratuito y no envía tus datos a ningún proveedor. Solo si no encuentra respuesta puedes elegir «Preguntar a la IA», que usa tu proveedor y tu clave.",
     "actions": []},
]

PAGE_SUGGESTIONS: Dict[str, List[str]] = {
    "home": ["¿Cómo importo mi encuesta?", "¿Qué son las preguntas abiertas recomendadas?", "¿Cómo elimino un estudio?"],
    "categorize": ["¿Cómo categorizo por temas?", "¿Qué significa «Otros» y «Ninguna»?", "¿Para qué sirven los diccionarios?"],
    "dashboard": ["¿Cómo corrijo etiquetas?", "¿Cómo mido la calidad de la categorización?", "¿Cómo se generan los insights?"],
    "awareness": ["¿Qué diferencia hay entre TOM, espontáneo y ayudado?", "¿Awareness usa lo que categoricé?", "¿Cómo escribo los códigos de pregunta?"],
    "settings": ["¿Dónde guardo mi API key?", "¿Qué proveedor de IA elijo?", "¿Cómo protegen mis datos?"],
    "admin": ["¿Qué puede hacer cada rol?", "¿Cómo restablezco la contraseña de alguien?", "¿Qué políticas de seguridad puedo configurar?"],
}

_STOP = set("""el la los las un una unos unas de del al a en y o u e que como cual cuales cuando donde quien para por con sin sobre
entre se su sus mi mis tu tus es son ser esta este esto estos estas hay puedo puede pueden quiero quisiera necesito hago hacer
hace uso usar usa lo le les me te nos si no mas muy ya tambien pero porque qué cómo cuál dónde cuánto""".split())
_SYNONYMS = {"subo": "subir", "suba": "subir", "carga": "cargar", "cargo": "cargar", "sube": "subir", "guardo": "guardar",
             "borro": "borrar", "elimino": "eliminar", "descargo": "descargar", "bajar": "descargar", "baja": "descargar",
             "contrasenas": "contrasena", "clave": "clave", "llaves": "llave", "graficas": "grafico", "graficos": "grafico",
             "grafica": "grafico", "corrijo": "corregir", "corrige": "corregir", "corrijas": "corregir", "corregimos": "corregir",
             "elijo": "elegir", "escoger": "elegir", "escojo": "elegir", "elegi": "elegir", "sirven": "servir", "sirve": "servir", "metrica": "calidad", "confianza": "calidad", "exactitud": "calidad", "acuerdo": "acuerdo"}


def _norm(text: str) -> str:
    text = unicodedata.normalize("NFKD", str(text).lower()).encode("ascii", "ignore").decode("ascii")
    return re.sub(r"[^a-z0-9/ ]+", " ", text)


def _stem(token: str) -> str:
    if re.fullmatch(r"p\d+(?:/p?\d+)*", token):  # P1, P7, P2_1… son «un código de pregunta»
        return "pcodigo"
    token = _SYNONYMS.get(token, token)
    return token[:6] if len(token) > 6 else token


def _stems(text: str) -> List[str]:
    return [_stem(token) for token in _norm(text).split() if token not in _STOP and len(token) > 1]


def _index() -> List[Dict]:
    docs = []
    for article in ARTICLES:
        kw_stems = set()
        for phrase in article["keywords"]:
            kw_stems.update(_stems(phrase))
        docs.append({
            "article": article, "kw": kw_stems,
            "title": set(_stems(article["title"])), "body": set(_stems(article["answer"])),
        })
    return docs


_DOCS = _index()
_N = len(_DOCS)
_DF: Dict[str, int] = {}
for _doc in _DOCS:
    for _stem_ in _doc["kw"] | _doc["title"] | _doc["body"]:
        _DF[_stem_] = _DF.get(_stem_, 0) + 1


def _idf(stem: str) -> float:
    return math.log(1 + (_N - _DF.get(stem, 0) + 0.5) / (_DF.get(stem, 0) + 0.5))


MIN_CONFIDENCE = 0.40


def search(question: str, page: Optional[str] = None, limit: int = 3) -> List[Dict]:
    """Artículos ordenados por relevancia, con una confianza entre 0 y 1."""
    query = list(dict.fromkeys(_stems(question)))
    if not query:
        return []
    # Las palabras que la guía desconoce (p. ej. «sirven») restan poco: no deben hundir una buena coincidencia
    ceiling = sum(_idf(stem) * 3 * (1.0 if stem in _DF else 0.4) for stem in query)
    results = []
    for doc in _DOCS:
        score = 0.0
        keyword_hits = 0
        for stem in query:
            weight = 3 if stem in doc["kw"] else 2 if stem in doc["title"] else 1 if stem in doc["body"] else 0
            if weight:
                score += _idf(stem) * weight
            if stem in doc["kw"]:
                keyword_hits += 1
        # Con 3 palabras o más exigimos 2 coincidencias de palabra clave: evita respuestas por una sola palabra suelta
        if keyword_hits < (2 if len(query) >= 3 else 1):
            continue
        confidence = score / ceiling
        if page and page in doc["article"].get("pages", []):
            confidence *= 1.12
        results.append({"article": doc["article"], "confidence": min(confidence, 1.0)})
    results.sort(key=lambda item: item["confidence"], reverse=True)
    return results[:limit]


def ask(question: str, page: Optional[str] = None) -> Dict:
    """Respuesta de la guía propia. `confident` indica si conviene mostrarla como respuesta directa."""
    found = search(question, page)
    if not found or found[0]["confidence"] < MIN_CONFIDENCE:
        return {
            "confident": False, "answer": "", "article": None, "confidence": round(found[0]["confidence"], 2) if found else 0.0,
            "actions": [], "related": [{"id": item["article"]["id"], "title": item["article"]["title"]} for item in found[:3]],
        }
    best = found[0]
    related = [
        {"id": item["article"]["id"], "title": item["article"]["title"]}
        for item in found[1:] if item["confidence"] >= best["confidence"] * 0.6
    ]
    return {
        "confident": True, "answer": best["article"]["answer"], "article": best["article"]["id"],
        "title": best["article"]["title"], "confidence": round(best["confidence"], 2),
        "actions": best["article"].get("actions", []), "related": related,
    }


def article_by_id(article_id: str) -> Optional[Dict]:
    return next((article for article in ARTICLES if article["id"] == article_id), None)


def answer_for(article_id: str) -> Optional[Dict]:
    """Respuesta directa de un artículo conocido (sin búsqueda)."""
    article = article_by_id(article_id)
    if article is None:
        return None
    return {
        "confident": True, "answer": article["answer"], "article": article["id"], "title": article["title"],
        "confidence": 1.0, "actions": article.get("actions", []), "related": [],
    }
