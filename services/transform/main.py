from fastapi import FastAPI
from shapely.geometry import mapping
from shapely.wkt import loads as wkt_loads

app = FastAPI()

def normalize_catch_basin(record: dict) -> dict:
    return {
        "source": "dep_catch_basins",
        "infrastructure_type": "sewer_catch_basin",
        "unit_id": record.get("unitid"),
        "scan_id": None,
        "depth_m": None,
        "anomaly_detected": None,
        "scan_date": None,
        "geometry": record.get("the_geom")
    }

def normalize_ecs_conduit(record: dict) -> dict:
    return {
        "source": "ecs_conduit",
        "nta_code": record.get("nta"),
        "nta_name": record.get("nta_name"),
        "borough": record.get("borough"),
        "conduit_route_mileage": float(record.get("conduit_route_mileage") or 0),
        "conduit_mileage_total": float(record.get("conduit_mileage_total") or 0),
        "conduit_mileage_available": float(record.get("conduit_mileage_available") or 0),
        "conduit_availability_ratio": float(record.get("conduit_mileage_available_1") or 0)
    }

def normalize_gpr(record: dict) -> dict:
    geometry = mapping(wkt_loads(record["geometry"]))
    return {
        "source": "gpr_vendor",
        "infrastructure_type": "gpr_scan_area",
        "unit_id": None,
        "scan_id": record.get("scan_id"),
        "depth_m": record.get("depth_m"),
        "anomaly_detected": record.get("anomaly_detected"),
        "scan_date": record.get("scan_date"),
        "geometry": geometry
    }

@app.get("/health")
def health():
    return {"status": "ok", "service": "transform"}

@app.post("/transform")
async def transform(payload: dict):
    features = []
    errors = []
    results = payload.get("results", {})

    for record in results.get("dep_catch_basins", {}).get("data", []):
        try:
            if record.get("the_geom"):
                features.append(normalize_catch_basin(record))
        except Exception as e:
            errors.append({"source": "dep_catch_basins", "error": str(e)})

    for record in results.get("ecs_conduit", {}).get("data", []):
        try:
            features.append(normalize_ecs_conduit(record))
        except Exception as e:
            errors.append({"source": "ecs_conduit", "error": str(e)})

    for record in results.get("gpr_vendor", {}).get("data", []):
        try:
            features.append(normalize_gpr(record))
        except Exception as e:
            errors.append({"source": "gpr_vendor", "error": str(e)})

    return {
        "feature_count": len(features),
        "error_count": len(errors),
        "errors": errors,
        "features": features
    }
