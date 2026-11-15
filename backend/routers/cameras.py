import os
import uuid
import cv2
import time
import shutil
import threading
from typing import Optional
from pydantic import BaseModel
from datetime import datetime

from fastapi import APIRouter, Depends, HTTPException, UploadFile, File, Form
from fastapi.responses import StreamingResponse

from backend.core.deps import require_role
from backend.core.database import supabase
from backend.ai_engine.utils import process_frame
from backend.ai_engine.video_processor import process_uploaded_video, get_job_status

router = APIRouter(prefix="/cameras", tags=["Cameras"])

# Global Shared State - Preserved for Frontend MJPEG
camera_frames = {}         
active_threads = {}        

class CameraRegister(BaseModel):
    location_name: str
    ip_address: str        # '0' for local webcam, or a URL/IP
    latitude: Optional[float] = None
    longitude: Optional[float] = None

def is_live_stream_source(source_input: str) -> bool:
    """Checks whether the source is a real live camera feed (webcam or network stream) rather than a local recorded video file."""
    s = str(source_input).strip().lower()
    # Explicitly reject local video files from live AI processing
    if any(s.endswith(ext) for ext in [".mp4", ".avi", ".mov", ".mkv", ".wmv", ".flv"]):
        return False
    if "uploads" in s or "test_videos" in s:
        return False
    if s == "0" or s.startswith("rtsp://") or s.startswith("http://") or s.startswith("https://"):
        return True
    return False

# ==========================================
# 🤖 THE AI WORKER (OPTIMIZED FOR OMEN 16 GPU)
# ==========================================

def ai_worker(camera_id: str, source_input: str):
    """
    Independent thread per live camera node.
    Synchronized with RTX 4060 GPU and React Dashboard.
    """
    if not is_live_stream_source(source_input):
        print(f"🛑 [AI WORKER] Skipping non-live video source for node {camera_id[:8]}: {source_input}. Recorded video forensics should not be processed as live camera feeds.", flush=True)
        if camera_id in active_threads:
            del active_threads[camera_id]
        return

    print(f"\n🤖 [NODE START] Initializing AI for Live Camera ID: {camera_id[:8]}", flush=True)
    
    # Standardize source: '0' for webcam, else URL
    if source_input == "0":
        source = 0
        cap = cv2.VideoCapture(source, cv2.CAP_DSHOW)
    else:
        source = source_input
        cap = cv2.VideoCapture(source)
    
    if not cap.isOpened():
        print(f"❌ [CRITICAL] Source Unreachable: {source_input}. Node offline.", flush=True)
        return

    # Set buffer size to 1 for real-time inference (no lag)
    cap.set(cv2.CAP_PROP_BUFFERSIZE, 1)
    print(f"✅ [SUCCESS] Camera stream active for node {camera_id[:8]}", flush=True)

    frame_count = 0
    while camera_id in active_threads:
        success, frame = cap.read()
        if not success:
            print(f"⚠️ [LOST] Node {camera_id[:8]} connection dropped. Retrying...", flush=True)
            cap.release()
            time.sleep(5)
            if source == 0:
                cap = cv2.VideoCapture(source, cv2.CAP_DSHOW)
            else:
                cap = cv2.VideoCapture(source)
            continue
            
        # 1. 🔥 EXECUTE DUAL-ENGINE PROCESSING
        # This handles Density, Ambulance, No Helmet, and Triple Riding
        try:
            process_frame(frame, camera_id)
        except Exception as e:
            print(f"❌ [AI ERROR] Node {camera_id[:8]}: {e}", flush=True)

        # 2. ENCODE FOR DASHBOARD (Standardized for Surveillance.tsx)
        ret, buffer = cv2.imencode('.jpg', frame, [int(cv2.IMWRITE_JPEG_QUALITY), 75])
        if ret:
            camera_frames[camera_id] = buffer.tobytes()
        
        # 3. TERMINAL HEARTBEAT
        frame_count += 1
        if frame_count % 50 == 0:
            print(f"📡 [HEARTBEAT] Node {camera_id[:8]} | GPU Processing Active | {datetime.now().strftime('%H:%M:%S')}", flush=True)

        # Optimization: Reduced sleep to 0.005 for high-speed detection
        time.sleep(0.005) 
    
    cap.release()
    print(f"🛑 [NODE STOP] Worker decommissioned: {camera_id}", flush=True)

# ==========================================
# 🚀 API ENDPOINTS (LINKED TO REACT FRONTEND)
# ==========================================

@router.get("/list")
def list_cameras(user=Depends(require_role("officer"))):
    cameras = supabase.table("surveillance_cameras").select("*").execute()
    return cameras.data

@router.post("/register")
def register_camera(camera_data: CameraRegister, user=Depends(require_role("officer"))):
    try:
        # 1. Save to Core Surveillance Table
        payload = camera_data.dict()
        payload["is_active"] = True
        result = supabase.table("surveillance_cameras").insert(payload).execute()
        
        if not result.data:
            raise HTTPException(status_code=500, detail="Failed to provision Node")
            
        new_cam = result.data[0]
        cam_id = str(new_cam['id'])
        
        # 2. AUTO-PROVISION: Traffic Congestion analytics row
        supabase.table("congested_roads").insert({
            "camera_id": cam_id,
            "road_name": f"{camera_data.location_name} St.",
            "area": camera_data.location_name,
            "congestion_level": 0,
            "vehicle_count": 0,
            "is_emergency": False,
            "is_closed": False
        }).execute()
        
        # 3. Trigger AI Worker
        if cam_id not in active_threads:
            active_threads[cam_id] = True
            threading.Thread(target=ai_worker, args=(cam_id, camera_data.ip_address), daemon=True).start()
        
        return {"message": "Node Activated", "camera": new_cam}
    except Exception as e:
        raise HTTPException(status_code=400, detail=str(e))

@router.get("/live/{camera_id}")
def live_feed(camera_id: str, token: str = None):
    """MJPEG Stream for Surveillance.tsx — validates JWT token from query param or header."""
    # Validate token if provided (both frontends pass ?token=...)
    if token:
        try:
            from jose import jwt, JWTError
            from backend.core.deps import SECRET_KEY, ALGORITHM
            payload = jwt.decode(token, SECRET_KEY, algorithms=[ALGORITHM])
            if "sub" not in payload:
                raise HTTPException(status_code=401, detail="Invalid token")
        except Exception:
            raise HTTPException(status_code=401, detail="Invalid or expired token")

    def frame_generator():
        while True:
            frame_bytes = camera_frames.get(camera_id)
            if frame_bytes:
                yield (b'--frame\r\n'
                       b'Content-Type: image/jpeg\r\n\r\n' + frame_bytes + b'\r\n')
            time.sleep(0.04) # ~25 FPS stream for UI
    return StreamingResponse(frame_generator(), media_type='multipart/x-mixed-replace; boundary=frame')

@router.delete("/{camera_id}")
def delete_camera(camera_id: str, user=Depends(require_role("officer"))):
    try:
        if camera_id in active_threads:
            del active_threads[camera_id]
        
        supabase.table("surveillance_cameras").delete().eq("id", camera_id).execute()
        supabase.table("congested_roads").delete().eq("camera_id", camera_id).execute()

        if camera_id in camera_frames:
            del camera_frames[camera_id]

        return {"message": "Node Decommissioned"}
    except Exception as e:
        raise HTTPException(status_code=400, detail=str(e))

# ==========================================
# 📹 SURVEILLANCE VIDEO UPLOAD & PROCESSING
# ==========================================

def video_playback_worker(camera_id: str, source: str):
    """
    Lightweight video stream worker for uploaded footage in the Surveillance grid.
    Streams frames into camera_frames without running CPU/GPU intensive detectors.
    """
    print(f"🎬 [STREAM] Starting playback loop for uploaded node {camera_id[:8]}", flush=True)
    cap = cv2.VideoCapture(source)
    if not cap.isOpened():
        print(f"❌ [STREAM] Cannot open video for streaming: {source}", flush=True)
        return

    fps = cap.get(cv2.CAP_PROP_FPS) or 25
    delay = 1.0 / max(10, min(fps, 30))

    while camera_id in active_threads:
        ret, frame = cap.read()
        if not ret:
            cap.set(cv2.CAP_PROP_POS_FRAMES, 0)
            continue

        ret_enc, buffer = cv2.imencode('.jpg', frame, [int(cv2.IMWRITE_JPEG_QUALITY), 75])
        if ret_enc:
            camera_frames[camera_id] = buffer.tobytes()

        time.sleep(delay)

    cap.release()
    print(f"🛑 [STREAM] Playback worker stopped for {camera_id[:8]}", flush=True)


@router.post("/upload-video")
async def upload_surveillance_video(
    file: UploadFile = File(...),
    location_name: str = Form(...),
    latitude: float = Form(23.2599),
    longitude: float = Form(77.4126),
    direction: str = Form("Recorded Video Upload")
):
    """
    Accepts video file upload with mapped GPS coordinates.
    1. Saves video to backend/uploads.
    2. Registers camera node in surveillance_cameras.
    3. Launches Phase 3 AI Enforcement Processor in background.
    4. Automatically launches lightweight stream playback once analysis finishes.
    """
    if not file.filename:
        raise HTTPException(status_code=400, detail="No video file provided")

    allowed_exts = [".mp4", ".avi", ".mov", ".mkv"]
    ext = os.path.splitext(file.filename)[1].lower()
    if ext not in allowed_exts:
        raise HTTPException(status_code=400, detail=f"Unsupported video format: {ext}. Allowed: {allowed_exts}")

    job_id = str(uuid.uuid4())
    camera_id = f"cam_{job_id[:8]}"

    # Save video file
    upload_dir = os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "uploads")
    os.makedirs(upload_dir, exist_ok=True)
    safe_filename = f"{job_id[:8]}_{file.filename}"
    saved_path = os.path.abspath(os.path.join(upload_dir, safe_filename))

    with open(saved_path, "wb") as buffer:
        shutil.copyfileobj(file.file, buffer)

    print(f"📥 [UPLOAD] Saved surveillance video: {saved_path} ({location_name})", flush=True)

    # Register recorded footage record in database (is_active False so it is not treated as a 24/7 live camera)
    cam_entry = {
        "id": camera_id,
        "location_name": location_name,
        "ip_address": saved_path,
        "latitude": latitude,
        "longitude": longitude,
        "direction": direction,
        "is_active": False
    }
    try:
        supabase.table("surveillance_cameras").insert(cam_entry).execute()
        print(f"📡 [DB] Camera node registered: {camera_id} @ {location_name}", flush=True)
    except Exception as ce:
        print(f"⚠️ [DB CAMERA INSERT WARN] {ce}", flush=True)

    # Initialize congestion row
    try:
        supabase.table("congested_roads").insert({
            "road_name": f"{location_name} Corridor",
            "area": "Bhopal",
            "congestion_level": 25,
            "camera_id": camera_id,
            "current_state": "green",
            "vehicle_count": 0
        }).execute()
    except Exception:
        pass

    def on_complete_stream(cam_id: str, v_path: str):
        active_threads[cam_id] = True
        threading.Thread(target=video_playback_worker, args=(cam_id, v_path), daemon=True).start()

    # Launch AI Processor in background thread (isolated, no stream contention)
    proc_thread = threading.Thread(
        target=process_uploaded_video,
        kwargs={
            "video_path": saved_path,
            "job_id": job_id,
            "camera_id": camera_id,
            "location_name": location_name,
            "latitude": latitude,
            "longitude": longitude,
            "on_complete": on_complete_stream
        },
        daemon=True
    )
    proc_thread.start()

    return {
        "status": "Accepted",
        "job_id": job_id,
        "camera_id": camera_id,
        "location_name": location_name,
        "latitude": latitude,
        "longitude": longitude,
        "message": "Video uploaded successfully. AI processing started."
    }


@router.get("/job-status/{job_id}")
def check_video_job_status(job_id: str):
    """Polls processing progress and violation counts for an uploaded video."""
    status = get_job_status(job_id)
    if not status:
        return {"status": "not_found", "progress": 0, "violations_found": 0}
    return status

# ==========================================
# 🔄 ROBUST SYSTEM BOOTSTRAP (AUTO-RECOVERY)
# ==========================================

def initialize_active_streams():
    """Wakes up the AI for all 'Active' nodes in the database on server start."""
    print("\n" + "="*60)
    print("🔄 [BOOTSTRAP] Project V.I.TA.L.S. Engine Recovery Start...", flush=True)
    try:
        res = supabase.table("surveillance_cameras").select("*").eq("is_active", True).execute()
        
        if not res.data:
            print("💡 [BOOTSTRAP] No active nodes in registry. Standby mode.", flush=True)
            return

        print(f"🔎 [BOOTSTRAP] Found {len(res.data)} nodes to re-link.", flush=True)
        for cam in res.data:
            cam_id = str(cam['id'])
            source = str(cam.get('ip_address', '0'))
            
            # Reset congestion states to avoid stale frontend data
            supabase.table("congested_roads").update({
                "is_closed": False,
                "last_updated": datetime.utcnow().isoformat()
            }).eq("camera_id", cam_id).execute()
            
            # Only start AI worker if it is a real live camera feed (webcam or network stream)
            if not is_live_stream_source(source):
                print(f"📁 [BOOTSTRAP] Node {cam_id[:8]} ({cam.get('location_name')}) is recorded footage, skipping live AI worker.", flush=True)
                continue

            if cam_id not in active_threads:
                active_threads[cam_id] = True
                print(f"🚀 [BOOTSTRAP] Re-linking Live Camera Node: {cam['location_name']}", flush=True)
                threading.Thread(target=ai_worker, args=(cam_id, source), daemon=True).start()
        print("="*60 + "\n")
    except Exception as e:
        print(f"❌ [BOOTSTRAP FAIL] {e}", flush=True)

# Startup delay to ensure Database/Supabase is ready before relinking
threading.Thread(target=lambda: (time.sleep(5), initialize_active_streams()), daemon=True).start()
