from fastapi import FastAPI
import asyncpg
import asyncio
import os
from datetime import datetime

app = FastAPI()

DB_URL = os.getenv("DB_URL", "postgresql://postgres:postgres@db:5432/gisdb")

async def get_db():
    return await asyncpg.connect(DB_URL)

async def cleanup_expired():
    """Delete expired records from both tables"""
    conn = await get_db()
    try:
        result_spatial = await conn.execute("""
            DELETE FROM underground_features WHERE expires_at < NOW()
        """)
        result_attribute = await conn.execute("""
            DELETE FROM underground_conduit WHERE expires_at < NOW()
        """)
        deleted_spatial = int(result_spatial.split()[-1])
        deleted_attribute = int(result_attribute.split()[-1])
        print(f"[{datetime.utcnow()}] TTL cleanup: {deleted_spatial} spatial, {deleted_attribute} attribute records deleted")
        return deleted_spatial, deleted_attribute
    finally:
        await conn.close()

async def scheduled_cleanup():
    """Run cleanup every 24 hours"""
    while True:
        await cleanup_expired()
        await asyncio.sleep(86400)

@app.on_event("startup")
async def startup():
    asyncio.create_task(scheduled_cleanup())

@app.get("/health")
def health():
    return {"status": "ok", "service": "ttl"}

@app.post("/cleanup")
async def manual_cleanup():
    """Manually trigger TTL cleanup"""
    deleted_spatial, deleted_attribute = await cleanup_expired()
    return {
        "status": "success",
        "deleted_spatial": deleted_spatial,
        "deleted_attribute": deleted_attribute,
        "timestamp": datetime.utcnow().isoformat()
    }

@app.get("/stats")
async def stats():
    """Get TTL statistics for both tables"""
    conn = await get_db()
    try:
        spatial_total = await conn.fetchval("SELECT COUNT(*) FROM underground_features")
        spatial_active = await conn.fetchval("SELECT COUNT(*) FROM underground_features WHERE expires_at > NOW()")
        spatial_expired = await conn.fetchval("SELECT COUNT(*) FROM underground_features WHERE expires_at < NOW()")

        attribute_total = await conn.fetchval("SELECT COUNT(*) FROM underground_conduit")
        attribute_active = await conn.fetchval("SELECT COUNT(*) FROM underground_conduit WHERE expires_at > NOW()")
        attribute_expired = await conn.fetchval("SELECT COUNT(*) FROM underground_conduit WHERE expires_at < NOW()")

        return {
            "spatial_features": {
                "total": spatial_total,
                "active": spatial_active,
                "expired_pending_cleanup": spatial_expired
            },
            "conduit_attributes": {
                "total": attribute_total,
                "active": attribute_active,
                "expired_pending_cleanup": attribute_expired
            }
        }
    finally:
        await conn.close()
