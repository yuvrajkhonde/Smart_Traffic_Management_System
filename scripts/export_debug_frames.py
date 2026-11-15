import os
import sys
import glob
import cv2
import numpy as np
import shutil
import torch
from datetime import datetime
from ultralytics import YOLO

CURRENT_DIR = os.path.dirname(os.path.abspath(__file__))
ROOT_DIR = os.path.join(CURRENT_DIR, "..")
sys.path.insert(0, ROOT_DIR)

from backend.ai_engine.enforcement_engine import (
    VehicleTrackState, IndianPlateOCREngine, build_3panel_composite_evidence,
    compute_normalized_sharpness
)

VIDEO_PATH = os.path.join(ROOT_DIR, "backend", "test_videos", "new.mp4")
M1_PATH = os.path.join(ROOT_DIR, "ai_models", "yolov8n.pt")
M2_PATH = os.path.join(ROOT_DIR, "ai_models", "best.pt")
OUTPUT_DIR = os.path.join(ROOT_DIR, "captured_test_frames")

# 1. Clean out old test frames
for folder in ["full_frames", "crops", "composites"]:
    target = os.path.join(OUTPUT_DIR, folder)
    os.makedirs(target, exist_ok=True)
    for f in glob.glob(os.path.join(target, "*.jpg")):
        try: os.remove(f)
        except Exception: pass

print(f"Cleaned old frames. Generating fresh Phase 3 frames into: {OUTPUT_DIR}")

device = "cuda:0" if torch.cuda.is_available() else "cpu"
print(f"Using compute device: {device}")

m1 = YOLO(M1_PATH)
m2 = YOLO(M2_PATH)
ocr_engine = IndianPlateOCREngine()

def compute_iop(person_box, bike_box):
    px1, py1, px2, py2 = person_box
    bx1, by1, bx2, by2 = bike_box
    inter_x1 = max(px1, bx1)
    inter_y1 = max(py1, by1)
    inter_x2 = min(px2, bx2)
    inter_y2 = min(py2, by2)
    if inter_x2 <= inter_x1 or inter_y2 <= inter_y1:
        return 0.0
    inter_area = (inter_x2 - inter_x1) * (inter_y2 - inter_y1)
    person_area = max(1, (px2 - px1) * (py2 - py1))
    return inter_area / float(person_area)

def is_person_riding_bike(person_box, bike_box):
    px1, py1, px2, py2 = person_box
    bx1, by1, bx2, by2 = bike_box
    bh = max(1, by2 - by1)
    bw = max(1, bx2 - bx1)
    ph = max(1, py2 - py1)
    pw = max(1, px2 - px1)

    # 1. Perspective Scale Gating
    if (ph / float(bh)) < 0.45 or (ph / float(bh)) > 2.2:
        return False

    # 2. Area Ratio Gating
    if ((pw * ph) / float(bw * bh)) < 0.18:
        return False

    # 3. Horizontal Co-occurrence
    if (px2 < (bx1 - int(bw * 0.15))) or (px1 > (bx2 + int(bw * 0.15))):
        return False

    # 4. Vertical Seat Penetration
    if py2 < (by1 + int(bh * 0.15)):
        return False

    # 5. Overlap check
    iop = compute_iop(person_box, bike_box)
    if iop >= 0.12:
        return True

    if (by1 - int(bh * 0.4)) <= py2 <= (by2 + int(bh * 0.1)):
        return True

    return False

def compute_iou(boxA, boxB):
    xA = max(boxA[0], boxB[0])
    yA = max(boxA[1], boxB[1])
    xB = min(boxA[2], boxB[2])
    yB = min(boxA[3], boxB[3])
    interArea = max(0, xB - xA) * max(0, yB - yA)
    boxAArea = max(1, (boxA[2] - boxA[0]) * (boxA[3] - boxA[1]))
    boxBArea = max(1, (boxB[2] - boxB[0]) * (boxB[3] - boxB[1]))
    return interArea / float(boxAArea + boxBArea - interArea)

cap = cv2.VideoCapture(VIDEO_PATH)
fps = cap.get(cv2.CAP_PROP_FPS) or 30.0
total_frames = int(cap.get(cv2.CAP_PROP_FRAME_COUNT))
print(f"Total video frames in new.mp4: {total_frames} (FPS: {fps:.1f})")

active_tracks: dict[int, VehicleTrackState] = {}
finalized_violations: list[dict] = []

ARTIFACT_DIR = os.getenv("ARTIFACT_DIR", os.path.join(ROOT_DIR, "captured_test_frames", "debug"))
os.makedirs(ARTIFACT_DIR, exist_ok=True)

def draw_badge(img, text, x, y, bg_color, text_color=(255, 255, 255), scale=0.55, thick=1):
    (w, h), baseline = cv2.getTextSize(text, cv2.FONT_HERSHEY_SIMPLEX, scale, thick)
    pad = 4
    x1 = max(0, x)
    y1 = max(0, y - h - pad * 2)
    x2 = min(img.shape[1], x + w + pad * 2)
    y2 = min(img.shape[0], y + baseline)
    cv2.rectangle(img, (x1, y1), (x2, y2), bg_color, -1)
    cv2.putText(img, text, (x1 + pad, y - pad), cv2.FONT_HERSHEY_SIMPLEX, scale, text_color, thick, cv2.LINE_AA)

def finalize_track(t_state: VehicleTrackState, frame_num: int):
    if t_state.state != "CONFIRMED":
        return

    print(f"\n🏆 [EVIDENCE FINALIZATION] Track ID {t_state.track_id} confirmed violation: '{t_state.confirmed_violation_type}'")
    print(f"   • Evaluable frames: {t_state.evaluable_frames} | No-helmet hits: {t_state.no_helmet_hits} ({t_state.no_helmet_hits/max(1, t_state.evaluable_frames)*100:.1f}%)")
    print(f"   • Plate candidates collected in buffer: {len(t_state.plate_candidates)}")

    # 1. OCR Consensus on candidate crops
    plate_crops = [p[1] for p in t_state.plate_candidates]
    plate_text, ocr_conf, is_auto_verified = ocr_engine.vote_on_crop_candidates(plate_crops)
    print(f"   • OCR Consensus Result: '{plate_text}' | Conf: {ocr_conf:.2f} | Auto-Verified: {is_auto_verified}")

    # 2. Build 3-Panel Composite
    full_scene = t_state.best_violation_frame
    rider_zoom = t_state.best_violation_crop
    plate_crop = t_state.plate_candidates[0][1] if t_state.plate_candidates else None

    hit_ratio = float(t_state.no_helmet_hits) / float(max(1, t_state.evaluable_frames))
    metadata = {
        "camera_id": "BHOPAL-CCTV-04",
        "timestamp": f"Frame {frame_num} ({datetime.now().strftime('%Y-%m-%d %H:%M:%S')})",
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
    print(f"   • 3-Panel Composite SHA-256: {sha256_hash[:16]}...")

    # 3. Save files
    comp_fname = f"composite_track{t_state.track_id}_{t_state.confirmed_violation_type.replace(' ', '_').lower()}.jpg"
    comp_path = os.path.join(OUTPUT_DIR, "composites", comp_fname)
    cv2.imwrite(comp_path, composite_img)
    print(f"   • Saved composite evidence: {comp_path}")

    # Sync to artifact gallery for user report
    art_path = os.path.join(ARTIFACT_DIR, f"phase3_{comp_fname}")
    shutil.copy2(comp_path, art_path)

    finalized_violations.append({
        "track_id": t_state.track_id,
        "type": t_state.confirmed_violation_type,
        "plate": plate_text,
        "ocr_conf": ocr_conf,
        "auto_verified": is_auto_verified,
        "hit_ratio": hit_ratio,
        "evaluable_frames": t_state.evaluable_frames,
        "composite_path": comp_path,
        "sha256": sha256_hash
    })
    t_state.state = "LOGGED"

frame_idx = 0
step = 1  # Continuous frame tracking for maximum ByteTrack stability

print("Processing video with ByteTrack + Phase 3 State Machine...")

while True:
    ret, frame = cap.read()
    if not ret:
        break
    frame_idx += 1

    frame_h, frame_w = frame.shape[:2]
    vis = frame.copy()

    scale = max(1.0, frame_w / 1920.0)
    thick = max(2, int(round(2 * scale)))
    fscale = 0.52 * scale
    fthick = max(1, int(round(1.5 * scale)))

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

    # Deduplicate persons (IoU > 0.40)
    m1_persons = []
    for p in raw_persons:
        if not any(compute_iou(p, dp) > 0.40 for dp in m1_persons):
            m1_persons.append(p)

    seen_track_ids_this_frame = set()

    for bike in m1_motos:
        bx1, by1, bx2, by2 = bike["box"]
        track_id = bike["tid"]
        bh = by2 - by1
        bw = max(1, bx2 - bx1)
        seen_track_ids_this_frame.add(track_id)

        if track_id not in active_tracks:
            active_tracks[track_id] = VehicleTrackState(track_id, fps=fps)
        t_state = active_tracks[track_id]

        assigned_riders = [p for p in m1_persons if is_person_riding_bike(p, bike["box"])]

        # Envelope
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

        cvis = crop.copy()
        cw = cvis.shape[1]
        cscale = max(0.6, min(2.0, cw / 600.0))
        cthick = max(1, int(round(2 * cscale)))
        cfscale = 0.5 * cscale
        cfthick = max(1, int(round(1.5 * cscale)))

        res2 = m2(crop, verbose=False, conf=0.08, imgsz=640, device=device)

        raw_helmets = []
        raw_no_helmets = []
        frame_plate_crops = []

        for b in res2[0].boxes:
            c2 = int(b.cls[0])
            lx1, ly1, lx2, ly2 = map(int, b.xyxy[0])
            cconf = float(b.conf[0])
            gx1, gy1, gx2, gy2 = lx1 + cx1, ly1 + cy1, lx2 + cx1, ly2 + cy1
            box_g = [gx1, gy1, gx2, gy2]
            box_l = [lx1, ly1, lx2, ly2]

            if c2 == 0 and cconf >= 0.25:  # With Helmet
                raw_helmets.append({"box_g": box_g, "box_l": box_l, "conf": cconf})
            elif c2 == 1 and cconf >= 0.25:  # Without Helmet
                raw_no_helmets.append({"box_g": box_g, "box_l": box_l, "conf": cconf})
            elif c2 == 2 and cconf >= 0.35:  # licence (gated by conf >= 0.35)
                pw = lx2 - lx1
                if pw >= 60:  # Gated by width >= 60px
                    p_crop = crop[max(0, ly1):ly2, max(0, lx1):lx2]
                    if p_crop.size > 0:
                        frame_plate_crops.append((cconf, p_crop))
                        cv2.rectangle(vis, (gx1, gy1), (gx2, gy2), (255, 0, 255), thick)
                        draw_badge(vis, f"Plate {cconf:.2f}", gx1, max(22, gy1 - 4), (180, 0, 180), scale=fscale * 0.85, thick=fthick)
                        cv2.rectangle(cvis, (lx1, ly1), (lx2, ly2), (255, 0, 255), cthick)
                        draw_badge(cvis, f"Plate {cconf:.2f}", lx1, max(18, ly1 - 3), (180, 0, 180), scale=cfscale, thick=cfthick)

        # Disambiguate overlapping heads (IoU > 0.35)
        valid_no_helmets = []
        for nh in raw_no_helmets:
            conflicting_h = [h for h in raw_helmets if compute_iou(nh["box_l"], h["box_l"]) > 0.35]
            if not conflicting_h or nh["conf"] > max(h["conf"] for h in conflicting_h):
                valid_no_helmets.append(nh)

        valid_helmets = []
        for h in raw_helmets:
            conflicting_nh = [nh for nh in raw_no_helmets if compute_iou(h["box_l"], nh["box_l"]) > 0.35]
            if not conflicting_nh or h["conf"] >= max(nh["conf"] for nh in conflicting_nh):
                valid_helmets.append(h)

        # Draw validated helmets / no-helmets on debug visualization
        for h in valid_helmets:
            gx1, gy1, gx2, gy2 = h["box_g"]
            cv2.rectangle(vis, (gx1, gy1), (gx2, gy2), (0, 255, 0), thick)
            draw_badge(vis, f"Helmet {h['conf']:.2f}", gx1, max(22, gy1 - 4), (0, 160, 0), scale=fscale * 0.85, thick=fthick)

        for nh in valid_no_helmets:
            gx1, gy1, gx2, gy2 = nh["box_g"]
            cv2.rectangle(vis, (gx1, gy1), (gx2, gy2), (0, 0, 255), thick)
            draw_badge(vis, f"No-Helmet {nh['conf']:.2f}", gx1, max(22, gy1 - 4), (0, 0, 200), scale=fscale * 0.85, thick=fthick)

        has_no_helmet = len(valid_no_helmets) > 0
        nh_conf = max([nh["conf"] for nh in valid_no_helmets], default=0.0)
        has_triple_riding = len(assigned_riders) >= 3

        # Update State Machine
        t_state.update_frame(
            bike_box=bike["box"],
            has_no_helmet=has_no_helmet,
            nh_conf=nh_conf,
            has_triple_riding=has_triple_riding,
            envelope_crop=crop,
            full_frame=frame,
            detected_plate_crops=frame_plate_crops
        )

        # Annotated debug badge for status
        status_text = f"Track {track_id} [{t_state.state}] (eval:{t_state.evaluable_frames}f hits:{t_state.no_helmet_hits})"
        badge_col = (0, 0, 200) if t_state.state == "CONFIRMED" else ((0, 140, 255) if t_state.state == "SUSPECTED" else (70, 70, 70))
        cv2.rectangle(vis, (bx1, by1), (bx2, by2), (255, 255, 0), thick)
        draw_badge(vis, status_text, bx1, max(28, by1 - int(10 * scale)), badge_col, scale=fscale, thick=fthick)

        # Early finalization check if plate has superb sharpness
        if t_state.can_finalize(video_ending=False):
            finalize_track(t_state, frame_idx)

        # Save sampled debug frames for review
        if frame_idx in [12, 24, 36, 48, 60, 80, 100, 120, 140]:
            crop_path = os.path.join(OUTPUT_DIR, "crops", f"phase3_crop_f{frame_idx:04d}_id{track_id}.jpg")
            cv2.imwrite(crop_path, cvis)

    # Check tracks lost in this frame
    for tid, t_state in list(active_tracks.items()):
        if tid not in seen_track_ids_this_frame and t_state.state != "LOGGED":
            has_terminated = t_state.mark_lost_frame()
            if has_terminated and t_state.can_finalize(video_ending=False):
                finalize_track(t_state, frame_idx)

    if frame_idx % 24 == 0:
        full_path = os.path.join(OUTPUT_DIR, "full_frames", f"phase3_full_f{frame_idx:04d}.jpg")
        cv2.imwrite(full_path, vis)

# Video End: Flush remaining active tracks
print("\n🏁 [VIDEO END] Flushing all remaining active confirmed tracks...")
for tid, t_state in active_tracks.items():
    if t_state.can_finalize(video_ending=True):
        finalize_track(t_state, frame_idx)

cap.release()

print("\n" + "=" * 65)
print("📊 PHASE 3 ENFORCEMENT SUMMARY:")
print(f"Total Video Frames Processed: {frame_idx}")
print(f"Total Unique Vehicle Tracks: {len(active_tracks)}")
print(f"Finalized Violations Logged: {len(finalized_violations)}")
print("=" * 65)
for v in finalized_violations:
    print(f"  • Track ID {v['track_id']}: {v['type']}")
    print(f"    - Extracted Plate: '{v['plate']}' (OCR Conf: {v['ocr_conf']:.2f}, Auto-Verified: {v['auto_verified']})")
    print(f"    - Hit Ratio     : {v['hit_ratio']*100:.1f}% across {v['evaluable_frames']} evaluable frames")
    print(f"    - SHA-256 Hash  : {v['sha256']}")
    print(f"    - Composite Path: {v['composite_path']}")
print("=" * 65)
