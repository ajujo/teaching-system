"""Core business logic module - F2 Phase.

F2 Modules (current phase):
- book_importer: Book import orchestrator
- pdf_extractor: PDF text extraction
- epub_extractor: EPUB text extraction
- text_normalizer: Text cleanup and normalization
- outline_extractor: Chapter/section detection
- outline_validator: Manual outline correction

Future modules are in src/teaching/future/
See docs/phase_guardrails.md for phase assignments.
"""

__all__ = [
    "book_importer",
    "pdf_extractor",
    "epub_extractor",
    "text_normalizer",
    "outline_extractor",
    "outline_validator",
]
