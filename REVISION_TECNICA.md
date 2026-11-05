# Revisión técnica de Insights Studio

## Alcance

Revisión del código fuente incluido en el ZIP: React/Vite, API FastAPI, lógica de categorización y Awareness, configuración Docker, documentación y pruebas. Esta revisión no inspeccionó una instancia desplegada, una base de datos real, cuentas de proveedores de IA ni el historial completo de Git.

Se escanearon los objetos Git incluidos buscando patrones comunes de credenciales de alta confianza; no hubo coincidencias. Esto no sustituye una revisión de secretos en el proveedor donde se desplegó la aplicación.

## Resultado funcional

La base ya contiene un flujo completo de importación, categorización, revisión, Dashboard y dos modos de Awareness. Se añadieron estos cambios:

- **Asistente de la plataforma:** botón flotante disponible en las pantallas autenticadas. Explica el uso de la plataforma con el modelo/proveedor seleccionado; algunas preguntas frecuentes (por ejemplo, dónde guardar o cambiar una API key) tienen respuesta local aun sin clave. El chat no persiste su historial.
- **Descargas de Awareness:** gráfico y tabla como imagen PNG, disponibles para cada perfil tanto en el módulo independiente como en el integrado. El reporte Excel existente se conserva.
- **Documentación y pruebas:** se describió el comportamiento agregado y se añadieron pruebas para el asistente.
- **Aislamiento de estudios:** cada estudio nuevo se crea con `owner_id`; las consultas de estudios y las rutas de clasificaciones filtran por ese dueño y responden 404 cuando otra cuenta intenta acceder. No hace falta una tabla nueva: la migración agrega `studies.owner_id` con una clave foránea a `users.id`.

## Hallazgos que conviene resolver

### Requisito crítico de migración antes de desplegar esta versión

1. **La base Neon debe migrarse antes de desplegar este código.** El ZIP original compartía los estudios entre usuarios. El parche ya filtra las rutas por dueño, pero las filas preexistentes no indican quién las creó. Ejecuta `backend/migrations/002_study_owner.sql`, asigna cada estudio histórico a una cuenta confirmada y luego ejecuta `003_enforce_study_owner.sql`. Hasta asignarlos, esos estudios quedan ocultos a todas las cuentas; no se asignan automáticamente.
2. **La configuración de despliegue es para desarrollo/local.** `docker-compose.yml` publica PostgreSQL y la API en puertos del host, y la imagen del backend inicia Uvicorn con `--reload`. No exponer esos puertos a Internet. El README también advierte que la aplicación no está endurecida para producción.

### Prioridad alta antes de publicar

3. **El rewrite de Vercel apunta a un backend fijo.** `frontend/vercel.json` dirige `/api/*` a `categorizaromc.onrender.com`; hay que confirmar que esa siga siendo la API correcta para el despliegue que se publique.
4. **Faltan controles de operación para cargas de producción.** Las llamadas a IA son síncronas, no hay cola de trabajos, y el código no muestra límite de intentos de inicio de sesión ni registro de auditoría. Para encuestas grandes o varios usuarios, conviene añadir cola, límites, registros y copias de seguridad.
5. **El servicio Streamlit continúa expuesto en Compose.** El frontend React ya usa las rutas `/api/awareness-flex`; el servicio separado `awareness` de puerto 8501 parece ser una versión heredada. Confirmar si se necesita y retirarlo o protegerlo si no forma parte del uso actual.

### Prioridad media

6. **La API key guardada depende de que `JWT_SECRET` permanezca estable.** El backend cifra las claves y el README explica que rotar este secreto impide descifrarlas. Hay que conservarlo de forma segura y documentar recuperación/rotación.
7. **La guía local de Windows enlazada no está en el ZIP.** `README.md` enlaza `INICIO_LOCAL_WINDOWS_SIN_DOCKER.md`, pero el archivo no aparece en el contenido recibido.
8. **El ZIP original incluye material generado innecesario.** Contiene el `.venv` de Python, el historial `.git` y `frontend/dist`; inflan el archivo y pueden confundir al instalar. El ZIP de entrega omite esos directorios y conserva el código, los datos de ejemplo y los archivos de dependencias.

## Verificación realizada

- Sintaxis Python: parseo correcto de los archivos del backend.
- Pruebas unitarias del asistente: 4 aprobadas.
- La suite Python completa no pudo ejecutarse en este entorno porque faltan las dependencias del proyecto (entre ellas pandas, FastAPI y SQLAlchemy).
- Las nuevas pruebas de autorización por dueño se agregaron, pero no pudieron ejecutarse aquí por esas dependencias ausentes.
- No se pudo correr el build de React/TypeScript: el ZIP no incluye `node_modules` y el entorno no tiene `tsc`. Debe ejecutarse `npm ci` y `npm run build` en un entorno con Node; luego, instalar `backend/requirements.txt` y ejecutar `python -m unittest discover -s tests -v` desde `backend/`.
