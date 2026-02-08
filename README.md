# Teaching System

Sistema de tutoría personal potenciado por LLM que transforma libros (PDF/EPUB) en experiencias de aprendizaje interactivas y personalizadas.

## Descripción

Teaching System es una herramienta de línea de comandos que permite:

- **Importar libros** en formato PDF o EPUB
- **Extraer y estructurar** el contenido automáticamente
- **Generar material de estudio** (apuntes, ejercicios, exámenes)
- **Sesiones de tutoría interactiva** con un tutor virtual potenciado por LLM
- **Seguimiento de progreso** multi-estudiante con persistencia

El sistema utiliza modelos de lenguaje (LLM) para generar explicaciones personalizadas, evaluar respuestas y adaptar el ritmo de enseñanza al estudiante.

## Características Principales

### Importación Inteligente de Libros
- Soporte para PDF y EPUB
- Extracción automática de texto con preservación de estructura
- Detección automática de capítulos y secciones (4 métodos: auto, toc, headings, llm)
- Normalización de texto para mejor procesamiento

### Generación de Material de Estudio
- Apuntes estructurados en español generados por LLM
- Ejercicios variados con diferentes niveles de dificultad
- Exámenes por capítulo con evaluación automática

### Tutoría Interactiva (Teaching-First)
- El tutor explica antes de preguntar
- Verificación de comprensión con feedback inmediato
- Reexplicación adaptativa con analogías cuando no se entiende
- Detección inteligente de "más ejemplos" o "no entiendo"
- Soporte multi-estudiante con progreso independiente
- **4 tutores con personalidades distintas** (Dra. Vega, Profe Nico, Inés, Capitán Ortega)
- **Políticas de enseñanza configurables** por tutor (estricto vs permisivo)

### Web API y Frontend (F9)
- **API REST** con FastAPI para integración con aplicaciones
- **Frontend Next.js** con interfaz de chat moderna
- **Server-Sent Events (SSE)** para streaming de eventos en tiempo real
- **Efecto typewriter** para animación de texto

### Persistencia y Seguimiento
- Estado de sesión guardado automáticamente
- Progreso por libro y capítulo
- Historial de intentos y calificaciones
- Academia virtual con múltiples perfiles de estudiante

## Estado Actual: F9 Completado

| Fase | Descripción | Estado |
|------|-------------|--------|
| F2 | Importación de libros | ✅ Completado |
| F3 | Segmentación en unidades | ✅ Completado |
| F4 | Generación de apuntes | ✅ Completado |
| F5 | Ejercicios y calificación | ✅ Completado |
| F6 | Exámenes por capítulo | ✅ Completado |
| F7 | Orquestación y tutoría | ✅ Completado |
| F8 | Personas, Policies, Events | ✅ Completado |
| F9 | Web API + Frontend | ✅ Completado |
| F10 | Interfaz gráfica avanzada | Planificado |

## Requisitos

### Sistema
- Python 3.11 o superior
- macOS o Linux
- 4GB RAM mínimo (8GB recomendado para LLM local)

### LLM Provider (uno de los siguientes)
- **LM Studio** (recomendado para uso local, gratuito)
- OpenAI API
- Anthropic API

## Instalación

### 1. Clonar el repositorio

```bash
git clone https://github.com/tu-usuario/teaching-system.git
cd teaching-system
```

### 2. Crear entorno virtual

Con conda:
```bash
conda create -n teaching python=3.11
conda activate teaching
```

O con uv (recomendado):
```bash
uv venv
source .venv/bin/activate
```

### 3. Instalar dependencias

```bash
uv pip install -e ".[dev]"
```

O con pip:
```bash
pip install -e ".[dev]"
```

### 4. Configurar variables de entorno

```bash
cp .env.example .env
# Editar .env con tu configuración
```

### 5. Configurar LM Studio (recomendado)

1. Descargar [LM Studio](https://lmstudio.ai/)
2. Cargar un modelo (ej: `neural-chat-7b-v3-2`, `llama-2-7b-chat`)
3. Iniciar el servidor local en puerto 1234

### 6. Verificar instalación

```bash
teach --help
```

## Uso Rápido

### Importar un libro

```bash
teach import-book ~/Books/clean-code.pdf --title "Clean Code" --language en
```

### Preparar el material

```bash
# Extraer texto
teach extract-raw clean-code

# Normalizar
teach normalize clean-code

# Detectar estructura de capítulos
teach outline clean-code

# Segmentar en unidades de estudio
teach plan clean-code

# Generar apuntes para una unidad
teach notes clean-code-ch01-u01
```

### Iniciar sesión de tutoría

```bash
teach tutor
```

El sistema te mostrará la **Academia de Aprendizaje**:
1. Selecciona o crea un perfil de estudiante
2. Elige un libro para estudiar
3. El tutor te guiará a través del contenido

### Comandos durante la tutoría

| Comando | Acción |
|---------|--------|
| `adelante` | Avanzar al siguiente punto |
| `apuntes` | Ver apuntes completos de la unidad |
| `control` | Mini-quiz de 5 preguntas |
| `examen` | Examen del capítulo completo |
| `stop` | Guardar progreso y salir |

### Flags útiles

```bash
# Especificar estudiante directamente
teach tutor --student "Juan"

# Listar estudiantes registrados
teach tutor --list-students

# Ajustar velocidad del texto
teach tutor --pace slow    # Más lento
teach tutor --pace fast    # Más rápido
```

## Estructura del Proyecto

```
Teaching System/
├── src/teaching/           # Código fuente principal
│   ├── cli/                # Comandos de línea (commands.py)
│   ├── config/             # Configuración de personas (F8)
│   │   └── personas.py     # TeachingPolicy, Persona loader
│   ├── core/               # Lógica de negocio
│   │   ├── book_importer.py
│   │   ├── pdf_extractor.py
│   │   ├── epub_extractor.py
│   │   ├── text_normalizer.py
│   │   ├── outline_extractor.py
│   │   ├── unit_planner.py
│   │   ├── notes_generator.py
│   │   ├── exercise_generator.py
│   │   ├── grader.py
│   │   ├── chapter_exam_generator.py
│   │   ├── exam_grader.py
│   │   └── tutor.py            # Orquestación F7 + Events F8
│   ├── web/                # Web API (F9)
│   │   ├── api.py          # FastAPI app
│   │   ├── schemas.py      # Pydantic models
│   │   ├── sessions.py     # SessionManager + SSE
│   │   └── routes/         # Endpoints REST
│   ├── llm/                # Cliente LLM unificado
│   ├── db/                 # Persistencia SQLite
│   └── utils/              # Utilidades
├── web/                    # Frontend Next.js (F9)
│   ├── src/app/            # Pages (Lobby, Session)
│   ├── src/components/     # React components
│   └── src/lib/            # API client, types
├── data/                   # Datos de libros importados
│   ├── books/{book_id}/    # Contenido por libro
│   ├── config/             # Configuración de personas
│   └── state/              # Estado de sesiones
├── prompts/                # Prompts del sistema
├── configs/                # Configuración
├── tests/                  # Suite de tests (968 tests)
│   ├── f2/ ... f9/         # Tests por fase
│   └── conftest.py
└── docs/                   # Documentación técnica
```

## Comandos Disponibles

### Importación (F2)
| Comando | Descripción |
|---------|-------------|
| `teach import-book FILE` | Importar PDF/EPUB |
| `teach extract-raw BOOK_ID` | Extraer texto bruto |
| `teach normalize BOOK_ID` | Normalizar texto |
| `teach outline BOOK_ID` | Detectar capítulos |

### Planificación (F3)
| Comando | Descripción |
|---------|-------------|
| `teach plan BOOK_ID` | Segmentar en unidades |

### Estudio (F4-F5)
| Comando | Descripción |
|---------|-------------|
| `teach notes UNIT_ID` | Generar apuntes |
| `teach exercise UNIT_ID` | Practicar ejercicios |
| `teach quiz UNIT_ID` | Modo quiz interactivo |
| `teach grade UNIT_ID ATTEMPT` | Calificar intento |

### Exámenes (F6)
| Comando | Descripción |
|---------|-------------|
| `teach exam-quiz CHAPTER_ID` | Iniciar examen |
| `teach exam-grade CHAPTER_ID` | Calificar examen |

### Tutoría (F7)
| Comando | Descripción |
|---------|-------------|
| `teach tutor` | Modo tutoría interactivo |
| `teach status` | Ver progreso del estudiante |
| `teach next` | Siguiente acción sugerida |

### Web API (F9)

```bash
# Iniciar servidor API
uv run uvicorn teaching.web.api:app --reload --port 8000

# Documentación interactiva
open http://localhost:8000/docs
```

| Endpoint | Descripción |
|----------|-------------|
| `GET /health` | Health check |
| `GET /api/students` | Listar estudiantes |
| `POST /api/students` | Crear estudiante |
| `GET /api/personas` | Listar tutores |
| `POST /api/sessions` | Iniciar sesión |
| `GET /api/sessions/{id}/events` | SSE de eventos |

### Frontend Web (F9)

```bash
cd web
npm install
npm run dev
# Abrir http://localhost:3000
```

### Administración
| Comando | Descripción |
|---------|-------------|
| `teach list` | Listar libros importados |
| `teach reset` | Reiniciar estado |
| `teach purge BOOK_ID` | Eliminar libro |

## Configuración

### Variables de Entorno (.env)

```bash
# LLM Provider: lmstudio (default), openai, anthropic
LLM_PROVIDER=lmstudio
LM_STUDIO_BASE_URL=http://localhost:1234/v1

# OpenAI (si se usa)
OPENAI_API_KEY=sk-...

# Anthropic (si se usa)
ANTHROPIC_API_KEY=sk-ant-...

# Paths
DATABASE_PATH=db/teaching.db
DATA_DIR=data
```

### Configuración de Modelos (configs/models.yaml)

```yaml
llm:
  provider: lmstudio
  base_url: http://localhost:1234/v1
  model: default
  temperature: 0.7
  max_tokens: 4096
```

## Tests

```bash
# Ejecutar todos los tests
uv run pytest tests/ -v

# Solo una fase específica
uv run pytest tests/f7/ -v

# Con cobertura
uv run pytest --cov=src tests/

# Test rápido
uv run pytest -q
```

**Estado actual: 968 tests pasando**

## Tecnologías

### Backend
- **Python 3.11+** - Lenguaje principal
- **Typer** - Framework CLI
- **Rich** - Output formateado en terminal
- **SQLite** - Base de datos local
- **PyMuPDF** - Extracción de PDF
- **EbookLib** - Parsing de EPUB
- **OpenAI SDK** - Cliente LLM (compatible con LM Studio)
- **Pydantic** - Validación de datos
- **Structlog** - Logging estructurado
- **FastAPI** - Web API (F9)
- **Uvicorn** - Servidor ASGI

### Frontend (F9)
- **Next.js 14** - React framework
- **TypeScript** - Tipado estático
- **Tailwind CSS** - Estilos
- **react-markdown** - Renderizado Markdown

## Documentación Adicional

- [Plan de Implementación](docs/Plan_implementacion.md) - Arquitectura detallada
- [Walkthrough](docs/Walkthrough.md) - Tutorial paso a paso
- [Contratos v1](docs/contracts_v1.md) - Esquemas de datos
- [CLI Spec v1](docs/cli_spec_v1.md) - Especificación de comandos
- [Phase Guardrails](docs/phase_guardrails.md) - Asignación de fases
- [Web API Quickstart](docs/webapi_quickstart.md) - Guía de la API REST
- [Frontend README](web/README_frontend.md) - Guía del frontend Next.js

## Contribuir

1. Fork del repositorio
2. Crear rama feature (`git checkout -b feature/nueva-funcionalidad`)
3. Commit cambios (`git commit -am 'Añadir nueva funcionalidad'`)
4. Push a la rama (`git push origin feature/nueva-funcionalidad`)
5. Crear Pull Request

## Licencia

MIT License

## Autor

Desarrollado con Claude Code.
