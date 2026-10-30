# Insights Studio · React + FastAPI + PostgreSQL

Primera migración local de la Plataforma de Insights. Mantiene en Python la lógica de clasificación, normalización de marcas, Awareness, insights y exportación Excel; React sustituye la interfaz Streamlit y PostgreSQL guarda los estudios y sus resultados.

## Qué incluye esta primera versión

- Importación local de CSV y XLSX, con selección de hoja cuando el libro tiene varias. Límite de 25 MB, 200.000 filas y 500 columnas.
- Estudios y respuestas persistidos en PostgreSQL; los datos permanecen después de cerrar y reiniciar la aplicación.
- Categorización con búsqueda y selección de cualquier encabezado del Excel; los códigos `CE1`, `CE1_1`, `CA1_2`, etc. se tratan como columnas distintas. Las sugerencias son solo una ayuda y no ocultan el resto de columnas.
- Procesamiento secuencial de varias columnas seleccionadas: marcas reutiliza el catálogo permitido; sentimiento usa las etiquetas fijas Positivo, Neutral, Negativo y Mixto/ambivalente; cada resultado se guarda por separado para poder revisarlo pregunta por pregunta.
- Al terminar satisfactoriamente un lote, descarga automáticamente un XLSX consolidado de tres hojas: `Datos`, `Preguntas y categorización` (respuesta y etiquetas juntas por pregunta) y `Diccionario` (categorías, descripciones, términos y alias disponibles). Las respuestas fuente vacías permanecen vacías, no se convierten en NS/NR; se puede volver a descargar tras guardar correcciones.
- Clasificación de temas o motivos con propuesta/edición de categorías y proveedores Gemini, Groq, Cohere, OpenRouter y Anthropic.
- Lista cerrada de marcas: una marca fuera del catálogo queda como **Otra**; “Ninguna” es una respuesta explícita sin marca y **NS/NR** representa falta de información.
- Diccionario opcional por categoría (sinónimos/palabras clave): las coincidencias explícitas se aplican antes del LLM; las respuestas sin coincidencia siguen al modelo.
- API keys por usuario y proveedor: se guardan cifradas, pueden reemplazarse o eliminarse desde Ajustes y el backend las carga automáticamente al clasificar.
- Frecuencias, cruces por segmento, generación de insights con citas de las respuestas y descarga de reporte Excel.
- Revisión de las primeras respuestas en el Dashboard y corrección manual de etiquetas, guardada en PostgreSQL.
- Flujo de categorización por pregunta con tres pasos: configurar, revisar catálogo y clasificar/editar; los catálogos aún no aplicados quedan guardados por estudio y pregunta en `classification_drafts`.
- Navegación de preguntas con estado pendiente/borrador/lista; al completar una pregunta puedes pasar a la siguiente sin perder los resultados anteriores.
- Selector desplegable de proveedor, modelo y clave temporal de sesión en la barra superior; la gestión persistente de claves se encuentra en Ajustes.
- Módulo Awareness autónomo basado en la aplicación Streamlit original: carga directamente CSV/XLSX, ofrece modos Bancos, Conglomerados y Personalizado, configura entidades, alias, normalizaciones, preguntas y demográficos, valida columnas y exporta el reporte Excel sin depender de un estudio ni del flujo de categorización. Corre como servicio separado en el puerto 8501.
- API documentada automáticamente en `http://localhost:8000/docs`.

El acceso requiere login y el registro limita el correo al dominio configurado. Los tokens de acceso JWT expiran según `ACCESS_TOKEN_MINUTES`. La clasificación por diccionario se combina con el clasificador LLM actual. Las llamadas largas de IA se procesan en la petición actual; para despliegue multiusuario conviene añadir worker/cola, auditoría y almacenamiento de archivos más robusto.

## Motores de clasificación y siguiente evolución

La versión incluida usa el cliente LLM ya existente (Gemini/Groq/Cohere/OpenRouter/Anthropic) con catálogo cerrado, y ahora consulta primero las palabras clave/sinónimos del diccionario. **No se instalaron ni se conectaron todavía `cat-survey`, `cat-llm`, BERTopic ni un modelo de embeddings**: son motores distintos y no se intercambian directamente. Para integrar `cat-survey`/`cat-llm` habría que adaptar su llamada y normalizar el formato de salida al esquema de filas/categorías de esta API. BERTopic es más útil para descubrir temas o entrenar con etiquetas humanas; para asignar un catálogo definido a cada respuesta, embeddings + ejemplos etiquetados y un umbral de confianza son un camino separado. Recomiendo conservar LLM + diccionario como ruta principal y añadir embeddings como opción de menor costo, con revisión humana de baja confianza; reservar BERTopic para exploración y propuesta de categorías.

La plataforma tampoco aísla actualmente estudios por usuario: el login protege las rutas, pero los usuarios autenticados comparten los estudios guardados. Para datos sensibles o distintos equipos, falta incorporar ownership/roles y migrar la base antes de producción.

## Opción recomendada: iniciar con Docker Desktop

Requisitos: Windows 10/11, macOS o Linux con **Docker Desktop/Engine y Docker Compose v2**. La primera ejecución descarga imágenes e instala dependencias; requiere conexión a Internet.

1. Descomprime `plataforma-insights-fullstack.zip` en una carpeta, por ejemplo `C:\Proyectos\plataforma-insights-fullstack`.
2. Abre PowerShell o una terminal en esa carpeta y crea el archivo local de variables:

   **PowerShell**
   ```powershell
   Copy-Item .env.example .env
   ```

   **macOS/Linux**
   ```bash
   cp .env.example .env
   ```

   Cambia `POSTGRES_PASSWORD` y reemplaza `JWT_SECRET` por un secreto aleatorio de al menos 32 caracteres. En PowerShell puedes generarlo con:

   ```powershell
   $bytes = New-Object byte[] 32
   $rng = [System.Security.Cryptography.RandomNumberGenerator]::Create()
   $rng.GetBytes($bytes)
   $JWT_SECRET = ([BitConverter]::ToString($bytes)).Replace('-', '').ToLower()
   $JWT_SECRET
   ```

   Copia el resultado en `.env` como el valor de `JWT_SECRET`. **Conserva el mismo secreto**: también deriva la clave de cifrado de las API keys; cambiarlo hace que las claves ya guardadas no se puedan descifrar. El backend lee el `.env` de la raíz también cuando se inicia desde `backend/`. `OMC_EMAIL_DOMAIN=omc.com` permite direcciones terminadas en `@omc.com`; configura solo el dominio, sin `@`, para tu organización. No compartas `.env`.

3. Inicia los servicios:
   ```bash
   docker compose up --build
   ```
   La primera construcción puede tardar varios minutos. Espera hasta que los servicios `api`, `db` y `web` estén listos.

4. Abre:
   - Aplicación: [http://localhost:5173](http://localhost:5173)
   - Documentación interactiva de la API: [http://localhost:8000/docs](http://localhost:8000/docs)
   - Estado de API y conexión a PostgreSQL: [http://localhost:8000/api/health](http://localhost:8000/api/health)

5. Crea una cuenta con tu correo corporativo permitido e inicia sesión. La contraseña debe tener al menos 12 caracteres. Luego, en **Ajustes**, elige proveedor y modelo y guarda la clave de API; se cifra en PostgreSQL y se usa automáticamente. Puedes reemplazarla o eliminarla en esa pantalla. Después importa un CSV/XLSX desde Inicio.

6. Para detener la aplicación, vuelve a la terminal y presiona `Ctrl+C`. Después, opcionalmente ejecuta:
   ```bash
   docker compose down
   ```
   Los estudios se mantienen en el volumen `insights_pgdata` y estarán disponibles al iniciar de nuevo.

   **No ejecutes `docker compose down -v` salvo que quieras borrar todos los estudios y sus datos.**

## Si no tienes Docker: PostgreSQL nativo en Windows

No necesitas Docker para usar esta plataforma. Instala PostgreSQL directamente en Windows y sigue la guía detallada de [inicio local sin Docker](INICIO_LOCAL_WINDOWS_SIN_DOCKER.md). La guía crea la base `insights` y explica cómo iniciar el backend y el frontend en dos terminales de VS Code.

## Alternativa: ejecutar API y React manualmente con PostgreSQL en Docker

Esta opción requiere Docker solo para PostgreSQL, además de Python 3.11+ y Node.js 20+.

1. En la raíz del proyecto, copia `.env.example` a `.env` y ajusta la contraseña, si hace falta.
2. Inicia solo PostgreSQL:
   ```bash
   docker compose up -d db
   ```
3. En una primera terminal, prepara el backend:

   **Windows PowerShell**
   ```powershell
   cd backend
   py -3.11 -m venv .venv
   .\.venv\Scripts\Activate.ps1
   pip install -r requirements.txt
   $env:DATABASE_URL = "postgresql+psycopg://insights:change-this-local@localhost:5433/insights"
   uvicorn app.main:app --reload --port 8000
   ```

   **macOS/Linux**
   ```bash
   cd backend
   python3 -m venv .venv
   source .venv/bin/activate
   pip install -r requirements.txt
   export DATABASE_URL='postgresql+psycopg://insights:change-this-local@localhost:5433/insights'
   uvicorn app.main:app --reload --port 8000
   ```

   Si cambiaste usuario, contraseña, base o puerto en `.env`, ajusta `DATABASE_URL` para que coincida.

4. En una segunda terminal, inicia el frontend:
   ```bash
   cd frontend
   npm install
   npm run dev
   ```
   Vite usa por defecto la API en `http://localhost:8000`. Si la API está en otra dirección, configura `VITE_API_PROXY` antes de ejecutar `npm run dev`.

5. Usa [http://localhost:5173](http://localhost:5173). Para cerrar, detén API y frontend con `Ctrl+C`; PostgreSQL puede seguir activo o apagarse con `docker compose stop db`.

También puedes probar la aplicación con `sample_data/ejemplo_encuesta.csv`.

## Estructura

```text
backend/
  app/                 API REST, modelos PostgreSQL, esquemas y servicios
  core/                Lógica Python reutilizada del proyecto Streamlit
frontend/
  src/App.tsx          Flujos React de estudio, categorización, dashboard y Awareness
  src/styles.css       Sistema visual editable
  vite.config.ts       Servidor local y proxy `/api` a FastAPI
docker-compose.yml     PostgreSQL + API + frontend
.env.example           Variables de desarrollo local (sin secretos reales)
```

## Guardado de claves de IA y SQL

La API crea `user_api_keys` al arrancar si `users` ya existe. Para crearla manualmente, conectado a la base `insights` y después de que `users` exista, ejecuta `backend/migrations/001_user_api_keys.sql`. La tabla almacena el ciphertext (no la clave en claro), usa `(user_id, provider)` como clave primaria y borra las claves al borrar al usuario. No cambies `JWT_SECRET` tras guardar claves.

## Modelo de datos local

- `studies`: metadatos de cada encuesta.
- `respondents`: una fila JSONB por respuesta de encuesta, con el número original de fila.
- `classifications`: categorías, etiquetas, aliases de marca, configuración e insights por pregunta.

La API crea las tablas cuando inicia. En Docker, PostgreSQL vive en un volumen; en el modo Windows sin Docker, usa el servicio PostgreSQL instalado localmente. No se suben los archivos del estudio a un servicio de Manus.

## Pruebas de lógica

Con el entorno Python activado e instalado (`pip install -r backend/requirements.txt`), desde `backend/` ejecuta:

```bash
python -m unittest discover -s tests -v
```

Las pruebas de marcas, diccionario, sentimiento e importación no requieren credenciales de IA ni conexión a PostgreSQL.

## Notas de seguridad

La configuración está pensada para desarrollo local. **No publiques estos puertos ni despliegues la aplicación directamente en Internet.** Todas las rutas `/api` excepto salud, registro e inicio de sesión requieren `Authorization: Bearer <JWT>`. El token se guarda en `sessionStorage`, se expira y el password se almacena con hash Argon2. Antes de un despliegue real todavía se recomienda HTTPS, limitación de intentos de login, autorización por usuario/estudio, registros de auditoría, backups y endurecimiento del CORS. Una API key escrita en Ajustes no persiste, pero sí se envía desde el navegador local a la API local y luego al proveedor seleccionado.
