import os
import cv2
import numpy as np
from ultralytics import YOLO

CURRENT_DIR = os.path.dirname(os.path.abspath(__file__))
M1_PATH = os.path.join(CURRENT_DIR, "yolov8n.pt")
M2_PATH = os.path.join(CURRENT_DIR, "best.pt")
VIDEO_PATH = os.path.join(CURRENT_DIR, "..", "backend", "test_videos", "north_lane.mp4")

m1 = YOLO(M1_PATH)
m2 = YOLO(M2_PATH)

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

cap = cv2.VideoCapture(VIDEO_PATH)
total = int(cap.get(cv2.CAP_PROP_FRAME_COUNT))
print(f"Testing Two-Stage Pipeline on {VIDEO_PATH} ({total} frames)...")

# Sample 30 frames
step = max(1, total // 30)
bikes_processed = 0
m2_detections_in_crops = 0

for f_idx in range(0, total, step):
    cap.set(cv2.CAP_PROP_POS_FRAMES, f_idx)
    ret, frame = cap.read()
    if not ret: continue
    
    h, w = frame.shape[:2]
    # Stage 1: M1 Full-frame tracking
    res1 = m1.track(frame, persist=True, verbose=False, conf=0.20, imgsz=640)
    
    m1_motos = []
    m1_persons = []
    for b in res1[0].boxes:
        c = int(b.cls[0])
        box = list(map(int, b.xyxy[0]))
        tid = int(b.id[0]) if b.id is not None else None
        if c == 3: # motorcycle
            m1_motos.append({"box": box, "tid": tid})
        elif c == 0: # person
            m1_persons.append(box)
            
    # Stage 2: For each motorcycle, build union crop & run M2
    for bike in m1_motos:
        bikes_processed += 1
        bbox = bike["box"]
        assigned_riders = [p for p in m1_persons if is_person_riding_bike(p, bbox)]
        
        # Calculate Union Envelope
        min_x, min_y, max_x, max_y = bbox
        if assigned_riders:
            for p in assigned_riders:
                min_x = min(min_x, p[0])
                min_y = min(min_y, p[1])
                max_x = max(max_x, p[2])
                max_y = max(max_y, p[3])
            pad_x = int((max_x - min_x) * 0.12)
            pad_y = int((max_y - min_y) * 0.12)
        else:
            bh = bbox[3] - bbox[1]
            bw = bbox[2] - bbox[0]
            min_y = max(0, bbox[1] - int(bh * 0.85))
            pad_x = int(bw * 0.15)
            pad_y = int(bh * 0.10)
            
        crop_x1 = max(0, min_x - pad_x)
        crop_y1 = max(0, min_y - pad_y)
        crop_x2 = min(w, max_x + pad_x)
        crop_y2 = min(h, max_y + pad_y)
        
        crop = frame[crop_y1:crop_y2, crop_x1:crop_x2]
        if crop.size == 0 or crop.shape[0] < 20 or crop.shape[1] < 20:
            continue
            
        # Run M2 on the crop at imgsz=640
        res2 = m2(crop, verbose=False, conf=0.10, imgsz=640)
        c_boxes = res2[0].boxes
        if len(c_boxes) > 0:
            m2_detections_in_crops += len(c_boxes)
            detected = [f"{m2.names[int(b.cls[0])]}({float(b.conf[0]):.2f})" for b in c_boxes]
            print(f"Frame {f_idx} Bike {bike['tid']}: Crop size {crop.shape[1]}x{crop.shape[0]} | Riders={len(assigned_riders)} | M2 found: {detected}")

cap.release()
print(f"\nDone! Processed {bikes_processed} motorcycle occurrences.")
print(f"Total M2 detections inside crops: {m2_detections_in_crops}")
