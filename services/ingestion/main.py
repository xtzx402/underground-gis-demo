from fastapi import FastAPI
import httpx

app = FastAPI()

SOURCES = {
    "dep_catch_basins": {
        "url": "https://data.cityofnewyork.us/resource/2w2g-fk3i.json",
        "format": "GeoJSON",
        "description": "NYC DEP citywide catch basins - underground sewer network points"
    },
    "ecs_conduit": {
        "url": "https://data.cityofnewyork.us/resource/x9i6-ckbm.json",
        "format": "tabular",
        "description": "Empire City Subway conduit coverage - underground fiber conduit by neighborhood"
    },
    "gpr_vendor": {
        "url": None,
        "format": "WKT",
        "description": "Mock GPR vendor scan data - subsurface polygon areas"
    }
}

MOCK_GPR_DATA = [
    {
        "scan_id": "GPR-001",
        "geometry": "POLYGON((-74.007 40.712, -74.005 40.712, -74.005 40.714, -74.007 40.714, -74.007 40.712))",
        "depth_m": 3.5,
        "anomaly_detected": True,
        "scan_date": "2026-06-15"
    },
    {
        "scan_id": "GPR-002",
        "geometry": "POLYGON((-74.010 40.715, -74.008 40.715, -74.008 40.717, -74.010 40.717, -74.010 40.715))",
        "depth_m": 2.1,
        "anomaly_detected": False,
        "scan_date": "2026-06-15"
    }
]

@app.get("/health")
def health():
    return {"status": "ok", "service": "ingestion"}

@app.get("/ingest")
async def ingest_all():
    results = {}

    async with httpx.AsyncClient(timeout=10.0) as client:
        try:
            response = await client.get(SOURCES["dep_catch_basins"]["url"], params={"$limit": 10})
            results["dep_catch_basins"] = {
                "status": "success",
                "format": "GeoJSON",
                "count": len(response.json()),
                "data": response.json()
            }
        except Exception as e:
            results["dep_catch_basins"] = {"status": "error", "message": str(e)}

        try:
            response = await client.get(SOURCES["ecs_conduit"]["url"], params={"$limit": 10})
            results["ecs_conduit"] = {
                "status": "success",
                "format": "tabular",
                "count": len(response.json()),
                "data": response.json()
            }
        except Exception as e:
            results["ecs_conduit"] = {"status": "error", "message": str(e)}

    results["gpr_vendor"] = {
        "status": "success",
        "format": "WKT",
        "count": len(MOCK_GPR_DATA),
        "data": MOCK_GPR_DATA
    }

    return {
        "status": "success",
        "sources": list(results.keys()),
        "results": results
    }

@app.get("/ingest/{source}")
async def ingest_source(source: str):
    if source not in SOURCES:
        return {"error": f"Source '{source}' not found", "available": list(SOURCES.keys())}

    if source == "gpr_vendor":
        return {"source": source, "format": "WKT", "data": MOCK_GPR_DATA}

    async with httpx.AsyncClient(timeout=10.0) as client:
        try:
            response = await client.get(SOURCES[source]["url"], params={"$limit": 10})
            return {
                "source": source,
                "format": SOURCES[source]["format"],
                "count": len(response.json()),
                "data": response.json()
            }
        except Exception as e:
            return {"status": "error", "message": str(e)}
