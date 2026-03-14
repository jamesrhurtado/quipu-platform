"""Social media and news monitoring tools — Google News, Bluesky, ReliefWeb."""

import json
import xml.etree.ElementTree as ET
from typing import Annotated

import httpx

from agent_framework import tool
from agents.scoring import wrap_tool_result


@tool
async def search_news(
    query: Annotated[str, "Search query (e.g. 'earthquake Peru', 'sismo Cajamarca')"],
    language: Annotated[str, "Language: 'en' for English, 'es' for Spanish"] = "es",
    max_results: Annotated[int, "Maximum number of results to return"] = 8,
) -> str:
    """Search Google News for recent articles about disasters. Supports English and Spanish queries."""
    lang_map = {
        "es": {"hl": "es", "gl": "PE", "ceid": "PE:es"},
        "en": {"hl": "en", "gl": "US", "ceid": "US:en"},
    }
    locale = lang_map.get(language, lang_map["es"])

    try:
        async with httpx.AsyncClient(follow_redirects=True) as client:
            resp = await client.get(
                "https://news.google.com/rss/search",
                params={"q": query, **locale},
                timeout=15,
            )
            resp.raise_for_status()

        root = ET.fromstring(resp.text)
        items = root.findall(".//item")
    except Exception as e:
        return wrap_tool_result(
            {"count": 0, "articles": [], "error": f"Google News unavailable: {e}"},
            source="Google News",
            timestamps=[],
        )

    results = []
    timestamps = []
    for item in items[:max_results]:
        title_el = item.find("title")
        link_el = item.find("link")
        pubdate_el = item.find("pubDate")
        source_el = item.find("source")

        pubdate = pubdate_el.text if pubdate_el is not None else ""
        results.append({
            "title": title_el.text if title_el is not None else "",
            "url": link_el.text if link_el is not None else "",
            "source": source_el.text if source_el is not None else "",
            "published": pubdate,
        })
        if pubdate:
            timestamps.append(pubdate)

    return wrap_tool_result(
        {"count": len(results), "articles": results},
        source="Google News",
        timestamps=timestamps,
    )


@tool
async def monitor_bluesky(
    keywords: Annotated[str, "Comma-separated keywords to search for (e.g. 'sismo,earthquake,terremoto')"],
    max_results: Annotated[int, "Maximum number of posts to return"] = 10,
) -> str:
    """Search recent Bluesky social media posts matching disaster keywords."""
    from config import settings

    if not settings.bluesky_enabled:
        return json.dumps({
            "count": 0,
            "posts": [],
            "source": "Bluesky",
            "reliability_score": 0.4,
            "freshness_score": 0.0,
            "note": "Bluesky monitoring is disabled",
        })

    from services.bluesky_buffer import bluesky_buffer

    keyword_list = [k.strip() for k in keywords.split(",") if k.strip()]
    posts = bluesky_buffer.search(keyword_list, max_results=max_results)

    timestamps = [p.get("created_at", "") for p in posts if p.get("created_at")]

    return wrap_tool_result(
        {"count": len(posts), "posts": posts, "buffer_stats": bluesky_buffer.stats()},
        source="Bluesky",
        timestamps=timestamps,
    )


@tool
async def search_reliefweb(
    query: Annotated[str, "Search query"],
    country: Annotated[str, "Country name to filter by, or 'all'"] = "all",
    disaster_type: Annotated[str, "Disaster type: earthquake, flood, cyclone, wildfire, drought, or 'all'"] = "all",
    days_back: Annotated[int, "Number of days to look back"] = 30,
) -> str:
    """Search ReliefWeb for humanitarian reports and situation updates."""
    from config import settings as app_settings

    url = "https://api.reliefweb.int/v1/reports"
    params = {"appname": app_settings.reliefweb_appname}
    payload: dict = {
        "query": {"value": query},
        "limit": 8,
        "sort": ["date.created:desc"],
        "fields": {
            "include": [
                "title", "url", "source", "date", "country",
                "disaster_type",
            ],
        },
    }

    filters = []
    if country != "all":
        filters.append({"field": "country.name", "value": country})
    if disaster_type != "all":
        filters.append({"field": "disaster_type.name", "value": disaster_type})
    if filters:
        payload["filter"] = {"conditions": filters, "operator": "AND"}

    try:
        async with httpx.AsyncClient() as client:
            resp = await client.post(url, params=params, json=payload, timeout=30)
            resp.raise_for_status()
            data = resp.json()
    except Exception as e:
        return wrap_tool_result(
            {
                "count": 0,
                "reports": [],
                "error": f"ReliefWeb API unavailable: {e}. Do NOT retry this tool — use other sources instead.",
            },
            source="ReliefWeb",
            timestamps=[],
        )

    reports = data.get("data", [])
    results = []
    timestamps = []
    for r in reports:
        fields = r.get("fields", {})
        date_created = fields.get("date", {}).get("created", "")
        results.append({
            "title": fields.get("title", ""),
            "url": fields.get("url", ""),
            "date": date_created,
            "source": [s.get("name", "") for s in fields.get("source", [])],
            "countries": [c.get("name", "") for c in fields.get("country", [])],
            "disaster_types": [d.get("name", "") for d in fields.get("disaster_type", [])],
        })
        if date_created:
            timestamps.append(date_created)

    return wrap_tool_result(
        {"count": len(results), "reports": results},
        source="ReliefWeb",
        timestamps=timestamps,
    )
