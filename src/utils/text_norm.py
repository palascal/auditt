"""Normalize text for keyword matching (case + accents)."""

from __future__ import annotations

import re
import unicodedata


def fold_text(value: str | None) -> str:
    """Lowercase and strip diacritics: 'Ténor' → 'tenor'."""
    if not value:
        return ""
    s = unicodedata.normalize("NFD", str(value))
    s = "".join(ch for ch in s if unicodedata.category(ch) != "Mn")
    return s.casefold()


def keywords_match(title: str | None, keywords: list[str] | None) -> bool:
    """True if every keyword appears in title (AND), ignoring case/accents."""
    if not keywords:
        return True
    hay = fold_text(title)
    return all(fold_text(k) in hay for k in keywords if str(k).strip())


# Mouthpiece / bec — avoid bare "embouchure" (too many false positives on FR ads)
_MOUTHPIECE_RE = re.compile(
    r"(?<![a-z0-9])(?:mouth\s*pieces?|mouthpieces?|becs?(?:\s+de|\s+sax|\s+metal)?|mpces?)(?![a-z0-9])"
)
_LIGATURE_RE = re.compile(
    r"(?<![a-z0-9])(?:ligatures?|ligatur)(?![a-z0-9])"
)


def is_mouthpiece_listing(*parts: str | None) -> bool:
    """True if text looks like a sax mouthpiece (bec), not a full horn."""
    hay = fold_text(" ".join(p for p in parts if p))
    if not hay:
        return False
    return bool(_MOUTHPIECE_RE.search(f" {hay} "))


def is_ligature_listing(*parts: str | None) -> bool:
    """True if text mentions a ligature."""
    hay = fold_text(" ".join(p for p in parts if p))
    if not hay:
        return False
    return bool(_LIGATURE_RE.search(f" {hay} "))
