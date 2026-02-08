"""CLI commands for the teaching system.

F2 Commands (current phase):
- import-book: Import a PDF or EPUB book
- outline: Extract book structure

Future commands (F3+) are stubbed but NOT implemented.
See docs/phase_guardrails.md for phase assignments.
"""

from pathlib import Path

import typer
from rich.console import Console

from teaching.core.book_importer import (
    BookImportError,
    DuplicateBookError,
    import_book as do_import_book,
)
from teaching.core.pdf_extractor import (
    extract_pdf,
    PdfExtractionError,
)
from teaching.core.epub_extractor import (
    extract_epub,
    EpubExtractionError,
)
from teaching.core.text_normalizer import (
    normalize_book,
    NormalizationError,
)
from teaching.core.outline_extractor import (
    extract_outline,
    generate_review_yaml,
    validate_and_apply_yaml,
    OutlineExtractionError,
)
from teaching.core.unit_planner import (
    generate_units,
    UnitPlanningError,
)
from teaching.core.notes_generator import (
    generate_notes,
    NotesGenerationError,
)
from teaching.core.exercise_generator import (
    generate_exercises,
    ExerciseGenerationError,
)
from teaching.core.attempt_repository import (
    submit_attempt,
    AttemptValidationError,
)
from teaching.core.grader import (
    grade_attempt,
    GradingError,
)
from teaching.core.chapter_exam_generator import (
    generate_chapter_exam,
    ExamGenerationError,
)
from teaching.core.exam_attempt_repository import (
    submit_exam_attempt as do_submit_exam_attempt,
    load_exam_set,
    ExamAnswer,
    ExamAttemptValidationError,
)
from teaching.core.exam_grader import (
    grade_exam_attempt,
    ExamGradingError,
)
from teaching.core.attempt_repository import Answer
from teaching.llm.client import LLMClient, LLMConfig
from teaching.db.books_repository import get_book_by_id
from teaching.utils.validators import (
    AmbiguousBookIdError,
    BookNotFoundError,
    get_available_book_ids,
    resolve_book_id,
)
from enum import Enum, auto


class TeachingState(Enum):
    """Estados del flujo de enseñanza teaching-first."""

    EXPLAINING = auto()  # Explicando un punto
    WAITING_INPUT = auto()  # Esperando respuesta del estudiante
    CHECKING = auto()  # Evaluando comprensión
    MORE_EXAMPLES = auto()  # Generando más ejemplos
    AWAITING_RETRY = auto()  # Esperando segunda respuesta tras feedback negativo
    REMEDIATION = auto()  # Reexplicando con analogía (solo si falla 2da vez)
    NEXT_POINT = auto()  # Transición al siguiente punto
    CONFIRM_ADVANCE = auto()  # Confirmar antes de avanzar al siguiente punto (F7.4)
    DEEPEN_EXPLANATION = auto()  # Profundizar en el concepto (F7.4)
    POST_FAILURE_CHOICE = auto()  # F8.2: Ofrecer opción de avanzar o quedarse tras fallo

app = typer.Typer(
    name="teach",
    help="Personal LLM-powered teaching system for book-based learning.",
    no_args_is_help=True,
)

console = Console()


def _resolve_book_id_or_exit(book_id_prefix: str) -> str:
    """Resolve book_id prefix to full ID, or exit with helpful error."""
    try:
        candidates = get_available_book_ids()
        return resolve_book_id(book_id_prefix, candidates)
    except BookNotFoundError as e:
        console.print(f"[red]✗ {e}[/red]")
        if candidates := get_available_book_ids():
            console.print("\nLibros disponibles:")
            for c in candidates:
                console.print(f"  - {c}")
        raise typer.Exit(code=1)
    except AmbiguousBookIdError as e:
        console.print(f"[red]✗ {e}[/red]")
        raise typer.Exit(code=1)


def _abort_future_phase(phase: int, command: str) -> None:
    """Abort execution for commands not yet implemented."""
    console.print(
        f"[yellow]⚠ Comando '{command}' disponible en Fase F{phase}[/yellow]\n"
        f"  Ver: docs/phase_guardrails.md"
    )


def _resolve_provider_model(
    provider: str | None,
    model: str | None,
) -> tuple[str, str]:
    """Resolve provider/model from config defaults if not provided.

    Args:
        provider: CLI-provided provider (None = use config default)
        model: CLI-provided model (None = use config default)

    Returns:
        tuple of (effective_provider, effective_model)
    """
    config = LLMConfig.from_yaml()
    effective_provider = provider if provider else config.provider
    effective_model = model if model else config.model
    return (effective_provider, effective_model)


def _truncate(text: str, max_len: int = 120) -> str:
    """Truncate text with ellipsis if too long."""
    if len(text) <= max_len:
        return text
    return text[:max_len - 3] + "..."
    raise typer.Exit(code=1)


# =============================================================================
# F2 COMMANDS - Current Phase
# =============================================================================


@app.command()
def import_book(
    file: str = typer.Argument(..., help="Path to PDF or EPUB file"),
    title: str | None = typer.Option(None, "--title", "-t", help="Book title"),
    author: str | None = typer.Option(
        None, "--author", "-a", help="Author(s), comma-separated"
    ),
    language: str = typer.Option("auto", "--language", "-l", help="Language: en, es, auto"),
    force: bool = typer.Option(False, "--force", "-f", help="Re-import if exists"),
) -> None:
    """Import a PDF or EPUB book into the system."""
    file_path = Path(file).expanduser().resolve()

    try:
        result = do_import_book(
            file_path=file_path,
            title=title,
            author=author,
            language=language,
            force=force,
        )

        if result.success:
            console.print(f"[green]✓ {result.message}[/green]")
            console.print(f"  [dim]book_id:[/dim] {result.book_id}")
            console.print(f"  [dim]path:[/dim]    {result.book_path}")
            if result.metadata:
                console.print(f"  [dim]title:[/dim]   {result.metadata.title}")
                if result.metadata.authors:
                    console.print(f"  [dim]authors:[/dim] {', '.join(result.metadata.authors)}")
        else:
            console.print(f"[red]✗ {result.message}[/red]")
            raise typer.Exit(code=1)

    except DuplicateBookError as e:
        console.print(f"[yellow]⚠ {e}[/yellow]")
        console.print(f"  [dim]existing book_id:[/dim] {e.existing_book_id}")
        raise typer.Exit(code=1)

    except BookImportError as e:
        console.print(f"[red]✗ {e}[/red]")
        raise typer.Exit(code=1)


@app.command(name="extract-raw")
def extract_raw(
    book_id: str = typer.Argument(
        ..., help="Book ID (e.g., 'martin-2008-clean') or unique prefix"
    ),
) -> None:
    """Extract raw text from an imported book (PDF or EPUB).

    Reads from data/books/{book_id}/source/ and writes to:
    - raw/content.txt (full text)
    - raw/pages/*.txt (for PDF) or raw/chapters/*.txt (for EPUB)

    Updates book.json with extraction metrics.
    """
    # Resolve prefix to full book_id
    resolved_id = _resolve_book_id_or_exit(book_id)

    # Get book info from DB to determine format
    book_record = get_book_by_id(resolved_id)
    if not book_record:
        console.print(f"[red]✗ Libro no encontrado en DB: {resolved_id}[/red]")
        raise typer.Exit(code=1)

    source_format = book_record.source_format
    book_path = Path("data/books") / resolved_id

    # Verify source exists
    source_dir = book_path / "source"
    if not source_dir.exists():
        console.print(f"[red]✗ Directorio source/ no encontrado: {source_dir}[/red]")
        raise typer.Exit(code=1)

    console.print(f"[blue]Extrayendo texto de {resolved_id} ({source_format})...[/blue]")

    try:
        if source_format == "pdf":
            result = extract_pdf(resolved_id)
            output_subdir = "pages"
        elif source_format == "epub":
            result = extract_epub(resolved_id)
            output_subdir = "chapters"
        else:
            console.print(f"[red]✗ Formato no soportado: {source_format}[/red]")
            raise typer.Exit(code=1)

        if result.success:
            console.print(f"[green]✓ {result.message}[/green]")
            console.print(f"  [dim]content:[/dim] {book_path / 'raw' / 'content.txt'}")
            console.print(f"  [dim]{output_subdir}:[/dim]  {book_path / 'raw' / output_subdir}/")

            # Show key metrics
            metrics = result.metrics
            if hasattr(metrics, "total_pages"):
                console.print(f"  [dim]pages:[/dim]   {metrics.total_pages}")
            if hasattr(metrics, "total_chapters"):
                console.print(f"  [dim]chapters:[/dim] {metrics.total_chapters}")
            console.print(f"  [dim]chars:[/dim]   {metrics.total_chars:,}")

            if hasattr(metrics, "is_likely_scanned") and metrics.is_likely_scanned:
                console.print(
                    "[yellow]⚠ PDF parece escaneado - considere OCR para mejor extracción[/yellow]"
                )

    except (PdfExtractionError, EpubExtractionError) as e:
        console.print(f"[red]✗ Error de extracción: {e}[/red]")
        raise typer.Exit(code=1)
    except FileNotFoundError as e:
        console.print(f"[red]✗ {e}[/red]")
        raise typer.Exit(code=1)


@app.command()
def normalize(
    book_id: str = typer.Argument(
        ..., help="Book ID (e.g., 'martin-2008-clean') or unique prefix"
    ),
) -> None:
    """Normalize extracted text (cleanup without changing meaning).

    Reads from data/books/{book_id}/raw/content.txt and writes to:
    - normalized/content.txt (cleaned text)
    - normalized/pages/*.txt or normalized/chapters/*.txt (if raw has them)

    Applies: hyphenation fixes, space normalization, Unicode cleanup.
    Updates book.json with normalization metrics.
    """
    # Resolve prefix to full book_id
    resolved_id = _resolve_book_id_or_exit(book_id)

    book_path = Path("data/books") / resolved_id

    # Verify raw content exists
    raw_content = book_path / "raw" / "content.txt"
    if not raw_content.exists():
        console.print(f"[red]✗ raw/content.txt no encontrado: {raw_content}[/red]")
        console.print("  Ejecuta primero: teach extract-raw {book_id}")
        raise typer.Exit(code=1)

    console.print(f"[blue]Normalizando texto de {resolved_id}...[/blue]")

    try:
        result = normalize_book(resolved_id)

        if result.success:
            console.print(f"[green]✓ {result.message}[/green]")
            console.print(f"  [dim]output:[/dim] {book_path / 'normalized' / 'content.txt'}")

            # Show metrics
            metrics = result.metrics
            console.print(f"  [dim]original:[/dim]   {metrics.original_chars:,} chars")
            console.print(f"  [dim]normalized:[/dim] {metrics.normalized_chars:,} chars")
            console.print(f"  [dim]removed:[/dim]    {metrics.chars_removed:,} ({metrics.chars_removed_ratio:.1%})")

            if metrics.hyphen_breaks_fixed > 0:
                console.print(f"  [dim]hyphen fixes:[/dim] {metrics.hyphen_breaks_fixed}")

            if metrics.content_loss_warning:
                console.print(
                    "[yellow]⚠ Pérdida de contenido significativa (>10%) - revisar manualmente[/yellow]"
                )

    except NormalizationError as e:
        console.print(f"[red]✗ Error de normalización: {e}[/red]")
        raise typer.Exit(code=1)
    except FileNotFoundError as e:
        console.print(f"[red]✗ {e}[/red]")
        raise typer.Exit(code=1)


@app.command()
def outline(
    book_id: str = typer.Argument(
        ..., help="Book ID (e.g., 'martin-2008-clean') or unique prefix"
    ),
    method: str = typer.Option("auto", help="Method: auto, toc, headings, llm"),
    review: bool = typer.Option(False, "--review", "-r", help="Generate YAML for manual editing"),
    validate: bool = typer.Option(False, "--validate", help="Validate and apply edited YAML"),
) -> None:
    """Extract chapter structure from a book.

    Reads from normalized/content.txt (or raw/content.txt as fallback).

    Methods:
    - auto: Try toc -> headings, pick best by confidence
    - toc: Detect table of contents in text
    - headings: Detect chapter/section patterns
    - llm: Use LLM for structure detection (fallback)

    With --review: Generates outline_draft.yaml for manual editing.
    With --validate: Applies edits from outline_draft.yaml.
    """
    # Resolve prefix to full book_id
    resolved_id = _resolve_book_id_or_exit(book_id)

    book_path = Path("data/books") / resolved_id

    # Validate mode: apply edited YAML
    if validate:
        console.print(f"[blue]Validando YAML editado para {resolved_id}...[/blue]")
        try:
            result = validate_and_apply_yaml(resolved_id)

            if result.success:
                console.print(f"[green]✓ {result.message}[/green]")
                console.print(f"  [dim]output:[/dim] {book_path / 'outline' / 'outline.json'}")
            else:
                console.print(f"[red]✗ Validación fallida[/red]")
                for warning in result.report.warnings:
                    console.print(f"  [yellow]• {warning}[/yellow]")
                raise typer.Exit(code=1)

        except FileNotFoundError as e:
            console.print(f"[red]✗ {e}[/red]")
            raise typer.Exit(code=1)
        return

    # Check content exists
    normalized_content = book_path / "normalized" / "content.txt"
    raw_content = book_path / "raw" / "content.txt"

    if not normalized_content.exists() and not raw_content.exists():
        console.print(f"[red]✗ No se encontró content.txt[/red]")
        console.print("  Ejecuta primero: teach extract-raw {book_id}")
        console.print("  Opcionalmente: teach normalize {book_id}")
        raise typer.Exit(code=1)

    console.print(f"[blue]Extrayendo outline de {resolved_id} (method={method})...[/blue]")

    try:
        result = extract_outline(resolved_id, method=method)  # type: ignore

        if result.success and result.outline:
            console.print(f"[green]✓ {result.message}[/green]")
            console.print(f"  [dim]output:[/dim]     {book_path / 'outline' / 'outline.json'}")
            console.print(f"  [dim]method:[/dim]     {result.report.method_used}")
            console.print(f"  [dim]confidence:[/dim] {result.report.confidence:.0%}")
            console.print(f"  [dim]chapters:[/dim]   {result.report.chapters_found}")
            console.print(f"  [dim]sections:[/dim]   {result.report.sections_found}")

            # Show warnings
            for warning in result.report.warnings:
                console.print(f"  [yellow]⚠ {warning}[/yellow]")

            # Generate YAML for review if requested or needed
            if review or result.needs_review:
                yaml_path = generate_review_yaml(resolved_id)
                console.print(f"\n[cyan]YAML generado para revisión:[/cyan]")
                console.print(f"  {yaml_path}")
                console.print(f"  Edita el archivo y ejecuta: teach outline {resolved_id} --validate")

        else:
            console.print(f"[red]✗ {result.message}[/red]")
            for warning in result.report.warnings:
                console.print(f"  [yellow]• {warning}[/yellow]")

            # Suggest review mode
            if result.needs_review:
                console.print(f"\n[cyan]Sugerencia:[/cyan] Usa --review para edición manual")

            raise typer.Exit(code=1)

    except OutlineExtractionError as e:
        console.print(f"[red]✗ Error de extracción: {e}[/red]")
        raise typer.Exit(code=1)
    except FileNotFoundError as e:
        console.print(f"[red]✗ {e}[/red]")
        raise typer.Exit(code=1)


# =============================================================================
# FUTURE COMMANDS - Stubbed for CLI discovery only
# NO imports from teaching.future - these are pure stubs
# =============================================================================


@app.command()
def plan(
    book_id: str = typer.Argument(
        ..., help="Book ID (e.g., 'martin-2008-clean') or unique prefix"
    ),
    force: bool = typer.Option(False, "--force", "-f", help="Overwrite existing units.json"),
) -> None:
    """Generate learning units plan from book outline.

    Reads from outline/outline.json and generates artifacts/units/units.json.

    Partitioning rules:
    - 0-6 sections -> 1 unit per chapter
    - 7-14 sections -> 2 units
    - 15-24 sections -> 3 units
    - 25-36 sections -> 4 units
    - 37-50 sections -> 5 units
    - >50 sections -> 6 units (max)

    Each unit targets ~20-35 minutes of learning time.
    """
    # Resolve prefix to full book_id
    resolved_id = _resolve_book_id_or_exit(book_id)

    book_path = Path("data/books") / resolved_id
    outline_path = book_path / "outline" / "outline.json"

    # Check outline exists
    if not outline_path.exists():
        console.print(f"[red]✗ outline.json no encontrado: {outline_path}[/red]")
        console.print("  Ejecuta primero: teach outline {book_id}")
        raise typer.Exit(code=1)

    console.print(f"[blue]Generando unidades para {resolved_id}...[/blue]")

    try:
        result = generate_units(resolved_id, force=force)

        if result.success:
            console.print(f"[green]✓ {result.message}[/green]")
            console.print(f"  [dim]output:[/dim]   {book_path / 'artifacts' / 'units' / 'units.json'}")
            console.print(f"  [dim]chapters:[/dim] {result.report.total_chapters}")
            console.print(f"  [dim]units:[/dim]    {result.report.total_units}")
            console.print(f"  [dim]sections:[/dim] {result.report.total_sections}")

            # Format time nicely
            total_hours = result.report.total_time_min // 60
            total_mins = result.report.total_time_min % 60
            if total_hours > 0:
                time_str = f"{total_hours}h {total_mins}min"
            else:
                time_str = f"{total_mins} min"
            console.print(f"  [dim]tiempo:[/dim]   {time_str} estimado")

            # Show warnings
            for warning in result.report.warnings:
                console.print(f"  [yellow]⚠ {warning}[/yellow]")

        else:
            console.print(f"[red]✗ {result.message}[/red]")
            for warning in result.report.warnings:
                console.print(f"  [yellow]• {warning}[/yellow]")
            raise typer.Exit(code=1)

    except UnitPlanningError as e:
        console.print(f"[red]✗ Error de planificación: {e}[/red]")
        raise typer.Exit(code=1)
    except FileNotFoundError as e:
        console.print(f"[red]✗ {e}[/red]")
        raise typer.Exit(code=1)


@app.command()
def notes(
    unit_id: str = typer.Argument(
        ..., help="Unit ID (e.g., 'paul-llm-engineer-s-handbook-ch01-u01')"
    ),
    provider: str | None = typer.Option(
        None, "--provider", "-p", help="LLM provider: lmstudio, openai, anthropic"
    ),
    model: str | None = typer.Option(
        None, "--model", "-m", help="Model name (overrides config)"
    ),
    force: bool = typer.Option(
        False, "--force", "-f", help="Overwrite existing notes"
    ),
) -> None:
    """Generate study notes for a learning unit.

    Reads from normalized content and uses LLM to generate:
    - Spanish study notes in Markdown format
    - Metadata JSON with source traceability

    Output: artifacts/notes/{unit_id}.md and {unit_id}.json

    Requires LLM server (LM Studio by default) to be running.
    """
    import re

    # Validate unit_id format
    match = re.match(r"(.+)-ch\d{2}-u\d{2}$", unit_id)
    if not match:
        console.print(f"[red]✗ Formato de unit_id inválido: {unit_id}[/red]")
        console.print("  Formato esperado: {{book_id}}-ch{{XX}}-u{{YY}}")
        console.print("  Ejemplo: paul-llm-engineer-s-handbook-ch01-u01")
        raise typer.Exit(code=1)

    book_id = match.group(1)
    book_path = Path("data/books") / book_id

    # Check book exists
    if not book_path.exists():
        console.print(f"[red]✗ Libro no encontrado: {book_id}[/red]")
        raise typer.Exit(code=1)

    # Check units.json exists
    units_path = book_path / "artifacts" / "units" / "units.json"
    if not units_path.exists():
        console.print(f"[red]✗ units.json no encontrado[/red]")
        console.print(f"  Ejecuta primero: teach plan {book_id}")
        raise typer.Exit(code=1)

    # Resolve provider/model from defaults
    effective_provider, effective_model = _resolve_provider_model(provider, model)

    console.print(f"[blue]Generando apuntes para {unit_id}...[/blue]")
    console.print(f"  [dim]LLM:[/dim] {effective_provider}/{effective_model}")

    try:
        result = generate_notes(
            unit_id=unit_id,
            provider=effective_provider,  # type: ignore
            model=effective_model,
            force=force,
        )

        if result.success:
            console.print(f"[green]✓ {result.message}[/green]")
            console.print(f"  [dim]notes:[/dim]    {result.notes_path}")
            console.print(f"  [dim]metadata:[/dim] {result.metadata_path}")

            if result.metadata:
                console.print(f"  [dim]pages:[/dim]    {result.metadata.start_page}-{result.metadata.end_page}")
                console.print(f"  [dim]chunks:[/dim]   {result.metadata.chunks_processed}")

                # Format time nicely
                time_sec = result.metadata.generation_time_ms / 1000
                if time_sec >= 60:
                    time_str = f"{time_sec / 60:.1f} min"
                else:
                    time_str = f"{time_sec:.1f} sec"
                console.print(f"  [dim]tiempo:[/dim]   {time_str}")

            # Show warnings
            for warning in result.warnings:
                console.print(f"  [yellow]⚠ {warning}[/yellow]")

        else:
            console.print(f"[red]✗ {result.message}[/red]")
            for warning in result.warnings:
                console.print(f"  [yellow]• {warning}[/yellow]")
            raise typer.Exit(code=1)

    except NotesGenerationError as e:
        console.print(f"[red]✗ Error de generación: {e}[/red]")
        raise typer.Exit(code=1)
    except Exception as e:
        # Catch LLM connection errors
        error_msg = str(e)
        if "connect" in error_msg.lower() or "connection" in error_msg.lower():
            console.print(f"[red]✗ No se pudo conectar al servidor LLM[/red]")
            console.print("  Verifica que LM Studio esté corriendo en localhost:1234")
        else:
            console.print(f"[red]✗ Error: {e}[/red]")
        raise typer.Exit(code=1)


@app.command()
def start_unit(
    unit_id: str = typer.Argument(..., help="Unit ID (e.g., 'book_id:unit:5')"),
) -> None:
    """[F4.2] Start an interactive learning unit session."""
    _abort_future_phase(4, "start-unit")


@app.command()
def exercise(
    unit_id: str = typer.Argument(
        ..., help="Unit ID (e.g., 'paul-llm-engineer-s-handbook-ch01-u01')"
    ),
    difficulty: str = typer.Option(
        "mid", "--difficulty", "-d", help="Difficulty: intro, mid, adv"
    ),
    types: str = typer.Option(
        "mixed", "--types", "-t", help="Types: quiz, practical, mixed"
    ),
    n: int = typer.Option(
        10, "--n", "-n", help="Number of exercises to generate"
    ),
    provider: str | None = typer.Option(
        None, "--provider", "-p", help="LLM provider: lmstudio, openai, anthropic"
    ),
    model: str | None = typer.Option(
        None, "--model", "-m", help="Model name (overrides config)"
    ),
    force: bool = typer.Option(
        False, "--force", "-f", help="Create new exercise set even if one exists"
    ),
) -> None:
    """Generate practice exercises for a learning unit.

    Reads unit content and uses LLM to generate exercises in Spanish.
    Supports multiple choice, true/false, and short answer questions.

    Output: artifacts/exercises/{unit_id}-ex{NN}.json

    Requires LLM server (LM Studio by default) to be running.
    """
    import re
    import os

    # Get data_dir from environment or default
    data_dir = Path(os.environ.get("TEACHING_DATA_DIR", "data"))

    # Validate unit_id format
    match = re.match(r"(.+)-ch\d{2}-u\d{2}$", unit_id)
    if not match:
        console.print(f"[red]✗ Formato de unit_id inválido: {unit_id}[/red]")
        console.print("  Formato esperado: {{book_id}}-ch{{XX}}-u{{YY}}")
        console.print("  Ejemplo: paul-llm-engineer-s-handbook-ch01-u01")
        raise typer.Exit(code=1)

    book_id = match.group(1)
    book_path = data_dir / "books" / book_id

    # Check book exists
    if not book_path.exists():
        console.print(f"[red]✗ Libro no encontrado: {book_id}[/red]")
        raise typer.Exit(code=1)

    # Parse types
    types_list = [t.strip() for t in types.split(",")]

    # Resolve provider/model from defaults
    effective_provider, effective_model = _resolve_provider_model(provider, model)

    console.print(f"[blue]Generando {n} ejercicios para {unit_id}...[/blue]")
    console.print(f"  [dim]LLM:[/dim] {effective_provider}/{effective_model}")

    try:
        result = generate_exercises(
            unit_id=unit_id,
            data_dir=data_dir,
            difficulty=difficulty,
            types=types_list,
            n=n,
            provider=effective_provider,
            model=effective_model,
            force=force,
        )

        if result.success:
            console.print(f"[green]✓ {result.message}[/green]")
            console.print(f"  [dim]archivo:[/dim]     {result.exercise_set_path}")
            console.print(f"  [dim]ejercicios:[/dim]  {len(result.exercises)}")

            if result.metadata:
                console.print(f"  [dim]puntos:[/dim]      {result.metadata.total_points}")
                console.print(f"  [dim]dificultad:[/dim]  {result.metadata.difficulty}")
                console.print(f"  [dim]modo:[/dim]        {result.metadata.mode}")

                # Format time
                time_sec = result.metadata.generation_time_ms / 1000
                time_str = f"{time_sec:.1f} sec" if time_sec < 60 else f"{time_sec/60:.1f} min"
                console.print(f"  [dim]tiempo:[/dim]      {time_str}")

            # Show warnings
            for warning in result.warnings:
                console.print(f"  [yellow]⚠ {warning}[/yellow]")

            # Instruction for next step
            console.print(f"\n[cyan]Siguiente paso:[/cyan]")
            console.print(f"  1. Crea un archivo answers.json con tus respuestas")
            console.print(f"  2. Ejecuta: teach submit {result.metadata.exercise_set_id} --answers answers.json")

        else:
            console.print(f"[red]✗ {result.message}[/red]")
            for warning in result.warnings:
                console.print(f"  [yellow]• {warning}[/yellow]")
            raise typer.Exit(code=1)

    except ExerciseGenerationError as e:
        console.print(f"[red]✗ Error de generación: {e}[/red]")
        raise typer.Exit(code=1)
    except Exception as e:
        error_msg = str(e)
        if "connect" in error_msg.lower() or "connection" in error_msg.lower():
            console.print(f"[red]✗ No se pudo conectar al servidor LLM[/red]")
            console.print("  Verifica que LM Studio esté corriendo en localhost:1234")
        else:
            console.print(f"[red]✗ Error: {e}[/red]")
        raise typer.Exit(code=1)


@app.command()
def submit(
    exercise_set_id: str = typer.Argument(
        ..., help="Exercise set ID (e.g., 'test-book-ch01-u01-ex01')"
    ),
    answers: str = typer.Option(
        ..., "--answers", "-a", help="Path to answers JSON file"
    ),
) -> None:
    """Submit answers for an exercise set.

    The answers file should be a JSON with this structure:
    {
      "answers": [
        {"exercise_id": "...-q01", "response": 0},
        {"exercise_id": "...-q02", "response": true},
        {"exercise_id": "...-q03", "response": "text answer"}
      ]
    }

    Output: artifacts/attempts/{exercise_set_id}-a{NN}.json
    """
    import os

    data_dir = Path(os.environ.get("TEACHING_DATA_DIR", "data"))
    answers_path = Path(answers).expanduser().resolve()

    if not answers_path.exists():
        console.print(f"[red]✗ Archivo de respuestas no encontrado: {answers_path}[/red]")
        raise typer.Exit(code=1)

    console.print(f"[blue]Enviando respuestas para {exercise_set_id}...[/blue]")

    try:
        result = submit_attempt(
            exercise_set_id=exercise_set_id,
            answers_path=answers_path,
            data_dir=data_dir,
        )

        if result.success:
            console.print(f"[green]✓ {result.message}[/green]")
            console.print(f"  [dim]archivo:[/dim]   {result.attempt_path}")
            console.print(f"  [dim]preguntas:[/dim] {result.attempt.total_questions}")

            # Instruction for next step
            console.print(f"\n[cyan]Siguiente paso:[/cyan]")
            console.print(f"  Ejecuta: teach grade {result.attempt.attempt_id}")

        else:
            console.print(f"[red]✗ {result.message}[/red]")
            for warning in result.warnings:
                console.print(f"  [yellow]• {warning}[/yellow]")
            raise typer.Exit(code=1)

    except AttemptValidationError as e:
        console.print(f"[red]✗ Error de validación: {e}[/red]")
        raise typer.Exit(code=1)


@app.command()
def grade(
    attempt_id: str = typer.Argument(
        ..., help="Attempt ID (e.g., 'test-book-ch01-u01-ex01-a01')"
    ),
    provider: str | None = typer.Option(
        None, "--provider", "-p", help="LLM provider for subjective grading"
    ),
    model: str | None = typer.Option(
        None, "--model", "-m", help="Model name (overrides config)"
    ),
    strict: bool = typer.Option(
        False, "--strict", "-s", help="Use strict grading mode"
    ),
) -> None:
    """Grade a submitted attempt.

    Auto-grades objective questions (multiple choice, true/false).
    Uses LLM for subjective questions (short answer).

    Output: artifacts/grades/{attempt_id}.json
    """
    import os

    data_dir = Path(os.environ.get("TEACHING_DATA_DIR", "data"))

    # Resolve provider/model from defaults
    effective_provider, effective_model = _resolve_provider_model(provider, model)

    console.print(f"[blue]Calificando intento {attempt_id}...[/blue]")
    console.print(f"  [dim]LLM:[/dim] {effective_provider}/{effective_model}")

    try:
        result = grade_attempt(
            attempt_id=attempt_id,
            data_dir=data_dir,
            provider=effective_provider,
            model=effective_model,
            strict=strict,
        )

        if result.success:
            report = result.report
            summary = report.summary

            # Status based on pass/fail
            if summary.passed:
                console.print(f"[green]✓ {result.message}[/green]")
            else:
                console.print(f"[yellow]✗ {result.message}[/yellow]")

            console.print(f"  [dim]archivo:[/dim]    {result.grade_path}")
            console.print(f"  [dim]correctas:[/dim]  {summary.correct_count}/{summary.total_questions}")
            console.print(f"  [dim]puntuación:[/dim] {summary.total_score:.1f}/{summary.max_score:.1f}")
            console.print(f"  [dim]porcentaje:[/dim] {summary.percentage:.1%}")
            console.print(f"  [dim]modo:[/dim]       {report.mode}")

            # Format time
            time_sec = report.grading_time_ms / 1000
            time_str = f"{time_sec:.1f} sec" if time_sec < 60 else f"{time_sec/60:.1f} min"
            console.print(f"  [dim]tiempo:[/dim]     {time_str}")

            # Show individual results summary
            console.print(f"\n[bold]Resultados por pregunta:[/bold]")
            for r in report.results:
                status = "✓" if r.is_correct else "✗" if r.is_correct is False else "?"
                color = "green" if r.is_correct else "red" if r.is_correct is False else "yellow"
                console.print(f"  [{color}]{status}[/{color}] {r.exercise_id}: {r.score:.0%} - {r.feedback[:60]}...")

            # Show warnings
            for warning in result.warnings:
                console.print(f"  [yellow]⚠ {warning}[/yellow]")

        else:
            console.print(f"[red]✗ {result.message}[/red]")
            for warning in result.warnings:
                console.print(f"  [yellow]• {warning}[/yellow]")
            raise typer.Exit(code=1)

    except GradingError as e:
        console.print(f"[red]✗ Error de calificación: {e}[/red]")
        raise typer.Exit(code=1)
    except Exception as e:
        error_msg = str(e)
        if "connect" in error_msg.lower() or "connection" in error_msg.lower():
            console.print(f"[red]✗ No se pudo conectar al servidor LLM[/red]")
            console.print("  Verifica que LM Studio esté corriendo en localhost:1234")
        else:
            console.print(f"[red]✗ Error: {e}[/red]")
        raise typer.Exit(code=1)


@app.command(name="review-grade")
def review_grade(
    grade_id: str = typer.Argument(
        ..., help="Grade/attempt ID (e.g., 'book-ch01-u01-ex01-a01')"
    ),
) -> None:
    """Review a grade report with Rich formatting.

    Displays a summary panel with score, pass/fail status, and mode,
    followed by a table of per-question results.

    Accepts the attempt_id (which is also the grade report filename).
    """
    import os
    import re
    import json
    from rich.table import Table
    from rich.panel import Panel

    data_dir = Path(os.environ.get("TEACHING_DATA_DIR", "data"))

    # Validate ID format: {book_id}-ch{XX}-u{YY}-ex{ZZ}-a{NN}
    match = re.match(r"(.+)-ch\d{2}-u\d{2}-ex\d{2}-a\d{2}$", grade_id)
    if not match:
        console.print(f"[red]✗ Formato de ID inválido: {grade_id}[/red]")
        console.print("  Formato esperado: {{book_id}}-ch{{XX}}-u{{YY}}-ex{{ZZ}}-a{{NN}}")
        raise typer.Exit(code=1)

    book_id = match.group(1)
    grade_path = data_dir / "books" / book_id / "artifacts" / "grades" / f"{grade_id}.json"

    # Check existence
    if not grade_path.exists():
        console.print(f"[yellow]⚠ Calificación no encontrada: {grade_id}[/yellow]")
        console.print(f"  Ejecuta primero: teach grade {grade_id}")
        raise typer.Exit(code=1)

    # Load grade report
    with open(grade_path, encoding="utf-8") as f:
        report = json.load(f)

    # Extract data
    summary = report["summary"]
    results = report["results"]

    # Header panel
    status = "APROBADO" if summary["passed"] else "NO APROBADO"
    color = "green" if summary["passed"] else "red"
    strict_text = " (ESTRICTO)" if report.get("strict") else ""

    header = (
        f"[bold]{summary['percentage']:.1%}[/bold] - [{color}]{status}[/{color}]{strict_text}\n"
        f"Correctas: {summary['correct_count']}/{summary['total_questions']} | "
        f"Puntos: {summary['total_score']:.1f}/{summary['max_score']:.1f}\n"
        f"Modo: {report['mode']} | LLM: {report['provider']}/{report['model']}"
    )
    console.print(Panel(header, title=f"[bold]{grade_id}[/bold]", expand=False))

    # Results table
    table = Table(show_header=True, header_style="bold")
    table.add_column("Pregunta", style="cyan", width=12)
    table.add_column("Estado", justify="center", width=10)
    table.add_column("Score", justify="center", width=8)
    table.add_column("Feedback", width=60)

    for r in results:
        # Extract short question ID (e.g., "q01")
        q_id = r["exercise_id"].split("-")[-1]

        # Determine result symbol
        if r["is_correct"] is True:
            status_icon = "[green]✓[/green]"
        elif r["is_correct"] is False:
            status_icon = "[red]✗[/red]"
        else:
            status_icon = "[yellow]?[/yellow]"

        # Truncate feedback
        feedback = _truncate(r.get("feedback", ""), 80)

        table.add_row(q_id, status_icon, f"{r['score']:.0%}", feedback)

    console.print(table)
    console.print(f"\n[dim]Archivo:[/dim] {grade_path}")


# =============================================================================
# QUIZ COMMAND - Interactive end-to-end flow
# =============================================================================


def _ask_mcq(exercise, console) -> int:
    """Ask MCQ question and loop until valid input (0..k-1)."""
    n_options = len(exercise.options)

    while True:
        for idx, opt in enumerate(exercise.options):
            console.print(f"  {idx}. {opt}")

        raw = typer.prompt(f"Elige una opción (0-{n_options - 1})")
        try:
            choice = int(raw.strip())
            if 0 <= choice < n_options:
                return choice
            console.print(f"[yellow]⚠ Debe ser 0-{n_options - 1}[/yellow]")
        except ValueError:
            console.print("[yellow]⚠ Ingresa un número[/yellow]")


def _ask_tf(exercise, console) -> bool:
    """Ask TF question and loop until valid input."""
    TRUE_VALUES = {"true", "t", "y", "yes", "1", "verdadero", "sí", "si"}
    FALSE_VALUES = {"false", "f", "n", "no", "0", "falso"}

    while True:
        raw = typer.prompt("Responde true/false (t/f, y/n, 1/0)").strip().lower()

        if raw in TRUE_VALUES:
            return True
        if raw in FALSE_VALUES:
            return False
        console.print("[yellow]⚠ Responde: true/false, t/f, y/n, 1/0[/yellow]")


def _ask_short_answer(exercise, console) -> str:
    """Ask short answer question and loop until non-empty."""
    while True:
        raw = typer.prompt("Respuesta").strip()

        if raw:
            return raw
        console.print("[yellow]⚠ La respuesta no puede estar vacía[/yellow]")


def _ask_question(num: int, total: int, exercise, console) -> str | int | bool:
    """Route to appropriate input handler based on exercise type."""
    console.print(f"\n[blue]Pregunta {num}/{total}[/blue]")
    console.print(f"[bold]{exercise.question}[/bold]")

    if exercise.type == "multiple_choice":
        return _ask_mcq(exercise, console)
    elif exercise.type == "true_false":
        return _ask_tf(exercise, console)
    else:  # short_answer or unknown
        return _ask_short_answer(exercise, console)


def _submit_interactive_attempt(
    exercise_set_id: str,
    answers: list[Answer],
    data_dir: Path,
) -> dict:
    """Create attempt directly from answer list (no file needed).

    Returns dict with attempt_path and attempt data.
    """
    import json
    import re
    from datetime import datetime, timezone

    # Extract book_id from exercise_set_id
    # Format: {book_id}-ch{XX}-u{YY}-ex{NN}
    match = re.match(r"(.+)-ch\d{2}-u\d{2}-ex\d{2}$", exercise_set_id)
    if not match:
        raise ValueError(f"Invalid exercise_set_id format: {exercise_set_id}")

    book_id = match.group(1)
    unit_id = re.match(r"(.+-ch\d{2}-u\d{2})-ex\d{2}$", exercise_set_id).group(1)

    # Determine next attempt number
    attempts_dir = data_dir / "books" / book_id / "artifacts" / "attempts"
    attempts_dir.mkdir(parents=True, exist_ok=True)

    existing = list(attempts_dir.glob(f"{exercise_set_id}-a*.json"))
    next_num = len(existing) + 1
    attempt_id = f"{exercise_set_id}-a{next_num:02d}"

    # Build attempt data
    attempt_data = {
        "$schema": "attempt_v1",
        "attempt_id": attempt_id,
        "exercise_set_id": exercise_set_id,
        "unit_id": unit_id,
        "book_id": book_id,
        "created_at": datetime.now(timezone.utc).isoformat(),
        "status": "pending",
        "answers": [a.to_dict() for a in answers],
        "total_questions": len(answers),
    }

    # Write to file
    attempt_path = attempts_dir / f"{attempt_id}.json"
    with open(attempt_path, "w", encoding="utf-8") as f:
        json.dump(attempt_data, f, indent=2, ensure_ascii=False)

    return {
        "attempt_path": attempt_path,
        "attempt_id": attempt_id,
        "attempt": attempt_data,
    }


@app.command()
def quiz(
    unit_id: str = typer.Argument(
        ..., help="Unit ID (e.g., 'paul-llm-engineer-s-handbook-ch01-u01')"
    ),
    n: int = typer.Option(
        5, "-n", help="Number of exercises to generate"
    ),
    types: str = typer.Option(
        "quiz", "-t", "--types", help="Exercise types: quiz, practical, mixed"
    ),
    difficulty: str = typer.Option(
        "mid", "-d", "--difficulty", help="Difficulty: intro, mid, adv"
    ),
    provider: str | None = typer.Option(
        None, "-p", "--provider", help="LLM provider: lmstudio, openai, anthropic"
    ),
    model: str | None = typer.Option(
        None, "-m", "--model", help="Model name (overrides config)"
    ),
    do_grade: bool = typer.Option(
        False, "--grade", "-g", help="Auto-grade after submission"
    ),
    strict: bool = typer.Option(
        False, "--strict", "-s", help="Use strict grading (binarize short_answer)"
    ),
    force: bool = typer.Option(
        False, "-f", "--force", help="Create new exercise set even if exists"
    ),
) -> None:
    """Take an interactive quiz for a learning unit.

    Generates exercises, asks questions interactively, saves attempt,
    and optionally grades automatically.

    Example:
        teach quiz paul-llm-engineer-s-handbook-ch01-u01 -n 5 -t quiz --grade
    """
    import re
    import os

    # Get data_dir from environment or default
    data_dir = Path(os.environ.get("TEACHING_DATA_DIR", "data"))

    # Validate unit_id format
    match = re.match(r"(.+)-ch\d{2}-u\d{2}$", unit_id)
    if not match:
        console.print(f"[red]✗ Formato de unit_id inválido: {unit_id}[/red]")
        console.print("  Formato esperado: {{book_id}}-ch{{XX}}-u{{YY}}")
        raise typer.Exit(code=1)

    book_id = match.group(1)
    book_path = data_dir / "books" / book_id

    # Check book exists
    if not book_path.exists():
        console.print(f"[red]✗ Libro no encontrado: {book_id}[/red]")
        raise typer.Exit(code=1)

    # Parse types
    types_list = [t.strip() for t in types.split(",")]

    # Resolve provider/model from defaults
    effective_provider, effective_model = _resolve_provider_model(provider, model)

    console.print(f"[blue]Generando {n} ejercicios para {unit_id}...[/blue]")
    console.print(f"  [dim]LLM:[/dim] {effective_provider}/{effective_model}")

    # 1. Generate exercise set
    try:
        result = generate_exercises(
            unit_id=unit_id,
            data_dir=data_dir,
            difficulty=difficulty,
            types=types_list,
            n=n,
            provider=effective_provider,
            model=effective_model,
            force=force,
        )

        if not result.success:
            console.print(f"[red]✗ {result.message}[/red]")
            raise typer.Exit(code=1)

    except ExerciseGenerationError as e:
        console.print(f"[red]✗ Error de generación: {e}[/red]")
        raise typer.Exit(code=1)
    except Exception as e:
        error_msg = str(e)
        if "connect" in error_msg.lower():
            console.print(f"[red]✗ No se pudo conectar al servidor LLM[/red]")
        else:
            console.print(f"[red]✗ Error: {e}[/red]")
        raise typer.Exit(code=1)

    exercises = result.exercises
    exercise_set_id = result.metadata.exercise_set_id

    # 2. Show quiz info
    console.print(f"\n[bold]Quiz: {unit_id}[/bold]")
    console.print(f"[dim]Ejercicios:[/dim] {len(exercises)}")
    console.print(f"[dim]Páginas:[/dim] {result.metadata.pages_used[:5]}...")

    # 3. Interactive question loop
    answers = []
    for i, ex in enumerate(exercises, 1):
        response = _ask_question(i, len(exercises), ex, console)
        answers.append(Answer(exercise_id=ex.exercise_id, response=response))

    # 4. Submit attempt (without external file)
    try:
        attempt_result = _submit_interactive_attempt(exercise_set_id, answers, data_dir)
        console.print(f"\n[green]✓[/green] Respuestas guardadas")
    except Exception as e:
        console.print(f"[red]✗ Error guardando respuestas: {e}[/red]")
        raise typer.Exit(code=1)

    # 5. Grade if requested
    grade_path = None
    if do_grade:
        strict_text = " (estricto)" if strict else ""
        console.print(f"[blue]Calificando{strict_text}...[/blue]")
        try:
            grade_result = grade_attempt(
                attempt_id=attempt_result["attempt_id"],
                data_dir=data_dir,
                provider=effective_provider,
                model=effective_model,
                strict=strict,
            )

            if grade_result.success:
                summary = grade_result.report.summary
                grade_path = grade_result.grade_path

                # Show result
                status_text = "Aprobado" if summary.passed else "No aprobado"
                status_color = "green" if summary.passed else "red"
                console.print(f"\n[bold]Resultado: {summary.percentage:.1%} - [{status_color}]{status_text}[/{status_color}][/bold]")
                console.print(f"[dim]Correctas:[/dim] {summary.correct_count}/{summary.total_questions}")
                console.print(f"[dim]Puntos:[/dim] {summary.total_score:.1f}/{summary.max_score:.1f}")
            else:
                console.print(f"[yellow]⚠ No se pudo calificar: {grade_result.message}[/yellow]")

        except Exception as e:
            console.print(f"[yellow]⚠ Error al calificar: {e}[/yellow]")

    # 6. Show file paths
    console.print(f"\n[green]✓ Quiz completado[/green]")
    console.print(f"[dim]Exercise set:[/dim] {result.exercise_set_path}")
    console.print(f"[dim]Attempt:[/dim] {attempt_result['attempt_path']}")
    if grade_path:
        console.print(f"[dim]Grade:[/dim] {grade_path}")


@app.command()
def exam(
    book_id: str = typer.Argument(
        ..., help="Book ID (e.g., 'paul-llm-engineer-s-handbook')"
    ),
    chapter: str = typer.Option(
        ..., "--chapter", "-c", help="Chapter: ch01, 1, etc."
    ),
    n: int = typer.Option(
        12, "-n", help="Number of questions to generate"
    ),
    difficulty: str = typer.Option(
        "mid", "-d", "--difficulty", help="Difficulty: intro, mid, adv"
    ),
    provider: str | None = typer.Option(
        None, "-p", "--provider", help="LLM provider: lmstudio, openai, anthropic"
    ),
    model: str | None = typer.Option(
        None, "-m", "--model", help="Model name (overrides config)"
    ),
    force: bool = typer.Option(
        False, "-f", "--force", help="Create new exam even if one exists"
    ),
) -> None:
    """Generate a chapter exam.

    Aggregates content from all units in the chapter and generates
    a comprehensive exam with source tracking.

    Output: artifacts/exams/{book_id}-ch{NN}-exam{XX}.json

    Example:
        teach exam paul-llm-engineer-s-handbook --chapter ch01 -n 12
    """
    import os

    data_dir = Path(os.environ.get("TEACHING_DATA_DIR", "data"))
    book_path = data_dir / "books" / book_id

    # Check book exists
    if not book_path.exists():
        console.print(f"[red]✗ Libro no encontrado: {book_id}[/red]")
        raise typer.Exit(code=1)

    # Resolve provider/model from defaults
    effective_provider, effective_model = _resolve_provider_model(provider, model)

    console.print(f"[blue]Generando examen de capítulo {chapter} para {book_id}...[/blue]")
    console.print(f"  [dim]LLM:[/dim] {effective_provider}/{effective_model}")

    try:
        result = generate_chapter_exam(
            book_id=book_id,
            chapter=chapter,
            data_dir=data_dir,
            n=n,
            difficulty=difficulty,
            provider=effective_provider,
            model=effective_model,
            force=force,
        )

        if result.success:
            console.print(f"[green]✓ {result.message}[/green]")
            console.print(f"  [dim]archivo:[/dim]     {result.exam_set_path}")
            console.print(f"  [dim]preguntas:[/dim]   {len(result.questions)}")

            if result.metadata:
                console.print(f"  [dim]unidades:[/dim]    {len(result.metadata.units_included)}")
                console.print(f"  [dim]puntos:[/dim]      {result.metadata.total_points}")
                console.print(f"  [dim]dificultad:[/dim]  {result.metadata.difficulty}")
                console.print(f"  [dim]umbral:[/dim]      {result.metadata.passing_threshold:.0%}")

                # Format time
                time_sec = result.metadata.generation_time_ms / 1000
                time_str = f"{time_sec:.1f} sec" if time_sec < 60 else f"{time_sec/60:.1f} min"
                console.print(f"  [dim]tiempo:[/dim]      {time_str}")

            # Show validation warnings prominently
            if result.metadata and not result.metadata.valid:
                console.print(f"\n[yellow bold]⚠ ADVERTENCIA: Exam set marcado como inválido[/yellow bold]")
                for w in result.metadata.validation_warnings:
                    console.print(f"  [yellow]• {w}[/yellow]")
            elif result.metadata and result.metadata.validation_warnings:
                console.print(f"\n[yellow]Advertencias de validación:[/yellow]")
                for w in result.metadata.validation_warnings:
                    console.print(f"  [dim]• {w}[/dim]")

            # Show other warnings
            other_warnings = [w for w in result.warnings if w not in (result.metadata.validation_warnings if result.metadata else [])]
            for warning in other_warnings:
                console.print(f"  [yellow]⚠ {warning}[/yellow]")

            # Instruction for next step
            console.print(f"\n[cyan]Siguiente paso:[/cyan]")
            console.print(f"  teach exam-quiz {result.metadata.exam_set_id} --grade --strict")

        else:
            console.print(f"[red]✗ {result.message}[/red]")
            for warning in result.warnings:
                console.print(f"  [yellow]• {warning}[/yellow]")
            raise typer.Exit(code=1)

    except ExamGenerationError as e:
        console.print(f"[red]✗ Error de generación: {e}[/red]")
        raise typer.Exit(code=1)
    except Exception as e:
        error_msg = str(e)
        if "connect" in error_msg.lower() or "connection" in error_msg.lower():
            console.print(f"[red]✗ No se pudo conectar al servidor LLM[/red]")
            console.print("  Verifica que LM Studio esté corriendo en localhost:1234")
        else:
            console.print(f"[red]✗ Error: {e}[/red]")
        raise typer.Exit(code=1)


# =============================================================================
# EXAM-QUIZ COMMAND - Interactive exam taking
# =============================================================================


def _ask_exam_question(num: int, total: int, question: dict, console) -> str | int | bool:
    """Route to appropriate input handler based on question type."""
    from teaching.core.chapter_exam_generator import ExamQuestion

    console.print(f"\n[blue]Pregunta {num}/{total}[/blue]")
    console.print(f"[bold]{question['question']}[/bold]")

    q_type = question.get("type", "short_answer")
    options = question.get("options", [])

    if q_type == "multiple_choice":
        # Reuse MCQ logic
        n_options = len(options)
        while True:
            for idx, opt in enumerate(options):
                console.print(f"  {idx}. {opt}")
            raw = typer.prompt(f"Elige una opción (0-{n_options - 1})")
            try:
                choice = int(raw.strip())
                if 0 <= choice < n_options:
                    return choice
                console.print(f"[yellow]⚠ Debe ser 0-{n_options - 1}[/yellow]")
            except ValueError:
                console.print("[yellow]⚠ Ingresa un número[/yellow]")

    elif q_type == "true_false":
        # Reuse TF logic
        TRUE_VALUES = {"true", "t", "y", "yes", "1", "verdadero", "sí", "si"}
        FALSE_VALUES = {"false", "f", "n", "no", "0", "falso"}
        while True:
            raw = typer.prompt("Responde true/false (t/f, y/n, 1/0)").strip().lower()
            if raw in TRUE_VALUES:
                return True
            if raw in FALSE_VALUES:
                return False
            console.print("[yellow]⚠ Responde: true/false, t/f, y/n, 1/0[/yellow]")

    else:  # short_answer
        while True:
            raw = typer.prompt("Respuesta").strip()
            if raw:
                return raw
            console.print("[yellow]⚠ La respuesta no puede estar vacía[/yellow]")


def _submit_interactive_exam_attempt(
    exam_set_id: str,
    answers: list[ExamAnswer],
    data_dir: Path,
) -> dict:
    """Create exam attempt directly from answer list."""
    import json
    import re
    from datetime import datetime, timezone

    # Extract book_id from exam_set_id: {book_id}-ch{NN}-exam{XX}
    match = re.match(r"(.+)-ch\d{2}-exam\d{2}$", exam_set_id)
    if not match:
        raise ValueError(f"Invalid exam_set_id format: {exam_set_id}")

    # Get book_id (everything before -ch)
    full_id = match.group(0)
    parts = full_id.rsplit("-ch", 1)
    book_id = parts[0]

    # Get chapter_id
    ch_match = re.search(r"-ch(\d{2})-exam\d{2}$", exam_set_id)
    chapter_num = int(ch_match.group(1))
    chapter_id = f"{book_id}:ch:{chapter_num}"

    # Determine next attempt number
    attempts_dir = data_dir / "books" / book_id / "artifacts" / "exam_attempts"
    attempts_dir.mkdir(parents=True, exist_ok=True)

    existing = list(attempts_dir.glob(f"{exam_set_id}-a*.json"))
    next_num = len(existing) + 1
    exam_attempt_id = f"{exam_set_id}-a{next_num:02d}"

    # Build attempt data
    attempt_data = {
        "$schema": "exam_attempt_v1",
        "exam_attempt_id": exam_attempt_id,
        "exam_set_id": exam_set_id,
        "book_id": book_id,
        "chapter_id": chapter_id,
        "created_at": datetime.now(timezone.utc).isoformat(),
        "status": "submitted",
        "answers": [{"question_id": a.question_id, "response": a.response} for a in answers],
        "total_questions": len(answers),
    }

    # Write to file
    attempt_path = attempts_dir / f"{exam_attempt_id}.json"
    with open(attempt_path, "w", encoding="utf-8") as f:
        json.dump(attempt_data, f, indent=2, ensure_ascii=False)

    return {
        "attempt_path": attempt_path,
        "exam_attempt_id": exam_attempt_id,
        "attempt": attempt_data,
    }


@app.command(name="exam-quiz")
def exam_quiz(
    exam_set_id: str = typer.Argument(
        ..., help="Exam set ID (e.g., 'test-book-ch01-exam01')"
    ),
    do_grade: bool = typer.Option(
        True, "--grade", "-g", help="Auto-grade after submission"
    ),
    strict: bool = typer.Option(
        True, "--strict", "-s", help="Use strict grading (default True for exams)"
    ),
    provider: str | None = typer.Option(
        None, "-p", "--provider", help="LLM provider for grading"
    ),
    model: str | None = typer.Option(
        None, "-m", "--model", help="Model name (overrides config)"
    ),
) -> None:
    """Take an interactive chapter exam.

    Loads an existing exam set, asks questions interactively,
    saves attempt, and grades (with strict mode by default).

    Example:
        teach exam-quiz test-book-ch01-exam01 --grade --strict
    """
    import os

    data_dir = Path(os.environ.get("TEACHING_DATA_DIR", "data"))

    # Load exam set
    exam_set = load_exam_set(exam_set_id, data_dir)
    if exam_set is None:
        console.print(f"[red]✗ Examen no encontrado: {exam_set_id}[/red]")
        raise typer.Exit(code=1)

    questions = exam_set.get("questions", [])
    if not questions:
        console.print(f"[red]✗ El examen no tiene preguntas[/red]")
        raise typer.Exit(code=1)

    # Resolve provider/model from defaults
    effective_provider, effective_model = _resolve_provider_model(provider, model)

    # Show exam info
    console.print(f"\n[bold]Examen: {exam_set.get('chapter_title', exam_set_id)}[/bold]")
    console.print(f"[dim]Preguntas:[/dim] {len(questions)}")
    console.print(f"[dim]Puntos totales:[/dim] {exam_set.get('total_points', '?')}")
    console.print(f"[dim]Umbral aprobación:[/dim] {exam_set.get('passing_threshold', 0.6):.0%}")

    # Show validation warnings if applicable
    exam_valid = exam_set.get("valid", True)
    exam_mode = exam_set.get("mode", "json")

    if not exam_valid:
        console.print(f"\n[yellow bold]⚠ Este examen está marcado como inválido.[/yellow bold]")
        console.print(f"[yellow]Las respuestas MCQ/TF no serán auto-calificadas.[/yellow]")
        for w in exam_set.get("validation_warnings", []):
            console.print(f"  [yellow]• {w}[/yellow]")
    elif exam_mode == "text_fallback":
        console.print(f"\n[yellow]⚠ Este examen fue generado con text_fallback.[/yellow]")
        console.print(f"[yellow]Las respuestas MCQ/TF serán marcadas para revisión.[/yellow]")

    # Interactive question loop
    answers = []
    for i, q in enumerate(questions, 1):
        response = _ask_exam_question(i, len(questions), q, console)
        answers.append(ExamAnswer(question_id=q["question_id"], response=response))

    # Submit attempt
    try:
        attempt_result = _submit_interactive_exam_attempt(exam_set_id, answers, data_dir)
        console.print(f"\n[green]✓[/green] Respuestas guardadas")
    except Exception as e:
        console.print(f"[red]✗ Error guardando respuestas: {e}[/red]")
        raise typer.Exit(code=1)

    # Grade if requested
    grade_path = None
    if do_grade:
        strict_text = " (ESTRICTO)" if strict else ""
        console.print(f"[blue]Calificando{strict_text}...[/blue]")
        try:
            grade_result = grade_exam_attempt(
                exam_attempt_id=attempt_result["exam_attempt_id"],
                data_dir=data_dir,
                provider=effective_provider,
                model=effective_model,
                strict=strict,
            )

            if grade_result.success:
                summary = grade_result.report.summary
                grade_path = grade_result.grade_path

                # Show result
                status_text = "Aprobado" if summary.passed else "No aprobado"
                status_color = "green" if summary.passed else "red"
                console.print(f"\n[bold]Resultado: {summary.percentage:.1%} - [{status_color}]{status_text}[/{status_color}][/bold]")
                console.print(f"[dim]Correctas:[/dim] {summary.correct_count}/{summary.total_questions}")
                console.print(f"[dim]Puntos:[/dim] {summary.total_score:.1f}/{summary.max_score:.1f}")

                if strict:
                    console.print(f"[dim]Modo:[/dim] ESTRICTO")
            else:
                console.print(f"[yellow]⚠ No se pudo calificar: {grade_result.message}[/yellow]")

        except Exception as e:
            console.print(f"[yellow]⚠ Error al calificar: {e}[/yellow]")

    # Show file paths
    console.print(f"\n[green]✓ Examen completado[/green]")
    console.print(f"[dim]Attempt:[/dim] {attempt_result['attempt_path']}")
    if grade_path:
        console.print(f"[dim]Grade:[/dim] {grade_path}")


@app.command(name="exam-submit")
def exam_submit(
    exam_set_id: str = typer.Argument(
        ..., help="Exam set ID (e.g., 'test-book-ch01-exam01')"
    ),
    answers: str = typer.Option(
        ..., "--answers", "-a", help="Path to answers JSON file"
    ),
) -> None:
    """Submit answers for a chapter exam from JSON file.

    The answers file should be a JSON with this structure:
    {
      "answers": [
        {"question_id": "...-q01", "response": 0},
        {"question_id": "...-q02", "response": true},
        {"question_id": "...-q03", "response": "text answer"}
      ]
    }

    Output: artifacts/exam_attempts/{exam_set_id}-a{NN}.json
    """
    import os

    data_dir = Path(os.environ.get("TEACHING_DATA_DIR", "data"))
    answers_path = Path(answers).expanduser().resolve()

    if not answers_path.exists():
        console.print(f"[red]✗ Archivo de respuestas no encontrado: {answers_path}[/red]")
        raise typer.Exit(code=1)

    console.print(f"[blue]Enviando respuestas de examen para {exam_set_id}...[/blue]")

    try:
        result = do_submit_exam_attempt(
            exam_set_id=exam_set_id,
            answers_path=answers_path,
            data_dir=data_dir,
        )

        if result.success:
            console.print(f"[green]✓ {result.message}[/green]")
            console.print(f"  [dim]archivo:[/dim]   {result.attempt_path}")
            console.print(f"  [dim]preguntas:[/dim] {result.attempt.total_questions}")

            # Instruction for next step
            console.print(f"\n[cyan]Siguiente paso:[/cyan]")
            console.print(f"  teach exam-grade {result.attempt.exam_attempt_id}")

        else:
            console.print(f"[red]✗ {result.message}[/red]")
            for warning in result.warnings:
                console.print(f"  [yellow]• {warning}[/yellow]")
            raise typer.Exit(code=1)

    except ExamAttemptValidationError as e:
        console.print(f"[red]✗ Error de validación: {e}[/red]")
        raise typer.Exit(code=1)


@app.command(name="exam-grade")
def exam_grade(
    exam_attempt_id: str = typer.Argument(
        ..., help="Exam attempt ID (e.g., 'test-book-ch01-exam01-a01')"
    ),
    provider: str | None = typer.Option(
        None, "-p", "--provider", help="LLM provider for subjective grading"
    ),
    model: str | None = typer.Option(
        None, "-m", "--model", help="Model name (overrides config)"
    ),
    strict: bool = typer.Option(
        True, "--strict", "-s", help="Use strict grading (default True for exams)"
    ),
) -> None:
    """Grade a submitted exam attempt.

    Auto-grades objective questions (MCQ, TF).
    Uses LLM for subjective questions (short answer).
    Defaults to strict mode (binarize short answer scores).

    Output: artifacts/exam_grades/{exam_attempt_id}.json
    """
    import os

    data_dir = Path(os.environ.get("TEACHING_DATA_DIR", "data"))

    # Resolve provider/model from defaults
    effective_provider, effective_model = _resolve_provider_model(provider, model)

    strict_text = " (ESTRICTO)" if strict else ""
    console.print(f"[blue]Calificando examen {exam_attempt_id}{strict_text}...[/blue]")
    console.print(f"  [dim]LLM:[/dim] {effective_provider}/{effective_model}")

    try:
        result = grade_exam_attempt(
            exam_attempt_id=exam_attempt_id,
            data_dir=data_dir,
            provider=effective_provider,
            model=effective_model,
            strict=strict,
        )

        if result.success:
            report = result.report
            summary = report.summary

            # Status based on pass/fail
            if summary.passed:
                console.print(f"[green]✓ {result.message}[/green]")
            else:
                console.print(f"[yellow]✗ {result.message}[/yellow]")

            console.print(f"  [dim]archivo:[/dim]    {result.grade_path}")
            console.print(f"  [dim]correctas:[/dim]  {summary.correct_count}/{summary.total_questions}")
            console.print(f"  [dim]puntuación:[/dim] {summary.total_score:.1f}/{summary.max_score:.1f}")
            console.print(f"  [dim]porcentaje:[/dim] {summary.percentage:.1%}")
            console.print(f"  [dim]modo:[/dim]       {report.mode}")
            if strict:
                console.print(f"  [dim]estricto:[/dim]   ESTRICTO")

            # Format time
            time_sec = report.grading_time_ms / 1000
            time_str = f"{time_sec:.1f} sec" if time_sec < 60 else f"{time_sec/60:.1f} min"
            console.print(f"  [dim]tiempo:[/dim]     {time_str}")

            # Show by-type breakdown
            if summary.by_type:
                console.print(f"\n[bold]Por tipo de pregunta:[/bold]")
                for q_type, data in summary.by_type.items():
                    if data["total"] > 0:
                        console.print(f"  {q_type}: {data['correct']}/{data['total']}")

            # Show by-unit breakdown
            if summary.by_unit:
                console.print(f"\n[bold]Por unidad:[/bold]")
                for unit_id, data in summary.by_unit.items():
                    pct = data["score"] / data["max"] if data["max"] > 0 else 0
                    short_id = unit_id.split("-")[-1] if "-" in unit_id else unit_id
                    console.print(f"  {short_id}: {data['score']:.1f}/{data['max']:.1f} ({pct:.0%})")

            # Show warnings
            for warning in result.warnings:
                console.print(f"  [yellow]⚠ {warning}[/yellow]")

        else:
            console.print(f"[red]✗ {result.message}[/red]")
            for warning in result.warnings:
                console.print(f"  [yellow]• {warning}[/yellow]")
            raise typer.Exit(code=1)

    except ExamGradingError as e:
        console.print(f"[red]✗ Error de calificación: {e}[/red]")
        raise typer.Exit(code=1)
    except Exception as e:
        error_msg = str(e)
        if "connect" in error_msg.lower() or "connection" in error_msg.lower():
            console.print(f"[red]✗ No se pudo conectar al servidor LLM[/red]")
            console.print("  Verifica que LM Studio esté corriendo en localhost:1234")
        else:
            console.print(f"[red]✗ Error: {e}[/red]")
        raise typer.Exit(code=1)


@app.command(name="exam-review")
def exam_review(
    exam_attempt_id: str = typer.Argument(
        ..., help="Exam attempt/grade ID (e.g., 'test-book-ch01-exam01-a01')"
    ),
) -> None:
    """Review a graded exam with Rich formatting.

    Displays a summary panel with score, pass/fail status, and breakdown
    by unit and question type, followed by a table of per-question results.

    Accepts the exam_attempt_id (which is also the grade report filename).
    """
    import os
    import re
    import json
    from rich.table import Table
    from rich.panel import Panel

    data_dir = Path(os.environ.get("TEACHING_DATA_DIR", "data"))

    # Validate ID format: {book_id}-ch{NN}-exam{XX}-a{NN}
    match = re.match(r"(.+)-ch\d{2}-exam\d{2}-a\d{2}$", exam_attempt_id)
    if not match:
        console.print(f"[red]✗ Formato de ID inválido: {exam_attempt_id}[/red]")
        console.print("  Formato esperado: {{book_id}}-ch{{XX}}-exam{{ZZ}}-a{{NN}}")
        raise typer.Exit(code=1)

    # Extract book_id
    full_id = match.group(0)
    parts = full_id.rsplit("-ch", 1)
    book_id = parts[0]

    grade_path = data_dir / "books" / book_id / "artifacts" / "exam_grades" / f"{exam_attempt_id}.json"

    # Check existence
    if not grade_path.exists():
        console.print(f"[yellow]⚠ Calificación de examen no encontrada: {exam_attempt_id}[/yellow]")
        console.print(f"  Ejecuta primero: teach exam-grade {exam_attempt_id}")
        raise typer.Exit(code=1)

    # Load grade report
    with open(grade_path, encoding="utf-8") as f:
        report = json.load(f)

    # Extract data
    summary = report["summary"]
    results = report["results"]

    # Header panel
    status = "APROBADO" if summary["passed"] else "NO APROBADO"
    color = "green" if summary["passed"] else "red"
    strict_text = " (ESTRICTO)" if report.get("strict") else ""

    header = (
        f"[bold]{summary['percentage']:.1%}[/bold] - [{color}]{status}[/{color}]{strict_text}\n"
        f"Correctas: {summary['correct_count']}/{summary['total_questions']} | "
        f"Puntos: {summary['total_score']:.1f}/{summary['max_score']:.1f}\n"
        f"Modo: {report['mode']} | LLM: {report['provider']}/{report['model']}"
    )
    console.print(Panel(header, title=f"[bold]{exam_attempt_id}[/bold]", expand=False))

    # By-type summary (if available)
    if summary.get("by_type"):
        console.print("\n[bold]Por tipo:[/bold]")
        for q_type, data in summary["by_type"].items():
            if data["total"] > 0:
                console.print(f"  {q_type}: {data['correct']}/{data['total']}")

    # By-unit summary (if available)
    if summary.get("by_unit"):
        console.print("\n[bold]Por unidad:[/bold]")
        for unit_id, data in summary["by_unit"].items():
            pct = data["score"] / data["max"] if data["max"] > 0 else 0
            short_id = unit_id.split("-")[-1] if "-" in unit_id else unit_id
            console.print(f"  {short_id}: {data['score']:.1f}/{data['max']:.1f} ({pct:.0%})")

    # Results table
    table = Table(show_header=True, header_style="bold")
    table.add_column("Pregunta", style="cyan", width=12)
    table.add_column("Estado", justify="center", width=10)
    table.add_column("Score", justify="center", width=8)
    table.add_column("Unidad", width=10)
    table.add_column("Feedback", width=50)

    for r in results:
        # Extract short question ID (e.g., "q01")
        q_id = r["question_id"].split("-")[-1]

        # Determine result symbol
        if r["is_correct"] is True:
            status_icon = "[green]✓[/green]"
        elif r["is_correct"] is False:
            status_icon = "[red]✗[/red]"
        else:
            status_icon = "[yellow]?[/yellow]"

        # Truncate feedback
        feedback = _truncate(r.get("feedback", ""), 60)

        # Extract short unit ID
        source_unit = r.get("source_unit_id", "?")
        short_unit = source_unit.split("-")[-1] if source_unit and "-" in source_unit else source_unit or "?"

        table.add_row(q_id, status_icon, f"{r['score']:.0%}", short_unit, feedback)

    console.print("\n")
    console.print(table)
    console.print(f"\n[dim]Archivo:[/dim] {grade_path}")


@app.command()
def status() -> None:
    """[F4] View student progress status."""
    _abort_future_phase(4, "status")


@app.command()
def study(
    unit_id: str = typer.Argument(..., help="Unit ID (e.g., 'book_id:unit:5')"),
) -> None:
    """[F4] Start an interactive study session."""
    _abort_future_phase(4, "study")


@app.command(name="next")
def next_activity() -> None:
    """[F4] Advance to the next suggested activity."""
    _abort_future_phase(4, "next")


# =============================================================================
# DATA MANAGEMENT COMMANDS - Explicit cleanup with confirmation
# =============================================================================


@app.command()
def reset(
    book_id: str = typer.Argument(
        ..., help="Book ID to reset (e.g., 'martin-2008-clean')"
    ),
    keep_source: bool = typer.Option(
        True, "--keep-source/--delete-source",
        help="Keep source file (default: keep)"
    ),
    yes: bool = typer.Option(
        False, "--yes", "-y", help="Skip confirmation prompt"
    ),
) -> None:
    """Reset a book to its imported state (delete extracted/normalized/outline data).

    This removes:
    - raw/ (extracted text)
    - normalized/ (normalized text)
    - outline/ (structure data)
    - artifacts/ (generated notes, exercises)

    Keeps:
    - source/ (original PDF/EPUB) unless --delete-source
    - book.json (metadata)
    - Database record
    """
    import shutil

    resolved_id = _resolve_book_id_or_exit(book_id)
    book_path = Path("data/books") / resolved_id

    if not book_path.exists():
        console.print(f"[red]✗ Directorio no encontrado: {book_path}[/red]")
        raise typer.Exit(code=1)

    # List what will be deleted
    dirs_to_delete = []
    for subdir in ["raw", "normalized", "outline", "artifacts"]:
        subpath = book_path / subdir
        if subpath.exists() and any(subpath.iterdir()):
            dirs_to_delete.append(subdir)

    if not keep_source:
        source_path = book_path / "source"
        if source_path.exists():
            dirs_to_delete.append("source")

    if not dirs_to_delete:
        console.print(f"[yellow]Nada que resetear en {resolved_id}[/yellow]")
        return

    # Show what will be deleted
    console.print(f"\n[bold]Se eliminarán los siguientes directorios de {resolved_id}:[/bold]")
    for d in dirs_to_delete:
        console.print(f"  [red]• {d}/[/red]")

    # Confirm
    if not yes:
        confirm = typer.confirm("\n¿Continuar?")
        if not confirm:
            console.print("[yellow]Cancelado[/yellow]")
            raise typer.Exit(code=0)

    # Delete directories
    for subdir in dirs_to_delete:
        subpath = book_path / subdir
        if subpath.exists():
            shutil.rmtree(subpath)
            console.print(f"  [dim]Eliminado:[/dim] {subdir}/")

    # Recreate empty structure (except source if deleted)
    for subdir in ["raw/pages", "normalized", "outline", "artifacts/notes"]:
        if subdir.startswith("source") and not keep_source:
            continue
        subpath = book_path / subdir
        subpath.mkdir(parents=True, exist_ok=True)

    console.print(f"\n[green]✓ Reset completado: {resolved_id}[/green]")


@app.command()
def purge(
    all_books: bool = typer.Option(
        False, "--all", help="Purge ALL books and database"
    ),
    yes: bool = typer.Option(
        False, "--yes", "-y", help="Skip first confirmation"
    ),
) -> None:
    """Purge all data (DESTRUCTIVE - requires double confirmation).

    This permanently deletes:
    - data/ directory (all books and artifacts)
    - db/ directory (database)

    Use with extreme caution!
    """
    import shutil

    if not all_books:
        console.print("[yellow]Uso: teach purge --all[/yellow]")
        console.print("  Este comando requiere --all para confirmar la intención.")
        raise typer.Exit(code=1)

    data_path = Path("data")
    db_path = Path("db")

    paths_to_delete = []
    if data_path.exists():
        paths_to_delete.append(("data/", data_path))
    if db_path.exists():
        paths_to_delete.append(("db/", db_path))

    if not paths_to_delete:
        console.print("[yellow]No hay datos que eliminar[/yellow]")
        return

    # First warning
    console.print("\n[bold red]⚠️  ADVERTENCIA: OPERACIÓN DESTRUCTIVA  ⚠️[/bold red]")
    console.print("\nSe eliminarán PERMANENTEMENTE:")
    for name, path in paths_to_delete:
        console.print(f"  [red]• {name}[/red]")

    # First confirmation
    if not yes:
        confirm1 = typer.confirm("\n¿Estás seguro de que quieres eliminar TODOS los datos?")
        if not confirm1:
            console.print("[yellow]Cancelado[/yellow]")
            raise typer.Exit(code=0)

    # Second confirmation (always required)
    console.print("\n[bold yellow]Segunda confirmación requerida.[/bold yellow]")
    confirm_text = typer.prompt(
        "Escribe 'ELIMINAR TODO' para confirmar",
        default="",
    )

    if confirm_text != "ELIMINAR TODO":
        console.print("[yellow]Cancelado - texto de confirmación incorrecto[/yellow]")
        raise typer.Exit(code=0)

    # Delete everything
    for name, path in paths_to_delete:
        shutil.rmtree(path)
        console.print(f"  [dim]Eliminado:[/dim] {name}")

    console.print("\n[green]✓ Purge completado - todos los datos han sido eliminados[/green]")


@app.command(name="list")
def list_books() -> None:
    """List all imported books."""
    from teaching.db.books_repository import get_all_books

    books = get_all_books()

    if not books:
        console.print("[yellow]No hay libros importados[/yellow]")
        console.print("  Usa: teach import-book <archivo.pdf>")
        return

    console.print(f"\n[bold]Libros importados ({len(books)}):[/bold]\n")

    for book in books:
        status_color = {
            "imported": "blue",
            "extracted": "cyan",
            "outlined": "green",
            "planned": "yellow",
            "active": "magenta",
            "completed": "green",
        }.get(book.status, "white")

        console.print(f"  [bold]{book.book_id}[/bold]")
        console.print(f"    [dim]title:[/dim]  {book.title}")
        console.print(f"    [dim]status:[/dim] [{status_color}]{book.status}[/{status_color}]")
        console.print()


# =============================================================================
# F7 - TUTOR MODE
# =============================================================================


def _ask_exam_question_tutor(
    num: int, total: int, question: dict, console: Console
) -> str | int | bool:
    """Ask an exam question interactively (for tutor mode).

    Similar to _ask_exam_question but without relying on exercise_id.
    """
    q_type = question.get("type", "")
    q_text = question.get("question", "")
    options = question.get("options", [])

    console.print(f"\n[bold]Pregunta {num}/{total}[/bold] ({q_type})")
    console.print(f"  {q_text}")

    if q_type == "multiple_choice":
        for i, opt in enumerate(options):
            console.print(f"    [dim]{i})[/dim] {opt}")
        n_options = len(options)
        while True:
            raw = typer.prompt(f"Elige una opción (0-{n_options - 1})")
            try:
                choice = int(raw.strip())
                if 0 <= choice < n_options:
                    return choice
                console.print(f"[yellow]⚠ Debe ser 0-{n_options - 1}[/yellow]")
            except ValueError:
                console.print("[yellow]⚠ Ingresa un número[/yellow]")

    elif q_type == "true_false":
        TRUE_VALUES = {"true", "t", "y", "yes", "1", "verdadero", "sí", "si"}
        FALSE_VALUES = {"false", "f", "n", "no", "0", "falso"}
        while True:
            raw = typer.prompt("Responde true/false (t/f, y/n, 1/0)").strip().lower()
            if raw in TRUE_VALUES:
                return True
            if raw in FALSE_VALUES:
                return False
            console.print("[yellow]⚠ Responde: true/false, t/f, y/n, 1/0[/yellow]")

    else:  # short_answer
        while True:
            raw = typer.prompt("Respuesta").strip()
            if raw:
                return raw
            console.print("[yellow]⚠ La respuesta no puede estar vacía[/yellow]")


def _run_unit_mini_quiz(
    unit_id: str,
    data_dir: Path,
    provider: str,
    model: str,
    console_obj: Console,
    n_questions: int = 5,
) -> bool:
    """Run a quick 5-question quiz for a unit.

    Args:
        unit_id: Unit to quiz on
        data_dir: Data directory
        provider: LLM provider
        model: LLM model
        console_obj: Rich console
        n_questions: Number of questions (default 5)

    Returns:
        True if passed (>=60%), False otherwise
    """
    from teaching.core.exercise_generator import generate_exercises
    from teaching.core.grader import grade_attempt
    from teaching.core.attempt_repository import Answer

    console_obj.print(f"\n[blue]Generando {n_questions} preguntas...[/blue]")

    # Generate exercises
    result = generate_exercises(
        unit_id=unit_id,
        data_dir=data_dir,
        difficulty="mid",
        types=["quiz"],
        n=n_questions,
        provider=provider,
        model=model,
    )

    if not result.success:
        console_obj.print(f"[yellow]⚠ No se pudo generar el quiz: {result.message}[/yellow]")
        return True  # Don't block progress

    exercises = result.exercises
    exercise_set_id = result.metadata.exercise_set_id

    console_obj.print(f"\n[bold]📝 Mini-Quiz: {n_questions} preguntas[/bold]")
    console_obj.print("[dim]Responde cada pregunta. Se calificará al final.[/dim]\n")

    # Interactive questions
    answers = []
    for i, ex in enumerate(exercises, 1):
        response = _ask_question(i, len(exercises), ex, console_obj)
        answers.append(Answer(exercise_id=ex.exercise_id, response=response))

    # Submit attempt
    attempt_result = _submit_interactive_attempt(exercise_set_id, answers, data_dir)

    # Grade with strict mode
    console_obj.print("\n[blue]Calificando...[/blue]")
    grade_result = grade_attempt(
        attempt_id=attempt_result["attempt_id"],
        data_dir=data_dir,
        provider=provider,
        model=model,
        strict=True,  # Strict grading for mini-quiz
    )

    if not grade_result.success:
        console_obj.print(f"[yellow]⚠ Error al calificar: {grade_result.message}[/yellow]")
        return True  # Don't block progress

    summary = grade_result.report.summary
    passed = summary.passed

    # Display result
    status_text = "✓ Aprobado" if passed else "✗ No aprobado"
    status_color = "green" if passed else "yellow"

    console_obj.print(f"\n[bold][{status_color}]{status_text}: {summary.percentage:.0%}[/{status_color}][/bold]")
    console_obj.print(f"[dim]Correctas: {summary.correct_count}/{summary.total_questions}[/dim]")

    # Show feedback for incorrect answers
    if not passed:
        console_obj.print("\n[cyan]Revisión de respuestas incorrectas:[/cyan]")
        for grade in grade_result.report.results:
            if not grade.is_correct:
                # Find the exercise
                ex = next((e for e in exercises if e.exercise_id == grade.exercise_id), None)
                if ex:
                    question_preview = ex.question[:60] + "..." if len(ex.question) > 60 else ex.question
                    console_obj.print(f"\n  [yellow]P:[/yellow] {question_preview}")
                    console_obj.print(f"  [green]R:[/green] {ex.correct_answer}")
                    if grade.feedback:
                        console_obj.print(f"  [dim]{grade.feedback}[/dim]")

    return passed


def _run_tutor_exam_flow(
    book_id: str,
    chapter_number: int,
    data_dir: Path,
    provider: str,
    model: str,
) -> str | None:
    """Generate exam set, handling invalid results with retry options.

    Returns exam_set_id if successful, None if failed/skipped.
    """
    chapter = f"ch{chapter_number:02d}"
    max_retries = 2
    n_questions = 12

    for attempt in range(max_retries + 1):
        console.print(f"\n[blue]Generando examen para capítulo {chapter_number}...[/blue]")

        result = generate_chapter_exam(
            book_id=book_id,
            chapter=chapter,
            data_dir=data_dir,
            n=n_questions,
            difficulty="mid",
            provider=provider,
            model=model,
        )

        if result.success and result.metadata and result.metadata.valid:
            console.print(f"[green]✓ Examen generado: {result.metadata.exam_set_id}[/green]")
            return result.metadata.exam_set_id

        # Handle invalid/failed exam
        if not result.success:
            console.print(f"[red]✗ Error: {result.message}[/red]")
        elif result.metadata and not result.metadata.valid:
            console.print("[yellow]⚠ Examen marcado como inválido:[/yellow]")
            for w in result.metadata.validation_warnings:
                console.print(f"  [yellow]• {w}[/yellow]")

        if attempt < max_retries:
            console.print("\n[cyan]Opciones:[/cyan]")
            console.print("  1. Reintentar generación")
            console.print("  2. Reducir preguntas a 8")
            console.print("  3. Saltar examen")

            choice = typer.prompt("Elige opción (1-3)", default="1")

            if choice == "1":
                continue  # Retry with same params
            elif choice == "2":
                n_questions = 8  # Reduce complexity
                continue
            elif choice == "3":
                return None
            else:
                continue
        else:
            console.print("[red]Máximo de reintentos alcanzado[/red]")
            if typer.confirm("¿Saltar examen?", default=True):
                return None

    return None


def _run_tutor_exam_quiz_flow(
    exam_set_id: str,
    data_dir: Path,
    provider: str,
    model: str,
    book_id: str,
) -> tuple[bool, str | None]:
    """Run interactive exam and return whether passed.

    Returns tuple of (passed: bool, exam_attempt_id: str | None)
    """
    # Load exam set
    exam_set = load_exam_set(exam_set_id, data_dir)
    if not exam_set:
        console.print(f"[red]✗ Examen no encontrado: {exam_set_id}[/red]")
        return False, None

    questions = exam_set.get("questions", [])

    # Check if exam is valid for auto-grading
    exam_valid = exam_set.get("valid", True)
    exam_mode = exam_set.get("mode", "json")

    if not exam_valid:
        console.print("\n[yellow bold]⚠ Este examen está marcado como inválido.[/yellow bold]")
        console.print("[yellow]Las respuestas MCQ/TF no serán auto-calificadas.[/yellow]")
    elif exam_mode == "text_fallback":
        console.print("\n[yellow]⚠ Este examen fue generado con text_fallback.[/yellow]")
        console.print("[yellow]Las respuestas MCQ/TF serán marcadas para revisión.[/yellow]")

    # Show exam info
    console.print(f"\n[bold]Examen: {exam_set.get('chapter_title', exam_set_id)}[/bold]")
    console.print(f"[dim]Preguntas:[/dim] {len(questions)}")
    console.print(f"[dim]Umbral:[/dim] {exam_set.get('passing_threshold', 0.6):.0%}")

    if not typer.confirm("\n¿Empezar el examen?", default=True):
        return False, None

    # Interactive questions
    answers = []
    for i, q in enumerate(questions, 1):
        response = _ask_exam_question_tutor(i, len(questions), q, console)
        answers.append(ExamAnswer(question_id=q["question_id"], response=response))

    # Submit attempt
    attempt_result = _submit_interactive_exam_attempt(exam_set_id, answers, data_dir)
    exam_attempt_id = attempt_result["exam_attempt_id"]

    console.print(f"\n[green]✓ Intento guardado: {exam_attempt_id}[/green]")

    # Grade
    console.print("[blue]Calificando (modo ESTRICTO)...[/blue]")
    grade_result = grade_exam_attempt(
        exam_attempt_id=exam_attempt_id,
        data_dir=data_dir,
        provider=provider,
        model=model,
        strict=True,
    )

    if grade_result.success:
        summary = grade_result.report.summary
        status = "Aprobado" if summary.passed else "No aprobado"
        color = "green" if summary.passed else "red"
        console.print(f"\n[bold]Resultado: {summary.percentage:.1%} - [{color}]{status}[/{color}][/bold]")
        console.print(f"[dim]Correctas:[/dim] {summary.correct_count}/{summary.total_questions}")

        # Show weak units if failed
        if not summary.passed and summary.by_unit:
            console.print("\n[yellow]Unidades débiles:[/yellow]")
            for unit_id, unit_data in summary.by_unit.items():
                max_score = unit_data.get("max", 1)
                unit_score = unit_data.get("score", 0)
                pct = unit_score / max_score if max_score > 0 else 0
                if pct < 0.6:
                    short_id = unit_id.split("-")[-1] if "-" in unit_id else unit_id
                    console.print(f"  [red]• {short_id}: {pct:.0%}[/red]")

        return summary.passed, exam_attempt_id
    else:
        console.print(f"[yellow]⚠ Error calificando: {grade_result.message}[/yellow]")
        return False, exam_attempt_id


@app.command()
def tutor(
    stop_session: bool = typer.Option(
        False, "--stop", help="Cerrar la sesión actual limpiamente"
    ),
    provider: str | None = typer.Option(
        None, "-p", "--provider", help="LLM provider: lmstudio, openai, anthropic"
    ),
    model: str | None = typer.Option(
        None, "-m", "--model", help="Nombre del modelo (override de config)"
    ),
    pace: str = typer.Option(
        "normal",
        "--pace",
        help="Velocidad de texto: slow, normal, fast",
    ),
    student: str | None = typer.Option(
        None,
        "--student",
        help="Nombre o ID del estudiante (salta el lobby)",
    ),
    list_students: bool = typer.Option(
        False,
        "--list-students",
        help="Listar estudiantes y salir",
    ),
) -> None:
    """Iniciar o reanudar sesión de tutor interactivo (teaching-first).

    El tutor te guía a través del estudio de un libro capítulo por capítulo:

    1. Selecciona un estudiante en el lobby Academia
    2. Selecciona un libro para estudiar
    3. El tutor explica punto por punto (clase guiada)
    4. Responde preguntas y verifica comprensión
    5. Toma el examen de capítulo
    6. Avanza al siguiente capítulo

    Comandos durante la sesión:
    - 'adelante': avanzar al siguiente punto
    - 'apuntes': ver apuntes completos de la unidad
    - 'control': lanzar mini-quiz de 5 preguntas
    - 'examen': lanzar examen de capítulo
    - 'stop': salir guardando progreso

    Ejemplos:

        teach tutor                  # Iniciar/reanudar sesión

        teach tutor --student Sergio # Ir directo con un estudiante

        teach tutor --list-students  # Ver estudiantes registrados

        teach tutor --pace slow      # Texto más lento

        teach tutor --stop           # Cerrar sesión
    """
    import os
    from datetime import datetime, timezone
    from typing import Iterator
    from rich.live import Live
    from rich.markdown import Markdown
    from rich.panel import Panel
    from rich.text import Text
    from teaching.core.tutor import (
        TutorState,
        load_tutor_state,
        save_tutor_state,
        list_available_books_with_metadata,
        get_chapter_info,
        get_units_for_chapter,
        load_chapter_notes,
        get_missing_notes_units,
        answer_question,
        generate_chapter_opening,
        extract_notes_summary,
        # Teaching-first mode (F7.3)
        TeachingPlan,
        TeachingPoint,
        generate_teaching_plan,
        explain_point,
        check_comprehension,
        reexplain_with_analogy,
        # Bug fixes F7.3.1
        detect_more_examples_intent,
        generate_more_examples,
        # UX fixes F7.4
        TutorPromptKind,
        is_advance_intent,
        is_affirmative,
        generate_deeper_explanation,
        # UX fixes F8.1
        is_negative,
        parse_confirm_advance_response,
        # UX fixes F8.2.1
        is_review_intent,
        parse_post_failure_choice_response,
        # F8.3: Teaching-first class flow
        TutorEvent,
        TutorEventType,
        generate_unit_opening,
        # Multi-student support (F7.3 Academia)
        StudentProfile,
        StudentsState,
        load_students_state,
        save_students_state,
        save_student_progress,
    )
    from teaching.config.personas import get_persona, TeachingPolicy
    from teaching.utils.text_utils import strip_think_streaming, ThrottledStreamer

    # ==========================================================================
    # F8.2: Helper functions for strictness policy
    # ==========================================================================

    def get_teaching_policy(student: StudentProfile | None) -> TeachingPolicy:
        """Get teaching policy for a student based on their persona.

        Args:
            student: The current student profile

        Returns:
            TeachingPolicy with appropriate strictness settings
        """
        if student is None:
            return TeachingPolicy()

        persona_id = student.tutor_persona_id or "dra_vega"
        persona = get_persona(persona_id)

        if persona is None:
            return TeachingPolicy()

        return persona.get_teaching_policy()

    def should_retry(
        current_attempts: int,
        policy: TeachingPolicy,
    ) -> bool:
        """Determine if the student should get another attempt.

        Args:
            current_attempts: Number of attempts so far (1 = first try failed)
            policy: Teaching policy from persona

        Returns:
            True if student should retry, False if should go to remediation
        """
        return current_attempts < policy.max_attempts_per_point

    def should_offer_advance(
        policy: TeachingPolicy,
    ) -> bool:
        """Determine if we should offer the 'escape hatch' to advance after failure.

        Args:
            policy: Teaching policy from persona

        Returns:
            True if should offer advance option
        """
        return policy.allow_advance_on_failure

    # Helper: Render streaming response with Rich Live
    def _render_streaming_response(
        stream: Iterator[str],
        console_obj: Console,
        use_markdown: bool = True,
    ) -> str:
        """Render streaming LLM response with Rich Live display.

        Filters out <think> tags in real-time.

        Returns the complete response text.
        """
        full_response = ""
        buffer = ""
        in_think = False

        with Live(Text(""), console=console_obj, refresh_per_second=10) as live:
            for chunk in stream:
                output, buffer, in_think = strip_think_streaming(chunk, buffer, in_think)
                full_response += output
                if use_markdown:
                    live.update(Markdown(full_response))
                else:
                    live.update(Text(full_response))

        # Flush remaining buffer
        if buffer and not in_think:
            full_response += buffer

        return full_response.strip()

    # Helper: Import book inline during tutor session
    def _handle_inline_import(data_dir_path: Path, console_obj: Console) -> str | None:
        """Import a book during tutor session.

        Returns book_id if successful, None otherwise.
        """
        from teaching.core.book_importer import import_book as do_import, DuplicateBookError

        console_obj.print("\n[cyan]📕 Añadir nuevo libro[/cyan]")
        console_obj.print("[dim]Escribe 'cancelar' para volver al menú[/dim]\n")

        file_path = typer.prompt("Ruta al archivo PDF/EPUB").strip()

        if file_path.lower() == "cancelar":
            return None

        # Expand user path and resolve
        path = Path(file_path).expanduser().resolve()

        if not path.exists():
            console_obj.print(f"[red]✗ Archivo no encontrado: {path}[/red]")
            return None

        # Ask for optional metadata
        title = typer.prompt("Título (Enter para usar nombre del archivo)", default="").strip() or None

        try:
            console_obj.print("[blue]Importando libro...[/blue]")
            result = do_import(
                file_path=path,
                title=title,
                data_dir=data_dir_path,
            )

            if result.success:
                console_obj.print(f"[green]✓ Libro importado: {result.book_id}[/green]")
                console_obj.print("[dim]Para prepararlo completamente, ejecuta:[/dim]")
                console_obj.print(f"[dim]  teach outline {result.book_id}[/dim]")
                console_obj.print(f"[dim]  teach units {result.book_id}[/dim]")
                return result.book_id
            else:
                console_obj.print(f"[red]✗ Error: {result.message}[/red]")
                return None

        except DuplicateBookError as e:
            console_obj.print(f"[yellow]⚠ El libro ya existe: {e.existing_book_id}[/yellow]")
            return e.existing_book_id
        except Exception as e:
            console_obj.print(f"[red]✗ Error al importar: {e}[/red]")
            return None

    # Helper: Academia Lobby for multi-student selection
    def _show_academia_lobby(
        students_state: StudentsState,
        data_dir_path: Path,
        console_obj: Console,
    ) -> StudentProfile | None:
        """Show Academia lobby and handle student selection/creation/deletion.

        Returns the selected StudentProfile, or None if user wants to exit.
        """
        while True:
            # Header
            console_obj.print("\n" + "=" * 50)
            console_obj.print("[bold cyan]🏛️  ACADEMIA DE APRENDIZAJE[/bold cyan]")
            console_obj.print("=" * 50)

            # List existing students
            if students_state.students:
                console_obj.print("\n[bold]Estudiantes:[/bold]\n")
                for i, s in enumerate(students_state.students, 1):
                    active = " ⭐" if s.student_id == students_state.active_student_id else ""
                    console_obj.print(f"  {i}. {s.name}{active}")
            else:
                console_obj.print("\n[dim]No hay estudiantes registrados.[/dim]")

            # Options
            console_obj.print("\n[bold]Opciones:[/bold]")
            console_obj.print("  0. ➕ Nuevo estudiante")
            if students_state.students:
                console_obj.print("  D. 🗑️  Eliminar estudiante")
            console_obj.print("  S. Salir")
            console_obj.print()

            # Get input
            choice = typer.prompt("Elige").strip()

            if choice.lower() == "s":
                console_obj.print("[dim]¡Hasta pronto![/dim]")
                return None

            if choice == "0":
                # Create new student
                console_obj.print("\n[cyan]➕ Nuevo estudiante[/cyan]")
                name = typer.prompt("Nombre").strip()
                if not name:
                    console_obj.print("[yellow]⚠ El nombre no puede estar vacío.[/yellow]")
                    continue
                if name.lower() == "cancelar":
                    continue

                # Check if name already exists
                if students_state.get_student_by_name(name):
                    console_obj.print(f"[yellow]⚠ Ya existe un estudiante con ese nombre.[/yellow]")
                    continue

                new_student = students_state.add_student(name)
                students_state.active_student_id = new_student.student_id
                save_students_state(students_state, data_dir_path)
                console_obj.print(f"\n[green]✓ ¡Bienvenido/a, {name}![/green]")
                return new_student

            if choice.lower() == "d" and students_state.students:
                # Delete student (F8: strict confirmation)
                if len(students_state.students) == 1:
                    console_obj.print("[red]✗ No puedes eliminar el único estudiante.[/red]")
                    continue

                console_obj.print("\n[red]🗑️  Eliminar estudiante[/red]")
                console_obj.print("Estudiantes:")
                for i, s in enumerate(students_state.students, 1):
                    # Show full name if surname exists
                    display_name = s.full_name if hasattr(s, "full_name") else s.name
                    console_obj.print(f"  {i}. {display_name} ({s.student_id})")

                del_choice = typer.prompt("Número del estudiante a eliminar (o 'cancelar')").strip()
                if del_choice.lower() == "cancelar":
                    continue

                try:
                    del_idx = int(del_choice) - 1
                    if 0 <= del_idx < len(students_state.students):
                        to_delete = students_state.students[del_idx]
                        full_name = to_delete.full_name if hasattr(to_delete, "full_name") else to_delete.name

                        # F8: Strict confirmation
                        console_obj.print(f"\n[bold red]⚠️  ELIMINAR ESTUDIANTE[/bold red]")
                        console_obj.print("[red]Esta acción es irreversible.[/red]")
                        console_obj.print(f"\nPara confirmar, escribe exactamente:")
                        console_obj.print(f"  [bold]DELETE {to_delete.student_id}[/bold]")
                        console_obj.print(f"  o el nombre completo: [bold]{full_name}[/bold]")

                        confirm = typer.prompt("\nConfirmación").strip()

                        # Check strict confirmation
                        expected_delete = f"DELETE {to_delete.student_id}"
                        if confirm == expected_delete or confirm.lower() == full_name.lower():
                            students_state.remove_student(to_delete.student_id)
                            save_students_state(students_state, data_dir_path)
                            console_obj.print(f"[green]✓ Estudiante {to_delete.name} eliminado.[/green]")
                        else:
                            console_obj.print("[yellow]Eliminación cancelada.[/yellow]")
                    else:
                        console_obj.print("[yellow]⚠ Número no válido.[/yellow]")
                except ValueError:
                    console_obj.print("[yellow]⚠ Introduce un número.[/yellow]")
                continue

            # Try to select a student by number
            try:
                idx = int(choice) - 1
                if 0 <= idx < len(students_state.students):
                    selected = students_state.students[idx]
                    students_state.active_student_id = selected.student_id
                    save_students_state(students_state, data_dir_path)
                    console_obj.print(f"\n[green]¡Hola, {selected.name}![/green]")
                    return selected
                else:
                    console_obj.print("[yellow]⚠ Número no válido.[/yellow]")
            except ValueError:
                console_obj.print("[yellow]⚠ Opción no reconocida.[/yellow]")

    data_dir = Path(os.environ.get("TEACHING_DATA_DIR", "data"))

    # Load multi-student state
    students_state = load_students_state(data_dir)

    # Handle --list-students flag
    if list_students:
        if not students_state.students:
            console.print("[dim]No hay estudiantes registrados.[/dim]")
        else:
            console.print("\n[bold cyan]📚 Estudiantes registrados:[/bold cyan]\n")
            for s in students_state.students:
                active = "⭐ " if s.student_id == students_state.active_student_id else "   "
                console.print(f"{active}{s.student_id}: {s.name}")
        return

    # Handle --stop flag
    if stop_session:
        active_student = students_state.get_active_student()
        if active_student:
            active_student.tutor_state.active_book_id = None
            save_students_state(students_state, data_dir)
        console.print("[green]✓ Sesión cerrada. Progreso guardado.[/green]")
        return

    # Resolve provider/model
    config = LLMConfig.from_yaml()
    effective_provider = provider if provider else config.provider
    effective_model = model if model else config.model

    # === PHASE 0: Academia Lobby (Multi-student) ===
    active_student: StudentProfile | None = None

    # Handle --student flag to skip lobby
    if student:
        # Try to find by ID or name
        active_student = students_state.get_student_by_id(student)
        if not active_student:
            active_student = students_state.get_student_by_name(student)
        if not active_student:
            console.print(f"[red]✗ Estudiante no encontrado: {student}[/red]")
            console.print("[dim]Usa --list-students para ver los registrados.[/dim]")
            return
        students_state.active_student_id = active_student.student_id
        save_students_state(students_state, data_dir)
    else:
        # Show Academia lobby
        active_student = _show_academia_lobby(students_state, data_dir, console)
        if active_student is None:
            # User chose to exit
            return

    # At this point we have an active student
    state = active_student.tutor_state
    state.user_name = active_student.name  # Ensure name is synced

    # Personalized greeting
    name_str = f", {state.user_name}" if state.user_name else ""

    # === PHASE 1: Book Selection ===
    console.print(f"\n[bold]¿Qué quieres estudiar hoy{name_str}?[/bold]\n")

    books = list_available_books_with_metadata(data_dir)

    # Show option to add new book
    console.print("  [dim]0. 📕 Añadir nuevo libro[/dim]")

    if books:
        # Show books with progress
        for i, book in enumerate(books, 1):
            prog = state.get_book_progress(book["book_id"])
            progress_str = ""
            if prog.completed_chapters:
                progress_str = f" [dim](capítulos {len(prog.completed_chapters)}/{book['total_chapters']} completados)[/dim]"
            elif prog.last_chapter_number > 0:
                progress_str = f" [dim](en capítulo {prog.last_chapter_number})[/dim]"
            console.print(f"  {i}. {book['title']}{progress_str}")
    else:
        console.print("\n  [yellow]No hay libros importados todavía.[/yellow]")

    console.print("\n[dim]Escribe 'stop' para salir[/dim]")

    # Book selection loop
    selected_book = None
    while True:
        max_choice = len(books) if books else 0
        choice = typer.prompt(f"Elige libro (0-{max_choice})")
        if choice.lower() == "stop":
            save_students_state(students_state, data_dir)
            console.print("[green]✓ Sesión cerrada.[/green]")
            return
        try:
            idx = int(choice)
            if idx == 0:
                # Handle inline import
                new_book_id = _handle_inline_import(data_dir, console)
                if new_book_id:
                    # Refresh book list
                    books = list_available_books_with_metadata(data_dir)
                    selected_book = next((b for b in books if b["book_id"] == new_book_id), None)
                    if selected_book:
                        break
                    else:
                        console.print("[yellow]El libro fue importado pero necesita ser preparado.[/yellow]")
                        console.print(f"[dim]Ejecuta: teach outline {new_book_id} && teach units {new_book_id}[/dim]")
                # Show menu again
                console.print("\n[bold]Libros disponibles:[/bold]")
                console.print("  [dim]0. 📕 Añadir nuevo libro[/dim]")
                for i, book in enumerate(books, 1):
                    console.print(f"  {i}. {book['title']}")
                continue
            elif books and 1 <= idx <= len(books):
                selected_book = books[idx - 1]
                break
        except ValueError:
            pass
        console.print("[yellow]⚠ Opción inválida[/yellow]")

    book_id = selected_book["book_id"]
    state.active_book_id = book_id
    book_progress = state.get_book_progress(book_id)

    console.print(f"\n[green]Libro seleccionado:[/green] {selected_book['title']}")

    # === PHASE 2: Resume or Start ===
    if book_progress.last_chapter_number > 0 and book_progress.last_chapter_number <= selected_book["total_chapters"]:
        resume = typer.confirm(
            f"\n¿Continuar desde capítulo {book_progress.last_chapter_number}?",
            default=True
        )
        if resume:
            current_chapter = book_progress.last_chapter_number
        else:
            current_chapter = 1
    else:
        current_chapter = 1

    # === PHASE 3: Chapter Loop ===
    total_chapters = selected_book["total_chapters"]

    while current_chapter <= total_chapters:
        # Update progress
        book_progress.last_chapter_number = current_chapter
        book_progress.last_session_at = datetime.now(timezone.utc).isoformat()
        save_students_state(students_state, data_dir)

        chapter_info = get_chapter_info(book_id, current_chapter, data_dir)
        if not chapter_info:
            console.print(f"[yellow]⚠ Capítulo {current_chapter} no encontrado[/yellow]")
            current_chapter += 1
            continue

        # Display chapter opening with context
        opening = generate_chapter_opening(book_id, current_chapter, data_dir)
        if opening:
            console.print()
            console.print(Panel(
                f"[bold]{opening['book_title']}[/bold]",
                title="📚 Libro",
                border_style="blue",
            ))
            console.print(Panel(
                f"[bold blue]Capítulo {current_chapter}: {opening['chapter_title']}[/bold blue]",
                border_style="cyan",
            ))
            if opening.get("overview"):
                console.print(f"\n[italic]{opening['overview']}[/italic]")
            if opening.get("objectives"):
                console.print("\n[bold]Objetivos de aprendizaje:[/bold]")
                for obj in opening["objectives"]:
                    console.print(f"  • {obj}")
            # Display units instead of sections (cleaner, no garbage)
            if opening.get("units"):
                console.print("\n[bold]En este capítulo veremos:[/bold]")
                total_time = sum(u.get("estimated_time_min", 0) for u in opening["units"])
                for unit in opening["units"]:
                    time_str = f" [dim](~{unit['estimated_time_min']} min)[/dim]" if unit.get("estimated_time_min") else ""
                    console.print(f"  • {unit['number']}. {unit['title']}{time_str}")
                if total_time > 0:
                    console.print(f"\n  [dim]Tiempo estimado: ~{total_time} minutos[/dim]")
            console.print()
        else:
            console.print(f"\n{'='*60}")
            console.print(f"[bold blue]Capítulo {current_chapter}: {chapter_info['title']}[/bold blue]")
            console.print(f"{'='*60}")

        # === PHASE 3a: Notes generation ===
        unit_ids = chapter_info["unit_ids"]
        missing_units = get_missing_notes_units(book_id, current_chapter, data_dir)

        if missing_units:
            console.print(f"\n[cyan]Dame un momento mientras preparo el material...[/cyan]")
            for unit_id in missing_units:
                console.print(f"  [dim]→ {unit_id}[/dim]")
                result = generate_notes(
                    unit_id=unit_id,
                    provider=effective_provider,
                    model=effective_model,
                    force=False,
                    data_dir=data_dir,
                )
                if not result.success:
                    console.print(f"    [yellow]⚠ Error: {result.message}[/yellow]")

        # Load notes for Q&A
        notes_content, units_with_notes = load_chapter_notes(book_id, current_chapter, data_dir)

        # === PHASE 3b: Teaching-First Unit Loop (F7.3) ===
        notes_dir = data_dir / "books" / book_id / "artifacts" / "notes"
        user_prompt = f"{state.user_name}:" if state.user_name else "Tú:"

        for unit_idx, unit_id in enumerate(units_with_notes):
            # Load this unit's notes
            unit_notes_path = notes_dir / f"{unit_id}.md"
            if not unit_notes_path.exists():
                continue

            unit_notes = unit_notes_path.read_text(encoding="utf-8")

            # Get unit number for display
            unit_num = unit_id.split("-u")[-1] if "-u" in unit_id else str(unit_idx + 1)
            unit_title = f"Unidad {unit_num}"

            # 1. GENERATE TEACHING PLAN (source of truth)
            plan = generate_teaching_plan(unit_notes, unit_id, unit_title)

            # 2. F8.3: APERTURA TIPO CLASE (sin mostrar apuntes)
            # Obtener nombre del estudiante y persona para personalizar
            active_student = students_state.get_active_student()
            student_name = active_student.name if active_student else ""
            persona_name = "tu tutor"
            if active_student and active_student.tutor_persona_id:
                persona = get_persona(active_student.tutor_persona_id)
                if persona:
                    persona_name = persona.name

            # Generar apertura de unidad
            opening_event = generate_unit_opening(
                unit_title=unit_title,
                plan=plan,
                student_name=student_name,
                persona_name=persona_name,
            )

            # Renderizar apertura
            console.print(f"\n[bold cyan]━━━ {unit_title} ━━━[/bold cyan]")
            console.print()
            console.print(Markdown(opening_event.markdown))

            # Esperar confirmación para empezar (respeta lenguaje natural)
            start_input = typer.prompt(f"\n{user_prompt}").strip()
            if start_input.lower() == "stop":
                save_students_state(students_state, data_dir)
                console.print("[green]✓ Sesión cerrada. Progreso guardado.[/green]")
                return

            # Si dice que no o pide apuntes, mostrar apuntes primero
            if is_negative(start_input) or start_input.lower() == "apuntes":
                console.print(f"\n[bold cyan]📝 Apuntes de la unidad:[/bold cyan]")
                console.print(Markdown(unit_notes))
                if not typer.confirm("¿Continuamos con la explicación?", default=True):
                    continue  # Siguiente unidad

            # 3. LOOP DE PUNTOS (Teaching Loop con máquina de estados)
            # F8.2: Get teaching policy for active student
            active_student = students_state.get_active_student()
            teaching_policy = get_teaching_policy(active_student)

            for point_idx, point in enumerate(plan.points):
                # Variables de estado por punto
                teaching_state = TeachingState.EXPLAINING
                explanation = ""
                last_check_question = ""
                user_input = ""
                last_prompt_kind = TutorPromptKind.NORMAL_QA  # F7.4: Trackear tipo de pregunta
                # F8.2: Per-point counters (reset for each new point)
                current_point_attempts = 0
                current_point_followups = 0

                while True:
                    # === Estado: EXPLAINING ===
                    if teaching_state == TeachingState.EXPLAINING:
                        console.print(f"\n[bold magenta]── Punto {point.number}: {point.title} ──[/bold magenta]")
                        try:
                            explanation = explain_point(
                                point=point,
                                notes_context=unit_notes,
                                provider=effective_provider,
                                model=effective_model,
                            )
                            console.print()
                            console.print(Markdown(explanation))

                            # Extraer pregunta de verificación del final
                            lines = explanation.strip().split("\n")
                            if lines and "?" in lines[-1]:
                                last_check_question = lines[-1]
                                # F7.4: Detectar tipo de pregunta
                                q_lower = last_check_question.lower()
                                if "profundizar" in q_lower or "más detalle" in q_lower or "saber más" in q_lower:
                                    last_prompt_kind = TutorPromptKind.ASK_DEEPEN
                                elif any(f"{c})" in last_check_question for c in "abcd"):
                                    last_prompt_kind = TutorPromptKind.ASK_MCQ
                                else:
                                    last_prompt_kind = TutorPromptKind.ASK_COMPREHENSION

                            teaching_state = TeachingState.WAITING_INPUT
                        except Exception as e:
                            console.print(f"[yellow]⚠ Error al explicar: {e}[/yellow]")
                            teaching_state = TeachingState.NEXT_POINT

                    # === Estado: WAITING_INPUT ===
                    elif teaching_state == TeachingState.WAITING_INPUT:
                        user_input = typer.prompt(f"\n{user_prompt}").strip()

                        # Comando: stop
                        if user_input.lower() == "stop":
                            save_students_state(students_state, data_dir)
                            console.print("[green]✓ Sesión cerrada. Progreso guardado.[/green]")
                            return

                        # === F8.1: Manejo especial para respuestas a CONFIRM_ADVANCE ===
                        if last_prompt_kind == TutorPromptKind.ASK_ADVANCE_CONFIRM:
                            parse_result = parse_confirm_advance_response(user_input)

                            if parse_result == "advance":
                                teaching_state = TeachingState.NEXT_POINT
                                continue
                            elif parse_result == "stay":
                                if detect_more_examples_intent(user_input):
                                    teaching_state = TeachingState.MORE_EXAMPLES
                                else:
                                    teaching_state = TeachingState.DEEPEN_EXPLANATION
                                continue
                            elif parse_result == "command":
                                pass  # Cae al manejo normal de comandos abajo
                            else:  # unknown
                                console.print("[dim]Responde Y para avanzar, o N para profundizar[/dim]")
                                continue

                        # === F8.2.1: Manejo especial para POST_FAILURE_CHOICE con parser dedicado ===
                        # GUARD: Nunca llama a check_comprehension, es decisión de flujo
                        if last_prompt_kind == TutorPromptKind.ASK_POST_FAILURE_CHOICE:
                            parse_result = parse_post_failure_choice_response(
                                user_input,
                                default_after_failure=teaching_policy.default_after_failure,
                            )

                            if parse_result == "advance":
                                teaching_state = TeachingState.NEXT_POINT
                                continue
                            elif parse_result == "review":
                                teaching_state = TeachingState.REMEDIATION
                                continue
                            elif parse_result == "command":
                                pass  # Cae al manejo normal de comandos abajo
                            else:  # unknown
                                console.print("[dim]Responde 'avanzar', 'repasar', 'más ejemplos' o 'stop'[/dim]")
                                continue

                        # Comando: adelante (avanzar sin evaluar) - ahora usa is_advance_intent
                        if user_input.lower() in ("adelante", "continuar", "sigo", "siguiente", "") or is_advance_intent(user_input):
                            teaching_state = TeachingState.NEXT_POINT
                            continue

                        # Comando: apuntes
                        if user_input.lower() == "apuntes":
                            console.print(f"\n[bold cyan]📝 Apuntes de la unidad:[/bold cyan]")
                            console.print(Markdown(unit_notes))
                            continue  # Sigue en WAITING_INPUT

                        # Comando: control (mini-quiz)
                        if user_input.lower() == "control":
                            _run_unit_mini_quiz(
                                unit_id=unit_id,
                                data_dir=data_dir,
                                provider=effective_provider,
                                model=effective_model,
                                console_obj=console,
                            )
                            continue  # Sigue en WAITING_INPUT

                        # Comando: examen
                        if user_input.lower() == "examen":
                            _run_tutor_exam_flow(
                                book_id=book_id,
                                chapter_number=current_chapter,
                                data_dir=data_dir,
                                provider=effective_provider,
                                model=effective_model,
                            )
                            continue  # Sigue en WAITING_INPUT

                        # *** FIX BUG 1: Detectar "más ejemplos" ANTES de evaluar ***
                        if detect_more_examples_intent(user_input):
                            teaching_state = TeachingState.MORE_EXAMPLES
                            continue

                        # *** F7.4: Respuesta afirmativa según contexto ***
                        if is_affirmative(user_input):
                            if last_prompt_kind == TutorPromptKind.ASK_DEEPEN:
                                # "Vale" a "¿Quieres profundizar?" → profundizar
                                teaching_state = TeachingState.DEEPEN_EXPLANATION
                                continue
                            elif last_prompt_kind == TutorPromptKind.ASK_ADVANCE_CONFIRM:
                                # "Sí" a "¿Avanzamos?" → avanzar
                                teaching_state = TeachingState.NEXT_POINT
                                continue
                            elif last_prompt_kind == TutorPromptKind.ASK_POST_EXAMPLES:
                                # Después de ejemplos, "sí" es ambiguo - pedir clarificación
                                console.print("[dim]¿Qué prefieres: (1) más ejemplos, (2) explicar con tus palabras, (3) avanzar?[/dim]")
                                continue  # Sigue en WAITING_INPUT
                            # else: va a CHECKING para evaluar MCQ o comprensión

                        # Input normal: evaluar comprensión
                        teaching_state = TeachingState.CHECKING

                    # === Estado: MORE_EXAMPLES (FIX BUG 1) ===
                    elif teaching_state == TeachingState.MORE_EXAMPLES:
                        # F8.2.1: Check followups limit BEFORE generating
                        current_point_followups += 1
                        if current_point_followups > teaching_policy.max_followups_per_point:
                            # Limit reached - offer choice to advance or stay
                            console.print("\n[yellow]Paremos aquí para no alargar demasiado.[/yellow]")
                            if should_offer_advance(teaching_policy):
                                teaching_state = TeachingState.POST_FAILURE_CHOICE
                            else:
                                # No escape hatch (e.g., capitan_ortega) -> go to remediation
                                teaching_state = TeachingState.REMEDIATION
                            continue

                        console.print("\n[dim]Claro, aquí tienes más ejemplos...[/dim]")
                        try:
                            more_examples = generate_more_examples(
                                point=point,
                                previous_explanation=explanation,
                                provider=effective_provider,
                                model=effective_model,
                            )
                            console.print()
                            console.print(Markdown(more_examples))

                            # F7.4: El prompt termina con opciones, no pregunta de verificación
                            # Marcar tipo para que "sí" no active CHECKING automáticamente
                            last_prompt_kind = TutorPromptKind.ASK_POST_EXAMPLES
                        except Exception as e:
                            console.print(f"[yellow]⚠ Error generando ejemplos: {e}[/yellow]")

                        # *** NO avanza: vuelve a esperar input ***
                        teaching_state = TeachingState.WAITING_INPUT

                    # === Estado: DEEPEN_EXPLANATION (F7.4) ===
                    elif teaching_state == TeachingState.DEEPEN_EXPLANATION:
                        # F8.2.1: Check followups limit BEFORE generating
                        current_point_followups += 1
                        if current_point_followups > teaching_policy.max_followups_per_point:
                            # Limit reached
                            console.print("\n[yellow]Paremos aquí para no alargar demasiado.[/yellow]")
                            if should_offer_advance(teaching_policy):
                                teaching_state = TeachingState.POST_FAILURE_CHOICE
                            else:
                                teaching_state = TeachingState.REMEDIATION
                            continue

                        console.print("\n[dim]Perfecto, profundicemos...[/dim]")
                        try:
                            deeper = generate_deeper_explanation(
                                point=point,
                                previous_explanation=explanation,
                                provider=effective_provider,
                                model=effective_model,
                            )
                            console.print()
                            console.print(Markdown(deeper))

                            # Actualizar explicación acumulada
                            explanation = explanation + "\n\n" + deeper

                            # Marcar tipo de prompt (opciones claras)
                            last_prompt_kind = TutorPromptKind.ASK_POST_EXAMPLES
                        except Exception as e:
                            console.print(f"[yellow]⚠ Error profundizando: {e}[/yellow]")

                        teaching_state = TeachingState.WAITING_INPUT

                    # === Estado: CHECKING ===
                    elif teaching_state == TeachingState.CHECKING:
                        # F8.2: Increment attempt counter
                        current_point_attempts += 1

                        try:
                            understood, feedback, needs_elaboration = check_comprehension(
                                check_question=last_check_question,
                                student_response=user_input,
                                concept_context=point.content[:500],
                                provider=effective_provider,
                                model=effective_model,
                            )
                            console.print(f"\n[cyan]{feedback}[/cyan]")

                            if understood and not needs_elaboration:
                                # F7.4: Ir a CONFIRM_ADVANCE en lugar de NEXT_POINT directo
                                teaching_state = TeachingState.CONFIRM_ADVANCE
                            elif needs_elaboration:
                                # "sí, lo entiendo" → pide elaboración, no trata como fallo
                                teaching_state = TeachingState.WAITING_INPUT
                            else:
                                # F8.2: Use policy to decide next state
                                if should_retry(current_point_attempts, teaching_policy):
                                    # Still have attempts left, ask for retry
                                    console.print("\n[dim]Inténtalo de nuevo. ¿Puedes explicarlo con tus palabras?[/dim]")
                                    teaching_state = TeachingState.AWAITING_RETRY
                                elif should_offer_advance(teaching_policy):
                                    # Out of attempts, offer choice to advance or stay
                                    teaching_state = TeachingState.POST_FAILURE_CHOICE
                                else:
                                    # No escape hatch, go to remediation
                                    teaching_state = TeachingState.REMEDIATION
                        except Exception as e:
                            console.print(f"[yellow]⚠ Error: {e}[/yellow]")
                            teaching_state = TeachingState.NEXT_POINT

                    # === Estado: AWAITING_RETRY (espera segundo intento) ===
                    elif teaching_state == TeachingState.AWAITING_RETRY:
                        # Leer input del estudiante para segundo intento
                        user_input = typer.prompt(f"\n{user_prompt}").strip()

                        # Comandos especiales también aplican aquí
                        if user_input.lower() == "stop":
                            save_students_state(students_state, data_dir)
                            console.print("[green]✓ Sesión cerrada. Progreso guardado.[/green]")
                            return

                        # F7.4: Aceptar comandos naturales de avance
                        if user_input.lower() in ("adelante", "continuar", "sigo", "siguiente", "") or is_advance_intent(user_input):
                            teaching_state = TeachingState.NEXT_POINT
                            continue

                        if user_input.lower() == "apuntes":
                            console.print(f"\n[bold cyan]📝 Apuntes de la unidad:[/bold cyan]")
                            console.print(Markdown(unit_notes))
                            continue  # Sigue en AWAITING_RETRY

                        # Detectar "más ejemplos"
                        if detect_more_examples_intent(user_input):
                            teaching_state = TeachingState.MORE_EXAMPLES
                            continue

                        # F8.2: Increment attempt counter for retry
                        current_point_attempts += 1

                        # Evaluar segundo intento
                        try:
                            understood, feedback, needs_elaboration = check_comprehension(
                                check_question=last_check_question,
                                student_response=user_input,
                                concept_context=point.content[:500],
                                provider=effective_provider,
                                model=effective_model,
                            )
                            console.print(f"\n[cyan]{feedback}[/cyan]")

                            if understood and not needs_elaboration:
                                # F7.4: Ir a CONFIRM_ADVANCE en lugar de NEXT_POINT
                                teaching_state = TeachingState.CONFIRM_ADVANCE
                            elif needs_elaboration:
                                # Pide más detalles, sigue esperando
                                teaching_state = TeachingState.WAITING_INPUT
                            else:
                                # F8.2: Use policy to decide next state
                                if should_retry(current_point_attempts, teaching_policy):
                                    # Still have attempts left (shouldn't happen with max=2)
                                    console.print("\n[dim]Inténtalo una vez más.[/dim]")
                                    # Stay in AWAITING_RETRY
                                elif should_offer_advance(teaching_policy):
                                    # Out of attempts, offer choice
                                    teaching_state = TeachingState.POST_FAILURE_CHOICE
                                else:
                                    # No escape hatch, go to remediation
                                    teaching_state = TeachingState.REMEDIATION
                        except Exception as e:
                            console.print(f"[yellow]⚠ Error: {e}[/yellow]")
                            teaching_state = TeachingState.REMEDIATION

                    # === Estado: REMEDIATION ===
                    elif teaching_state == TeachingState.REMEDIATION:
                        console.print("\n[dim]Déjame explicarlo de otra manera...[/dim]")
                        try:
                            reexplanation = reexplain_with_analogy(
                                point=point,
                                original_question=last_check_question,
                                provider=effective_provider,
                                model=effective_model,
                            )
                            console.print()
                            console.print(Markdown(reexplanation))

                            # Actualizar pregunta de verificación
                            lines = reexplanation.strip().split("\n")
                            if lines and "?" in lines[-1]:
                                last_check_question = lines[-1]
                        except Exception as e:
                            console.print(f"[yellow]⚠ Error: {e}[/yellow]")

                        # Después de reexplicar, esperar input
                        teaching_state = TeachingState.WAITING_INPUT

                    # === Estado: CONFIRM_ADVANCE (F7.4) ===
                    elif teaching_state == TeachingState.CONFIRM_ADVANCE:
                        console.print("[green]¡Perfecto![/green]")
                        console.print("[dim]¿Avanzamos al siguiente punto? [Y/n][/dim]")
                        last_prompt_kind = TutorPromptKind.ASK_ADVANCE_CONFIRM
                        teaching_state = TeachingState.WAITING_INPUT

                    # === Estado: POST_FAILURE_CHOICE (F8.2) ===
                    elif teaching_state == TeachingState.POST_FAILURE_CHOICE:
                        # Offer escape hatch after failed attempts
                        console.print("\n[yellow]No pasa nada, este concepto es complejo.[/yellow]")

                        # Show options with default based on policy
                        if teaching_policy.default_after_failure == "advance":
                            console.print("[dim]¿Qué prefieres? [A]vanzar (recomendado) | [R]epasar[/dim]")
                        else:
                            console.print("[dim]¿Qué prefieres? [A]vanzar | [R]epasar (recomendado)[/dim]")

                        last_prompt_kind = TutorPromptKind.ASK_POST_FAILURE_CHOICE
                        teaching_state = TeachingState.WAITING_INPUT

                    # === Estado: NEXT_POINT ===
                    elif teaching_state == TeachingState.NEXT_POINT:
                        break  # Sale del while, continúa con siguiente punto

            # 4. F8.3: CIERRE DE UNIDAD - ahora sí mostrar apuntes
            console.print(f"\n[bold green]✓ ¡Muy bien! Has completado {unit_title}.[/bold green]")
            console.print(f"\n[bold cyan]📝 Aquí tienes los apuntes para repasar:[/bold cyan]")
            console.print(Markdown(unit_notes))

            # Ofrecer mini-quiz
            if typer.confirm("\n¿Hacemos un control rápido de 5 preguntas?", default=True):
                passed = _run_unit_mini_quiz(
                    unit_id=unit_id,
                    data_dir=data_dir,
                    provider=effective_provider,
                    model=effective_model,
                    console_obj=console,
                )

                if not passed:
                    retry = typer.confirm("¿Quieres repasar e intentar de nuevo?", default=False)
                    if retry:
                        console.print("\n[cyan]Repasa los apuntes:[/cyan]")
                        console.print(Markdown(unit_notes))
                        if typer.confirm("¿Intentar el quiz de nuevo?", default=True):
                            _run_unit_mini_quiz(
                                unit_id=unit_id,
                                data_dir=data_dir,
                                provider=effective_provider,
                                model=effective_model,
                                console_obj=console,
                            )

            # Continue to next unit?
            if unit_idx < len(units_with_notes) - 1:
                if not typer.confirm("\n¿Continuar con la siguiente unidad?", default=True):
                    save_students_state(students_state, data_dir)
                    console.print("[green]✓ Progreso guardado. ¡Hasta la próxima![/green]")
                    return

        # === PHASE 3c: Exam ===
        take_exam = typer.confirm("\n¿Pasamos al examen?", default=True)

        if not take_exam:
            console.print("[dim]Saltando examen...[/dim]")
            current_chapter += 1
            continue

        # Generate exam
        exam_set_id = _run_tutor_exam_flow(
            book_id=book_id,
            chapter_number=current_chapter,
            data_dir=data_dir,
            provider=effective_provider,
            model=effective_model,
        )

        if exam_set_id is None:
            # Exam generation failed or skipped
            if typer.confirm("¿Continuar al siguiente capítulo sin examen?", default=True):
                current_chapter += 1
            continue

        # Run exam-quiz flow
        passed, exam_attempt_id = _run_tutor_exam_quiz_flow(
            exam_set_id=exam_set_id,
            data_dir=data_dir,
            provider=effective_provider,
            model=effective_model,
            book_id=book_id,
        )

        # Track attempt in state
        if exam_attempt_id:
            if exam_set_id not in book_progress.chapter_attempts:
                book_progress.chapter_attempts[exam_set_id] = []
            book_progress.chapter_attempts[exam_set_id].append(exam_attempt_id)
            save_students_state(students_state, data_dir)

        if passed:
            # Mark chapter complete
            if current_chapter not in book_progress.completed_chapters:
                book_progress.completed_chapters.append(current_chapter)
            console.print(f"\n[green bold]🎉 ¡Capítulo {current_chapter} completado![/green bold]")
            save_students_state(students_state, data_dir)
            current_chapter += 1
        else:
            # Remediation
            console.print("\n[yellow]No aprobaste. Vamos a repasar.[/yellow]")
            retry = typer.confirm("¿Reintentar el examen?", default=True)
            if not retry:
                current_chapter += 1

    # All chapters complete
    console.print(f"\n[green bold]🎓 ¡Felicidades! Has completado el libro '{selected_book['title']}'[/green bold]")
    save_students_state(students_state, data_dir)


if __name__ == "__main__":
    app()
