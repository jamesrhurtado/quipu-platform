"""Social media and news monitoring tools — GDELT, Bluesky, ReliefWeb."""

import json
from typing import Annotated

import httpx

from agents.scoring import wrap_tool_result
from semantic_kernel.functions import kernel_function


class SocialNewsPlugin:
    """Tools for searching news articles and social media for disaster information."""

    @kernel_function(description="Search GDELT DOC 2.0 for news articles about disasters.")
    async def search_gdelt_news(
        self,
        query: Annotated[str, "Search query (e.g. 'earthquake Peru')"],
        source_country: Annotated[str, "Two-letter country code to filter sources, or 'all'"] = "all",
        timespan: Annotated[str, "Time span: 15min, 1h, 1d, 7d"] = "7d",
        max_results: Annotated[int, "Maximum number of results to return"] = 15,
    ) -> Annotated[str, "JSON string with news articles"]:
        # Map timespan to GDELT format (minutes)
        timespan_map = {"15min": "15", "1h": "60", "1d": "1440", "7d": "10080"}
        ts = timespan_map.get(timespan, "10080")

        url = "https://api.gdeltproject.org/api/v2/doc/doc"
        params = {
            "query": query,
            "mode": "ArtList",
            "maxrecords": min(max_results, 50),
            "format": "json",
            "timespan": f"{ts}min",
        }
        if source_country != "all":
            params["query"] += f" sourcecountry:{source_country}"

        try:
            async with httpx.AsyncClient() as client:
                resp = await client.get(url, params=params, timeout=30)
                resp.raise_for_status()
                data = resp.json()
        except (httpx.ConnectTimeout, httpx.ReadTimeout, httpx.HTTPStatusError, Exception) as e:
            return wrap_tool_result(
                {"count": 0, "articles": [], "error": f"GDELT unavailable: {e}"},
                source="GDELT",
                timestamps=[],
            )

        articles = data.get("articles", [])
        results = []
        timestamps = []
        for a in articles[:max_results]:
            seendate = a.get("seendate", "")
            results.append({
                "title": a.get("title", ""),
                "url": a.get("url", ""),
                "source": a.get("domain", ""),
                "language": a.get("language", ""),
                "country": a.get("sourcecountry", ""),
                "seendate": seendate,
                "socialimage": a.get("socialimage", ""),
            })
            if seendate:
                timestamps.append(seendate)

        return wrap_tool_result(
            {"count": len(results), "articles": results},
            source="GDELT",
            timestamps=timestamps,
        )

    @kernel_function(description="Search recent Bluesky social media posts matching disaster keywords.")
    async def monitor_bluesky(
        self,
        keywords: Annotated[str, "Comma-separated keywords to search for (e.g. 'sismo,earthquake,terremoto')"],
        max_results: Annotated[int, "Maximum number of posts to return"] = 30,
    ) -> Annotated[str, "JSON string with matching social media posts"]:
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

    @kernel_function(description="Search ReliefWeb for humanitarian reports and situation updates.")
    async def search_reliefweb(
        self,
        query: Annotated[str, "Search query"],
        country: Annotated[str, "Country name to filter by, or 'all'"] = "all",
        disaster_type: Annotated[str, "Disaster type: earthquake, flood, cyclone, wildfire, drought, or 'all'"] = "all",
        days_back: Annotated[int, "Number of days to look back"] = 30,
    ) -> Annotated[str, "JSON string with humanitarian reports"]:
        from config import settings as app_settings

        url = "https://api.reliefweb.int/v1/reports"
        params = {"appname": app_settings.reliefweb_appname}
        payload: dict = {
            "query": {"value": query},
            "limit": 15,
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
