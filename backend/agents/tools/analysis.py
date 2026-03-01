"""Analysis tools — database queries, situation reports, and risk assessment."""

import json
from datetime import datetime, timezone
from typing import Annotated

from agents.scoring import wrap_tool_result
from db import get_pool
from semantic_kernel.functions import kernel_function


class AnalysisPlugin:
    """Tools for analyzing aggregated disaster data and generating reports."""

    @kernel_function(description="Query the event database using a natural language description. Translates to a PostGIS spatial query.")
    async def query_event_database(
        self,
        query_description: Annotated[str, "Natural language description of what to query, e.g. 'earthquakes above magnitude 5 in South America in the last week'"],
        time_range_hours: Annotated[int, "How many hours back to search"] = 168,
    ) -> Annotated[str, "JSON string with query results"]:
        pool = await get_pool()
        async with pool.acquire() as conn:
            query_lower = query_description.lower()

            base_where = "created_at > NOW() - make_interval(hours => $1)"
            params: list = [time_range_hours]
            idx = 2

            type_filters = {
                "earthquake": "earthquake",
                "quake": "earthquake",
                "sismo": "earthquake",
                "fire": "wildfire",
                "incendio": "wildfire",
                "flood": "flood",
                "inundación": "flood",
                "storm": "storm",
                "hurricane": "cyclone",
                "cyclone": "cyclone",
                "volcano": "volcano",
                "drought": "drought",
            }

            for keyword, event_type in type_filters.items():
                if keyword in query_lower:
                    base_where += f" AND event_type = ${idx}"
                    params.append(event_type)
                    idx += 1
                    break

            import re
            mag_match = re.search(r"magnitude\s*(?:>|above|over|greater than)\s*(\d+\.?\d*)", query_lower)
            if mag_match:
                base_where += f" AND magnitude >= ${idx}"
                params.append(float(mag_match.group(1)))
                idx += 1

            if "severe" in query_lower or "critical" in query_lower or "major" in query_lower:
                base_where += f" AND severity >= ${idx}"
                params.append(4)
                idx += 1

            region_boxes = {
                "south america": (-56, -82, 13, -34),
                "central america": (7, -92, 18, -77),
                "mexico": (14, -118, 33, -86),
                "peru": (-18, -82, 0, -68),
                "chile": (-56, -76, -17, -66),
                "brazil": (-34, -74, 6, -34),
                "colombia": (-5, -80, 13, -66),
                "argentina": (-55, -74, -21, -53),
                "amazon": (-15, -75, 5, -45),
                "caribbean": (10, -85, 25, -60),
                "latin america": (-56, -118, 33, -34),
            }

            for region, (min_lat, min_lon, max_lat, max_lon) in region_boxes.items():
                if region in query_lower:
                    base_where += (
                        f" AND ST_Intersects(coordinates, "
                        f"ST_MakeEnvelope(${idx}, ${idx+1}, ${idx+2}, ${idx+3}, 4326)::geography)"
                    )
                    params.extend([min_lon, min_lat, max_lon, max_lat])
                    idx += 4
                    break

            query = f"""
                SELECT external_id, source, event_type, title, description,
                       severity, magnitude,
                       ST_Y(coordinates::geometry) as lat,
                       ST_X(coordinates::geometry) as lon,
                       started_at, created_at
                FROM events
                WHERE {base_where}
                ORDER BY severity DESC, created_at DESC
                LIMIT 50
            """

            rows = await conn.fetch(query, *params)

            stats_query = f"""
                SELECT event_type, COUNT(*) as count,
                       AVG(severity) as avg_severity,
                       MAX(magnitude) as max_magnitude
                FROM events WHERE {base_where}
                GROUP BY event_type
                ORDER BY count DESC
            """
            stats_rows = await conn.fetch(stats_query, *params)

        results = []
        timestamps = []
        for r in rows:
            results.append({
                "source": r["source"],
                "event_type": r["event_type"],
                "title": r["title"],
                "severity": r["severity"],
                "magnitude": r["magnitude"],
                "lat": r["lat"],
                "lon": r["lon"],
                "started_at": r["started_at"].isoformat() if r["started_at"] else None,
            })
            if r["created_at"]:
                timestamps.append(r["created_at"].isoformat())

        stats = [
            {
                "event_type": s["event_type"],
                "count": s["count"],
                "avg_severity": round(float(s["avg_severity"]), 1) if s["avg_severity"] else None,
                "max_magnitude": float(s["max_magnitude"]) if s["max_magnitude"] else None,
            }
            for s in stats_rows
        ]

        return wrap_tool_result(
            {"query": query_description, "total_results": len(results), "events": results, "statistics": stats},
            source="local database",
            timestamps=timestamps,
        )

    @kernel_function(description="Generate a structured situation report (sitrep) from event data for a region.")
    async def generate_situation_report(
        self,
        event_summary: Annotated[str, "Summary of events gathered by other agents"],
        region: Annotated[str, "Geographic region this report covers"],
        severity: Annotated[int, "Overall severity assessment 1-5"],
    ) -> Annotated[str, "JSON string with the structured situation report"]:
        pool = await get_pool()
        async with pool.acquire() as conn:
            report_id = await conn.fetchval(
                """
                INSERT INTO situation_reports (region, severity, content)
                VALUES ($1, $2, $3)
                RETURNING id
                """,
                region,
                severity,
                event_summary,
            )

        return wrap_tool_result(
            {
                "report_id": str(report_id),
                "region": region,
                "severity": severity,
                "content": event_summary,
                "generated_at": datetime.now(timezone.utc).isoformat(),
                "note": "This situation report has been stored for reference.",
            },
            source="local database",
            timestamps=[datetime.now(timezone.utc).isoformat()],
        )

    @kernel_function(description="Compute a composite risk assessment for a region based on event severity, fire density, media coverage, and data confidence.")
    async def compute_risk_assessment(
        self,
        region: Annotated[str, "Geographic region to assess"],
        max_severity: Annotated[float, "Maximum event severity observed (1-5 scale)"] = 1.0,
        fire_count: Annotated[int, "Number of active fire detections"] = 0,
        news_article_count: Annotated[int, "Number of news articles found"] = 0,
        avg_confidence: Annotated[float, "Average source confidence (0-1)"] = 0.5,
    ) -> Annotated[str, "JSON string with risk assessment"]:
        from agents.risk_engine import compute_risk

        assessment = compute_risk(
            region=region,
            max_severity=max_severity,
            fire_count=fire_count,
            news_article_count=news_article_count,
            avg_confidence=avg_confidence,
        )

        # Persist to database
        pool = await get_pool()
        async with pool.acquire() as conn:
            await conn.execute(
                """
                INSERT INTO risk_assessments (region, risk_score, risk_level, components, explanation)
                VALUES ($1, $2, $3, $4, $5)
                """,
                assessment.region,
                assessment.risk_score,
                assessment.risk_level,
                json.dumps(assessment.components),
                assessment.explanation,
            )

        return wrap_tool_result(
            {
                "region": assessment.region,
                "risk_score": assessment.risk_score,
                "risk_level": assessment.risk_level,
                "components": assessment.components,
                "explanation": assessment.explanation,
            },
            source="local database",
            timestamps=[datetime.now(timezone.utc).isoformat()],
        )
