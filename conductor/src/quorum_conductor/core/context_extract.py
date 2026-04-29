"""Document extraction + URL fetch helpers.

Per design-doc §1.8:

* Documents → extract to Markdown text up front (PDFs via pdfplumber,
  DOCX via python-docx, plaintext/Markdown stored as-is). The
  extracted Markdown lives at `context/docs/raw/<name>.md`. Large
  docs (>~5K tokens) get summarised by an agent and the digest
  written to `context/docs/digested/<name>.md`; small docs stay raw.
* URLs → fetched, converted to Markdown via trafilatura, cached at
  `context/web/cached/<name>.md`. Failed fetches surface a clear
  error so the user can fix the URL or remove the entry.

Token counting is approximate — we don't load a real tokenizer for
v1; rough heuristic of `words * 1.3` is close enough for the
"is-this-doc-big-enough-to-warrant-digestion" decision.
"""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

DOC_DIGEST_TOKEN_THRESHOLD = 5_000


# ---------------------------------------------------------------------- #
# Document extraction
# ---------------------------------------------------------------------- #


@dataclass(frozen=True)
class ExtractedDoc:
    """A document after extraction.

    `markdown` is the plaintext-or-Markdown body the agent sees.
    `tokens_estimated` drives the auto-digest threshold.
    """

    markdown: str
    tokens_estimated: int


class DocumentExtractError(RuntimeError):
    """Raised when a doc can't be parsed (e.g. scanned PDF without OCR)."""


def extract_doc(source: Path) -> ExtractedDoc:
    """Extract Markdown text from a local file.

    Supported extensions: .md, .markdown, .txt, .pdf, .docx.
    Other types raise DocumentExtractError.
    """
    suffix = source.suffix.lower()
    if suffix in {".md", ".markdown", ".txt"}:
        text = source.read_text(encoding="utf-8", errors="replace")
    elif suffix == ".pdf":
        text = _extract_pdf(source)
    elif suffix == ".docx":
        text = _extract_docx(source)
    else:
        raise DocumentExtractError(
            f"Unsupported file type {suffix!r}. v1 supports .md, .txt, .pdf, .docx."
        )
    text = text.strip() + "\n"
    return ExtractedDoc(markdown=text, tokens_estimated=_estimate_tokens(text))


def _extract_pdf(source: Path) -> str:
    """Extract text from a PDF using pdfplumber.

    Pages are joined with `\n\n## Page N\n\n` headers so the agent can
    refer back to specific pages later. Empty pages (scanned PDFs
    without OCR) raise so the user gets a clear error.
    """
    try:
        import pdfplumber
    except ImportError as exc:  # pragma: no cover
        raise DocumentExtractError(f"pdfplumber not available: {exc}") from exc

    chunks: list[str] = []
    any_text = False
    with pdfplumber.open(str(source)) as pdf:
        for i, page in enumerate(pdf.pages, start=1):
            page_text = (page.extract_text() or "").strip()
            chunks.append(f"## Page {i}\n\n{page_text}")
            if page_text:
                any_text = True
    if not any_text:
        raise DocumentExtractError(
            "PDF has no extractable text. v1 doesn't OCR scanned documents — "
            "convert to a text PDF (or paste the text into a Note) and retry."
        )
    return "\n\n".join(chunks)


def _extract_docx(source: Path) -> str:
    """Extract text from a Word document using python-docx."""
    try:
        from docx import Document
    except ImportError as exc:  # pragma: no cover
        raise DocumentExtractError(f"python-docx not available: {exc}") from exc

    doc = Document(str(source))
    paras = [p.text for p in doc.paragraphs if p.text.strip()]
    return "\n\n".join(paras)


def _estimate_tokens(text: str) -> int:
    """Rough heuristic: words * 1.3 ≈ tokens.

    Real tokenisation differs by model; this is good enough to decide
    whether a doc warrants digestion. Tightens up if/when we add
    `tiktoken` or model-specific tokenisers in v2.
    """
    return int(len(text.split()) * 1.3)


# ---------------------------------------------------------------------- #
# URL fetch
# ---------------------------------------------------------------------- #


@dataclass(frozen=True)
class FetchedUrl:
    """A URL after fetch + readability extraction."""

    url: str
    title: str
    markdown: str


class UrlFetchError(RuntimeError):
    """Raised when a URL can't be fetched or has no extractable content."""


def fetch_url(url: str, *, timeout_s: float = 20.0) -> FetchedUrl:
    """Fetch `url` and extract the readable body as Markdown.

    Uses trafilatura (Readability + boilerplate stripping) to keep
    the payload sane. Raises UrlFetchError on any failure — the
    caller decides how to surface to the user.
    """
    try:
        import trafilatura
    except ImportError as exc:  # pragma: no cover
        raise UrlFetchError(f"trafilatura not available: {exc}") from exc

    raw = trafilatura.fetch_url(url)
    if not raw:
        raise UrlFetchError(f"Could not fetch {url}.")
    markdown = trafilatura.extract(
        raw,
        output_format="markdown",
        include_comments=False,
        include_tables=True,
        favor_recall=True,
    )
    if not markdown or not markdown.strip():
        raise UrlFetchError(
            f"{url} fetched but no readable text was extracted. "
            "If the page is a SPA or paywalled, save the rendered HTML as a doc instead."
        )
    metadata = trafilatura.extract_metadata(raw)
    title = (metadata.title if metadata and metadata.title else url).strip()
    return FetchedUrl(url=url, title=title, markdown=markdown.strip() + "\n")


def estimate_tokens(text: str) -> int:
    """Public wrapper for the rough token-count heuristic."""
    return _estimate_tokens(text)


__all__ = [
    "DOC_DIGEST_TOKEN_THRESHOLD",
    "DocumentExtractError",
    "ExtractedDoc",
    "FetchedUrl",
    "UrlFetchError",
    "estimate_tokens",
    "extract_doc",
    "fetch_url",
]
