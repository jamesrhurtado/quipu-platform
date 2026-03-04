"""Fire monitoring tools — NASA FIRMS active fire detection."""

import json
from typing import Annotated

import httpx

from agents.scoring import wrap_tool_result
from config import settings
from semantic_kernel.functions import kernel_function


class FireMonitorPlugin:
    """Tools for querying active fire detections from NASA FIRMS."""

    @kernel_function(description="Query NASA FIRMS for active fire detections near a location.")
    async def query_active_fires(
        self,
        lat: Annotated[float, "Center latitude"],
        lon: Annotated[float, "Center longitude"],
        radius_km: Annotated[float, "Search radius in kilometers"] = 100,
        days_back: Annotated[int, "Number of days to look back (1-10)"] = 1,
        min_confidence: Annotated[str, "Minimum confidence: low, nominal, high"] = "nominal",
    ) -> Annotated[str, "JSON string with active fire data"]:
        if not settings.nasa_firms_map_key:
            return json.dumps({"error": "FIRMS API key not configured", "fires": []})

        # FIRMS API expects area as W,S,E,N bbox
        delta = radius_km / 111.0  # rough degree conversion
        bbox = f"{lon - delta},{lat - delta},{lon + delta},{lat + delta}"

        url = (
            f"https://firms.modaps.eosdis.nasa.gov/api/area/csv/"
            f"{settings.nasa_firms_map_key}/VIIRS_SNPP_NRT/{bbox}/{days_back}"
        )

        try:
            async with httpx.AsyncClient() as client:
                resp = await client.get(url, timeout=60)
                resp.raise_for_status()
        except Exception as e:
            return wrap_tool_result(
                {"count": 0, "fires": [], "error": f"NASA FIRMS unavailable: {e}"},
                source="NASA FIRMS",
                timestamps=[],
            )

        lines = resp.text.strip().split("\n")
        if len(lines) < 2:
            return wrap_tool_result(
                {"count": 0, "fires": []},
                source="NASA FIRMS",
                timestamps=[],
            )

        headers = lines[0].split(",")
        fires = []
        timestamps = []
        conf_order = {"low": 0, "nominal": 1, "high": 2}
        min_conf_val = conf_order.get(min_confidence, 0)

        for line in lines[1:]:
            values = line.split(",")
            if len(values) != len(headers):
                continue
            fire = dict(zip(headers, values))

            fire_conf = fire.get("confidence", "nominal").lower()
            if conf_order.get(fire_conf, 0) < min_conf_val:
                continue

            acq_date = fire.get("acq_date", "")
            fires.append({
                "lat": float(fire.get("latitude", 0)),
                "lon": float(fire.get("longitude", 0)),
                "brightness": fire.get("bright_ti4", ""),
                "frp": fire.get("frp", ""),
                "confidence": fire.get("confidence", ""),
                "acq_date": acq_date,
                "acq_time": fire.get("acq_time", ""),
                "instrument": fire.get("instrument", ""),
            })
            if acq_date:
                timestamps.append(acq_date)

        return wrap_tool_result(
            {"count": len(fires), "fires": fires[:100]},
            source="NASA FIRMS",
            timestamps=timestamps,
        )
