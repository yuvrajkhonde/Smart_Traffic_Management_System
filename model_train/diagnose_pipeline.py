import os
import sys
import cv2
from ultralytics import YOLO

CURRENT_DIR = os.path.dirname(os.path.abspath(__file__))
VIDEO_PATH = os.path.join(CURRENT_DIR, "..", "backend", "test_videos", "east_lane.mp4")
MODEL_M1_PATH = os.path.join(CURRENT_DIR, "yolov8n.pt")
MODEL_M2_PATH = os.path.join(CURRENT_DIR, "best.pt")

if not os.path.exists(VIDEO_PATH):
    # Try alternate video
    alt = os.path.join(CURRENT_DIR, "..", "backend", "test_videos", "west_lane.mp4")
    if os.path.exists(alt):
        VIDEO_PATH = alt

print(f"=== V.I.T.A.L.S. Model Diagnostic Tool ===")
print(f"Video: {VIDEO_PATH}")
print(f"M1 Path: {MODEL_M1_PATH}")
print(f"M2 Path: {MODEL_M2_PATH}")

if not os.path.exists(VIDEO_PATH):
    print("No test video found! Exiting.")
    sys.exit(0)

m1 = YOLO(MODEL_M1_PATH)
m2 = YOLO(MODEL_M2_PATH)

print(f"M1 Classes (COCO): {len(m1.names)} classes")
print(f"M2 Classes (Custom): {m2.names}")

cap = cv2.VideoCapture(VIDEO_PATH)
total_frames = int(cap.get(cv2.CAP_PROP_FRAME_COUNT))
fps = cap.get(cv2.CAP_PROP_FPS) or 25
print(f"Total Frames: {total_frames}, FPS: {fps}")

sample_indices = [int(total_frames * r) for r in [0.1, 0.2, 0.3, 0.4, 0.5]]
detected_summary = {"m1_vehicles": 0, "m1_motorcycles": 0, "m1_persons": 0,
                    "m2_helmets": 0, "m2_plates": 0, "m2_motos": 0, "m2_persons": 0}

for idx, f_no in enumerate(sample_indices):
    cap.set(cv2.CAP_PROP_POS_FRAMES, f_no)
    ret, frame = cap.read()
    if not ret:
        continue
    
    h, w = frame.shape[:2]
    # Run M1
    res1 = m1(frame, verbose=False, conf=0.25, imgsz=640)
    # Run M2
    res2 = m2(frame, verbose=False, conf=0.20, imgsz=640)
    
    boxes1 = res1[0].boxes
    boxes2 = res2[0].boxes
    
    m1_counts = {}
    for b in boxes1:
        cls_id = int(b.cls[0])
        name = m1.names[cls_id]
        m1_counts[name] = m1_counts.get(name, 0) + 1
        if cls_id in [2, 3, 5, 7]:
            detected_summary["m1_vehicles"] += 1
        if cls_id == 3:
            detected_summary["m1_motorcycles"] += 1
        if cls_id == 0:
            detected_summary["m1_persons"] += 1
            
    m2_counts = {}
    for b in boxes2:
        cls_id = int(b.cls[0])
        name = m2.names[cls_id]
        m2_counts[name] = m2_counts.get(name, 0) + 1
        conf = float(b.conf[0])
        if cls_id == 0: detected_summary["m2_helmets"] += 1
        elif cls_id == 1: detected_summary["m2_plates"] += 1
        elif cls_id == 2: detected_summary["m2_motos"] += 1
        elif cls_id == 3: detected_summary["m2_persons"] += 1

    print(f"\n[Sample Frame {f_no} / {total_frames} ({w}x{h})]")
    print(f"  M1 (yolov8n): {m1_counts}")
    print(f"  M2 (best.pt): {m2_counts}")

cap.release()

print("\n" + "="*50)
print("DIAGNOSTIC SUMMARY ACROSS SAMPLES:")
for k, v in detected_summary.items():
    print(f"  {k:20s}: {v}")
print("="*50)
