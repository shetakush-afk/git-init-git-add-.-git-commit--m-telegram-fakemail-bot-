import csv
import io
import os
import re
from collections import Counter
from typing import Dict, List

import requests

BASE_URL = "https://www.courtlistener.com/api/rest/v4/search/"
REQUEST_TIMEOUT_SECONDS = 20
MAX_LIMIT = 100
MAX_KEYWORD_LIMIT = 30

LEGAL_SUFFIXES = (
    "judgment",
    "case law",
    "legal precedent",
    "appeal",
    "petition",
    "order",
)

COMMON_STOPWORDS = {
    "about",
    "after",
    "against",
    "between",
    "case",
    "court",
    "for",
    "from",
    "into",
    "law",
    "legal",
    "order",
    "over",
    "that",
    "the",
    "their",
    "these",
    "this",
    "those",
    "under",
    "with",
}

MANUAL_VARIANTS = {
    "bail": [
        "anticipatory bail",
        "regular bail",
        "bail cancellation",
    ],
    "contract": [
        "breach of contract",
        "contract dispute",
        "specific performance contract",
    ],
    "property": [
        "property possession",
        "property title dispute",
        "land ownership dispute",
    ],
    "divorce": [
        "mutual consent divorce",
        "contested divorce",
        "maintenance after divorce",
    ],
    "criminal": [
        "criminal appeal",
        "criminal revision",
        "criminal procedure",
    ],
}


class LegalSourceError(RuntimeError):
    """Raised when the legal source API cannot be reached or parsed."""


def _build_headers() -> Dict[str, str]:
    headers = {"User-Agent": "LegalDumpBot/1.0"}
    api_key = os.getenv("COURTLISTENER_API_KEY")
    if api_key:
        headers["Authorization"] = f"Token {api_key}"
    return headers


def _format_citation(citation) -> str:
    if isinstance(citation, str):
        return citation
    if isinstance(citation, list):
        cites = [
            item.get("cite")
            for item in citation
            if isinstance(item, dict) and item.get("cite")
        ]
        return "; ".join(cites)
    return ""


def _normalize_case(item: Dict[str, object]) -> Dict[str, str]:
    absolute_url = str(item.get("absolute_url") or "")
    if absolute_url and not absolute_url.startswith("http"):
        absolute_url = f"https://www.courtlistener.com{absolute_url}"

    return {
        "case_name": str(item.get("caseName") or item.get("caseNameFull") or "Unknown"),
        "court": str(item.get("court") or "Unknown"),
        "date_filed": str(item.get("dateFiled") or "Unknown"),
        "docket_number": str(item.get("docketNumber") or ""),
        "citation": _format_citation(item.get("citation")),
        "url": absolute_url,
    }


def _tokenize_text(value: str) -> List[str]:
    if not value:
        return []

    tokens = re.findall(r"[A-Za-z]{3,}", value.lower())
    if not tokens:
        tokens = [part.lower() for part in value.split() if len(part) >= 3]
    return [token for token in tokens if token not in COMMON_STOPWORDS]


def _push_unique(bucket: List[str], text: str):
    cleaned = (text or "").strip()
    if cleaned and cleaned not in bucket:
        bucket.append(cleaned)


def _rank_related_terms(cases: List[Dict[str, str]]) -> List[str]:
    counter: Counter = Counter()
    for case in cases:
        line = " ".join(
            [
                case.get("case_name", ""),
                case.get("court", ""),
                case.get("citation", ""),
            ]
        )
        for token in _tokenize_text(line):
            counter[token] += 1
    return [word for word, _ in counter.most_common(40)]


def search_cases(query: str, limit: int = 20) -> List[Dict[str, str]]:
    cleaned_query = (query or "").strip()
    if not cleaned_query:
        return []

    wanted = max(1, min(limit, MAX_LIMIT))
    results: List[Dict[str, str]] = []
    next_url = BASE_URL
    params = {"q": cleaned_query, "order_by": "score desc"}
    headers = _build_headers()

    try:
        while next_url and len(results) < wanted:
            response = requests.get(
                next_url,
                params=params,
                headers=headers,
                timeout=REQUEST_TIMEOUT_SECONDS,
            )
            response.raise_for_status()
            payload = response.json()

            for item in payload.get("results", []):
                if isinstance(item, dict):
                    results.append(_normalize_case(item))
                if len(results) >= wanted:
                    break

            next_url = payload.get("next")
            params = None
    except requests.RequestException as exc:
        raise LegalSourceError(
            "Legal data source tak pahunch nahi hui. Thodi der baad dobara try karein."
        ) from exc
    except ValueError as exc:
        raise LegalSourceError(
            "Legal data source se invalid response mila."
        ) from exc

    return results


def generate_keywords(seed_query: str, limit: int = 12) -> List[str]:
    cleaned_query = (seed_query or "").strip()
    if not cleaned_query:
        return []

    wanted = max(3, min(limit, MAX_KEYWORD_LIMIT))
    keywords: List[str] = []
    base_tokens = _tokenize_text(cleaned_query)

    _push_unique(keywords, cleaned_query)

    for token in base_tokens:
        _push_unique(keywords, token)
        for variant in MANUAL_VARIANTS.get(token, []):
            _push_unique(keywords, variant)
        for suffix in LEGAL_SUFFIXES:
            _push_unique(keywords, f"{token} {suffix}")

    for suffix in ("judgment", "case law", "latest order"):
        _push_unique(keywords, f"{cleaned_query} {suffix}")

    try:
        cases = search_cases(cleaned_query, limit=20)
    except LegalSourceError:
        cases = []

    if cases:
        related_tokens = _rank_related_terms(cases)
        for token in related_tokens:
            if token in base_tokens or token in COMMON_STOPWORDS:
                continue
            _push_unique(keywords, f"{cleaned_query} {token}")
            _push_unique(keywords, f"{token} judgment")
            if len(keywords) >= wanted * 3:
                break

    return keywords[:wanted]


def build_csv_dump(query: str, cases: List[Dict[str, str]]) -> io.BytesIO:
    csv_buffer = io.StringIO()
    writer = csv.DictWriter(
        csv_buffer,
        fieldnames=[
            "query",
            "case_name",
            "court",
            "date_filed",
            "docket_number",
            "citation",
            "url",
        ],
    )
    writer.writeheader()

    for case in cases:
        writer.writerow(
            {
                "query": query,
                "case_name": case.get("case_name", ""),
                "court": case.get("court", ""),
                "date_filed": case.get("date_filed", ""),
                "docket_number": case.get("docket_number", ""),
                "citation": case.get("citation", ""),
                "url": case.get("url", ""),
            }
        )

    file_buffer = io.BytesIO(csv_buffer.getvalue().encode("utf-8"))
    file_buffer.seek(0)
    return file_buffer
