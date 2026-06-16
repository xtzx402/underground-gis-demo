from fastapi import FastAPI
import asyncpg
import json
import os
from datetime import datetime, timedelta

app = FastAPI()

DB_URL = os.getenv("DB_URL", "postgresql://postgres:postgres@db:5432/gisdb")

async def get_db():
    return await asyncpg.connect(DB_URL)

@app.on_event("startup")
async def startup():
    conn = await get_db()
    try:
        await conn.execute("CREATE EXTENSION IF NOT EXISTS postgis;")
        await conn.execute("""
            CREATE TABLE IF NOT EXISTS underground_features (
                id SERIAL PRIMARY KEY,
                source VARCHAR(100) NOT NULL,
                infrastructure_type VARCHAR(100),
                unit_id VARCHAR(50),
                scan_id VARCHAR(50),
                depth_m FLOAT,
                anomaly_detected BOOLEAN,
                scan_date VARCHAR(20),
                geometry GEOMETRY(Geometry, 4326),
                ingested_at TIMESTAMP DEFAULT NOW(),
                expires_at TIMESTAMP DEFAULT NOW() + INTERVAL '14 days'
            );
        """)
        await conn.execute("""
            CREATE TABLE IF NOT EXISTS underground_conduit (
                id SERIAL PRIMARY KEY,
                source VARCHAR(100) NOT NULL,
                nta_code VARCHAR(20),
                nta_name VARCHAR(100),
                borough VARCHAR(50),
                conduit_route_mileage FLOAT,
                conduit_mileage_total FLOAT,
                conduit_mileage_available FLOAT,
                conduit_availability_ratio FLOAT,
                ingested_at TIMESTAMP DEFAULT NOW(),
                expires_at TIMESTAMP DEFAULT NOW() + INTERVAL '14 days'
            );
        """)
        await conn.execute("CREATE INDEX IF NOT EXISTS idx_geometry ON underground_features USING GIST(geometry);")
        await conn.execute("CREATE INDEX IF NOT EXISTS idx_nta_code ON underground_conduit(nta_code);")
    finally:
        await conn.close()

@app.get("/health")
def health():
    return {"status": "ok", "service": "storage"}

@app.post("/store")
async def store_features(payload: dict):
    features = payload.get("features", [])
    stored_spatial = 0
    stored_attribute = 0
    errors = []

    conn = await get_db()
    try:
        for feature in features:
            source = feature.get("source", "unknown")
            try:
                if source == "ecs_conduit":
                    await conn.execute("""
                        INSERT INTO underground_conduit
                            (source, nta_code, nta_name, borough,
                             conduit_route_mileage, conduit_mileage_total,
                             conduit_mileage_available, conduit_availability_ratio,
                             expires_at)
                        VALUES ($1,$2,$3,$4,$5,$6,$7,$8,$9)
                    """,
                        source,
                        feature.get("nta_code"),
                        feature.get("nta_name"),
                        feature.get("borough"),
                        feature.get("conduit_route_mileage"),
                        feature.get("conduit_mileage_total"),
                        feature.get("conduit_mileage_available"),
                        feature.get("conduit_availability_ratio"),
                        datetime.utcnow() + timedelta(days=14)
                    )
                    stored_attribute += 1
                else:
                    geometry = feature.get("geometry")
                    if not geometry:
                        continue
                    await conn.execute("""
                        INSERT INTO underground_features
                            (source, infrastructure_type, unit_id, scan_id,
                             depth_m, anomaly_detected, scan_date,
                             geometry, expires_at)
                        VALUES ($1,$2,$3,$4,$5,$6,$7,
                                ST_SetSRID(ST_GeomFromGeoJSON($8),4326),$9)
                    """,
                        source,
                        feature.get("infrastructure_type"),
                        feature.get("unit_id"),
                        feature.get("scan_id"),
                        feature.get("depth_m"),
                        feature.get("anomaly_detected"),
                        feature.get("scan_date"),
                        json.dumps(geometry),
                        datetime.utcnow() + timedelta(days=14)
                    )
                    stored_spatial += 1
            except Exception as e:
                errors.append({"source": source, "error": str(e)})
    finally:
        await conn.close()

    return {
        "status": "success",
        "stored_spatial": stored_spatial,
        "stored_attribute": stored_attribute,
        "error_count": len(errors),
        "errors": errors
    }

@app.get("/features")
async def get_features(limit: int = 20):
    conn = await get_db()
    try:
        rows = await conn.fetch("""
            SELECT id, source, infrastructure_type, unit_id, scan_id,
                   depth_m, anomaly_detected, scan_date,
                   ST_AsGeoJSON(geometry) as geometry,
                   ingested_at, expires_at
            FROM underground_features
            WHERE expires_at > NOW()
            ORDER BY ingested_at DESC
            LIMIT $1
        """, limit)

        features = []
        for row in rows:
            features.append({
                "id": row["id"],
                "type": "Feature",
                "geometry": json.loads(row["geometry"]) if row["geometry"] else None,
                "properties": {
                    "source": row["source"],
                    "infrastructure_type": row["infrastructure_type"],
                    "unit_id": row["unit_id"],
                    "scan_id": row["scan_id"],
                    "depth_m": row["depth_m"],
                    "anomaly_detected": row["anomaly_detected"],
                    "scan_date": row["scan_date"],
                    "ingested_at": row["ingested_at"].isoformat(),
                    "expires_at": row["expires_at"].isoformat()
                }
            })
        return {"type": "FeatureCollection", "count": len(features), "features": features}
    finally:
        await conn.close()

@app.get("/conduit")
async def get_conduit(borough: str = None):
    conn = await get_db()
    try:
        if borough:
            rows = await conn.fetch("""
                SELECT * FROM underground_conduit
                WHERE expires_at > NOW() AND borough = $1
                ORDER BY conduit_mileage_total DESC
            """, borough)
        else:
            rows = await conn.fetch("""
                SELECT * FROM underground_conduit
                WHERE expires_at > NOW()
                ORDER BY conduit_mileage_total DESC
            """)
        return {"count": len(rows), "data": [dict(row) for row in rows]}
    finally:
        await conn.close()

@app.get("/features/bbox")
async def get_features_by_bbox(
    min_lon: float = -74.05,
    min_lat: float = 40.68,
    max_lon: float = -73.93,
    max_lat: float = 40.85
):
    conn = await get_db()
    try:
        rows = await conn.fetch("""
            SELECT id, source, infrastructure_type,
                   ST_AsGeoJSON(geometry) as geometry
            FROM underground_features
            WHERE expires_at > NOW()
            AND ST_Within(geometry, ST_MakeEnvelope($1,$2,$3,$4,4326))
        """, min_lon, min_lat, max_lon, max_lat)

        features = [
            {
                "id": row["id"],
                "type": "Feature",
                "geometry": json.loads(row["geometry"]) if row["geometry"] else None,
                "properties": {
                    "source": row["source"],
                    "infrastructure_type": row["infrastructure_type"]
                }
            }
            for row in rows
        ]
        return {
            "type": "FeatureCollection",
            "count": len(features),
            "bbox": [min_lon, min_lat, max_lon, max_lat],
            "features": features
        }
    finally:
        await conn.close()
