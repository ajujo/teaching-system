# Riesgos de Implementación y Mitigaciones

> **Contexto:** Riesgos específicos de la fase de implementación (no de diseño)  
> **Fecha:** 2026-01-28

---

## Matriz de Riesgos

| ID | Riesgo | Probabilidad | Impacto | Prioridad |
|----|--------|--------------|---------|-----------|
| R1 | PDFs escaneados sin OCR | Alta | Alto | 🔴 Crítico |
| R2 | EPUBs mal formados | Media | Medio | 🟡 Alto |
| R3 | Límite de contexto LLM | Alta | Alto | 🔴 Crítico |
| R4 | Latencia de LM Studio | Media | Medio | 🟡 Alto |
| R5 | Detección de outline incorrecta | Alta | Alto | 🔴 Crítico |
| R6 | Inconsistencia de IDs entre JSON y SQLite | Baja | Alto | 🟡 Alto |
| R7 | Normalización de texto elimina contenido importante | Media | Alto | 🟡 Alto |
| R8 | Dependencias incompatibles (pymupdf/ebooklib) | Baja | Medio | 🟢 Medio |
| R9 | Estado corrupto tras crash | Media | Alto | 🟡 Alto |
| R10 | Grading inconsistente del LLM | Alta | Medio | 🟡 Alto |

---

## Detalle de Riesgos y Mitigaciones

### R1: PDFs Escaneados sin OCR 🔴

**Descripción:** Usuario importa PDF que es imagen escaneada sin capa de texto.

**Detección:**

- `pdf_extractor` detecta <100 caracteres extraídos en documento de múltiples páginas

**Mitigación:**

```python
# En pdf_extractor.py
def _validate_extraction(pages: list[str], total_pages: int) -> ValidationResult:
    total_chars = sum(len(p) for p in pages)
    chars_per_page = total_chars / total_pages if total_pages > 0 else 0
    
    if chars_per_page < 100:
        return ValidationResult(
            valid=False,
            error="PDF parece ser imagen escaneada sin texto. Sugerencia: usa OCR primero.",
            suggestion="Prueba con ocrmypdf: ocrmypdf input.pdf output.pdf"
        )
```

**Alternativa futura:** Integrar OCR opcional con `pytesseract` (F2.x)

---

### R2: EPUBs Mal Formados 🟡

**Descripción:** EPUB tiene estructura no estándar o HTML corrupto.

**Detección:**

- Excepciones de `ebooklib` al parsear
- HTML sin texto después de limpieza

**Mitigación:**

```python
# En epub_extractor.py
def extract_epub(file_path: Path, output_dir: Path) -> ExtractionResult:
    try:
        book = epub.read_epub(str(file_path))
    except Exception as e:
        return ExtractionResult(
            success=False,
            error=f"EPUB corrupto o no estándar: {e}",
            suggestion="Intenta convertir con Calibre: ebook-convert input.epub output.epub"
        )
    
    # Fallback: si no hay items de tipo documento
    documents = list(book.get_items_of_type(ebooklib.ITEM_DOCUMENT))
    if not documents:
        # Intentar leer todos los items
        documents = [i for i in book.get_items() if i.get_content()]
```

---

### R3: Límite de Contexto LLM 🔴

**Descripción:** Contenido de unidad/capítulo excede ventana de contexto del modelo.

**Detección:**

- Calcular tokens antes de enviar (aproximación: chars/4)
- Modelo: típicamente 8K-32K tokens

**Mitigación (Estrategia de Chunking):**

```python
# En llm_client.py
MAX_CONTEXT_TOKENS = 8000  # Configurable según modelo
CHARS_PER_TOKEN = 4  # Aproximación

def prepare_content(content: str, max_tokens: int = MAX_CONTEXT_TOKENS) -> list[str]:
    """Divide contenido en chunks que quepan en contexto."""
    max_chars = max_tokens * CHARS_PER_TOKEN
    
    if len(content) <= max_chars:
        return [content]
    
    # Dividir por párrafos respetando límite
    paragraphs = content.split('\n\n')
    chunks = []
    current_chunk = ""
    
    for para in paragraphs:
        if len(current_chunk) + len(para) > max_chars:
            if current_chunk:
                chunks.append(current_chunk)
            current_chunk = para
        else:
            current_chunk += "\n\n" + para if current_chunk else para
    
    if current_chunk:
        chunks.append(current_chunk)
    
    return chunks

def generate_with_chunks(prompt_template: str, content: str) -> str:
    """Genera respuesta procesando chunks si es necesario."""
    chunks = prepare_content(content)
    
    if len(chunks) == 1:
        return call_llm(prompt_template.format(content=chunks[0]))
    
    # Para múltiples chunks: generar resúmenes intermedios
    summaries = []
    for i, chunk in enumerate(chunks):
        summary_prompt = f"Resume los puntos clave de esta parte ({i+1}/{len(chunks)}):\n{chunk}"
        summaries.append(call_llm(summary_prompt))
    
    # Generar respuesta final con resúmenes
    combined = "\n\n---\n\n".join(summaries)
    return call_llm(prompt_template.format(content=combined))
```

---

### R4: Latencia de LM Studio 🟡

**Descripción:** Respuestas lentas afectan UX, especialmente en modo interactivo.

**Detección:**

- Timeouts >30s
- Usuario experimenta esperas largas

**Mitigación:**

```python
# En llm_client.py
import asyncio
from functools import lru_cache

# 1. Timeouts configurables
LLM_TIMEOUT_SECONDS = 60
LLM_TIMEOUT_INTERACTIVE = 30

# 2. Streaming para feedback inmediato
async def call_llm_streaming(prompt: str, callback: Callable[[str], None]):
    """Llama al LLM y hace streaming de tokens."""
    async with aiohttp.ClientSession() as session:
        async with session.post(
            f"{LLM_BASE_URL}/v1/chat/completions",
            json={"messages": [{"role": "user", "content": prompt}], "stream": True}
        ) as response:
            async for line in response.content:
                if line.startswith(b"data: "):
                    data = json.loads(line[6:])
                    if content := data.get("choices", [{}])[0].get("delta", {}).get("content"):
                        callback(content)

# 3. Cache de respuestas similares
@lru_cache(maxsize=100)
def get_cached_response(prompt_hash: str) -> str | None:
    """Cache en memoria para prompts idénticos."""
    pass

# 4. Indicador de progreso
def show_thinking_indicator():
    """Muestra indicador mientras el LLM procesa."""
    with console.status("[bold green]El profesor está pensando..."):
        pass
```

---

### R5: Detección de Outline Incorrecta 🔴

**Descripción:** El sistema detecta capítulos incorrectamente, afectando toda la estructura.

**Mitigación multi-capa:**

```python
# 1. Múltiples métodos con scoring
def extract_outline(book_id: str, content: str, pages: list[str], toc: list | None, method: str) -> OutlineResult:
    results = []
    
    if method in ["auto", "toc"] and toc:
        results.append(("toc", _extract_from_toc(toc, book_id), 0.95))
    
    if method in ["auto", "headings"]:
        results.append(("headings", _extract_from_headings(pages, book_id), 0.75))
    
    if method in ["auto", "llm"] and len(results) == 0 or all(r[2] < 0.7 for r in results):
        results.append(("llm", _extract_with_llm(content, book_id), 0.60))
    
    # Seleccionar mejor resultado
    best = max(results, key=lambda x: x[2])
    
    # 2. Validación mínima
    if len(best[1].chapters) < 2:
        return OutlineResult(
            outline=best[1],
            confidence=best[2],
            needs_review=True,
            warning="Solo se detectaron {len(best[1].chapters)} capítulos. Revisa con --review"
        )
    
    return OutlineResult(outline=best[1], confidence=best[2], needs_review=best[2] < 0.8)

# 3. Forzar revisión si confianza baja
if result.confidence < 0.7:
    console.print("[yellow]⚠️ Confianza baja en detección. Ejecuta:[/]")
    console.print(f"  teach outline {book_id} --review")
```

---

### R6: Inconsistencia de IDs 🟡

**Descripción:** IDs en archivos JSON no coinciden con registros SQLite.

**Mitigación:**

```python
# Usar transacciones para operaciones atómicas
def import_book_atomic(file_path: Path, ...) -> BookResult:
    """Importa libro de forma atómica (todo o nada)."""
    book_id = str(uuid.uuid4())
    book_dir = DATA_DIR / "books" / book_id
    
    try:
        # 1. Crear estructura temporal
        temp_dir = book_dir.with_suffix(".tmp")
        temp_dir.mkdir(parents=True)
        
        # 2. Generar archivos
        book_json = generate_book_json(book_id, ...)
        save_json(temp_dir / "book.json", book_json)
        
        # 3. Insertar en DB
        with db.transaction():
            db.insert_book(book_id, ...)
            
            # 4. Mover a ubicación final (atómico en mismo filesystem)
            temp_dir.rename(book_dir)
        
        return BookResult(success=True, book_id=book_id)
        
    except Exception as e:
        # Rollback: eliminar archivos temporales
        if temp_dir.exists():
            shutil.rmtree(temp_dir)
        raise ImportError(f"Falló importación: {e}")

# Validador de consistencia
def validate_consistency(book_id: str) -> list[str]:
    """Verifica que JSON y DB estén sincronizados."""
    errors = []
    
    # Verificar que book.json existe
    book_json_path = DATA_DIR / "books" / book_id / "book.json"
    if not book_json_path.exists():
        errors.append(f"book.json no existe para {book_id}")
    
    # Verificar que DB tiene registro
    db_record = db.get_book(book_id)
    if not db_record:
        errors.append(f"Registro DB no existe para {book_id}")
    
    # Verificar IDs coinciden
    if book_json_path.exists():
        book_data = load_json(book_json_path)
        if book_data.get("book_id") != book_id:
            errors.append(f"ID mismatch: JSON={book_data.get('book_id')}, esperado={book_id}")
    
    return errors
```

---

### R7: Normalización Elimina Contenido 🟡

**Descripción:** Reglas de normalización demasiado agresivas eliminan contenido válido.

**Mitigación:**

```python
# 1. Configuración granular
@dataclass
class NormalizerOptions:
    fix_hyphenation: bool = True
    remove_pagination: bool = True
    normalize_whitespace: bool = True
    preserve_code_blocks: bool = True
    preserve_tables: bool = True
    min_paragraph_length: int = 20  # No eliminar párrafos cortos si son mayores
    
# 2. Logging detallado de cambios
def normalize_text(raw_text: str, options: NormalizerOptions) -> NormalizedResult:
    stats = NormalizationStats()
    
    if options.fix_hyphenation:
        text, count = _fix_hyphenation_with_count(raw_text)
        stats.hyphenations_fixed = count
        logger.debug(f"Guiones de fin de línea corregidos: {count}")
    
    # ... más transformaciones con logging
    
    return NormalizedResult(
        text=text,
        stats=stats,
        reversible=False  # Indicar si se puede revertir
    )

# 3. Modo preview
def normalize_preview(raw_text: str, options: NormalizerOptions) -> str:
    """Muestra diff de cambios sin aplicar."""
    result = normalize_text(raw_text, options)
    return generate_diff(raw_text, result.text)

# 4. Guardar original siempre
# En book_importer: guardar raw/ antes de normalizar
```

---

### R8: Dependencias Incompatibles 🟢

**Descripción:** Conflictos entre pymupdf, ebooklib u otras dependencias.

**Mitigación:**

```toml
# pyproject.toml - pins estrictos
[project]
dependencies = [
    "pymupdf>=1.23.0,<1.24",  # Pin minor version
    "ebooklib>=0.18,<0.19",
    # ... resto con pins
]

[project.optional-dependencies]
dev = [
    "pytest>=7.0",
    "pytest-cov>=4.0",
]
```

```bash
# Script de verificación de entorno
# scripts/check_env.py
def check_dependencies():
    """Verifica que todas las dependencias funcionan."""
    try:
        import fitz  # pymupdf
        import ebooklib
        import langdetect
        print("✓ Todas las dependencias OK")
    except ImportError as e:
        print(f"✗ Falta dependencia: {e}")
        sys.exit(1)
```

---

### R9: Estado Corrupto tras Crash 🟡

**Descripción:** Crash durante operación deja estado inconsistente.

**Mitigación:**

```python
# 1. Checkpoints en operaciones largas
def extract_outline_with_checkpoints(book_id: str, ...) -> OutlineResult:
    checkpoint_file = DATA_DIR / "books" / book_id / ".outline_checkpoint.json"
    
    # Recuperar de checkpoint si existe
    if checkpoint_file.exists():
        logger.info("Recuperando de checkpoint...")
        checkpoint = load_json(checkpoint_file)
        # Continuar desde último estado guardado
    
    try:
        # Guardar checkpoint después de cada paso costoso
        toc_result = _extract_from_toc(...)
        save_json(checkpoint_file, {"step": "toc", "result": toc_result})
        
        headings_result = _extract_from_headings(...)
        save_json(checkpoint_file, {"step": "headings", "result": headings_result})
        
        # ... completar
        
    finally:
        # Limpiar checkpoint si completó
        if checkpoint_file.exists():
            checkpoint_file.unlink()

# 2. CLI con comando de recovery
@app.command()
def recover(book_id: str):
    """Recupera estado de un libro tras crash."""
    errors = validate_consistency(book_id)
    if errors:
        console.print(f"[red]Errores encontrados: {errors}")
        # Ofrecer opciones de recuperación
```

---

### R10: Grading Inconsistente 🟡

**Descripción:** El LLM da puntuaciones diferentes a respuestas similares.

**Mitigación:**

```python
# 1. Rúbricas estrictas (ya en diseño de prompts)

# 2. Normalización de respuestas antes de evaluar
def normalize_student_response(response: str) -> str:
    """Normaliza respuesta para evaluación consistente."""
    response = response.lower().strip()
    response = re.sub(r'\s+', ' ', response)
    # Remover puntuación irrelevante
    return response

# 3. Evaluación determinista cuando es posible
def grade_multiple_choice(response: str, correct: int, options: list[str]) -> GradeResult:
    """Grading determinista para multiple choice."""
    # Parsear respuesta como letra o número
    normalized = response.strip().upper()
    
    if normalized in ["A", "B", "C", "D"]:
        answer_idx = ord(normalized) - ord("A")
    elif normalized.isdigit():
        answer_idx = int(normalized) - 1
    else:
        # Buscar match con texto de opción
        for i, opt in enumerate(options):
            if normalized in opt.lower():
                answer_idx = i
                break
        else:
            return GradeResult(score=0, feedback="Respuesta no reconocida")
    
    is_correct = answer_idx == correct
    return GradeResult(
        score=1.0 if is_correct else 0.0,
        is_correct=is_correct,
        feedback="¡Correcto!" if is_correct else f"Incorrecto. La respuesta era: {options[correct]}"
    )

# 4. Logging de grading para auditoría
def grade_with_audit(exercise: Exercise, response: str) -> GradeResult:
    result = grade_response(exercise, response)
    
    # Log para análisis posterior
    audit_log.info({
        "exercise_id": exercise.id,
        "type": exercise.type,
        "response": response,
        "score": result.score,
        "grader_mode": result.grader_mode,
        "timestamp": datetime.now().isoformat()
    })
    
    return result
```

---

## Checklist de Mitigación por Fase

### F2: Ingesta + Outline

- [ ] R1: Detectar PDFs escaneados y dar error claro
- [ ] R2: Manejar EPUBs mal formados gracefully
- [ ] R5: Implementar múltiples métodos de outline con scoring
- [ ] R6: Usar transacciones atómicas
- [ ] R7: Logging de normalización + guardar original

### F3-F4: Units + Notes

- [ ] R3: Implementar chunking de contenido largo
- [ ] R4: Implementar streaming + indicadores de progreso

### F5-F6: Ejercicios + Exámenes

- [ ] R10: Grading determinista para opciones múltiples
- [ ] R10: Logging de auditoría

### F7: LangGraph

- [ ] R9: Checkpoints de estado del grafo
