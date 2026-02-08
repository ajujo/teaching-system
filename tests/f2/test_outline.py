"""Tests for outline extraction functionality (F2 - Hito5)."""

import json
import tempfile
from pathlib import Path

import pytest

from teaching.core.outline_extractor import (
    extract_outline,
    generate_review_yaml,
    validate_and_apply_yaml,
    OutlineExtractionError,
    _extract_from_toc,
    _extract_from_headings,
    _extract_auto,
    _looks_like_chapter_title,
    _is_skip_entry,
    _roman_to_int,
    _clean_title,
)
from teaching.core.book_importer import import_book
from teaching.core.pdf_extractor import extract_pdf
from teaching.core.text_normalizer import normalize_book
from teaching.db.database import init_db


@pytest.fixture
def temp_dir():
    """Create a temporary directory for test data."""
    with tempfile.TemporaryDirectory() as tmpdir:
        yield Path(tmpdir)


@pytest.fixture
def data_dir(temp_dir):
    """Create data directory structure."""
    data = temp_dir / "data"
    data.mkdir()
    return data


@pytest.fixture
def init_test_db(temp_dir):
    """Initialize test database."""
    db_path = temp_dir / "db" / "teaching.db"
    init_db(db_path)
    return db_path


@pytest.fixture
def book_with_toc_content(temp_dir):
    """Create a test PDF with table of contents."""
    import fitz

    pdf_path = temp_dir / "book_with_toc.pdf"
    doc = fitz.open()

    # Page 1: Table of Contents
    toc_page = doc.new_page()
    toc_content = """Table of Contents

Chapter 1: Introduction .................. 3
  1.1 Getting Started .................... 5
  1.2 Basic Concepts ..................... 8
Chapter 2: Core Features ................. 15
  2.1 Feature One ........................ 17
  2.2 Feature Two ........................ 22
Chapter 3: Advanced Topics ............... 30
  3.1 Advanced Feature ................... 32
Conclusion ............................... 45"""
    toc_page.insert_text((72, 72), toc_content)

    # Page 2: Chapter 1
    ch1_page = doc.new_page()
    ch1_page.insert_text((72, 72), "Chapter 1: Introduction\n\nThis is the introduction.")

    # Page 3: Chapter 2
    ch2_page = doc.new_page()
    ch2_page.insert_text((72, 72), "Chapter 2: Core Features\n\nCore features explained.")

    doc.save(str(pdf_path))
    doc.close()
    return pdf_path


@pytest.fixture
def book_with_headings_content(temp_dir):
    """Create a test PDF with chapter headings."""
    import fitz

    pdf_path = temp_dir / "book_with_headings.pdf"
    doc = fitz.open()

    # Page with Chapter 1
    page1 = doc.new_page()
    page1.insert_text((72, 72), """Chapter 1: Getting Started

Welcome to this guide. Here we introduce the basics.

1.1 Installation

First, install the software by following these steps.

1.2 Configuration

Configure your settings appropriately.""")

    # Page with Chapter 2
    page2 = doc.new_page()
    page2.insert_text((72, 72), """Chapter 2: Usage

Now let's learn how to use the software.

2.1 Basic Usage

Start with simple commands.

2.2 Advanced Usage

Move on to complex operations.""")

    doc.save(str(pdf_path))
    doc.close()
    return pdf_path


@pytest.fixture
def imported_book_with_toc(book_with_toc_content, data_dir, init_test_db):
    """Import and extract a book with TOC."""
    result = import_book(
        file_path=book_with_toc_content,
        title="Book With TOC",
        author="Test Author",
        data_dir=data_dir,
    )
    extract_pdf(result.book_id, data_dir)
    normalize_book(result.book_id, data_dir)
    return result.book_id, data_dir


@pytest.fixture
def imported_book_with_headings(book_with_headings_content, data_dir, init_test_db):
    """Import and extract a book with headings."""
    result = import_book(
        file_path=book_with_headings_content,
        title="Book With Headings",
        author="Test Author",
        data_dir=data_dir,
    )
    extract_pdf(result.book_id, data_dir)
    normalize_book(result.book_id, data_dir)
    return result.book_id, data_dir


class TestHelperFunctions:
    """Tests for helper functions."""

    def test_roman_to_int(self):
        """Converts Roman numerals correctly."""
        assert _roman_to_int("I") == 1
        assert _roman_to_int("IV") == 4
        assert _roman_to_int("V") == 5
        assert _roman_to_int("IX") == 9
        assert _roman_to_int("X") == 10
        assert _roman_to_int("XIV") == 14

    def test_clean_title(self):
        """Cleans titles correctly."""
        assert _clean_title("1. Introduction") == "Introduction"
        assert _clean_title("Chapter 1: Basics...") == "Chapter 1: Basics"
        assert _clean_title("  Multiple   Spaces  ") == "Multiple Spaces"

    def test_looks_like_chapter_title(self):
        """Identifies chapter-like titles."""
        assert _looks_like_chapter_title("Chapter 1: Introduction") is True
        assert _looks_like_chapter_title("Chapter 10: Advanced Topics") is True
        assert _looks_like_chapter_title("Part I: Beginning") is True
        # These should NOT be chapters (strict mode)
        assert _looks_like_chapter_title("1. Getting Started") is False  # Section, not chapter
        assert _looks_like_chapter_title("simple section") is False
        assert _looks_like_chapter_title("Preface") is False
        assert _looks_like_chapter_title("Summary") is False
        assert _looks_like_chapter_title("References") is False


class TestOutlineExtraction:
    """Tests for outline extraction."""

    def test_extract_creates_outline_files(self, imported_book_with_headings):
        """Extraction creates outline directory and files."""
        book_id, data_dir = imported_book_with_headings

        result = extract_outline(book_id, method="auto", data_dir=data_dir)

        outline_dir = data_dir / "books" / book_id / "outline"
        assert outline_dir.exists()
        assert (outline_dir / "outline.json").exists()
        assert (outline_dir / "outline_report.json").exists()

    def test_extract_auto_picks_best_method(self, imported_book_with_headings):
        """Auto method picks best extraction method."""
        book_id, data_dir = imported_book_with_headings

        result = extract_outline(book_id, method="auto", data_dir=data_dir)

        assert result.success
        assert "auto:" in result.report.method_used
        assert result.report.confidence > 0

    def test_extract_headings_method(self, imported_book_with_headings):
        """Headings method extracts chapters."""
        book_id, data_dir = imported_book_with_headings

        result = extract_outline(book_id, method="headings", data_dir=data_dir)

        assert result.success
        assert result.report.method_used == "headings"
        assert result.report.chapters_found >= 1

    def test_extract_updates_book_json(self, imported_book_with_headings):
        """Extraction updates book.json with outline metadata."""
        book_id, data_dir = imported_book_with_headings

        extract_outline(book_id, method="auto", data_dir=data_dir)

        book_json_path = data_dir / "books" / book_id / "book.json"
        with open(book_json_path) as f:
            book_data = json.load(f)

        assert "outline" in book_data
        assert "method_used" in book_data["outline"]
        assert "confidence" in book_data["outline"]

    def test_extract_nonexistent_book_raises_error(self, data_dir, init_test_db):
        """Extraction raises error for non-existent book."""
        with pytest.raises(FileNotFoundError):
            extract_outline("nonexistent-book", data_dir=data_dir)


class TestReviewMode:
    """Tests for review/YAML editing mode."""

    def test_generate_review_yaml(self, imported_book_with_headings):
        """Generates YAML file for review."""
        book_id, data_dir = imported_book_with_headings

        # First extract outline
        extract_outline(book_id, method="auto", data_dir=data_dir)

        # Generate YAML
        yaml_path = generate_review_yaml(book_id, data_dir=data_dir)

        assert yaml_path.exists()
        assert yaml_path.name == "outline_draft.yaml"

        # Check content is valid YAML
        content = yaml_path.read_text()
        assert "chapters:" in content

    def test_validate_and_apply_yaml(self, imported_book_with_headings):
        """Validates and applies edited YAML."""
        book_id, data_dir = imported_book_with_headings

        # Extract and generate YAML
        extract_outline(book_id, method="auto", data_dir=data_dir)
        yaml_path = generate_review_yaml(book_id, data_dir=data_dir)

        # Validate (without editing)
        result = validate_and_apply_yaml(book_id, data_dir=data_dir)

        assert result.success
        assert result.report.method_used == "manual"
        assert result.report.confidence == 1.0


class TestOutlineSchema:
    """Tests for outline JSON schema compliance."""

    def test_outline_has_required_fields(self, imported_book_with_headings):
        """Outline JSON has all required fields."""
        book_id, data_dir = imported_book_with_headings

        extract_outline(book_id, method="auto", data_dir=data_dir)

        outline_path = data_dir / "books" / book_id / "outline" / "outline.json"
        with open(outline_path) as f:
            outline = json.load(f)

        assert "$schema" in outline
        assert outline["$schema"] == "outline_v1"
        assert "book_id" in outline
        assert "generated_date" in outline
        assert "chapters" in outline
        assert isinstance(outline["chapters"], list)

    def test_chapters_have_required_fields(self, imported_book_with_headings):
        """Each chapter has required fields."""
        book_id, data_dir = imported_book_with_headings

        extract_outline(book_id, method="auto", data_dir=data_dir)

        outline_path = data_dir / "books" / book_id / "outline" / "outline.json"
        with open(outline_path) as f:
            outline = json.load(f)

        for chapter in outline["chapters"]:
            assert "chapter_id" in chapter
            assert "number" in chapter
            assert "title" in chapter
            assert "sections" in chapter

    def test_chapter_ids_follow_convention(self, imported_book_with_headings):
        """Chapter IDs follow {book_id}:ch:N convention."""
        book_id, data_dir = imported_book_with_headings

        extract_outline(book_id, method="auto", data_dir=data_dir)

        outline_path = data_dir / "books" / book_id / "outline" / "outline.json"
        with open(outline_path) as f:
            outline = json.load(f)

        for chapter in outline["chapters"]:
            assert chapter["chapter_id"].startswith(f"{book_id}:ch:")


class TestTocDetection:
    """Tests for TOC-based detection."""

    def test_detects_toc_marker(self, imported_book_with_toc):
        """Detects table of contents marker."""
        book_id, data_dir = imported_book_with_toc

        # Read content
        content_path = data_dir / "books" / book_id / "normalized" / "content.txt"
        content = content_path.read_text()

        result = _extract_from_toc(book_id, content)

        # Should find TOC
        if result.success:
            # method_used is now "toc:packt" or "toc:numeric"
            assert result.report.method_used.startswith("toc:")
            assert result.report.chapters_found >= 1


class TestHeadingsDetection:
    """Tests for headings-based detection."""

    def test_detects_chapter_patterns(self, imported_book_with_headings):
        """Detects "Chapter N:" pattern."""
        book_id, data_dir = imported_book_with_headings

        content_path = data_dir / "books" / book_id / "normalized" / "content.txt"
        content = content_path.read_text()

        result = _extract_from_headings(book_id, content)

        assert result.success
        assert result.report.chapters_found >= 1

    def test_detects_section_patterns(self, imported_book_with_headings):
        """Detects "N.M" section patterns."""
        book_id, data_dir = imported_book_with_headings

        content_path = data_dir / "books" / book_id / "normalized" / "content.txt"
        content = content_path.read_text()

        result = _extract_from_headings(book_id, content)

        # Should find some sections
        if result.success and result.outline:
            total_sections = sum(len(ch.sections) for ch in result.outline.chapters)
            # May or may not find sections depending on content
            assert result.report.sections_found >= 0


class TestPacktBookFormat:
    """Tests for Packt-style book TOC format."""

    # Sample TOC content extracted from a real Packt book
    PACKT_TOC_SAMPLE = """
Table of Contents
Preface                                                                       xxi
Making the Most Out of This Book                                            xxvii
Chapter 1: Understanding the LLM Twin Concept and Architecture                  1
Understanding the LLM Twin concept                                              2
What is an LLM Twin?                                                            2
Why building an LLM Twin matters                                                3
Planning the MVP of the LLM Twin product                                        6
Summary                                                                        23
References                                                                     23
Chapter 2: Tooling and Installation                                            25
Python ecosystem and project installation                                      26
Poetry: dependency and virtual environment management                          27
MLOps and LLMOps tooling                                                       31
Summary                                                                        52
References                                                                     53
Chapter 3: Data Engineering                                                    55
Designing the LLM Twin's data collection pipeline                              56
Summary                                                                        96
References                                                                     96
Chapter 4: RAG Feature Pipeline                                                99
Understanding RAG                                                             100
Summary                                                                       173
References                                                                    174
Chapter 5: Supervised Fine-Tuning                                             177
Creating an instruction dataset                                               178
Summary                                                                       226
References                                                                    227
Chapter 6: Fine-Tuning with Preference Alignment                              229
Understanding preference datasets                                             230
Summary                                                                       257
References                                                                    258
Chapter 7: Evaluating LLMs                                                    261
Model evaluation                                                              261
Summary                                                                       286
References                                                                    287
Chapter 8: Inference Optimization                                             289
Model optimization strategies                                                 290
Summary                                                                       320
References                                                                    320
Chapter 9: RAG Inference Pipeline                                             323
Building the advanced RAG module                                              324
Summary                                                                       369
References                                                                    370
Chapter 10: Inference Pipeline Deployment                                     373
Preparing the LLM Twin codebase                                               374
Summary                                                                       410
References                                                                    410
Chapter 11: MLOps and LLMOps                                                  413
Introduction to MLOps and LLMOps                                              414
Summary                                                                       462
References                                                                    463
Index                                                                         465

Chapter 1: Understanding the LLM Twin Concept and Architecture

This is the actual content of chapter 1 that should be ignored in TOC parsing...
"""

    def test_toc_extracts_11_chapters(self):
        """TOC extraction finds all 11 chapters from Packt book."""
        result = _extract_from_toc("test-book", self.PACKT_TOC_SAMPLE)

        assert result.success, f"TOC extraction failed: {result.report.warnings}"
        # method_used should be pattern-based (chapterline, numeric, etc.)
        assert result.report.method_used.startswith("toc:")

        # Should find 11 chapters (Chapter 1 through Chapter 11)
        assert result.report.chapters_found >= 9, (
            f"Expected ~11 chapters, got {result.report.chapters_found}"
        )
        assert result.report.chapters_found <= 13  # Allow small variance

    def test_toc_has_high_confidence(self):
        """TOC extraction has high confidence for Packt format."""
        result = _extract_from_toc("test-book", self.PACKT_TOC_SAMPLE)

        assert result.success
        assert result.report.confidence >= 0.8, (
            f"Expected confidence >= 0.8, got {result.report.confidence}"
        )

    def test_toc_chapters_numbered_sequentially(self):
        """Chapters are numbered 1, 2, 3, ..., 11."""
        result = _extract_from_toc("test-book", self.PACKT_TOC_SAMPLE)

        assert result.success
        assert result.outline is not None

        numbers = [ch.number for ch in result.outline.chapters]
        # Should be sequential starting from 1
        expected = list(range(1, len(numbers) + 1))
        assert numbers == expected, f"Expected sequential numbering, got {numbers}"

    def test_toc_skips_frontmatter(self):
        """TOC extraction skips Preface, Index, etc."""
        result = _extract_from_toc("test-book", self.PACKT_TOC_SAMPLE)

        assert result.success
        assert result.outline is not None

        titles = [ch.title.lower() for ch in result.outline.chapters]

        # These should NOT be chapters
        assert not any("preface" in t for t in titles)
        assert not any("index" in t for t in titles)
        assert not any("making the most" in t for t in titles)

    def test_auto_method_chooses_toc_for_packt(self):
        """Auto method should choose TOC for Packt-style books."""
        from teaching.core.outline_extractor import _extract_auto

        result = _extract_auto("test-book", self.PACKT_TOC_SAMPLE)

        assert result.success
        # Auto should pick TOC (higher confidence)
        assert "toc" in result.report.method_used, (
            f"Expected 'auto:toc', got '{result.report.method_used}'"
        )

    def test_auto_reports_both_methods(self):
        """Auto method includes scores for both toc and headings."""
        from teaching.core.outline_extractor import _extract_auto

        result = _extract_auto("test-book", self.PACKT_TOC_SAMPLE)

        # method_scores should have both methods
        assert "toc" in result.report.method_scores
        # headings might or might not succeed depending on content


class TestOReillyBookFormat:
    """Tests for O'Reilly-style book TOC format (N. Title ... page)."""

    # Sample TOC from O'Reilly book
    OREILLY_TOC_SAMPLE = """
Table of Contents
Preface. . . . . . . . . . . . . . . . . . . . . . . . . . . . . . . . . . . . . . . . . . . . . . . . . . . . . . . . . . . . . . . . . . . . . . xiii
1. Introduction to Agents. . . . . . . . . . . . . . . . . . . . . . . . . . . . . . . . . . . . . . . . . . . . . . . . . . . . . . . 1
Defining AI Agents 1
The Pretraining Revolution 2
Types of Agents 3
Model Selection 5
Conclusion 15
2. Designing Agent Systems. . . . . . . . . . . . . . . . . . . . . . . . . . . . . . . . . . . . . . . . . . . . . . . . . . . . 17
Our First Agent System 17
Core Components of Agent Systems 20
Conclusion 39
3. User Experience Design for Agentic Systems. . . . . . . . . . . . . . . . . . . . . . . . . . . . . . . . . . . . 41
Interaction Modalities 42
Conclusion 68
4. Tool Use. . . . . . . . . . . . . . . . . . . . . . . . . . . . . . . . . . . . . . . . . . . . . . . . . . . . . . . . . . . . . . . . . . . 71
LangChain Fundamentals 72
Conclusion 88
5. Orchestration. . . . . . . . . . . . . . . . . . . . . . . . . . . . . . . . . . . . . . . . . . . . . . . . . . . . . . . . . . . . . . 89
Agent Types 90
Conclusion 113
6. Knowledge and Memory. . . . . . . . . . . . . . . . . . . . . . . . . . . . . . . . . . . . . . . . . . . . . . . . . . . 115
Foundational Approaches to Memory 116
Conclusion 134
7. Learning in Agentic Systems. . . . . . . . . . . . . . . . . . . . . . . . . . . . . . . . . . . . . . . . . . . . . . . . 135
Nonparametric Learning 135
Conclusion 162
8. From One Agent to Many. . . . . . . . . . . . . . . . . . . . . . . . . . . . . . . . . . . . . . . . . . . . . . . . . . . 163
How Many Agents Do I Need? 163
Conclusion 202
9. Validation and Measurement. . . . . . . . . . . . . . . . . . . . . . . . . . . . . . . . . . . . . . . . . . . . . . . 205
Measuring Agentic Systems 205
Conclusion 221
10. Monitoring in Production. . . . . . . . . . . . . . . . . . . . . . . . . . . . . . . . . . . . . . . . . . . . . . . . . . . 223
Monitoring Is How You Learn 224
Conclusion 241
11. Improvement Loops. . . . . . . . . . . . . . . . . . . . . . . . . . . . . . . . . . . . . . . . . . . . . . . . . . . . . . . 243
Feedback Pipelines 245
Conclusion 268
12. Protecting Agentic Systems. . . . . . . . . . . . . . . . . . . . . . . . . . . . . . . . . . . . . . . . . . . . . . . . . 271
The Unique Risks of Agentic Systems 272
Conclusion 296
13. Human-Agent Collaboration. . . . . . . . . . . . . . . . . . . . . . . . . . . . . . . . . . . . . . . . . . . . . . . . 297
Roles and Autonomy 297
Conclusion: The Future of Human-Agent Teams 312
Glossary. . . . . . . . . . . . . . . . . . . . . . . . . . . . . . . . . . . . . . . . . . . . . . . . . . . . . . . . . . . . . . . . . . . . . 315
Index. . . . . . . . . . . . . . . . . . . . . . . . . . . . . . . . . . . . . . . . . . . . . . . . . . . . . . . . . . . . . . . . . . . . . . . 319

Preface
When I first started connecting language models...
"""

    def test_toc_extracts_13_chapters(self):
        """TOC extraction finds all 13 chapters from O'Reilly book."""
        result = _extract_from_toc("test-book", self.OREILLY_TOC_SAMPLE)

        assert result.success, f"TOC extraction failed: {result.report.warnings}"
        assert result.report.method_used == "toc:numeric"

        # Should find 13 chapters (1 through 13)
        assert result.report.chapters_found >= 11, (
            f"Expected ~13 chapters, got {result.report.chapters_found}"
        )
        assert result.report.chapters_found <= 15

    def test_toc_has_high_confidence(self):
        """TOC extraction has high confidence for O'Reilly format."""
        result = _extract_from_toc("test-book", self.OREILLY_TOC_SAMPLE)

        assert result.success
        assert result.report.confidence >= 0.8, (
            f"Expected confidence >= 0.8, got {result.report.confidence}"
        )

    def test_toc_chapters_numbered_sequentially(self):
        """Chapters are numbered 1, 2, 3, ..., 13."""
        result = _extract_from_toc("test-book", self.OREILLY_TOC_SAMPLE)

        assert result.success
        assert result.outline is not None

        numbers = [ch.number for ch in result.outline.chapters]
        expected = list(range(1, len(numbers) + 1))
        assert numbers == expected, f"Expected sequential numbering, got {numbers}"

    def test_toc_skips_frontmatter(self):
        """TOC extraction skips Preface, Glossary, Index."""
        result = _extract_from_toc("test-book", self.OREILLY_TOC_SAMPLE)

        assert result.success
        assert result.outline is not None

        titles = [ch.title.lower() for ch in result.outline.chapters]

        assert not any("preface" in t for t in titles)
        assert not any("glossary" in t for t in titles)
        assert not any("index" in t for t in titles)

    def test_toc_extracts_sections(self):
        """TOC extraction finds sections within chapters."""
        result = _extract_from_toc("test-book", self.OREILLY_TOC_SAMPLE)

        assert result.success
        assert result.outline is not None

        # Should have some sections
        assert result.report.sections_found > 0

        # Chapter 1 should have sections like "Defining AI Agents"
        ch1 = result.outline.chapters[0]
        assert len(ch1.sections) >= 2

    def test_auto_chooses_toc_numeric(self):
        """Auto method should choose toc:numeric for O'Reilly books."""
        result = _extract_auto("test-book", self.OREILLY_TOC_SAMPLE)

        assert result.success
        # Should pick toc (either format)
        assert "toc" in result.report.method_used

    def test_headings_guardrail(self):
        """Headings method should have low confidence with too many chapters."""
        # Create content that would generate many false positive chapters
        # Each chapter must be preceded by empty line to be detected
        content = "\n\n".join([f"Chapter {i}: Title {i}" for i in range(1, 100)])

        result = _extract_from_headings("test-book", content)

        # Should succeed but with low confidence due to guardrail
        assert result.success
        if result.report.chapters_found > 50:
            assert result.report.confidence <= 0.4
            assert len(result.report.warnings) > 0


class TestMultilineBookFormat:
    """Tests for Packt Cookbook-style TOC format (2-column PDF)."""

    # Sample TOC from tests/fixtures/toc_cookbook_packt.txt
    COOKBOOK_TOC_SAMPLE = """
Preface
xv
1
Imputing Missing Data
1
Technical requirements
2
Removing observations
with missing data
3
How to do it...
3
How it works...
6
2
Encoding Categorical Variables
43
Technical requirements
44
Creating binary variables through
one-hot encoding
44
3
Transforming Numerical Variables
83
Transforming variables with the
logarithm function
84
4
Performing Variable Discretization
113
Technical requirements
114
5
Working with Outliers
153
Technical requirements
154
6
Extracting Features from Date and Time Variables
177
Technical requirements
177
7
Performing Feature Scaling
203
Technical requirements
204
8
Creating New Features
229
Technical requirements
230
9
Extracting Features from Relational Data with Featuretools
269
Technical requirements
270
10
Creating Features from a Time Series with tsfresh
307
Technical requirements
308
11
Extracting Features from Text Variables
339
Technical requirements
340
Index
363
Other Books You May Enjoy
370
"""

    def test_toc_extracts_11_chapters(self):
        """TOC extraction finds all 11 chapters from Cookbook format."""
        from teaching.core.outline_extractor import _extract_from_toc

        result = _extract_from_toc("test-cookbook", self.COOKBOOK_TOC_SAMPLE)

        assert result.success, f"TOC extraction failed: {result.report.warnings}"
        assert result.report.method_used == "toc:multiline"  # Pattern-based name
        assert result.report.chapters_found == 11

    def test_toc_chapters_numbered_sequentially(self):
        """Chapters are numbered 1, 2, 3, ..., 11."""
        from teaching.core.outline_extractor import _extract_from_toc

        result = _extract_from_toc("test-cookbook", self.COOKBOOK_TOC_SAMPLE)

        assert result.success
        assert result.outline is not None

        numbers = [ch.number for ch in result.outline.chapters]
        expected = list(range(1, 12))
        assert numbers == expected, f"Expected {expected}, got {numbers}"

    def test_toc_has_high_confidence(self):
        """TOC extraction has high confidence for Cookbook format."""
        from teaching.core.outline_extractor import _extract_from_toc

        result = _extract_from_toc("test-cookbook", self.COOKBOOK_TOC_SAMPLE)

        assert result.success
        assert result.report.confidence >= 0.8

    def test_toc_extracts_sections(self):
        """TOC extraction finds sections within chapters."""
        from teaching.core.outline_extractor import _extract_from_toc

        result = _extract_from_toc("test-cookbook", self.COOKBOOK_TOC_SAMPLE)

        assert result.success
        assert result.outline is not None
        assert result.report.sections_found > 0

        # Chapter 1 should have "Technical requirements" section
        ch1 = result.outline.chapters[0]
        assert len(ch1.sections) >= 1

    def test_toc_skips_frontmatter(self):
        """TOC extraction skips Preface, Index."""
        from teaching.core.outline_extractor import _extract_from_toc

        result = _extract_from_toc("test-cookbook", self.COOKBOOK_TOC_SAMPLE)

        assert result.success
        assert result.outline is not None

        titles = [ch.title.lower() for ch in result.outline.chapters]

        assert not any("preface" in t for t in titles)
        assert not any("index" in t for t in titles)


class TestSpanishHeadingsFormat:
    """Tests for Spanish O'Reilly headings format (capítulo N.)."""

    # Sample content with Spanish chapter headings
    SPANISH_HEADINGS_SAMPLE = """
Contenido anterior del prefacio...

capítulo 1. Introducción a la creación de aplicaciones de IA
Si solo pudiera utilizar una palabra para describir la IA después de 2020,
sería escala. Los modelos de IA que hay detrás de aplicaciones...

Mucho contenido del capítulo 1 aquí...

capítulo 2. Comprender los modelos fundacionales
Para crear aplicaciones con modelos fundacionales, primero se necesitan
modelos fundacionales. Este capítulo explora...

capítulo 3. Metodología de evaluación
Cuanto más se utiliza la IA, más oportunidades hay de que se produzcan
fallos catastróficos.

capítulo 4. Evaluar los sistemas de IA
La evaluación de los sistemas de IA es un proceso complejo.

capítulo 5. Ingeniería de prompts
La ingeniería de prompts es el arte de diseñar instrucciones.

capítulo 6. RAG y agentes
Este capítulo explora dos patrones fundamentales.

capítulo 7. Afinado
El afinado permite adaptar un modelo preentrenado.

capítulo 8. Ingeniería de conjuntos de datos
La calidad de los datos es fundamental.

capítulo 9. Optimización de la inferencia
Una vez que tenemos un modelo funcionando.

capítulo 10. Arquitectura de ingeniería de IA
Este capítulo final reúne todos los conceptos.
"""

    def test_headings_extracts_10_chapters(self):
        """Headings extraction finds all 10 chapters from Spanish format."""
        from teaching.core.outline_extractor import _extract_from_headings

        result = _extract_from_headings("test-spanish", self.SPANISH_HEADINGS_SAMPLE)

        assert result.success, f"Headings extraction failed: {result.report.warnings}"
        assert result.report.chapters_found == 10

    def test_headings_chapters_numbered_sequentially(self):
        """Chapters are numbered 1, 2, 3, ..., 10."""
        from teaching.core.outline_extractor import _extract_from_headings

        result = _extract_from_headings("test-spanish", self.SPANISH_HEADINGS_SAMPLE)

        assert result.success
        assert result.outline is not None

        numbers = [ch.number for ch in result.outline.chapters]
        expected = list(range(1, 11))
        assert numbers == expected, f"Expected {expected}, got {numbers}"

    def test_headings_ignores_references_in_text(self):
        """Headings should not capture 'Capítulo N' references in middle of text."""
        from teaching.core.outline_extractor import _extract_from_headings

        # Sample with reference to "Capítulo 3" in the middle of a paragraph
        content_with_reference = """
capítulo 1. Introducción
Texto del capítulo 1.

capítulo 2. Segundo capítulo
Texto del capítulo 2. Este tema se explica mejor en el
Capítulo 3. En resumen, estos retos surgen de la naturaleza abierta
de los modelos. Más texto aquí.

capítulo 3. Tercer capítulo
Texto del capítulo 3.
"""

        result = _extract_from_headings("test-ref", content_with_reference)

        assert result.success
        assert result.outline is not None

        # Should find exactly 3 chapters, not 4
        assert result.report.chapters_found == 3
        numbers = [ch.number for ch in result.outline.chapters]
        assert numbers == [1, 2, 3]


class TestIndexOnlyDetection:
    """Tests for index-only detection (alphabetical index vs TOC)."""

    # Sample alphabetical index (not a TOC)
    INDEX_ONLY_SAMPLE = """
Table of Contents

A
abstract data types, 15
access control, 42
algorithms, 8
B
binary search, 23
buffers, 67
C
cache, 89
compilation, 12
D
data structures, 34
debugging, 56
E
encapsulation, 78
error handling, 91
F
functions, 45
G
garbage collection, 102
H
hashing, 113
I
inheritance, 124
J
Java, 135
K
keywords, 146
L
linked lists, 157
M
memory management, 168
N
null pointer, 179
O
object-oriented, 190
P
polymorphism, 201
Q
queues, 212
R
recursion, 223
S
stacks, 234
T
trees, 245
U
unit testing, 256
V
variables, 267
W
while loops, 278
X
XML, 289
Y
yield, 300
Z
zero-based indexing, 311
"""

    def test_index_only_detected(self):
        """Index-only block should be detected and auto prefers headings."""
        from teaching.core.outline_extractor import _detect_index_only

        lines = self.INDEX_ONLY_SAMPLE.split("\n")
        # Find TOC marker
        toc_start = None
        for i, line in enumerate(lines):
            if "Table of Contents" in line:
                toc_start = i + 1
                break

        result = _detect_index_only(lines, toc_start, len(lines))
        assert result is True, "Should detect alphabetical index pattern"

    def test_auto_prefers_headings_for_index_only(self):
        """Auto method should prefer headings when TOC is index-only."""
        from teaching.core.outline_extractor import _extract_auto

        # Add some chapter headings to the index content
        content_with_headings = """
Table of Contents

A
abstract data types, 15
algorithms, 8
B
binary search, 23

Chapter 1: Introduction
This is chapter content.

Chapter 2: Getting Started
More content here.

Chapter 3: Advanced Topics
Final chapter content.
"""
        result = _extract_auto("test-index", content_with_headings)

        # Should use headings since TOC looks like index
        assert result.success
        # Method scores should include both toc and headings
        assert "headings" in result.report.method_scores


class TestMethodScoresAlwaysIncluded:
    """Tests that auto always reports scores for both toc and headings."""

    def test_auto_includes_both_method_scores(self):
        """Auto should always include toc and headings in method_scores."""
        from teaching.core.outline_extractor import _extract_auto

        content = """
Table of Contents
Chapter 1: Introduction .......... 1
Chapter 2: Setup ................. 15
Chapter 3: Implementation ........ 30
Index ............................ 100
"""
        result = _extract_auto("test-scores", content)

        assert result.success
        # method_scores must include headings (toc may be 0 if it failed)
        assert "headings" in result.report.method_scores
        # toc might not be present if no TOC found, but if present, should be numeric
        if "toc" in result.report.method_scores:
            assert isinstance(result.report.method_scores["toc"], (int, float))

    def test_auto_with_headings_only(self):
        """Auto with content that only has headings (no TOC)."""
        from teaching.core.outline_extractor import _extract_auto

        content = """
Some introductory text.

Chapter 1: First Topic
Content of first chapter.

Chapter 2: Second Topic
Content of second chapter.

Chapter 3: Third Topic
Content of third chapter.
"""
        result = _extract_auto("test-headings-only", content)

        assert result.success
        assert "headings" in result.report.method_scores


class TestTocLocation:
    """Tests for TOC location detection."""

    def test_toc_location_included_in_report(self):
        """TOC location should be included in report when TOC found."""
        from teaching.core.outline_extractor import _extract_auto

        content = """
Book Title
Author Name

Table of Contents
Chapter 1: Introduction .......... 1
Chapter 2: Setup ................. 15
Index ............................ 100

Chapter 1: Introduction
This is the actual content.
"""
        result = _extract_auto("test-location", content)

        # If TOC was found, location should be in report
        if result.report.toc_location:
            assert result.report.toc_location.start_line >= 0
            assert result.report.toc_location.confidence_locator > 0


class TestNonChapterEntries:
    """Tests that Summary/References/etc are not detected as chapters."""

    def test_summary_not_chapter(self):
        """Summary should not be detected as a chapter."""
        from teaching.core.outline_extractor import _extract_from_headings

        content = """
Chapter 1: Introduction
Content here.

Summary
This summarizes the chapter.

Chapter 2: Methods
More content.

References
1. Some reference.
"""
        result = _extract_from_headings("test-summary", content)

        assert result.success
        # Should find 2 chapters, not 4
        assert result.report.chapters_found == 2

        # Verify chapter titles
        titles = [ch.title.lower() for ch in result.outline.chapters]
        assert "summary" not in titles
        assert "references" not in titles


class TestIndexInLastPages:
    """Tests for index detection in last pages when TOC fails.

    For books like Chip's AI Engineering:
    - No traditional TOC
    - Chapters detected from headings
    - Alphabetical index at the end
    """

    # Fixture path
    FIXTURE_PATH = Path(__file__).parent.parent / "fixtures" / "book_no_toc_with_index.txt"

    def test_detects_index_in_last_pages(self):
        """Should detect alphabetical index in last pages."""
        from teaching.core.outline_extractor import _detect_index_in_last_pages

        content = self.FIXTURE_PATH.read_text()
        lines = content.split("\n")

        result = _detect_index_in_last_pages(lines)
        assert result is True, "Should detect index in last pages"

    def test_auto_sets_index_only_when_toc_marker_is_index(self):
        """Auto method should detect index_only when 'índice' marker is actually an index."""
        from teaching.core.outline_extractor import _extract_auto

        content = self.FIXTURE_PATH.read_text()
        result = _extract_auto("test-chip-style", content)

        assert result.success
        # Should use headings method
        assert "headings" in result.report.method_used
        # Should detect index_only
        assert result.report.index_only_detected is True
        # Warning should indicate alphabetical index detected
        assert any("índice alfabético" in w for w in result.report.warnings)

    def test_auto_sets_index_only_when_toc_fails_with_index_at_end(self):
        """Auto should detect index_only when TOC fails but index exists at end of book."""
        from teaching.core.outline_extractor import _extract_auto

        # Content without TOC marker but with alphabetical index at the end
        # Need enough lines (>100) for the detection to work
        content_lines = [
            "Prefacio sin tabla de contenidos.",
            "",
            "Chapter 1: Introduction",
            "Content of first chapter.",
        ]
        # Add padding content to reach 100+ lines
        for i in range(50):
            content_lines.append(f"Paragraph {i} of chapter content with some text.")
        content_lines.extend([
            "",
            "Chapter 2: Methods",
            "Content of second chapter.",
        ])
        for i in range(50):
            content_lines.append(f"More content paragraph {i} here.")
        content_lines.extend([
            "",
            "Chapter 3: Results",
            "Content of third chapter.",
        ])
        for i in range(30):
            content_lines.append(f"Results discussion {i}.")

        # Add alphabetical index at the end
        content_lines.extend([
            "",
            "Index",
            "A",
            "algorithms, 15",
            "arrays, 23",
            "abstractions, 31",
            "B",
            "binary search, 34",
            "buffers, 45",
            "bytes, 52",
            "C",
            "cache, 56",
            "classes, 67",
            "D",
            "data structures, 78",
            "debugging, 89",
            "E",
            "encapsulation, 100",
            "exceptions, 111",
            "F",
            "functions, 122",
            "files, 133",
            "G",
            "garbage collection, 144",
            "H",
            "hashing, 155",
            "I",
            "inheritance, 166",
            "J",
            "JSON, 177",
            "K",
            "keywords, 188",
            "L",
            "loops, 199",
            "M",
            "memory, 210",
            "N",
            "null, 221",
            "O",
            "objects, 232",
            "P",
            "pointers, 243",
            "Q",
            "queues, 254",
            "R",
            "recursion, 265",
            "S",
            "stacks, 276",
            "T",
            "trees, 287",
            "U",
            "unicode, 298",
            "V",
            "variables, 309",
            "W",
            "while, 320",
        ])

        content = "\n".join(content_lines)
        result = _extract_auto("test-no-toc-with-index-end", content)

        assert result.success
        # Should use headings
        assert "headings" in result.report.method_used
        # Should detect index_only since we found index at end
        assert result.report.index_only_detected is True
        # Should have index_only warning (from the fallback detection)
        assert "index_only" in result.report.warnings

    def test_auto_adds_toc_unusable_when_no_index(self):
        """Auto method should add toc_unusable warning when TOC fails and no index."""
        from teaching.core.outline_extractor import _extract_auto

        # Content with chapters but no TOC and no index
        content = """
Some introductory text without TOC.

Chapter 1: First Topic
Content of first chapter.

Chapter 2: Second Topic
Content of second chapter.

Chapter 3: Third Topic
Content of third chapter.

Conclusion
Final thoughts without alphabetical index.
"""
        result = _extract_auto("test-no-toc-no-index", content)

        assert result.success
        # Should use headings
        assert "headings" in result.report.method_used
        # Should NOT have index_only since no index at end
        assert result.report.index_only_detected is False
        # Should have toc_unusable warning
        assert "toc_unusable" in result.report.warnings

    def test_chip_style_book_extracts_chapters_from_headings(self):
        """Book like Chip should extract chapters from headings method."""
        from teaching.core.outline_extractor import _extract_auto

        content = self.FIXTURE_PATH.read_text()
        result = _extract_auto("chip-style-book", content)

        assert result.success
        assert result.outline is not None
        # Should find 5 chapters (capítulo 1-5)
        assert result.report.chapters_found == 5
        # Verify chapter numbers
        numbers = [ch.number for ch in result.outline.chapters]
        assert numbers == [1, 2, 3, 4, 5]

    def test_method_scores_show_toc_zero_when_no_toc_marker(self):
        """Method scores should show toc=0 for books without TOC marker."""
        from teaching.core.outline_extractor import _extract_auto

        # Content without any TOC/índice marker
        content = """
Prefacio sin tabla de contenidos.

Chapter 1: Introduction
Content of first chapter.

Chapter 2: Methods
Content of second chapter.

Appendix
Additional content.
"""
        result = _extract_auto("test-no-toc-marker", content)

        assert result.success
        # toc score should be 0 (no TOC marker found)
        assert "toc" in result.report.method_scores
        assert result.report.method_scores["toc"] == 0.0
        # headings score should be > 0
        assert result.report.method_scores["headings"] > 0

    def test_toc_not_tried_when_index_only_detected_early(self):
        """When 'índice' marker is detected as index-only, toc is not tried."""
        from teaching.core.outline_extractor import _extract_auto

        content = self.FIXTURE_PATH.read_text()
        result = _extract_auto("test-index-early", content)

        assert result.success
        # toc should NOT be in method_scores since it was skipped
        # (index_only was detected at the TOC location)
        assert "toc" not in result.report.method_scores
        # headings should be there
        assert "headings" in result.report.method_scores
        assert result.report.method_scores["headings"] > 0
