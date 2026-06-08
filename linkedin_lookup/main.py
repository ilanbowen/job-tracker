import os
from urllib.parse import urlparse, urlunparse

import requests
from fastapi import FastAPI, HTTPException, Query
from pydantic import BaseModel

TAVILY_ENDPOINT = "https://api.tavily.com/search"

app = FastAPI(title="Job Tracker LinkedIn Lookup")


class LinkedInCandidate(BaseModel):
    url: str
    title: str | None = None
    snippet: str | None = None
    score: float | None = None
    query: str


def normalize_url(url: str) -> str:
    parsed = urlparse(url)
    return urlunparse(
        (
            parsed.scheme,
            parsed.netloc.lower(),
            parsed.path.rstrip("/"),
            "",
            "",
            "",
        )
    )


def is_valid_linkedin_url(url: str, target_type: str) -> bool:
    parsed = urlparse(url)
    host = parsed.netloc.lower()
    path = parsed.path.lower()

    if not host.endswith("linkedin.com"):
        return False

    if target_type == "person":
        return path.startswith("/in/")

    if target_type == "company":
        return path.startswith("/company/")

    return False


def build_query(target_type: str, name: str, company_hint: str | None = None) -> str:
    if target_type == "person":
        if company_hint:
            return f'"{name}" "{company_hint}" site:linkedin.com/in'
        return f'"{name}" site:linkedin.com/in'

    if target_type == "company":
        return f'"{name}" site:linkedin.com/company'

    raise ValueError("target_type must be person or company")


def search_tavily(query: str, max_results: int = 5) -> list[dict]:
    api_key = os.getenv("TAVILY_API_KEY")

    if not api_key:
        raise HTTPException(status_code=503, detail="TAVILY_API_KEY is not configured")

    try:
        response = requests.post(
            TAVILY_ENDPOINT,
            headers={"Content-Type": "application/json"},
            json={
                "api_key": api_key,
                "query": query,
                "search_depth": "basic",
                "max_results": max_results,
                "include_answer": False,
                "include_raw_content": False,
                "include_domains": ["linkedin.com"],
            },
            timeout=30,
        )
        response.raise_for_status()
    except requests.Timeout as exc:
        raise HTTPException(status_code=504, detail="LinkedIn lookup timed out") from exc
    except requests.RequestException as exc:
        raise HTTPException(status_code=502, detail=f"Tavily lookup failed: {exc}") from exc

    return response.json().get("results", [])


def find_linkedin_urls(target_type: str, name: str, company_hint: str | None = None, limit: int = 5) -> list[LinkedInCandidate]:
    clean_name = name.strip()
    if not clean_name:
        raise HTTPException(status_code=400, detail="Name is required")

    query = build_query(target_type, clean_name, company_hint)
    results = search_tavily(query, max_results=10)

    candidates: list[LinkedInCandidate] = []
    seen = set()

    for result in results:
        raw_url = result.get("url", "")
        if not raw_url:
            continue

        url = normalize_url(raw_url)

        if url in seen:
            continue

        if not is_valid_linkedin_url(url, target_type):
            continue

        seen.add(url)
        candidates.append(
            LinkedInCandidate(
                url=url,
                title=result.get("title"),
                snippet=result.get("content"),
                score=result.get("score"),
                query=query,
            )
        )

    return candidates[:limit]


@app.get("/health")
def health() -> dict[str, str]:
    return {"status": "ok", "service": "linkedin-lookup"}


@app.get("/lookup/company", response_model=list[LinkedInCandidate])
def lookup_company(
    name: str = Query(..., min_length=1),
    limit: int = Query(5, ge=1, le=10),
):
    return find_linkedin_urls(target_type="company", name=name, limit=limit)
