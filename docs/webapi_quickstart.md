# Web API Quickstart (F9)

API REST para el Teaching System usando FastAPI.

## Inicio rápido

```bash
# Iniciar servidor de desarrollo
uv run uvicorn teaching.web.api:app --reload --port 8000
```

Abrir http://localhost:8000/docs para ver la documentación interactiva (Swagger UI).

## Endpoints

### Health

```
GET /health
```

Respuesta:
```json
{
  "status": "ok",
  "version": "0.1.0",
  "timestamp": "2024-01-15T10:30:00Z"
}
```

### Students

```
GET  /api/students          # Listar estudiantes
GET  /api/students/{id}     # Obtener estudiante
POST /api/students          # Crear estudiante
DELETE /api/students/{id}   # Eliminar estudiante
```

Crear estudiante:
```bash
curl -X POST http://localhost:8000/api/students \
  -H "Content-Type: application/json" \
  -d '{"name": "Ana", "surname": "Garcia", "email": "ana@example.com"}'
```

### Personas

```
GET /api/personas          # Listar personas disponibles
GET /api/personas/{id}     # Obtener persona por ID
```

Ejemplo:
```bash
curl http://localhost:8000/api/personas/dra_vega
```

### Books (F9.1)

```
GET /api/books             # Listar libros disponibles
GET /api/books/{id}        # Obtener detalles de un libro
```

Listar libros:
```bash
curl http://localhost:8000/api/books
```

Respuesta:
```json
{
  "books": [
    {
      "id": "llm-intro",
      "title": "Introduction to LLMs",
      "authors": ["AI Research Team"],
      "total_chapters": 5,
      "has_outline": true,
      "has_units": true
    }
  ],
  "count": 1
}
```

Obtener detalle con capítulos:
```bash
curl http://localhost:8000/api/books/llm-intro
```

### Sessions

```
POST   /api/sessions              # Iniciar sesion de enseñanza
GET    /api/sessions/{id}         # Obtener estado de sesion
DELETE /api/sessions/{id}         # Terminar sesion
POST   /api/sessions/{id}/input   # Enviar input del usuario
GET    /api/sessions/{id}/events  # Stream de eventos (SSE)
```

Iniciar sesion:
```bash
curl -X POST http://localhost:8000/api/sessions \
  -H "Content-Type: application/json" \
  -d '{"student_id": "stu01", "book_id": "llm-intro", "chapter_number": 1}'
```

Enviar input:
```bash
curl -X POST http://localhost:8000/api/sessions/{session_id}/input \
  -H "Content-Type: application/json" \
  -d '{"text": "si, entiendo"}'
```

## Server-Sent Events (SSE)

Para recibir eventos en tiempo real, conectarse al endpoint SSE:

```javascript
const eventSource = new EventSource('/api/sessions/{session_id}/events');

eventSource.addEventListener('tutor_event', (event) => {
  const data = JSON.parse(event.data);
  console.log('Event:', data.event_type, data.markdown);
});

eventSource.addEventListener('keepalive', () => {
  console.log('Connection alive');
});

eventSource.addEventListener('close', () => {
  eventSource.close();
});
```

Tipos de eventos:
- `tutor_event`: Evento del tutor (explicacion, pregunta, feedback)
- `keepalive`: Ping para mantener conexion (cada 30s)
- `close`: La sesion ha terminado
- `error`: Error en la sesion

## Estructura del TutorEvent

```json
{
  "event_id": "evt_000001",
  "event_type": "POINT_EXPLANATION",
  "turn_id": 1,
  "seq": 2,
  "title": "Punto 1: Tokenizacion",
  "markdown": "La tokenizacion es el proceso de...",
  "data": {}
}
```

Event types:
- `UNIT_OPENING`: Apertura de unidad
- `POINT_OPENING`: Titulo de nuevo punto
- `POINT_EXPLANATION`: Explicacion del punto
- `ASK_CHECK`: Pregunta de verificacion
- `FEEDBACK`: Feedback a respuesta del estudiante
- `ASK_CONFIRM_ADVANCE`: Pregunta para avanzar
- `UNIT_NOTES`: Apuntes completos
- `ASK_UNIT_NEXT`: Pregunta siguiente unidad

## Desarrollo

### dev.sh - Script de desarrollo unificado

El proyecto incluye un script `dev.sh` para manejar backend y frontend:

```bash
# Arrancar todo
./dev.sh start

# Parar todo
./dev.sh stop

# Reiniciar
./dev.sh restart

# Ver estado
./dev.sh status

# Ver logs (tail -f)
./dev.sh logs
```

**Notas:**
- PIDs en `.pids/backend.pid` y `.pids/frontend.pid`
- Logs en `.logs/backend.log` y `.logs/frontend.log`
- Detecta conflictos de puertos y procesos duplicados

### Sesiones efímeras

Las sesiones se almacenan **en memoria** y se pierden al reiniciar el servidor.
La respuesta de sesión incluye `"ephemeral": true` para indicar esto.

Si un usuario recarga una página de sesión tras reiniciar el servidor:
- El frontend detecta el 404
- Muestra un mensaje explicativo
- Redirige automáticamente al lobby

### Debug de libros

Para diagnosticar problemas con la lista de libros:

```bash
curl http://localhost:8000/api/books/debug
```

Respuesta:
```json
{
  "source": "data/books/ directory scan",
  "data_dir": "/path/to/data",
  "data_dir_exists": true,
  "books_dir_exists": true,
  "book_dirs_found": 6,
  "books_with_metadata": 6,
  "book_ids": ["book1", "book2", ...],
  "cwd": "/path/to/project"
}
```

### Tests

```bash
# Tests F9 solamente
uv run pytest tests/f9/ -v

# Suite completa
uv run pytest -q
```

### Estructura del paquete

```
src/teaching/web/
├── __init__.py       # Exports create_app
├── api.py            # FastAPI app factory
├── schemas.py        # Pydantic models
├── sessions.py       # SessionManager
├── tutor_engine.py   # TutorEngine (F9.1) - orquesta lógica de enseñanza
└── routes/
    ├── __init__.py
    ├── health.py     # GET /health
    ├── students.py   # /api/students
    ├── personas.py   # /api/personas
    ├── sessions.py   # /api/sessions
    └── books.py      # /api/books (F9.1)
```

## TutorEngine (F9.1)

El TutorEngine es el componente que orquesta la lógica de enseñanza para sesiones web.
Reutiliza las funciones del core (`explain_point`, `check_comprehension`, etc.) y mantiene
el estado de cada sesión.

Estados de enseñanza (WebTeachingState):
- `UNIT_OPENING`: Apertura de unidad
- `WAIT_UNIT_START`: Esperando que el estudiante inicie
- `EXPLAINING`: Explicando un punto
- `WAITING_INPUT`: Esperando respuesta del estudiante
- `CHECKING`: Verificando comprensión
- `AWAITING_RETRY`: Esperando reintento tras respuesta incorrecta
- `REMEDIATION`: Re-explicando con analogía
- `CONFIRM_ADVANCE`: Confirmando avance al siguiente punto
- `UNIT_COMPLETE`: Unidad completada
