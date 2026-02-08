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
├── __init__.py      # Exports create_app
├── api.py           # FastAPI app factory
├── schemas.py       # Pydantic models
├── sessions.py      # SessionManager
└── routes/
    ├── __init__.py
    ├── health.py    # GET /health
    ├── students.py  # /api/students
    ├── personas.py  # /api/personas
    └── sessions.py  # /api/sessions
```
