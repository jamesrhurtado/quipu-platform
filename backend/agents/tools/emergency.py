"""Emergency monitoring tools — USGS, GDACS, EONET, and cached events."""

from typing import Annotated

import httpx

from agents.scoring import wrap_tool_result
from db import get_pool
from semantic_kernel.functions import kernel_function


class EmergencyPlugin:
    """Tools for querying real-time emergency and disaster data."""

    @kernel_function(description="Query recent earthquakes from USGS within a geographic bounding box.")
    async def query_earthquakes(
        self,
        min_lat: Annotated[float, "Minimum latitude of bounding box"],
        max_lat: Annotated[float, "Maximum latitude of bounding box"],
        min_lon: Annotated[float, "Minimum longitude of bounding box"],
        max_lon: Annotated[float, "Maximum longitude of bounding box"],
        min_magnitude: Annotated[float, "Minimum earthquake magnitude"] = 2.5,
        days_back: Annotated[int, "Number of days to look back (1-30)"] = 7,
    ) -> Annotated[str, "JSON string with earthquake data"]:
        url = "https://earthquake.usgs.gov/fdsnws/event/1/query"
        params = {
            "format": "geojson",
            "minlatitude": min_lat,
            "maxlatitude": max_lat,
            "minlongitude": min_lon,
            "maxlongitude": max_lon,
            "minmagnitude": min_magnitude,
            "starttime": f"now-{days_back}days",
            "orderby": "time",
            "limit": 20,
        }
        try:
            async with httpx.AsyncClient() as client:
                resp = await client.get(url, params=params, timeout=30)
                resp.raise_for_status()
                data = resp.json()
        except Exception as e:
            return wrap_tool_result(
                {"count": 0, "earthquakes": [], "error": f"USGS unavailable: {e}"},
                source="USGS",
                timestamps=[],
            )

        features = data.get("features", [])
        results = []
        timestamps = []
        for f in features:
            p = f["properties"]
            c = f["geometry"]["coordinates"]
            results.append({
                "magnitude": p.get("mag"),
                "place": p.get("place"),
                "time": p.get("time"),
                "depth_km": c[2] if len(c) > 2 else None,
                "lat": c[1],
                "lon": c[0],
                "url": p.get("url"),
                "felt": p.get("felt"),
                "tsunami": p.get("tsunami"),
            })
            # USGS time is millisecond unix timestamp
            if p.get("time"):
                timestamps.append(p["time"])

        return wrap_tool_result(
            {"count": len(results), "earthquakes": results},
            source="USGS",
            timestamps=timestamps,
        )

    @kernel_function(description="Query GDACS disaster alerts filtered by event type, alert level, or country.")
    async def query_gdacs_alerts(
        self,
        event_type: Annotated[str, "Event type: EQ, TC, FL, VO, WF, DR, or 'all'"] = "all",
        alert_level: Annotated[str, "Alert level: Red, Orange, Green, or 'all'"] = "all",
        days_back: Annotated[int, "Number of days to look back"] = 7,
    ) -> Annotated[str, "JSON string with GDACS alerts"]:
        import xml.etree.ElementTree as ET

        url = "https://www.gdacs.org/xml/rss.xml"
        try:
            async with httpx.AsyncClient() as client:
                resp = await client.get(url, timeout=30)
                resp.raise_for_status()
        except Exception as e:
            return wrap_tool_result(
                {"count": 0, "alerts": [], "error": f"GDACS unavailable: {e}"},
                source="GDACS",
                timestamps=[],
            )

        root = ET.fromstring(resp.text)
        items = root.findall(".//item")

        results = []
        timestamps = []
        for item in items:
            entry = {}
            for child in item:
                tag = child.tag.split("}")[-1] if "}" in child.tag else child.tag
                prefix = child.tag.split("}")[0].replace("{", "") if "}" in child.tag else ""
                key = f"gdacs:{tag}" if "gdacs" in prefix else f"geo:{tag}" if "geo" in prefix else tag
                entry[key] = child.text

            et = entry.get("gdacs:eventtype", "")
            al = entry.get("gdacs:alertlevel", "")

            if event_type != "all" and et != event_type:
                continue
            if alert_level != "all" and al != alert_level:
                continue

            from_date = entry.get("gdacs:fromdate", "")
            results.append({
                "title": entry.get("title", ""),
                "event_type": et,
                "alert_level": al,
                "country": entry.get("gdacs:country", ""),
                "lat": entry.get("geo:lat", ""),
                "lon": entry.get("geo:long", ""),
                "from_date": from_date,
                "severity": entry.get("gdacs:severity", ""),
                "population": entry.get("gdacs:population", ""),
            })
            if from_date:
                timestamps.append(from_date)

        return wrap_tool_result(
            {"count": len(results), "alerts": results[:20]},
            source="GDACS",
            timestamps=timestamps,
        )

    @kernel_function(description="Query NASA EONET for active natural events by category.")
    async def query_eonet_events(
        self,
        category: Annotated[str, "Category: wildfires, severeStorms, volcanoes, floods, earthquakes, seaLakeIce, or 'all'"] = "all",
        days_back: Annotated[int, "Number of days to look back"] = 30,
        status: Annotated[str, "Event status: open, closed, or all"] = "open",
    ) -> Annotated[str, "JSON string with EONET events"]:
        url = "https://eonet.gsfc.nasa.gov/api/v3/events"
        params = {"status": status, "limit": 30, "days": days_back}
        if category != "all":
            params["category"] = category

        try:
            async with httpx.AsyncClient() as client:
                resp = await client.get(url, params=params, timeout=30)
                resp.raise_for_status()
                data = resp.json()
        except Exception as e:
            return wrap_tool_result(
                {"count": 0, "events": [], "error": f"NASA EONET unavailable: {e}"},
                source="NASA EONET",
                timestamps=[],
            )

        events = data.get("events", [])
        results = []
        timestamps = []
        for evt in events:
            geometries = evt.get("geometry", evt.get("geometries", []))
            latest = geometries[-1] if isinstance(geometries, list) and geometries else {}
            coords = latest.get("coordinates", [])
            categories = evt.get("categories", [])

            event_date = latest.get("date", "")
            results.append({
                "title": evt.get("title", ""),
                "category": categories[0].get("title", "") if categories else "",
                "date": event_date,
                "lat": coords[1] if len(coords) > 1 else None,
                "lon": coords[0] if coords else None,
                "sources": [s.get("url", "") for s in evt.get("sources", [])],
            })
            if event_date:
                timestamps.append(event_date)

        return wrap_tool_result(
            {"count": len(results), "events": results},
            source="NASA EONET",
            timestamps=timestamps,
        )

    @kernel_function(description="Query cached events from the local PostGIS database within a radius of a point.")
    async def query_cached_events(
        self,
        lat: Annotated[float, "Center latitude"],
        lon: Annotated[float, "Center longitude"],
        radius_km: Annotated[float, "Search radius in kilometers"] = 500,
        event_type: Annotated[str, "Filter by event type or 'all'"] = "all",
        hours_back: Annotated[int, "Number of hours to look back"] = 48,
    ) -> Annotated[str, "JSON string with cached events"]:
        conditions = [
            "ST_DWithin(coordinates, ST_SetSRID(ST_MakePoint($1, $2), 4326)::geography, $3)",
            "created_at > NOW() - make_interval(hours => $4)",
        ]
        params: list = [lon, lat, radius_km * 1000, hours_back]
        idx = 5

        if event_type != "all":
            conditions.append(f"event_type = ${idx}")
            params.append(event_type)

        where = " AND ".join(conditions)
        query = f"""
            SELECT external_id, source, event_type, title, description,
                   severity, magnitude,
                   ST_Y(coordinates::geometry) as lat,
                   ST_X(coordinates::geometry) as lon,
                   started_at, created_at
            FROM events WHERE {where}
            ORDER BY severity DESC, created_at DESC
            LIMIT 30
        """

        pool = await get_pool()
        async with pool.acquire() as conn:
            rows = await conn.fetch(query, *params)

        results = []
        timestamps = []
        for r in rows:
            results.append({
                "external_id": r["external_id"],
                "source": r["source"],
                "event_type": r["event_type"],
                "title": r["title"],
                "description": r["description"],
                "severity": r["severity"],
                "magnitude": r["magnitude"],
                "lat": r["lat"],
                "lon": r["lon"],
                "started_at": r["started_at"].isoformat() if r["started_at"] else None,
            })
            if r["created_at"]:
                timestamps.append(r["created_at"].isoformat())

        return wrap_tool_result(
            {"count": len(results), "events": results},
            source="local database",
            timestamps=timestamps,
        )
