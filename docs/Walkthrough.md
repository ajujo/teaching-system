# Walkthrough - Guía Completa de Teaching System

Esta guía te llevará paso a paso desde la instalación hasta una sesión completa de tutoría.

## Tabla de Contenidos

1. [Instalación](#1-instalación)
2. [Configuración de LM Studio](#2-configuración-de-lm-studio)
3. [Tu Primer Libro](#3-tu-primer-libro)
4. [Generación de Material](#4-generación-de-material)
5. [Sesión de Tutoría](#5-sesión-de-tutoría)
6. [Ejercicios y Exámenes](#6-ejercicios-y-exámenes)
7. [Multi-Estudiante](#7-multi-estudiante)
8. [Comandos de Referencia](#8-comandos-de-referencia)
9. [Solución de Problemas](#9-solución-de-problemas)

---

## 1. Instalación

### Requisitos Previos

- Python 3.11 o superior
- macOS o Linux
- LM Studio (recomendado) o cuenta OpenAI/Anthropic
- Un libro en PDF o EPUB para probar

### Paso 1: Clonar el repositorio

```bash
git clone https://github.com/tu-usuario/teaching-system.git
cd teaching-system
```

### Paso 2: Crear entorno virtual

**Opción A: Con uv (recomendado)**
```bash
# Instalar uv si no lo tienes
curl -LsSf https://astral.sh/uv/install.sh | sh

# Crear entorno y activar
uv venv
source .venv/bin/activate
```

**Opción B: Con conda**
```bash
conda create -n teaching python=3.11
conda activate teaching
```

### Paso 3: Instalar dependencias

```bash
# Con uv
uv pip install -e ".[dev]"

# O con pip
pip install -e ".[dev]"
```

### Paso 4: Verificar instalación

```bash
teach --help
```

Deberías ver la lista de comandos disponibles:

```
Usage: teach [OPTIONS] COMMAND [ARGS]...

  Personal LLM-powered teaching system for book-based learning.

Commands:
  import-book    Import a PDF or EPUB book
  extract-raw    Extract raw text from book
  normalize      Normalize extracted text
  outline        Extract chapter structure
  plan           Generate learning units
  notes          Generate study notes
  tutor          Start interactive tutoring session
  ...
```

---

## 2. Configuración de LM Studio

LM Studio es la opción recomendada para usar modelos LLM localmente sin costo.

### Paso 1: Descargar LM Studio

1. Ve a [lmstudio.ai](https://lmstudio.ai/)
2. Descarga la versión para tu sistema operativo
3. Instala y abre la aplicación

### Paso 2: Descargar un modelo

1. En LM Studio, ve a la pestaña "Search"
2. Busca un modelo recomendado:
   - `neural-chat-7b-v3-2` (ligero, bueno para tutoring)
   - `llama-2-7b-chat` (más capaz)
   - `mistral-7b-instruct` (buen balance)
3. Haz clic en "Download"

### Paso 3: Iniciar el servidor

1. Ve a la pestaña "Local Server"
2. Selecciona el modelo descargado
3. Haz clic en "Start Server"
4. Verifica que aparezca: `Server running on port 1234`

### Paso 4: Configurar Teaching System

```bash
# Copiar plantilla de configuración
cp .env.example .env

# Editar (opcional, los valores por defecto funcionan con LM Studio)
nano .env
```

Contenido de `.env`:
```bash
LLM_PROVIDER=lmstudio
LM_STUDIO_BASE_URL=http://localhost:1234/v1
```

### Verificar conexión

```bash
curl http://localhost:1234/v1/models
```

Deberías ver el modelo cargado.

---

## 3. Tu Primer Libro

### Importar un libro PDF

```bash
teach import-book ~/Downloads/mi-libro.pdf \
  --title "Mi Libro de Aprendizaje" \
  --author "Autor del Libro" \
  --language es
```

Salida esperada:
```
✓ Libro importado exitosamente
  ID: mi-libro-de-aprendizaje
  Ubicación: data/books/mi-libro-de-aprendizaje/
```

### Verificar importación

```bash
teach list
```

```
┌────────────────────────────┬────────────────────┬──────────┐
│ Book ID                    │ Title              │ Status   │
├────────────────────────────┼────────────────────┼──────────┤
│ mi-libro-de-aprendizaje    │ Mi Libro de...     │ imported │
└────────────────────────────┴────────────────────┴──────────┘
```

### Extraer y normalizar texto

```bash
# Extraer texto bruto del PDF
teach extract-raw mi-libro

# Normalizar el texto
teach normalize mi-libro
```

### Detectar estructura de capítulos

```bash
# Detección automática
teach outline mi-libro
```

Si la detección automática no es perfecta, puedes usar el modo review:

```bash
# Generar YAML para edición manual
teach outline mi-libro --review

# Editar el archivo generado
nano data/books/mi-libro/outline/outline_draft.yaml

# Aplicar cambios
teach outline mi-libro --validate
```

### Crear unidades de estudio

```bash
teach plan mi-libro
```

Esto crea unidades de 20-35 minutos basadas en los capítulos.

---

## 4. Generación de Material

### Generar apuntes para una unidad

```bash
# Ver unidades disponibles
cat data/books/mi-libro/artifacts/units/units.json | jq '.units[].unit_id'

# Generar apuntes para la primera unidad
teach notes mi-libro-ch01-u01
```

El sistema usará LLM para generar apuntes estructurados en español.

### Ver los apuntes generados

```bash
cat data/books/mi-libro/artifacts/notes/mi-libro-ch01-u01.md
```

Estructura típica de apuntes:
```markdown
# Tema del Capítulo

## Resumen
Breve resumen del contenido...

## Conceptos Clave
- Concepto 1: Explicación
- Concepto 2: Explicación

## Explicación Paso a Paso
### 1. Primer Punto
Contenido detallado...

### 2. Segundo Punto
Contenido detallado...

## Ejemplos Prácticos
...
```

---

## 5. Sesión de Tutoría

### Iniciar el tutor

```bash
teach tutor
```

### Primera vez: Academia de Aprendizaje

```
🏛️ Academia de Aprendizaje

  0. ➕ Nuevo estudiante
  D. 🗑️ Eliminar estudiante
  S. Salir

Selecciona una opción: 0

Nombre del nuevo estudiante: Juan

✓ Estudiante 'Juan' creado exitosamente
```

### Seleccionar libro

```
¿Qué quieres estudiar hoy, Juan?

  0. 📕 Añadir nuevo libro
  1. Mi Libro de Aprendizaje

Elige libro (0-1): 1

Libro seleccionado: Mi Libro de Aprendizaje
```

### Flujo de enseñanza

El tutor sigue un flujo "teaching-first":

```
╭──────────────────────────────────────────────────────────────────────────────╮
│ Capítulo 1: Introducción                                                     │
╰──────────────────────────────────────────────────────────────────────────────╯

━━━ Unidad 1 ━━━

En esta unidad veremos:
  1. Conceptos básicos
  2. Fundamentos teóricos
  3. Aplicaciones prácticas

── Punto 1: Conceptos básicos ──

[El tutor explica el concepto...]

¿Qué entiendes por este concepto en tus propias palabras?

Juan: Es cuando...
```

### Comandos durante la tutoría

| Escribes | Acción |
|----------|--------|
| Tu respuesta | El tutor evalúa si entendiste |
| `adelante` | Salta al siguiente punto |
| `apuntes` | Muestra los apuntes completos |
| `control` | Mini-quiz de 5 preguntas |
| `examen` | Examen del capítulo |
| `stop` | Guarda y sale |

### Si no entiendes

```
Juan: No estoy seguro, ¿puedes darme más ejemplos?

[El tutor detecta la solicitud]

Claro, aquí tienes más ejemplos...

[Genera ejemplos adicionales sin avanzar]

¿Ahora te queda más claro?
```

### Salir y guardar

```
Juan: stop

✓ Sesión cerrada. Progreso guardado.
```

### Continuar después

```bash
teach tutor --student Juan
```

El tutor recordará dónde te quedaste.

---

## 6. Ejercicios y Exámenes

### Ejercicios por unidad

```bash
# Iniciar ejercicios
teach exercise mi-libro-ch01-u01
```

```
Ejercicio 1 de 5:

¿Cuál es la diferencia entre X e Y?

Tu respuesta: [escribes tu respuesta]

Enviando respuesta...
✓ Respuesta guardada (attempt_001)

Calificando...

Score: 85/100
Feedback: Buena explicación. Podrías mencionar también...
```

### Modo quiz (más rápido)

```bash
teach quiz mi-libro-ch01-u01
```

### Examen de capítulo

```bash
# Iniciar examen
teach exam-quiz mi-libro-ch01

# Después de responder todo
teach exam-grade mi-libro-ch01
```

```
═══════════════════════════════════════
         RESULTADOS DEL EXAMEN
═══════════════════════════════════════

Score Final: 78%

Pregunta 1: ✓ Correcto (10/10)
Pregunta 2: ✓ Correcto (10/10)
Pregunta 3: ✗ Incorrecto (5/10)
...

Temas dominados:
  ✓ Conceptos básicos
  ✓ Fundamentos

Temas a repasar:
  ✗ Aplicaciones avanzadas
```

---

## 7. Multi-Estudiante

### Crear múltiples estudiantes

```bash
teach tutor

# En el menú de Academia:
0. ➕ Nuevo estudiante

# Crear "María"
# Crear "Pedro"
```

### Cambiar entre estudiantes

```bash
# Usar flag --student
teach tutor --student María

# O desde el menú de Academia
teach tutor
# Seleccionar el número del estudiante
```

### Ver estudiantes registrados

```bash
teach tutor --list-students
```

```
Estudiantes registrados:
  1. Juan (stu01) - Último acceso: 2026-02-07
  2. María (stu02) - Último acceso: 2026-02-06
  3. Pedro (stu03) - Último acceso: 2026-02-05
```

### Eliminar estudiante

```bash
teach tutor

# En el menú:
D. 🗑️ Eliminar estudiante

# Confirmar escribiendo el nombre exacto
```

### Progreso independiente

Cada estudiante tiene su propio progreso:
- Capítulos completados
- Intentos de examen
- Libro activo

---

## 8. Comandos de Referencia

### Importación y Preparación

```bash
# Importar libro
teach import-book ARCHIVO [--title TITULO] [--author AUTOR] [--language IDIOMA]

# Extraer texto
teach extract-raw BOOK_ID

# Normalizar
teach normalize BOOK_ID [--force]

# Detectar capítulos
teach outline BOOK_ID [--method auto|toc|headings|llm] [--review] [--validate]

# Crear unidades
teach plan BOOK_ID [--force]
```

### Generación de Material

```bash
# Generar apuntes
teach notes UNIT_ID [--provider PROV] [--model MODEL]
```

### Estudio y Práctica

```bash
# Ejercicios
teach exercise UNIT_ID
teach quiz UNIT_ID

# Exámenes
teach exam-quiz CHAPTER_ID
teach exam-grade CHAPTER_ID
```

### Tutoría

```bash
# Iniciar tutoría
teach tutor [--student NOMBRE] [--pace slow|normal|fast]

# Ver progreso
teach status

# Siguiente acción sugerida
teach next

# Listar estudiantes
teach tutor --list-students
```

### Administración

```bash
# Listar libros
teach list [--format json|table]

# Eliminar libro
teach purge BOOK_ID [--force]

# Reiniciar estado
teach reset [--hard]
```

---

## 9. Solución de Problemas

### Error: "LM Studio connection refused"

```bash
# Verificar que LM Studio está corriendo
curl http://localhost:1234/v1/models

# Si no responde:
# 1. Abrir LM Studio
# 2. Cargar un modelo
# 3. Iniciar servidor (Local Server → Start)
```

### Error: "Book not found"

```bash
# Ver libros disponibles
teach list

# Usar prefijo (no necesitas ID completo)
teach tutor mi-libro  # Encuentra "mi-libro-de-aprendizaje"
```

### Error: "outline.json not found"

```bash
# Ejecutar pipeline completo
teach extract-raw BOOK_ID
teach normalize BOOK_ID
teach outline BOOK_ID
teach plan BOOK_ID
```

### Error: "notes not generated"

```bash
# Generar notas primero
teach notes UNIT_ID

# Verificar que existen
ls data/books/BOOK_ID/artifacts/notes/
```

### El tutor no responde / tarda mucho

1. Verificar LM Studio tiene modelo cargado
2. Modelos más pequeños son más rápidos (7B vs 13B)
3. Aumentar timeout en configs/models.yaml

### Perdí mi progreso

El progreso se guarda en `data/state/students_v1.json`. Si existe backup:

```bash
# Restaurar desde backup
cp data/state/students_v1.json.bak data/state/students_v1.json
```

### Quiero empezar de cero

```bash
# Solo sesión (mantiene libros)
teach reset

# Todo (borra libros y BD)
teach reset --hard
```

---

## Ejemplo Completo: De PDF a Tutoría

```bash
# 1. Importar
teach import-book ~/Books/python-crash-course.pdf \
  --title "Python Crash Course" \
  --language en

# 2. Extraer y normalizar
teach extract-raw python
teach normalize python

# 3. Detectar estructura
teach outline python

# 4. Crear unidades
teach plan python

# 5. Generar apuntes del primer capítulo
teach notes python-ch01-u01

# 6. Iniciar tutoría
teach tutor

# Crear estudiante "Ana"
# Seleccionar "Python Crash Course"
# ¡A estudiar!
```

---

## Tips para Mejor Experiencia

1. **Usa modelos de 7B** para respuestas más rápidas
2. **Revisa el outline** manualmente para mejor estructura
3. **Estudia por unidades** de 20-30 minutos
4. **Usa "más ejemplos"** cuando no entiendas
5. **Haz los quizzes** para reforzar aprendizaje
6. **Guarda progreso** con `stop` antes de cerrar

---

¡Feliz aprendizaje! 📚
