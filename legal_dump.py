import csv
import io
import os
from typing import Dict, List

import requests

BASE_URL = "https://www.courtlistener.com/api/rest/v4/search/"
REQUEST_TIMEOUT_SECONDS = 20
MAX_LIMIT = 100


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
