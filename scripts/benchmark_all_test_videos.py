"""
═══════════════════════════════════════════════════════════════════════════════
  📊 V.I.T.A.L.S. Phase 3: Comprehensive Multi-Video Benchmark Suite
  Evaluates all lane videos in backend/test_videos/ against Phase 3 Pipeline:
  - east_lane.mp4
  - north_lane.mp4
  - south_lane.mp4
  - west_lane.mp4
═══════════════════════════════════════════════════════════════════════════════
"""

import os
import sys
import cv2
import time
import shutil
import numpy as np
import torch
from datetime import datetime
from ultralytics import YOLO

CURRENT_DIR = os.path.dirname(os.path.abspath(__file__))
ROOT_DIR = os.path.join(CURRENT_DIR, "..")
sys.path.insert(0, ROOT_DIR)

from backend.ai_engine.enforcement_engine import (
    VehicleTrackState, IndianPlateOCREngine, build_3panel_composite_evidence
)
from backend.ai_engine.utils import (
    compute_iou, compute_iop, is_person_riding_bike
)

VIDEO_DIR = os.path.join(ROOT_DIR, "backend", "test_videos")
BENCHMARK_DIR = os.path.join(ROOT_DIR, "captured_test_frames", "benchmarks")
ARTIFACT_DIR = os.getenv("ARTIFACT_DIR", os.path.join(ROOT_DIR, "captured_test_frames", "benchmarks", "images"))

os.makedirs(BENCHMARK_DIR, exist_ok=True)
os.makedirs(ARTIFACT_DIR, exist_ok=True)

device = "cuda:0" if torch.cuda.is_available() else "cpu"
print(f"🚀 Initializing Benchmark Suite [Compute Device: {device}]")

m1 = YOLO(os.path.join(ROOT_DIR, "ai_models", "yolov8n.pt"))
m2 = YOLO(os.path.join(ROOT_DIR, "ai_models", "best.pt"))
ocr_engine = IndianPlateOCREngine()

VIDEO_FILES = [
    "east_lane.mp4",
    "south_lane.mp4",
    "west_lane.mp4",
    "north_lane.mp4",
    "new.mp4"
]

def process_benchmark_video(video_name: str) -> dict:
    video_path = os.path.join(VIDEO_DIR, video_name)
    if not os.path.exists(video_path):
        return {"error": f"File not found: {video_path}"}

    cap = cv2.VideoCapture(video_path)
    if not cap.isOpened():
        return {"error": f"Cannot open video: {video_path}"}

    total_frames = int(cap.get(cv2.CAP_PROP_FRAME_COUNT))
    fps = cap.get(cv2.CAP_PROP_FPS) or 30.0
    duration_sec = total_frames / max(1.0, fps)

    # For long surveillance videos (e.g. north_lane 18,415 frames), sample up to 1500 frames with step=2
    frame_step = 2 if total_frames > 400 else 1
    max_frames_to_read = 1500 if total_frames > 2000 else total_frames

    print("\n" + "=" * 65, flush=True)
    print(f"📹 Processing: {video_name}", flush=True)
    print(f"   Frames: {total_frames} (Evaluating up to {max_frames_to_read}) | FPS: {fps:.1f} | Duration: {duration_sec:.1f}s | Step: {frame_step}", flush=True)
    print("=" * 65, flush=True)

    active_tracks: dict[int, VehicleTrackState] = {}
    finalized_violations: list[dict] = []
    
    start_time = time.time()
    frame_idx = 0
    evaluated_frame_count = 0

    def finalize_track(t_state: VehicleTrackState, f_idx: int):
        if t_state.state != "CONFIRMED":
            return

        plate_crops = [p[1] for p in t_state.plate_candidates]
        plate_text, ocr_conf, is_auto_verified = ocr_engine.vote_on_crop_candidates(plate_crops)

        full_scene = t_state.best_violation_frame
        rider_zoom = t_state.best_violation_crop
        plate_crop = t_state.plate_candidates[0][1] if t_state.plate_candidates else None

        hit_ratio = float(t_state.no_helmet_hits) / float(max(1, t_state.evaluable_frames))
        meta = {
            "camera_id": f"BHOPAL-{video_name.replace('.mp4', '').upper()}",
            "timestamp": f"Frame {f_idx} (T+{f_idx/max(1, fps):.1f}s)",
            "violation_type": t_state.confirmed_violation_type,
            "plate_text": plate_text,
            "hit_ratio": hit_ratio,
            "track_id": t_state.track_id
        }

        composite_img, sha256_hash = build_3panel_composite_evidence(
            full_scene if full_scene is not None else np.zeros((720, 1280, 3), dtype=np.uint8),
            rider_zoom,
            plate_crop,
            meta
        )

        lane_tag = video_name.replace(".mp4", "")
        comp_fname = f"benchmark_{lane_tag}_track{t_state.track_id}_{t_state.confirmed_violation_type.replace(' ', '_').lower()}.jpg"
        comp_path = os.path.join(BENCHMARK_DIR, comp_fname)
        cv2.imwrite(comp_path, composite_img)

        # Sync to artifacts
        art_path = os.path.join(ARTIFACT_DIR, comp_fname)
        shutil.copy2(comp_path, art_path)

        finalized_violations.append({
            "track_id": t_state.track_id,
            "type": t_state.confirmed_violation_type,
            "plate": plate_text,
            "ocr_conf": ocr_conf,
            "auto_verified": is_auto_verified,
            "evaluable_frames": t_state.evaluable_frames,
            "hit_ratio": hit_ratio,
            "composite_filename": comp_fname,
            "sha256": sha256_hash
        })
        t_state.state = "LOGGED"
        print(f"   🚨 [CONFIRMED & LOGGED] Track {t_state.track_id}: {t_state.confirmed_violation_type} | Plate: {plate_text} | Evidence: {comp_fname}", flush=True)

    while True:
        ret, frame = cap.read()
        if not ret or frame_idx >= max_frames_to_read:
            break
        frame_idx += 1

        if frame_idx % frame_step != 0:
            continue
        evaluated_frame_count += 1

        frame_h, frame_w = frame.shape[:2]

        # Stage 1: ByteTrack continuous tracking
        res1 = m1.track(frame, persist=True, verbose=False, conf=0.20, imgsz=960, device=device)

        m1_motos = []
        raw_persons = []
        for b in res1[0].boxes:
            c = int(b.cls[0])
            box = list(map(int, b.xyxy[0]))
            tid = int(b.id[0]) if b.id is not None else None
            conf = float(b.conf[0])
            if c == 3 and tid is not None:
                m1_motos.append({"box": box, "tid": tid, "conf": conf})
            elif c == 0:
                raw_persons.append(box)

        # Deduplicate overlapping persons (IoU > 0.40)
        m1_persons = []
        for p in raw_persons:
            if not any(compute_iou(p, dp) > 0.40 for dp in m1_persons):
                m1_persons.append(p)

        seen_tids = set()

        for bike in m1_motos:
            bx1, by1, bx2, by2 = bike["box"]
            tid = bike["tid"]
            bh = by2 - by1
            bw = max(1, bx2 - bx1)
            seen_tids.add(tid)

            if tid not in active_tracks:
                active_tracks[tid] = VehicleTrackState(tid, fps=fps)
            t_state = active_tracks[tid]

            assigned_riders = [p for p in m1_persons if is_person_riding_bike(p, bike["box"])]

            # Bounding box envelope
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

            res2 = m2(crop, verbose=False, conf=0.08, imgsz=640, device=device)

            raw_helmets = []
            raw_no_helmets = []
            frame_plate_crops = []

            for b in res2[0].boxes:
                c2 = int(b.cls[0])
                lx1, ly1, lx2, ly2 = map(int, b.xyxy[0])
                cconf = float(b.conf[0])
                box_l = [lx1, ly1, lx2, ly2]

                if c2 == 0 and cconf >= 0.25:
                    raw_helmets.append({"box_l": box_l, "conf": cconf})
                elif c2 == 1 and cconf >= 0.25:
                    raw_no_helmets.append({"box_l": box_l, "conf": cconf})
                elif c2 == 2 and cconf >= 0.35:
                    pw = lx2 - lx1
                    if pw >= 60:
                        p_crop = crop[max(0, ly1):ly2, max(0, lx1):lx2]
                        if p_crop.size > 0:
                            frame_plate_crops.append((cconf, p_crop))

            # Disambiguate overlapping heads
            valid_no_helmets = []
            for nh in raw_no_helmets:
                conflicting_h = [h for h in raw_helmets if compute_iou(nh["box_l"], h["box_l"]) > 0.35]
                if not conflicting_h or nh["conf"] > max(h["conf"] for h in conflicting_h):
                    valid_no_helmets.append(nh)

            has_no_helmet = len(valid_no_helmets) > 0
            nh_conf = max([nh["conf"] for nh in valid_no_helmets], default=0.0)
            has_triple_riding = len(assigned_riders) >= 3

            t_state.update_frame(
                bike_box=bike["box"],
                has_no_helmet=has_no_helmet,
                nh_conf=nh_conf,
                has_triple_riding=has_triple_riding,
                envelope_crop=crop,
                full_frame=frame,
                detected_plate_crops=frame_plate_crops
            )

        # Increment lost frames for tracks missing in this frame
        for tid, t_state in list(active_tracks.items()):
            if tid not in seen_tids and t_state.state != "LOGGED":
                has_term = t_state.mark_lost_frame()
                if has_term and t_state.can_finalize(video_ending=False):
                    finalize_track(t_state, frame_idx)

    # End of video: flush any remaining active confirmed tracks
    for tid, t_state in active_tracks.items():
        if t_state.can_finalize(video_ending=True):
            finalize_track(t_state, frame_idx)

    cap.release()
    total_elapsed = time.time() - start_time
    proc_fps = float(evaluated_frame_count) / max(0.001, total_elapsed)

    result_summary = {
        "video_name": video_name,
        "total_frames": total_frames,
        "evaluated_frames": evaluated_frame_count,
        "duration_sec": duration_sec,
        "elapsed_sec": total_elapsed,
        "fps_throughput": proc_fps,
        "unique_tracks": len(active_tracks),
        "violations_count": len(finalized_violations),
        "violations": finalized_violations
    }

    print(f"✅ {video_name} Complete in {total_elapsed:.1f}s ({proc_fps:.1f} FPS) | Tracks: {len(active_tracks)} | Violations: {len(finalized_violations)}", flush=True)
    return result_summary

if __name__ == "__main__":
    benchmark_results = []
    print("=" * 65, flush=True)
    print("🚦 V.I.T.A.L.S. MULTI-VIDEO BENCHMARK RUN", flush=True)
    print(f"Total Videos to Benchmark: {len(VIDEO_FILES)}", flush=True)
    print("=" * 65, flush=True)

    for vid in VIDEO_FILES:
        res = process_benchmark_video(vid)
        benchmark_results.append(res)

    print("\n" + "=" * 65, flush=True)
    print("🏁 BENCHMARK SUITE COMPLETE", flush=True)
    print("=" * 65, flush=True)
    for res in benchmark_results:
        vname = res.get("video_name", "Unknown")
        tracks = res.get("unique_tracks", 0)
        viols = res.get("violations_count", 0)
        fps_t = res.get("fps_throughput", 0.0)
        print(f"  • {vname:16s}: {tracks:3d} tracks | {viols:2d} violations | {fps_t:5.1f} FPS", flush=True)
        for v in res.get("violations", []):
            print(f"      -> Track {v['track_id']:2d}: {v['type']} | Plate: {v['plate']} (Auto-Verified: {v['auto_verified']})", flush=True)
    print("=" * 65, flush=True)
