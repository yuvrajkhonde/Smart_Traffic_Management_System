from fastapi import APIRouter, Depends, HTTPException, status
from backend.core.database import supabase
from backend.core.deps import get_current_user, require_role
from pydantic import BaseModel
import uuid
from datetime import datetime
from collections import defaultdict

router = APIRouter(prefix="/traffic", tags=["Traffic"])

# ─────────────────────────────────────────────────────────────
# Schemas
# ─────────────────────────────────────────────────────────────
class AccidentCreate(BaseModel):
    description: str
    severity: str = "Minor"
    injuries: int = 0
    fatalities: int = 0
    latitude: float
    longitude: float

class SignalAdjust(BaseModel):
    camera_id: str
    car_count: int = 0
    truck_count: int = 0
    bus_count: int = 0
    motorcycle_count: int = 0
    ambulance_count: int = 0
    is_emergency: bool = False


# ─────────────────────────────────────────────────────────────
# Auto-Adjust: Receives YOLO data → feeds the RL Agent
# ─────────────────────────────────────────────────────────────
@router.post("/auto-adjust")
def auto_adjust_signal(data: SignalAdjust):
    """
    Entry point for camera YOLO outputs.
    Auto-registers the camera, feeds the PPO Agent, and updates
    the congested_roads table for UI vehicle count display.
    """
    # Weighted vehicle sum for density calculation
    weighted_sum = (
        data.car_count +
        (data.motorcycle_count * 0.5) +
        (data.truck_count * 2.0) +
        (data.bus_count * 2.5) +
        (data.ambulance_count * 5.0)
    )
    K = 20.0
    density_pct = min(int((weighted_sum / K) * 100), 100)
    total_vehicles = (data.car_count + data.truck_count + data.bus_count +
                      data.motorcycle_count + data.ambulance_count)
    is_emergency = data.is_emergency or data.ambulance_count > 0

    # (AI Signal Logic removed per user request; ready for new intelligence)

    # 3. Update vehicle count + density in congested_roads (signal state written by RL push)
    try:
        supabase.table("congested_roads").update({
            "vehicle_count":   total_vehicles,
            "congestion_level": density_pct,
            "is_emergency":    is_emergency,
            "last_updated":    datetime.utcnow().isoformat()
        }).eq("camera_id", data.camera_id).execute()
    except Exception:
        pass

    return {
        "status": "SUCCESS",
        "vehicle_count": total_vehicles,
        "density_pct": density_pct,
        "signal_override": is_emergency
    }


# ─────────────────────────────────────────────────────────────
# Congestion View: Merges RL signal state into congested_roads
# This is what Surveillance.tsx polls every second.
# ─────────────────────────────────────────────────────────────
@router.get("/congestion")
def get_congestion():
    """
    Returns the live signal state for every camera node.
    Merges real-time RL decisions (current_state, recommended_time)
    on top of the raw congested_roads rows.
    """
    # Fetch all road rows
    try:
        rows = supabase.table("congested_roads").select("*").execute().data or []
    except Exception:
        rows = []

    merged = []
    for row in rows:
        # Default fallback until new AI engine is built
        row.setdefault("current_state", "red")
        row.setdefault("recommended_time", 0)
        merged.append(row)

    return merged


# ─────────────────────────────────────────────────────────────
# Announcements View: Exposes live audio announcements
# ─────────────────────────────────────────────────────────────
@router.get("/announcements")
def get_announcements():
    """Returns the list of recent traffic announcements."""
    return []


# ─────────────────────────────────────────────────────────────
# Accident Reporting
# ─────────────────────────────────────────────────────────────
@router.post("/accident")
def report_accident(data: AccidentCreate, user=Depends(require_role("officer"))):
    """Officer manually reports a road accident."""
    try:
        accident_data = {
            "id":          str(uuid.uuid4()),
            "description": data.description,
            "severity":    data.severity,
            "injuries":    data.injuries,
            "fatalities":  data.fatalities,
            "latitude":    data.latitude,
            "longitude":   data.longitude,
            "reported_by": user["sub"],
            "reported_at": datetime.utcnow().isoformat(),
        }
        response = supabase.table("accidents").insert(accident_data).execute()
        return response.data[0] if response.data else None
    except Exception as e:
        raise HTTPException(status_code=400, detail=str(e))


@router.get("/analytics")
def get_accident_analytics(user=Depends(get_current_user)):
    """Monthly accident stats for the Officer Dashboard BarChart."""
    response = supabase.table("accidents").select("reported_at, injuries, fatalities").execute()
    monthly_data = defaultdict(lambda: {"injuries": 0, "fatalities": 0})

    for record in (response.data or []):
        try:
            dt = datetime.fromisoformat(record["reported_at"].replace("Z", "+00:00"))
            month = dt.strftime("%b")
            monthly_data[month]["injuries"]  += record.get("injuries", 0) or 0
            monthly_data[month]["fatalities"] += record.get("fatalities", 0) or 0
        except Exception:
            continue

    return [{"name": month, **vals} for month, vals in monthly_data.items()]


@router.get("/live-accidents")
def get_live_accidents():
    """GIS heatmap: returns all accident lat/lng coordinates."""
    try:
        return supabase.table("accidents").select("*").execute().data or []
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/challan-heatmap")
def get_challan_heatmap():
    """
    GIS heatmap: Returns aggregated issued challans and detected violations
    mapped to camera GPS coordinates.
    Updates dynamically when challans are issued or videos uploaded.
    """
    try:
        # 1. Fetch camera coordinates map
        cams_res = supabase.table("surveillance_cameras").select("id, location_name, latitude, longitude").execute()
        cameras = cams_res.data or []
        cam_map = {c["id"]: c for c in cameras if c.get("latitude") and c.get("longitude")}

        # 2. Fetch issued challans
        ch_res = supabase.table("e_challans").select("id, violation_id, amount, status, location, issued_at").execute()
        challans = ch_res.data or []

        # 3. Fetch violations
        v_res = supabase.table("violations").select("id, camera_id, violation_type, location, status, detected_at").execute()
        violations = v_res.data or []
        v_map = {v["id"]: v for v in violations}

        # Aggregate points by coordinate cluster (lat, lng rounded to 4 decimals ~11 meters)
        clusters = {}

        for ch in challans:
            v_id = ch.get("violation_id")
            v = v_map.get(v_id)
            lat, lng = None, None
            loc_name = ch.get("location") or "Bhopal Junction"

            if v and v.get("camera_id") in cam_map:
                cam = cam_map[v["camera_id"]]
                lat, lng = cam["latitude"], cam["longitude"]
                loc_name = cam.get("location_name") or loc_name
            else:
                for cam in cam_map.values():
                    if cam.get("location_name", "").lower() in loc_name.lower():
                        lat, lng = cam["latitude"], cam["longitude"]
                        break

            if lat is not None and lng is not None:
                key = (round(lat, 4), round(lng, 4))
                if key not in clusters:
                    clusters[key] = {
                        "latitude": lat,
                        "longitude": lng,
                        "location_name": loc_name,
                        "challan_count": 0,
                        "violation_count": 0,
                        "total_fines": 0,
                        "violation_types": set(),
                        "latest_timestamp": ch.get("issued_at")
                    }
                clusters[key]["challan_count"] += 1
                clusters[key]["total_fines"] += int(ch.get("amount", 1000) or 1000)
                if v:
                    clusters[key]["violation_types"].add(v.get("violation_type", "Traffic Violation"))

        # Also map all violations to their camera coordinates
        for v in violations:
            cam_id = v.get("camera_id")
            if cam_id in cam_map:
                cam = cam_map[cam_id]
                lat, lng = cam["latitude"], cam["longitude"]
                key = (round(lat, 4), round(lng, 4))
                if key not in clusters:
                    clusters[key] = {
                        "latitude": lat,
                        "longitude": lng,
                        "location_name": cam.get("location_name", "Surveillance Junction"),
                        "challan_count": 0,
                        "violation_count": 0,
                        "total_fines": 0,
                        "violation_types": set(),
                        "latest_timestamp": v.get("detected_at")
                    }
                clusters[key]["violation_count"] += 1
                clusters[key]["violation_types"].add(v.get("violation_type", "Violation"))

        # Convert to serializable list with calculated heatmap weight/intensity
        heatmap_data = []
        for key, item in clusters.items():
            # Intensity scales with number of challans + violations (0.4 base, up to 1.0)
            score = item["challan_count"] * 1.5 + item["violation_count"] * 0.5
            intensity = min(1.0, max(0.40, score * 0.25))
            heatmap_data.append({
                "latitude": item["latitude"],
                "longitude": item["longitude"],
                "location_name": item["location_name"],
                "challan_count": item["challan_count"],
                "violation_count": item["violation_count"],
                "total_fines": item["total_fines"],
                "violation_types": list(item["violation_types"]),
                "intensity": round(intensity, 2),
                "latest_timestamp": item["latest_timestamp"]
            })

        return heatmap_data
    except Exception as e:
        print(f"⚠️ [CHALLAN HEATMAP ERROR] {e}", flush=True)
        return []
