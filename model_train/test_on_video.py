"""
═══════════════════════════════════════════════════════════════
  🎥 V.I.T.A.L.S. — Video Visual Debugger & Enforcement Tester
  Tests detection models and spatial fusion logic on any video.
  Saves annotated frames and outputs why violations pass/fail.
═══════════════════════════════════════════════════════════════
"""

import os
import sys
import cv2
import argparse
import numpy as np
from ultralytics import YOLO

def box_center(box):
    return ((box[0] + box[2]) // 2, (box[1] + box[3]) // 2)

def box_contains(outer, point):
    px, py = point
    return outer[0] <= px <= outer[2] and outer[1] <= py <= outer[3]

def compute_iou(boxA, boxB):
    xA, yA = max(boxA[0], boxB[0]), max(boxA[1], boxB[1])
    xB, yB = min(boxA[2], boxB[2]), min(boxA[3], boxB[3])
    inter = max(0, xB - xA) * max(0, yB - yA)
    if inter == 0: return 0.0
    areaA = (boxA[2] - boxA[0]) * (boxA[3] - boxA[1])
    areaB = (boxB[2] - boxB[0]) * (boxB[3] - boxB[1])
    return inter / float(areaA + areaB - inter)

def run_debug(video_path: str, m1_path: str, m2_path: str, output_dir: str, conf_m1: float = 0.25, conf_m2: float = 0.10, max_frames: int = 150):
    os.makedirs(output_dir, exist_ok=True)
    print(f"🎬 Loading video: {video_path}")
    print(f"📦 Model 1 (Tracker): {m1_path} (conf={conf_m1})")
    print(f"📦 Model 2 (Custom) : {m2_path} (conf={conf_m2})")
    print(f"📁 Output Directory : {output_dir}\n")

    m1 = YOLO(m1_path)
    m2 = YOLO(m2_path)

    cap = cv2.VideoCapture(video_path)
    if not cap.isOpened():
        print(f"❌ Failed to open video: {video_path}")
        return

    frame_idx = 0
    saved_violations = 0

    while True:
        ret, frame = cap.read()
        if not ret or frame_idx >= max_frames:
            break

        frame_idx += 1
        vis = frame.copy()

        # Step 1: Run M1 (COCO tracking)
        res1 = m1(frame, verbose=False, conf=conf_m1, imgsz=640)
        # Step 2: Run M2 (Custom enforcement)
        res2 = m2(frame, verbose=False, conf=conf_m2, imgsz=640)

        m1_motos = []
        m1_persons = []
        for b in res1[0].boxes:
            c = int(b.cls[0])
            box = list(map(int, b.xyxy[0]))
            conf = float(b.conf[0])
            if c == 3:  # motorcycle
                m1_motos.append({"box": box, "conf": conf})
                cv2.rectangle(vis, (box[0], box[1]), (box[2], box[3]), (0, 255, 0), 2)
                cv2.putText(vis, f"M1:Bike {conf:.2f}", (box[0], box[1]-5), 0, 0.5, (0, 255, 0), 1)
            elif c == 0:  # person
                m1_persons.append(box)
                cv2.rectangle(vis, (box[0], box[1]), (box[2], box[3]), (255, 200, 0), 1)

        m2_helmets = []
        m2_plates = []
        m2_persons = []
        m2_motos = []
        for b in res2[0].boxes:
            c = int(b.cls[0])
            box = list(map(int, b.xyxy[0]))
            conf = float(b.conf[0])
            name = m2.names.get(c, str(c))
            
            if c == 0:  # Helmet
                m2_helmets.append(box)
                cv2.rectangle(vis, (box[0], box[1]), (box[2], box[3]), (0, 255, 255), 2)
                cv2.putText(vis, f"Helmet {conf:.2f}", (box[0], box[1]-5), 0, 0.4, (0, 255, 255), 1)
            elif c == 1:  # Plate
                m2_plates.append(box)
                cv2.rectangle(vis, (box[0], box[1]), (box[2], box[3]), (255, 0, 255), 2)
                cv2.putText(vis, f"Plate {conf:.2f}", (box[0], box[1]-5), 0, 0.4, (255, 0, 255), 1)
            elif c == 2:  # Motorcycle
                m2_motos.append(box)
            elif c == 3:  # Person
                m2_persons.append(box)

        # Spatial reasoning check
        for bike in m1_motos:
            bx1, by1, bx2, by2 = bike["box"]
            bh = by2 - by1
            expanded = [bx1, max(0, by1 - int(bh * 0.8)), bx2, by2]
            cv2.rectangle(vis, (expanded[0], expanded[1]), (expanded[2], expanded[3]), (255, 120, 0), 1)

            # Persons on bike
            riders = [p for p in m1_persons if box_contains(expanded, box_center(p))]
            
            # Check Triple Riding
            if len(riders) >= 3:
                cv2.putText(vis, f"VIOLATION: Triple Riding ({len(riders)})", (bx1, expanded[1]-15), 0, 0.6, (0, 0, 255), 2)
                saved_violations += 1

            # Check Helmets
            for r in riders:
                rh = r[3] - r[1]
                head_zone = [r[0], r[1], r[2], r[1] + int(rh * 0.35)]
                has_h = any(compute_iou(head_zone, h) > 0.1 for h in m2_helmets)
                if not has_h:
                    cv2.putText(vis, "NO HELMET", (r[0], r[1]-5), 0, 0.5, (0, 0, 255), 2)

        if frame_idx % 20 == 0:
            out_frame = os.path.join(output_dir, f"frame_{frame_idx:04d}.jpg")
            cv2.imwrite(out_frame, vis)
            print(f"  Frame {frame_idx:03d} -> M1 Bikes: {len(m1_motos)}, Persons: {len(m1_persons)} | M2 Helmets: {len(m2_helmets)}, Plates: {len(m2_plates)}")

    cap.release()
    print(f"\n✅ Diagnostic Finished. Annotated sample frames saved to: {output_dir}")

if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Debug YOLO video detection")
    parser.add_argument("--video", type=str, default="../backend/test_videos/north_lane.mp4", help="Video path")
    parser.add_argument("--m1", type=str, default="yolov8n.pt", help="Path to yolov8n.pt")
    parser.add_argument("--m2", type=str, default="best.pt", help="Path to best.pt")
    parser.add_argument("--out", type=str, default="debug_output", help="Output directory")
    parser.add_argument("--conf-m2", type=float, default=0.08, help="Model 2 confidence threshold")
    parser.add_argument("--frames", type=int, default=100, help="Max frames to process")

    args = parser.parse_args()

    v = args.video
    if not os.path.isabs(v):
        v = os.path.join(os.path.dirname(__file__), v)
    m1 = args.m1
    if not os.path.isabs(m1):
        m1 = os.path.join(os.path.dirname(__file__), m1)
    m2 = args.m2
    if not os.path.isabs(m2):
        m2 = os.path.join(os.path.dirname(__file__), m2)
    out = args.out
    if not os.path.isabs(out):
        out = os.path.join(os.path.dirname(__file__), out)

    run_debug(v, m1, m2, out, conf_m2=args.conf_m2, max_frames=args.frames)
