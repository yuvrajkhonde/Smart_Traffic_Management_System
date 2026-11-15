"""
V.I.T.A.L.S. Phase 2: Live Surveillance Video Testing Script
Runs the Two-Stage Pipeline on real traffic footage (north_lane.mp4) using:
  - Stage 1: yolov8n.pt (Vehicles + Riders + ByteTrack persistent trajectory)
  - Stage 2: Newly trained Phase 2 model (With Helmet, Without Helmet, Licence)
Outputs annotated full frames and high-res enforcement crops to ml_training/test_outputs/
"""

import os
import cv2
import numpy as np
from ultralytics import YOLO

CURRENT_DIR = os.path.dirname(os.path.abspath(__file__))
ROOT_DIR = os.path.join(CURRENT_DIR, "..")
VIDEO_PATH = os.path.join(ROOT_DIR, "backend", "test_videos", "north_lane.mp4")
M1_PATH = os.path.join(ROOT_DIR, "ai_models", "yolov8n.pt")
M2_PATH = os.path.join(CURRENT_DIR, "runs", "phase2_enforcement", "weights", "best.pt")
OUTPUT_DIR = os.path.join(CURRENT_DIR, "test_outputs")

os.makedirs(os.path.join(OUTPUT_DIR, "full_frames"), exist_ok=True)
os.makedirs(os.path.join(OUTPUT_DIR, "crops"), exist_ok=True)

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
    iop = compute_iop(person_box, bike_box)
    if iop >= 0.15:
        return True
    px1, py1, px2, py2 = person_box
    bx1, by1, bx2, by2 = bike_box
    bh = by2 - by1
    pw = px2 - px1
    pcx = (px1 + px2) // 2
    if (bx1 - int(pw * 0.4)) <= pcx <= (bx2 + int(pw * 0.4)):
        if (by1 - int(bh * 0.4)) <= py2 <= (by2 + int(bh * 0.1)):
            return True
    return False

def test(m2_weights=None):
    weights = m2_weights or M2_PATH
    if not os.path.exists(weights):
        print(f"❌ Weights not found: {weights}")
        return

    print("=" * 65)
    print("🎥 Testing Trained Model on CCTV Video")
    print(f"Video  : {VIDEO_PATH}")
    print(f"Stage 1: {M1_PATH}")
    print(f"Stage 2: {weights}")
    print("=" * 65)

    m1 = YOLO(M1_PATH)
    m2 = YOLO(weights)

    cap = cv2.VideoCapture(VIDEO_PATH)
    frame_idx = 0
    track_state = {}
    saved_frames = 0

    while True:
        ret, frame = cap.read()
        if not ret or frame_idx >= 200:
            break
        frame_idx += 1

        frame_h, frame_w = frame.shape[:2]
        vis = frame.copy()

        # Stage 1: Tracking on consecutive frames
        res1 = m1.track(frame, persist=True, verbose=False, conf=0.20, imgsz=640)

        m1_motos = []
        m1_persons = []
        for b in res1[0].boxes:
            c = int(b.cls[0])
            box = list(map(int, b.xyxy[0]))
            tid = int(b.id[0]) if b.id is not None else 0
            if c == 3:
                m1_motos.append({"box": box, "tid": tid})
            elif c == 0:
                m1_persons.append(box)

        # Stage 2: Enforcement on each motorcycle
        for bike in m1_motos:
            bx1, by1, bx2, by2 = bike["box"]
            tid = bike["tid"]
            bh = by2 - by1
            bw = bx2 - bx1

            # Rider association
            riders = [p for p in m1_persons if is_person_riding_bike(p, bike["box"])]

            # Dynamic Envelope Crop
            min_x, min_y, max_x, max_y = bx1, by1, bx2, by2
            if riders:
                for p in riders:
                    min_x, min_y = min(min_x, p[0]), min(min_y, p[1])
                    max_x, max_y = max(max_x, p[2]), max(max_y, p[3])
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

            cv2.rectangle(vis, (bx1, by1), (bx2, by2), (255, 255, 0), 2)
            cv2.putText(vis, f"Bike ID:{tid}", (bx1, by2 + 15), 0, 0.45, (255, 255, 0), 1)

            crop = frame[cy1:cy2, cx1:cx2]
            if crop.size == 0 or crop.shape[0] < 20 or crop.shape[1] < 20:
                continue

            cvis = crop.copy()
            res2 = m2(crop, verbose=False, conf=0.25, imgsz=640)

            detected_helmets = []
            detected_no_helmets = []
            detected_plates = []

            for b in res2[0].boxes:
                c2 = int(b.cls[0])
                conf = float(b.conf[0])
                lx1, ly1, lx2, ly2 = map(int, b.xyxy[0])
                gx1, gy1, gx2, gy2 = lx1 + cx1, ly1 + cy1, lx2 + cx1, ly2 + cy1

                # 0: With Helmet, 1: Without Helmet, 2: licence
                if c2 == 0:
                    detected_helmets.append((gx1, gy1, gx2, gy2, conf))
                    cv2.rectangle(vis, (gx1, gy1), (gx2, gy2), (0, 255, 0), 2)
                    cv2.putText(vis, f"Helmet {conf:.2f}", (gx1, max(12, gy1 - 3)), 0, 0.4, (0, 255, 0), 1)
                    cv2.rectangle(cvis, (lx1, ly1), (lx2, ly2), (0, 255, 0), 2)
                    cv2.putText(cvis, f"Helmet {conf:.2f}", (lx1, max(12, ly1 - 3)), 0, 0.4, (0, 255, 0), 1)
                elif c2 == 1:
                    detected_no_helmets.append((gx1, gy1, gx2, gy2, conf))
                    cv2.rectangle(vis, (gx1, gy1), (gx2, gy2), (0, 0, 255), 2)
                    cv2.putText(vis, f"NO HELMET {conf:.2f}", (gx1, max(12, gy1 - 3)), 0, 0.4, (0, 0, 255), 1)
                    cv2.rectangle(cvis, (lx1, ly1), (lx2, ly2), (0, 0, 255), 2)
                    cv2.putText(cvis, f"NO HELMET {conf:.2f}", (lx1, max(12, ly1 - 3)), 0, 0.4, (0, 0, 255), 1)
                elif c2 == 2:
                    if bh >= 65:  # Resolution Gate
                        detected_plates.append((gx1, gy1, gx2, gy2, conf))
                        cv2.rectangle(vis, (gx1, gy1), (gx2, gy2), (255, 0, 255), 2)
                        cv2.putText(vis, f"Plate {conf:.2f}", (gx1, max(12, gy1 - 3)), 0, 0.4, (255, 0, 255), 1)

            # Triple Riding check
            if len(riders) >= 3:
                cv2.putText(vis, f"TRIPLE RIDING ({len(riders)})", (cx1, max(30, cy1 - 10)), 0, 0.6, (0, 0, 255), 2)
                cv2.putText(cvis, f"TRIPLE RIDING ({len(riders)})", (10, 30), 0, 0.6, (0, 0, 255), 2)

            # Save sample crops
            if frame_idx % 20 == 0 and saved_frames < 10:
                c_out = os.path.join(OUTPUT_DIR, "crops", f"test_crop_f{frame_idx:04d}_id{tid}.jpg")
                cv2.imwrite(c_out, cvis)

        if m1_motos and frame_idx % 20 == 0 and saved_frames < 8:
            f_out = os.path.join(OUTPUT_DIR, "full_frames", f"test_frame_{frame_idx:04d}.jpg")
            cv2.imwrite(f_out, vis)
            saved_frames += 1
            print(f"  Saved test frame {frame_idx:03d}")

    cap.release()
    print(f"\n✅ Surveillance Video Test Complete! Outputs saved in: {OUTPUT_DIR}")

if __name__ == "__main__":
    test()
