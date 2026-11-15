"""
═══════════════════════════════════════════════════════════════════════════════
  🎬 VIDEO PROCESSOR — Phase 3 Production Offline Violation Engine
  Processes uploaded .mp4 files with:
  1. ByteTrack Continuous Trajectory Tracking
  2. Evaluable-Frames Gated State Machine (No dilute ratio from distant bikes)
  3. Decoupled Evidence Ring-Buffer (Best Violation Frame + Best Plate Crop)
  4. Multi-Frame Indian EasyOCR Consensus Voting
  5. Official 3-Panel Composite Challan Builder with SHA-256 Hash
  6. Deferred Finalization (Guaranteed Flush on Video Completion)
═══════════════════════════════════════════════════════════════════════════════
"""

import os
import cv2
import time
import uuid
import threading
import numpy as np
from datetime import datetime
import torch
from ultralytics import YOLO

from backend.ai_engine.utils import (
    plate_reader, EVIDENCE_PATH,
    CUSTOM_CLS_WITH_HELMET, CUSTOM_CLS_WITHOUT_HELMET, CUSTOM_CLS_PLATE,
    compute_iou, compute_iop, is_person_riding_bike
)
from backend.ai_engine.enforcement_engine import (
    VehicleTrackState, IndianPlateOCREngine, build_3panel_composite_evidence
)
from backend.core.database import create_supabase_client

# ── Dedicated Isolated YOLO Models for Video Processing (Prevents Tracker Contention) ──
_BASE_DIR = os.path.dirname(os.path.abspath(__file__))
_MODELS_DIR = os.path.join(_BASE_DIR, "..", "..", "ai_models")
_DEVICE = "cuda" if torch.cuda.is_available() else "cpu"

print(f"🎬 [VIDEO ENGINE INIT] Loading dedicated YOLO models on {_DEVICE}...", flush=True)
proc_det_model = YOLO(os.path.join(_MODELS_DIR, "yolov8n.pt")).to(_DEVICE)
proc_custom_model = YOLO(os.path.join(_MODELS_DIR, "best.pt")).to(_DEVICE)
_proc_lock = threading.Lock()

# Track active video jobs
_active_jobs: dict[str, dict] = {}
_jobs_lock = threading.Lock()


def get_job_status(job_id: str) -> dict | None:
    """Returns the current status of a video processing job."""
    with _jobs_lock:
        return _active_jobs.get(job_id)


def process_uploaded_video(
    video_path: str,
    job_id: str,
    camera_id: str = None,
    location_name: str = "Bhopal City (Video Upload)",
    latitude: float = 23.2599,
    longitude: float = 77.4126,
    on_complete = None
):
    """
    Main entry point for offline video processing.
    Runs ByteTrack trajectory tracking + Phase 2 model + Phase 3 Enforcement State Machine.
    """
    active_cam_id = camera_id or f"upload_{job_id[:8]}"
    print(f"\n🎬 [VIDEO] Job {job_id[:8]} STARTED — Node: {active_cam_id} @ {location_name} ({video_path})", flush=True)

    with _jobs_lock:
        _active_jobs[job_id] = {
            "status": "processing",
            "progress": 0,
            "violations_found": 0,
            "camera_id": active_cam_id,
            "location_name": location_name,
            "latitude": latitude,
            "longitude": longitude,
            "started_at": datetime.utcnow().isoformat()
        }

    # Reset ByteTrack tracker state for a clean, deterministic video run
    with _proc_lock:
        if hasattr(proc_det_model, 'predictor') and proc_det_model.predictor is not None:
            proc_det_model.predictor.trackers = []

    cap = cv2.VideoCapture(video_path)
    if not cap.isOpened():
        print(f"❌ [VIDEO] Cannot open: {video_path}", flush=True)
        with _jobs_lock:
            _active_jobs[job_id]["status"] = "failed"
            _active_jobs[job_id]["error"] = "Cannot open video file"
        return

    total_frames = int(cap.get(cv2.CAP_PROP_FRAME_COUNT))
    fps = cap.get(cv2.CAP_PROP_FPS) or 30.0
    # For shorter videos (<= 500 frames), evaluate every frame for maximum tracking precision
    frame_skip = 1 if total_frames <= 500 else max(1, int(fps / 15))
    effective_fps = max(1.0, fps / frame_skip)

    print(f"📊 [VIDEO] Total frames: {total_frames} | Video FPS: {fps:.0f} | Effective FPS: {effective_fps:.1f} | Step: every {frame_skip} frame(s)", flush=True)

    ocr_engine = IndianPlateOCREngine(plate_reader)
    active_tracks: dict[int, VehicleTrackState] = {}
    violations_found = 0
    fake_camera_id = active_cam_id

    db = None
    try:
        db = create_supabase_client()
        # Ensure camera_id exists in surveillance_cameras so foreign key does not fail
        if db:
            existing = db.table("surveillance_cameras").select("id").eq("id", fake_camera_id).execute()
            if not existing.data:
                db.table("surveillance_cameras").insert({
                    "id": fake_camera_id,
                    "location_name": location_name,
                    "ip_address": video_path,
                    "latitude": latitude,
                    "longitude": longitude,
                    "direction": "Recorded Video Upload",
                    "is_active": True
                }).execute()
                print(f"📡 [VIDEO PROVISION] Auto-registered camera node: {fake_camera_id}", flush=True)
    except Exception as e:
        print(f"⚠️ [VIDEO] DB camera verification warning: {e}", flush=True)

    def finalize_track(t_state: VehicleTrackState, event_timestamp: str):
        nonlocal violations_found
        if t_state.state != "CONFIRMED":
            return

        print(f"\n⚡ [FINALIZING TRACK {t_state.track_id}] {t_state.confirmed_violation_type} | "
              f"Hits: {t_state.no_helmet_hits}/{t_state.evaluable_frames} evaluable frames", flush=True)

        # 1. OCR Multi-Frame Consensus Voting on Top 3-5 Crops
        plate_crops = [p[1] for p in t_state.plate_candidates]
        plate_text, ocr_conf, is_auto_verified = ocr_engine.vote_on_crop_candidates(plate_crops)
        print(f"🔤 [TRACK {t_state.track_id} OCR RESULT] Plate: '{plate_text}' | Conf: {ocr_conf:.2f} | "
              f"Auto-Verified: {is_auto_verified}", flush=True)

        # 2. Pick Best Frames for 3-Panel Composite
        full_scene = t_state.best_violation_frame
        if full_scene is None and t_state.plate_candidates:
            full_scene = np.zeros((720, 1280, 3), dtype=np.uint8)

        rider_zoom = t_state.best_violation_crop
        plate_crop = t_state.plate_candidates[0][1] if t_state.plate_candidates else None

        hit_ratio = float(t_state.no_helmet_hits) / float(max(1, t_state.evaluable_frames))
        metadata = {
            "camera_id": fake_camera_id,
            "timestamp": event_timestamp,
            "violation_type": t_state.confirmed_violation_type,
            "plate_text": plate_text,
            "hit_ratio": hit_ratio,
            "track_id": t_state.track_id
        }

        composite_img, sha256_hash = build_3panel_composite_evidence(
            full_scene if full_scene is not None else np.zeros((720, 1280, 3), dtype=np.uint8),
            rider_zoom,
            plate_crop,
            metadata
        )

        # 3. Save Composite Image to disk
        comp_id = uuid.uuid4().hex[:12]
        comp_filename = f"comp_{comp_id}.jpg"
        comp_path = os.path.join(EVIDENCE_PATH, comp_filename)
        cv2.imwrite(comp_path, composite_img)

        # Save Raw Original unannotated scene with hash
        raw_filename = f"raw_{comp_id}.jpg"
        raw_path = os.path.join(EVIDENCE_PATH, raw_filename)
        if full_scene is not None:
            cv2.imwrite(raw_path, full_scene)

        # 4. Insert into dedicated `uploaded_video_violations` table and `violations` table
        mean_conf = float(np.mean(t_state.conf_history)) if t_state.conf_history else 0.85
        violation_id = str(uuid.uuid4())
        clean_plate = plate_text if plate_text != "UNREADABLE" else "UNKNOWN"
        detected_iso = datetime.utcnow().isoformat()
        video_fname = os.path.basename(video_path)

        if db:
            # Table 1: Separate dedicated table for uploaded video forensic records
            uv_payload = {
                "id": violation_id,
                "job_id": job_id,
                "video_filename": video_fname,
                "camera_id": fake_camera_id,
                "location": location_name,
                "latitude": latitude,
                "longitude": longitude,
                "violation_type": t_state.confirmed_violation_type,
                "plate_number": clean_plate,
                "confidence_score": round(mean_conf, 2),
                "hit_ratio": round(hit_ratio, 2),
                "evaluable_frames": t_state.evaluable_frames,
                "sha256_hash": sha256_hash,
                "evidence_image_url": f"http://localhost:8000/static/evidence/{comp_filename}",
                "raw_frame_url": f"http://localhost:8000/static/evidence/{raw_filename}",
                "status": "pending",
                "severity": "high" if t_state.confirmed_violation_type == "Triple Riding" else "medium",
                "is_auto_verified": is_auto_verified,
                "detected_at": detected_iso
            }
            try:
                db.table("uploaded_video_violations").insert(uv_payload).execute()
                print(f"📁 [SEPARATE TABLE] Logged to uploaded_video_violations: {violation_id[:8]} | {clean_plate}", flush=True)
            except Exception as uve:
                print(f"⚠️ [UPLOADED_VIOLATIONS DB WARN] {uve}", flush=True)

            # Table 2: Unified violations table for officer e-challan review queue & GIS heatmap
            v_payload = {
                "id": violation_id,
                "camera_id": fake_camera_id,
                "violation_type": t_state.confirmed_violation_type,
                "evidence_image_url": f"http://localhost:8000/static/evidence/{comp_filename}",
                "confidence_score": round(mean_conf, 2),
                "plate_number": clean_plate,
                "status": "pending",
                "source": "uploaded_video",
                "location": location_name,
                "severity": "high" if t_state.confirmed_violation_type == "Triple Riding" else "medium",
                "detected_at": detected_iso
            }
            try:
                db.table("violations").insert(v_payload).execute()
                print(f"💾 [DB INSERT] Violation logged to violations queue: ID {v_payload['id'][:8]} | {clean_plate}", flush=True)
            except Exception as dbe:
                print(f"⚠️ [DB INSERT ERROR] {dbe}", flush=True)
                # Resilient fallback: lookup any existing camera in table if foreign key violated
                try:
                    cams = db.table("surveillance_cameras").select("id").limit(1).execute()
                    if cams.data:
                        v_payload["camera_id"] = cams.data[0]["id"]
                        db.table("violations").insert(v_payload).execute()
                        print(f"💾 [DB INSERT RETRY] Logged with fallback camera ID {v_payload['camera_id'][:8]}", flush=True)
                except Exception as retry_err:
                    print(f"❌ [DB INSERT RETRY FAILED] {retry_err}", flush=True)

        t_state.state = "LOGGED"
        violations_found += 1

    frame_idx = 0
    try:
        while True:
            ret, frame = cap.read()
            if not ret:
                break

            frame_idx += 1
            if frame_idx % frame_skip != 0:
                continue

            # Update progress periodically
            if frame_idx % (frame_skip * 8) == 0:
                with _jobs_lock:
                    _active_jobs[job_id]["progress"] = min(98, int((frame_idx / max(1, total_frames)) * 100))
                    _active_jobs[job_id]["violations_found"] = violations_found

            frame_h, frame_w = frame.shape[:2]
            current_timestamp = datetime.utcnow().strftime("%Y-%m-%d %H:%M:%S")

            # ═══════════════════════════════════════════════════════════
            # STAGE 1: ByteTrack Continuous Trajectory Tracking
            # ═══════════════════════════════════════════════════════════
            with _proc_lock:
                m1_res = proc_det_model.track(frame, persist=True, verbose=False, conf=0.20, imgsz=960)

            m1_motos = []
            raw_persons = []
            for b in m1_res[0].boxes:
                c = int(b.cls[0])
                box = list(map(int, b.xyxy[0]))
                tid = int(b.id[0]) if b.id is not None else None
                if c == 3 and tid is not None:
                    m1_motos.append({"box": box, "tid": tid})
                elif c == 0:
                    raw_persons.append(box)

            # Deduplicate persons
            m1_persons = []
            for p in raw_persons:
                if not any(compute_iou(p, dp) > 0.40 for dp in m1_persons):
                    m1_persons.append(p)

            seen_track_ids_this_frame = set()

            # ═══════════════════════════════════════════════════════════
            # STAGE 2: Motorcycle Union Envelopes & Phase 2 Model
            # ═══════════════════════════════════════════════════════════
            for moto in m1_motos:
                bx1, by1, bx2, by2 = moto["box"]
                tid = moto["tid"]
                bh = by2 - by1
                bw = bx2 - bx1
                seen_track_ids_this_frame.add(tid)

                if tid not in active_tracks:
                    active_tracks[tid] = VehicleTrackState(tid, fps=effective_fps)
                t_state = active_tracks[tid]

                assigned_riders = [p for p in m1_persons if is_person_riding_bike(p, moto["box"])]

                # Union envelope
                min_x, min_y, max_x, max_y = bx1, by1, bx2, by2
                if assigned_riders:
                    for p in assigned_riders:
                        min_x = min(min_x, p[0])
                        min_y = min(min_y, p[1])
                        max_x = max(max_x, p[2])
                        max_y = max(max_y, p[3])
                    pad_x = int((max_x - min_x) * 0.15)
                    pad_y = int((max_y - min_y) * 0.15)
                else:
                    min_y = max(0, by1 - int(bh * 0.85))
                    pad_x = int(bw * 0.15)
                    pad_y = int(bh * 0.10)

                cx1 = max(0, min_x - pad_x)
                cy1 = max(0, min_y - pad_y)
                cx2 = min(frame_w, max_x + pad_x)
                cy2 = min(frame_h, max_y + pad_y)

                crop = frame[cy1:cy2, cx1:cx2]
                if crop.size == 0 or crop.shape[0] < 20 or crop.shape[1] < 20:
                    continue

                # Run custom_model on the high-res envelope crop
                raw_helmets = []
                raw_no_helmets = []
                frame_plate_crops = []

                try:
                    with _proc_lock:
                        c_res = proc_custom_model(crop, verbose=False, conf=0.08, imgsz=640)
                    for b in c_res[0].boxes:
                        c2 = int(b.cls[0])
                        lx1, ly1, lx2, ly2 = map(int, b.xyxy[0])
                        cconf = float(b.conf[0])
                        gx1, gy1, gx2, gy2 = lx1 + cx1, ly1 + cy1, lx2 + cx1, ly2 + cy1
                        box_g = [gx1, gy1, gx2, gy2]
                        box_l = [lx1, ly1, lx2, ly2]

                        if c2 == CUSTOM_CLS_WITH_HELMET and cconf >= 0.25:
                            raw_helmets.append({"box_l": box_l, "conf": cconf})
                        elif c2 == CUSTOM_CLS_WITHOUT_HELMET and cconf >= 0.25:
                            raw_no_helmets.append({"box_l": box_l, "conf": cconf})
                        elif c2 == CUSTOM_CLS_PLATE and cconf >= 0.35:
                            # Plate crop from high-res envelope
                            p_crop = crop[max(0, ly1):ly2, max(0, lx1):lx2]
                            if p_crop.size > 0 and p_crop.shape[1] >= 60:
                                frame_plate_crops.append((cconf, p_crop))
                except Exception:
                    pass

                # Head detection disambiguation (IoU > 0.35)
                valid_no_helmets = []
                for nh in raw_no_helmets:
                    conflicting_h = [h for h in raw_helmets if compute_iou(nh["box_l"], h["box_l"]) > 0.35]
                    if not conflicting_h or nh["conf"] > max(h["conf"] for h in conflicting_h):
                        valid_no_helmets.append(nh)

                has_no_helmet = len(valid_no_helmets) > 0
                nh_conf = max([nh["conf"] for nh in valid_no_helmets], default=0.0)
                has_triple_riding = len(assigned_riders) >= 3

                # Update State Machine
                t_state.update_frame(
                    bike_box=moto["box"],
                    has_no_helmet=has_no_helmet,
                    nh_conf=nh_conf,
                    has_triple_riding=has_triple_riding,
                    envelope_crop=crop,
                    full_frame=frame,
                    detected_plate_crops=frame_plate_crops
                )

                # Early finalization check if plate has superb sharpness
                if t_state.can_finalize(video_ending=False):
                    finalize_track(t_state, current_timestamp)

            # Increment lost frames for tracks not observed in this frame
            for tid, t_state in list(active_tracks.items()):
                if tid not in seen_track_ids_this_frame and t_state.state != "LOGGED":
                    has_terminated = t_state.mark_lost_frame()
                    if has_terminated and t_state.can_finalize(video_ending=False):
                        finalize_track(t_state, current_timestamp)

            # Update live job progress
            progress = int((frame_idx / max(total_frames, 1)) * 100)
            with _jobs_lock:
                _active_jobs[job_id]["progress"] = min(progress, 99)
                _active_jobs[job_id]["violations_found"] = violations_found

        # ═══════════════════════════════════════════════════════════
        # STAGE 3: Video-End Flush of Remaining Active Confirmed Tracks
        # ═══════════════════════════════════════════════════════════
        print("\n🏁 [VIDEO LOOP END] Flushing remaining active confirmed tracks...", flush=True)
        final_timestamp = datetime.utcnow().strftime("%Y-%m-%d %H:%M:%S")
        for tid, t_state in active_tracks.items():
            if t_state.can_finalize(video_ending=True):
                finalize_track(t_state, final_timestamp)

    except Exception as e:
        print(f"❌ [VIDEO] Processing error: {e}", flush=True)
        with _jobs_lock:
            _active_jobs[job_id]["status"] = "failed"
            _active_jobs[job_id]["error"] = str(e)
        return
    finally:
        cap.release()

    # Clean up temporary scratch video files, keep permanent node uploads
    if "temp_" in os.path.basename(video_path) or "scratch_" in os.path.basename(video_path):
        try:
            os.remove(video_path)
            print(f"🗑️ [VIDEO] Temp file cleaned: {video_path}", flush=True)
        except Exception:
            pass

    with _jobs_lock:
        _active_jobs[job_id]["status"] = "completed"
        _active_jobs[job_id]["progress"] = 100
        _active_jobs[job_id]["violations_found"] = violations_found
        _active_jobs[job_id]["completed_at"] = datetime.utcnow().isoformat()

    print(f"🎉 [VIDEO] Job {job_id[:8]} COMPLETE — {violations_found} confirmed violations logged.", flush=True)

    if on_complete and callable(on_complete):
        try:
            on_complete(active_cam_id, video_path)
        except Exception as oce:
            print(f"⚠️ [VIDEO] on_complete callback warning: {oce}", flush=True)

