from fastapi import FastAPI
import httpx
import os

app = FastAPI(title="Underground GIS API")

INGESTION_URL = os.getenv("INGESTION_URL", "http://ingestion:8000")
TRANSFORM_URL = os.getenv("TRANSFORM_URL", "http://transform:8001")
STORAGE_URL = os.getenv("STORAGE_URL", "http://storage:8002")
TTL_URL = os.getenv("TTL_URL", "http://ttl:8003")

@app.get("/health")
async def health():
    """Check health of all services"""
    services = {}
    async with httpx.AsyncClient(timeout=5.0) as client:
        for name, url in [
            ("ingestion", INGESTION_URL),
            ("transform", TRANSFORM_URL),
            ("storage", STORAGE_URL),
            ("ttl", TTL_URL)
        ]:
            try:
                r = await client.get(f"{url}/health")
                services[name] = r.json()
            except Exception as e:
                services[name] = {"status": "error", "message": str(e)}
    return {"status": "ok", "service": "api", "dependencies": services}

@app.post("/pipeline/run")
async def run_pipeline():
    """
    Run full data pipeline:
    ingest -> transform -> store
    """
    async with httpx.AsyncClient(timeout=30.0) as client:
        # Step 1: Ingest from all sources
        ingest_response = await client.get(f"{INGESTION_URL}/ingest")
        raw_data = ingest_response.json()

        # Step 2: Transform to normalized format
        transform_response = await client.post(
            f"{TRANSFORM_URL}/transform",
            json=raw_data
        )
        transformed_data = transform_response.json()

        # Step 3: Store to PostGIS
        store_response = await client.post(
            f"{STORAGE_URL}/store",
            json=transformed_data
        )
        store_result = store_response.json()

    return {
        "status": "success",
        "pipeline": {
            "sources_ingested": raw_data.get("sources", []),
            "transformed_count": transformed_data.get("feature_count", 0),
            "stored_spatial": store_result.get("stored_spatial", 0),
            "stored_attribute": store_result.get("stored_attribute", 0),
            "errors": store_result.get("errors", [])
        }
    }

@app.get("/features")
async def get_features(limit: int = 20):
    """Get active spatial features (catch basins + GPR scans)"""
    async with httpx.AsyncClient(timeout=10.0) as client:
        response = await client.get(
            f"{STORAGE_URL}/features",
            params={"limit": limit}
        )
        return response.json()

@app.get("/features/bbox")
async def get_features_bbox(
    min_lon: float = -74.05,
    min_lat: float = 40.68,
    max_lon: float = -73.93,
    max_lat: float = 40.85
):
    """Spatial query - get features within NYC bounding box"""
    async with httpx.AsyncClient(timeout=10.0) as client:
        response = await client.get(
            f"{STORAGE_URL}/features/bbox",
            params={
                "min_lon": min_lon,
                "min_lat": min_lat,
                "max_lon": max_lon,
                "max_lat": max_lat
            }
        )
        return response.json()

@app.get("/conduit")
async def get_conduit(borough: str = None):
    """Get ECS conduit coverage data by neighborhood"""
    async with httpx.AsyncClient(timeout=10.0) as client:
        params = {}
        if borough:
            params["borough"] = borough
        response = await client.get(
            f"{STORAGE_URL}/conduit",
            params=params
        )
        return response.json()

@app.get("/ttl/stats")
async def ttl_stats():
    """Get TTL statistics for both tables"""
    async with httpx.AsyncClient(timeout=10.0) as client:
        response = await client.get(f"{TTL_URL}/stats")
        return response.json()

@app.post("/ttl/cleanup")
async def trigger_cleanup():
    """Manually trigger TTL cleanup"""
    async with httpx.AsyncClient(timeout=10.0) as client:
        response = await client.post(f"{TTL_URL}/cleanup")
        return response.json()
