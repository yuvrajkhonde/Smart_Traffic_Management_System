import cv2
import uuid
import time
import os
import re
import numpy as np
import threading
from datetime import datetime, timedelta
from ultralytics import YOLO
import easyocr
import torch
from concurrent.futures import ThreadPoolExecutor
from backend.core.database import create_supabase_client

# ─────────────────────────────────────────────────────────────
# 1. INITIALIZATION & HARDWARE SETUP
# ─────────────────────────────────────────────────────────────
ai_lock = threading.Lock() 
# Robust Indian license plate regex pattern
INDIAN_PLATE_PATTERN = r"^[A-Z]{2}[0-9]{1,2}[A-Z]{0,3}[0-9]{1,4}$"

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
# Models live in the root ai_models/ directory
MODELS_DIR = os.path.join(BASE_DIR, "..", "..", "ai_models")
# Evidence images are served from backend/static/evidence
EVIDENCE_PATH = os.path.join(BASE_DIR, "..", "static", "evidence")
os.makedirs(EVIDENCE_PATH, exist_ok=True)

device = "cuda" if torch.cuda.is_available() else "cpu"
print(f"🚀 ENGINE BOOT: V.I.TA.L.S. [Device: {device}]", flush=True)

# Loading the Dual-Model Pipeline
det_model = YOLO(os.path.join(MODELS_DIR, "yolov8n.pt")).to(device)
custom_model = YOLO(os.path.join(MODELS_DIR, "best.pt")).to(device)
plate_reader = easyocr.Reader(['en'], gpu=True if device == "cuda" else False)

# ─── Custom Model Class Map (Phase 2 Model: With Helmet, Without Helmet, licence) ───
# {0: 'With Helmet', 1: 'Without Helmet', 2: 'licence'}
CUSTOM_CLS_WITH_HELMET    = 0
CUSTOM_CLS_WITHOUT_HELMET = 1
CUSTOM_CLS_PLATE          = 2

# ─── Background I/O Thread Pool ───
_bg_pool = ThreadPoolExecutor(max_workers=3, thread_name_prefix="vitals_io")
_thread_local = threading.local()

def _get_bg_supabase():
    """Per-thread Supabase client (no socket sharing between threads)."""
    if not hasattr(_thread_local, 'supabase'):
        _thread_local.supabase = create_supabase_client()
    return _thread_local.supabase

# ─── Cooldown & Tracking State ───
_violation_cooldown = {}
_COOLDOWN_SECONDS = 15
_MAX_COOLDOWN_ENTRIES = 200

# ByteTrack multi-frame state tracking: track_id -> telemetry & voting history
_track_state = {}
_MAX_TRACKED_ENTRIES = 500

# ─────────────────────────────────────────────────────────────
# 2. HELPER FUNCTIONS
# ─────────────────────────────────────────────────────────────
def compute_iou(boxA, boxB):
    """Calculates intersection over union for spatial association."""
    xA, yA = max(boxA[0], boxB[0]), max(boxA[1], boxB[1])
    xB, yB = min(boxA[2], boxB[2]), min(boxA[3], boxB[3])
    inter = max(0, xB - xA) * max(0, yB - yA)
    if inter == 0: return 0.0
    areaA = (boxA[2]-boxA[0])*(boxA[3]-boxA[1])
    areaB = (boxB[2]-boxB[0])*(boxB[3]-boxB[1])
    return inter / float(areaA + areaB - inter)

def compute_iop(person_box, bike_box):
    """Calculates Intersection over Person (area of overlap / area of person)."""
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
    """
    Perspective-aware rider association:
    Ensures person is physically mounted on the bike and not a distant
    background pedestrian whose 2D projection happens to overlap.
    """
    px1, py1, px2, py2 = person_box
    bx1, by1, bx2, by2 = bike_box
    bh = max(1, by2 - by1)
    bw = max(1, bx2 - bx1)
    ph = max(1, py2 - py1)
    pw = max(1, px2 - px1)

    # 1. Perspective Scale Gating: A rider must have proportional height to the motorcycle
    # Distant background pedestrians have ph/bh < 0.35
    if (ph / float(bh)) < 0.45 or (ph / float(bh)) > 2.2:
        return False

    # 2. Area Ratio Gating: Reject tiny background persons (area < 18% of motorcycle)
    if ((pw * ph) / float(bw * bh)) < 0.18:
        return False

    # 3. Vertical Penetration: Rider's lower body must reach into the upper half of the motorcycle
    if py2 < (by1 + int(bh * 0.15)):
        return False

    # 4. Horizontal alignment: Rider's horizontal center must align with the bike
    pcx = (px1 + px2) // 2
    if not ((bx1 - int(pw * 0.20)) <= pcx <= (bx2 + int(pw * 0.20))):
        return False

    # 5. Overlap check: Rider must actually penetrate the motorcycle bounding box
    iop = compute_iop(person_box, bike_box)
    return iop >= 0.20

def box_contains(outer, inner_center):
    """Check if a point (cx, cy) is inside a box [x1,y1,x2,y2]."""
    cx, cy = inner_center
    return outer[0] <= cx <= outer[2] and outer[1] <= cy <= outer[3]

def box_center(box):
    """Returns (cx, cy) of a box."""
    return ((box[0]+box[2])//2, (box[1]+box[3])//2)

def is_ambulance_heuristic(crop):
    """HSV Color isolation for emergency red."""
    if crop.size == 0: return False
    hsv = cv2.cvtColor(crop, cv2.COLOR_BGR2HSV)
    mask = cv2.bitwise_or(cv2.inRange(hsv, np.array([0, 120, 70]), np.array([10, 255, 255])),
                          cv2.inRange(hsv, np.array([170, 120, 70]), np.array([180, 255, 255])))
    return (np.sum(mask > 0) / (crop.shape[0] * crop.shape[1])) * 100 > 3.0

# ─────────────────────────────────────────────────────────────
# 3. OCR FUNCTIONS
# ─────────────────────────────────────────────────────────────

LETTERS_TO_DIGITS = {
    'O': '0', 'I': '1', 'Z': '2', 'S': '5', 'B': '8', 'G': '6', 'T': '7', 'D': '0'
}
DIGITS_TO_LETTERS = {
    '0': 'O', '1': 'I', '2': 'Z', '5': 'S', '8': 'B'
}

def to_letter(c):
    return DIGITS_TO_LETTERS.get(c, c)

def to_digit(c):
    return LETTERS_TO_DIGITS.get(c, c)

def normalize_indian_plate(text):
    text = re.sub(r'[^A-Z0-9]', '', text.upper())
    if len(text) < 7:
        return None
    
    best_overall_score = -1
    best_overall_plate = None
    
    # Try all substrings of length 7 to 10
    for length in range(7, min(11, len(text) + 1)):
        for start in range(len(text) - length + 1):
            candidate = text[start:start+length]
            
            # State code: first 2 chars must be letters
            state = to_letter(candidate[0]) + to_letter(candidate[1])
            state_score = 0
            for c in candidate[:2]:
                if c.isalpha(): state_score += 2
                elif c in DIGITS_TO_LETTERS: state_score += 1
            
            remaining = candidate[2:]
            L = len(remaining)
            
            for d in [1, 2]:
                for s in [0, 1, 2, 3]:
                    for n in [1, 2, 3, 4]:
                        if d + s + n == L:
                            dist_part = remaining[:d]
                            ser_part = remaining[d:d+s]
                            num_part = remaining[d+s:]
                            
                            score = state_score
                            for char in dist_part:
                                if char.isdigit(): score += 2
                                elif char in LETTERS_TO_DIGITS: score += 1
                            for char in ser_part:
                                if char.isalpha(): score += 2
                                elif char in DIGITS_TO_LETTERS: score += 1
                            for char in num_part:
                                if char.isdigit(): score += 2
                                elif char in LETTERS_TO_DIGITS: score += 1
                                
                            # Preference weight for common plate length distributions
                            if L == 8 and d == 2 and s == 2 and n == 4:
                                score += 0.5
                            elif L == 7 and d == 2 and s == 1 and n == 4:
                                score += 0.5
                            elif L == 7 and d == 1 and s == 2 and n == 4:
                                score += 0.5
                            elif L == 6 and d == 2 and s == 0 and n == 4:
                                score += 0.5
                                
                            if score > best_overall_score:
                                best_overall_score = score
                                normalized_dist = "".join(to_digit(c) for c in dist_part)
                                normalized_ser = "".join(to_letter(c) for c in ser_part)
                                normalized_num = "".join(to_digit(c) for c in num_part)
                                best_overall_plate = state + normalized_dist + normalized_ser + normalized_num
                                
    return best_overall_plate

def preprocess_plate_crop(crop, upscale=True):
    if crop is None or crop.size == 0:
        return None
    h, w = crop.shape[:2]
    # Scale crop to minimum 200px width for better OCR readability
    if upscale and w < 200:
        scale = 200.0 / w
        new_w = 200
        new_h = int(h * scale)
        crop = cv2.resize(crop, (new_w, new_h), interpolation=cv2.INTER_CUBIC)
    
    gray = cv2.cvtColor(crop, cv2.COLOR_BGR2GRAY)
    clahe = cv2.createCLAHE(clipLimit=2.0, tileGridSize=(8, 8))
    gray = clahe.apply(gray)
    gray = cv2.bilateralFilter(gray, 9, 75, 75)
    return gray

def run_ocr_pipeline(crop):
    """Runs OCR pipeline with preprocessing and retry logic."""
    gray = preprocess_plate_crop(crop)
    if gray is None:
        return "UNKNOWN"
        
    # Attempt 1: Standard preprocessed gray
    results = plate_reader.readtext(gray, detail=0)
    if results:
        raw_txt = "".join(results).upper().replace(" ", "").replace("-", "")
        print(f"🔎 [OCR RAW ATTEMPT 1] '{raw_txt}'", flush=True)
        normalized = normalize_indian_plate(raw_txt)
        if normalized and re.match(INDIAN_PLATE_PATTERN, normalized):
            print(f"🔤 [OCR PASS 1] Plate: {normalized}", flush=True)
            return normalized
            
    # Attempt 2: Adaptive thresholding
    thresh = cv2.adaptiveThreshold(gray, 255, cv2.ADAPTIVE_THRESH_GAUSSIAN_C, cv2.THRESH_BINARY, 11, 2)
    results = plate_reader.readtext(thresh, detail=0)
    if results:
        raw_txt = "".join(results).upper().replace(" ", "").replace("-", "")
        print(f"🔎 [OCR RAW ATTEMPT 2] '{raw_txt}'", flush=True)
        normalized = normalize_indian_plate(raw_txt)
        if normalized and re.match(INDIAN_PLATE_PATTERN, normalized):
            print(f"🔤 [OCR PASS 2] Plate: {normalized}", flush=True)
            return normalized
            
    # Attempt 3: Inverted thresholding
    inverted = cv2.bitwise_not(thresh)
    results = plate_reader.readtext(inverted, detail=0)
    if results:
        raw_txt = "".join(results).upper().replace(" ", "").replace("-", "")
        print(f"🔎 [OCR RAW ATTEMPT 3] '{raw_txt}'", flush=True)
        normalized = normalize_indian_plate(raw_txt)
        if normalized and re.match(INDIAN_PLATE_PATTERN, normalized):
            print(f"🔤 [OCR PASS 3] Plate: {normalized}", flush=True)
            return normalized
            
    return "UNKNOWN"

def execute_ocr_on_crop(evidence_path):
    """Background OCR on saved evidence. Returns plate or 'UNKNOWN'."""
    try:
        img = cv2.imread(evidence_path)
        if img is None: return "UNKNOWN"
        return run_ocr_pipeline(img)
    except Exception as e:
        print(f"⚠️ [OCR ERROR] {e}", flush=True)
    return "UNKNOWN"

def try_ocr_on_plates(plate_boxes, frame):
    """Try OCR on each detected plate box (already in global coords)."""
    for px1, py1, px2, py2 in plate_boxes:
        crop = frame[max(0, py1):py2, max(0, px1):px2]
        if crop.size == 0: continue
        res_plate = run_ocr_pipeline(crop)
        if res_plate != "UNKNOWN":
            return res_plate
    return "UNKNOWN"

# ─────────────────────────────────────────────────────────────
# 4. PARALLEL DUAL-MODEL INTELLIGENCE LOOP
# ─────────────────────────────────────────────────────────────
def process_frame(frame, camera_id):
    vehicle_count, is_emergency = 0, False
    
    # ═══════════════════════════════════════════════════════════
    # PASS 1: Model 1 — Full-Frame Tracking (yolov8n)
    # Detects: person(0), car(2), motorcycle(3), bus(5), truck(7)
    # Provides: tracking IDs, vehicle counting, emergency detection
    # ═══════════════════════════════════════════════════════════
    with ai_lock:
        m1_res = det_model.track(frame, persist=True, verbose=False, conf=0.25, imgsz=640)

    # Collect all Model 1 detections by class
    m1_motorcycles = []  # [{box, track_id}]
    m1_persons = []      # [box]
    m1_vehicles = []     # [{box, cls}]
    
    for b in m1_res[0].boxes:
        cls = int(b.cls[0])
        box = list(map(int, b.xyxy[0]))
        tid = int(b.id[0]) if b.id is not None else None
        
        if cls in [2, 3, 5, 7]:
            vehicle_count += 1
            m1_vehicles.append({"box": box, "cls": cls, "tid": tid})
            
            if cls in [5, 7] and is_ambulance_heuristic(frame[box[1]:box[3], box[0]:box[2]]):
                is_emergency = True
            
            # Green tracking box for all vehicles
            cv2.rectangle(frame, (box[0], box[1]), (box[2], box[3]), (0, 255, 0), 2)
        
        if cls == 0:  # Person
            m1_persons.append(box)
        
        if cls == 3 and tid is not None:  # Motorcycle with tracking
            m1_motorcycles.append({"box": box, "tid": tid})

    # ═══════════════════════════════════════════════════════════
    # PASS 2: TWO-STAGE CROP PIPELINE FOR ENFORCEMENT
    # Stage 1 (above) detected & tracked motorcycles + persons.
    # Stage 2 (below): For each motorcycle, build a union crop
    # enclosing the bike and all riders, upscale to 640, and run
    # custom_model (best.pt) on the crop. This matches best.pt's
    # training scale and eliminates full-frame resolution loss!
    # ═══════════════════════════════════════════════════════════
    frame_h, frame_w = frame.shape[:2]

    for bike in m1_motorcycles:
        bx1, by1, bx2, by2 = bike["box"]
        track_id = bike["tid"]
        bh = by2 - by1
        bw = bx2 - bx1

        # ── Step 2a: Overlap-based rider association ──
        assigned_riders = [p for p in m1_persons if is_person_riding_bike(p, bike["box"])]

        # ── Step 2b: Calculate Union Envelope (Bike + Riders) ──
        min_x, min_y, max_x, max_y = bx1, by1, bx2, by2
        if assigned_riders:
            for p in assigned_riders:
                min_x = min(min_x, p[0])
                min_y = min(min_y, p[1])
                max_x = max(max_x, p[2])
                max_y = max(max_y, p[3])
            pad_x = int((max_x - min_x) * 0.12)
            pad_y = int((max_y - min_y) * 0.12)
        else:
            # Generous upward expansion (85% of bike height) so rider head isn't sliced off
            min_y = max(0, by1 - int(bh * 0.85))
            pad_x = int(bw * 0.15)
            pad_y = int(bh * 0.10)

        crop_x1 = max(0, min_x - pad_x)
        crop_y1 = max(0, min_y - pad_y)
        crop_x2 = min(frame_w, max_x + pad_x)
        crop_y2 = min(frame_h, max_y + pad_y)

        # Draw enforcement envelope (Orange) on live UI feed
        cv2.rectangle(frame, (crop_x1, crop_y1), (crop_x2, crop_y2), (255, 140, 0), 2)
        cv2.putText(frame, f"ID:{track_id}", (crop_x1, max(15, crop_y1 - 5)), 0, 0.45, (255, 140, 0), 1)

        crop = frame[crop_y1:crop_y2, crop_x1:crop_x2]
        if crop.size == 0 or crop.shape[0] < 20 or crop.shape[1] < 20:
            continue

        # ── Step 2c: Run Custom Model on High-Res Crop ──
        crop_helmets = []
        crop_no_helmets = []
        crop_plates = []
        try:
            with ai_lock:
                crop_res = custom_model(crop, verbose=False, conf=0.25, imgsz=640)
            for b in crop_res[0].boxes:
                cls2 = int(b.cls[0])
                cx1, cy1, cx2, cy2 = map(int, b.xyxy[0])
                cconf = float(b.conf[0])
                # Convert to global frame coordinates
                gx1, gy1, gx2, gy2 = cx1 + crop_x1, cy1 + crop_y1, cx2 + crop_x1, cy2 + crop_y1
                gbox = [gx1, gy1, gx2, gy2]

                if cls2 == CUSTOM_CLS_WITH_HELMET:
                    crop_helmets.append({"box": gbox, "conf": cconf})
                    cv2.rectangle(frame, (gx1, gy1), (gx2, gy2), (0, 255, 0), 2)
                    cv2.putText(frame, f"Helmet {cconf:.2f}", (gx1, max(12, gy1 - 3)), 0, 0.45, (0, 255, 0), 1)
                elif cls2 == CUSTOM_CLS_WITHOUT_HELMET:
                    crop_no_helmets.append({"box": gbox, "conf": cconf})
                    cv2.rectangle(frame, (gx1, gy1), (gx2, gy2), (0, 0, 255), 2)
                    cv2.putText(frame, f"No-Helmet {cconf:.2f}", (gx1, max(12, gy1 - 3)), 0, 0.45, (0, 0, 255), 1)
                elif cls2 == CUSTOM_CLS_PLATE:
                    crop_plates.append({"box": gbox, "conf": cconf, "crop_box": [cx1, cy1, cx2, cy2]})
                    cv2.rectangle(frame, (gx1, gy1), (gx2, gy2), (255, 0, 255), 2)
                    cv2.putText(frame, f"Plate {cconf:.2f}", (gx1, max(12, gy1 - 3)), 0, 0.45, (255, 0, 255), 1)
        except Exception as e:
            print(f"⚠️ [CROP INFERENCE ERROR] {e}", flush=True)

        # ── Step 2d: Resolution Gating for License Plate OCR ──
        plate_txt = "UNKNOWN"
        # Resolution Gate: Only attempt plate OCR if motorcycle is close enough to be physically legible
        # Distance Gate: bh >= 75px prevents trying to read 12px blurred background dots
        is_close_enough_for_alpr = (bh >= 75)

        if is_close_enough_for_alpr:
            if crop_plates:
                plate_boxes_global = [p["box"] for p in crop_plates]
                plate_txt = try_ocr_on_plates(plate_boxes_global, frame)

            # Fallback plate crop from lower 35% of bike if plate not detected explicitly
            if plate_txt == "UNKNOWN":
                lower_bike = frame[max(0, by2 - int(bh * 0.38)):min(frame_h, by2 + 10), max(0, bx1 - 10):min(frame_w, bx2 + 10)]
                if lower_bike.size > 0 and lower_bike.shape[0] >= 20 and lower_bike.shape[1] >= 40:
                    plate_txt = run_ocr_pipeline(lower_bike)

        # ── Step 2e: ByteTrack Temporal State Tracking ──
        now_ts = time.time()
        if track_id not in _track_state:
            _track_state[track_id] = {
                "frames_seen": 0,
                "helmet_hits": 0,
                "no_helmet_hits": 0,
                "riders_history": [],
                "violations_issued": set(),
                "last_seen": now_ts
            }
        t_state = _track_state[track_id]
        t_state["frames_seen"] += 1
        t_state["last_seen"] = now_ts

        total_riders = max(len(assigned_riders), 1)
        t_state["riders_history"].append(total_riders)

        # Check positive helmet vs positive no-helmet in current frame
        has_positive_helmet = len(crop_helmets) > 0
        has_positive_no_helmet = len(crop_no_helmets) > 0

        # Disambiguate if both detected on same rider
        if has_positive_helmet and has_positive_no_helmet:
            max_h = max(h["conf"] for h in crop_helmets)
            max_nh = max(nh["conf"] for nh in crop_no_helmets)
            if max_h >= max_nh:
                has_positive_no_helmet = False
            else:
                has_positive_helmet = False

        if has_positive_helmet:
            t_state["helmet_hits"] += 1
        elif has_positive_no_helmet:
            t_state["no_helmet_hits"] += 1

        fired_for_track = t_state["violations_issued"]

        # ── Step 2f: VIOLATION 1 — TRIPLE RIDING (Multi-Frame Confirmed) ──
        # Require >= 3 riders observed consistently (at least 8 frames, and >= 60% of track history)
        recent_riders = t_state["riders_history"][-20:]
        triple_count = sum(1 for r in recent_riders if r >= 3)
        is_confirmed_triple = (
            t_state["frames_seen"] >= 12 and
            triple_count >= 8 and
            (triple_count / float(len(recent_riders))) >= 0.60
        )
        if is_confirmed_triple and "Triple Riding" not in fired_for_track:
            evidence = frame[crop_y1:crop_y2, crop_x1:crop_x2]
            cv2.putText(frame, f"VIOLATION: TRIPLE RIDING ({total_riders})", (crop_x1, max(30, crop_y1 - 15)), 
                        0, 0.7, (0, 0, 255), 2)
            _fire_violation("Triple Riding", plate_txt, camera_id, 0.95, evidence, track_id)
            t_state["violations_issued"].add("Triple Riding")

        # ── Step 2g: VIOLATION 2 — NO HELMET (Positive Class Confirmation) ──
        # Benefit of doubt: Any helmet hit along vehicle trajectory clears the rider!
        # Positive violation requires >= 3 confirmed 'Without Helmet' detections and 0 helmet hits
        is_confirmed_no_helmet = (
            t_state["frames_seen"] >= 6 and 
            t_state["helmet_hits"] == 0 and 
            t_state["no_helmet_hits"] >= 3
        )

        if t_state["helmet_hits"] > 0:
            # Visual feedback: Rider is wearing helmet!
            cv2.putText(frame, f"HELMET OK ({t_state['helmet_hits']})", (bx1, max(20, by1 - 8)), 0, 0.5, (0, 255, 0), 2)
        elif is_confirmed_no_helmet and "No Helmet" not in fired_for_track:
            evidence = frame[crop_y1:crop_y2, crop_x1:crop_x2]
            cv2.putText(frame, "VIOLATION: NO HELMET", (bx1, max(20, by1 - 8)), 0, 0.55, (0, 0, 255), 2)
            _fire_violation("No Helmet", plate_txt, camera_id, 0.88, evidence, track_id)
            t_state["violations_issued"].add("No Helmet")
        else:
            cv2.putText(frame, f"Checking... ({t_state['frames_seen']}f)", (bx1, max(20, by1 - 8)), 0, 0.4, (200, 200, 200), 1)

    # ─── Periodic Cleanup ───
    now = time.time()
    if len(_violation_cooldown) > _MAX_COOLDOWN_ENTRIES:
        expired = [k for k, v in _violation_cooldown.items() if now - v > _COOLDOWN_SECONDS * 3]
        for k in expired:
            del _violation_cooldown[k]

    # Clean up track states older than 8 seconds
    if len(_track_state) > _MAX_TRACKED_ENTRIES or len(_track_state) > 100:
        stale_tracks = [tid for tid, s in _track_state.items() if now - s.get("last_seen", 0) > 8.0]
        for tid in stale_tracks:
            del _track_state[tid]
    
    # Background telemetry (throttled to every 1 second for hyper-fast response)
    _throttle_key = f"telem_{camera_id}"
    if _throttle_key not in _violation_cooldown or now - _violation_cooldown[_throttle_key] > 1:
        _violation_cooldown[_throttle_key] = now
        _bg_pool.submit(_sync_telemetry_bg, camera_id, vehicle_count, is_emergency)

# ─────────────────────────────────────────────────────────────
# 5. FIRE-AND-FORGET VIOLATION POSTING
# ─────────────────────────────────────────────────────────────

def _fire_violation(v_type, plate_txt, camera_id, conf, crop, track_id, source=None):
    """Cooldown check (fast, in GPU thread), then dispatch to background."""
    cache_key = f"{camera_id}_{v_type}_{track_id}"
    now = time.time()
    if cache_key in _violation_cooldown and now - _violation_cooldown[cache_key] < _COOLDOWN_SECONDS:
        return
    _violation_cooldown[cache_key] = now

    if crop is None or crop.size == 0: 
        return

    # Save evidence immediately (local I/O only — fast)
    img_name = f"ev_{uuid.uuid4().hex[:8]}.jpg"
    img_path = os.path.join(EVIDENCE_PATH, img_name)
    cv2.imwrite(img_path, crop)

    # Dispatch all DB work to background
    _bg_pool.submit(_post_violation_bg, v_type, plate_txt, camera_id, conf, img_name, img_path)

FINE_AMOUNTS = {
    "No Helmet": 500,
    "Triple Riding": 1000,
    "Wrong Side": 1500,
    "Speeding": 2000,
    "Signal Jump": 1000
}

def _post_violation_bg(v_type, plate_number, cam_id, conf, img_name, img_path):
    """Background thread: Posts violation + challan to Supabase, then runs OCR."""
    try:
        db = _get_bg_supabase()
        clean_plate = re.sub(r'[^A-Z0-9]', '', plate_number.upper())
        
        # Dedup check (same plate+violation within 60s)
        if clean_plate not in ["UNKNOWN", "PENDING", ""]:
            time_threshold = (datetime.utcnow() - timedelta(seconds=60)).isoformat()
            recent = db.table("violations")\
                .select("id")\
                .eq("camera_id", str(cam_id))\
                .eq("violation_type", v_type)\
                .eq("plate_number", clean_plate)\
                .gt("detected_at", time_threshold)\
                .execute()
            if recent.data:
                print(f"⚠️ [DEDUP] Duplicate violation ignored for {clean_plate} ({v_type}) within 60s", flush=True)
                try:
                    if os.path.exists(img_path):
                        os.remove(img_path)
                except Exception:
                    pass
                return
                
        v_id = str(uuid.uuid4())
        payload = {
            "id": v_id,
            "camera_id": str(cam_id), 
            "violation_type": v_type,
            "evidence_image_url": f"http://localhost:8000/static/evidence/{img_name}",
            "confidence_score": float(conf), 
            "plate_number": clean_plate if clean_plate not in ["UNKNOWN", "PENDING"] else "UNKNOWN",
            "source": "live_camera",
            "status": "pending",
            "detected_at": datetime.utcnow().isoformat()
        }
        
        db.table("violations").insert(payload).execute()
        print(f"✅ [LIVE VIOLATION LOGGED] {v_type} | Plate: {payload['plate_number']} | Queued for officer review", flush=True)

        # Background OCR: update UNKNOWN → actual plate
        if payload["plate_number"] == "UNKNOWN":
            ocr_plate = execute_ocr_on_crop(img_path)
            if ocr_plate != "UNKNOWN":
                # Check for duplicate after OCR
                time_threshold = (datetime.utcnow() - timedelta(seconds=60)).isoformat()
                recent = db.table("violations")\
                    .select("id")\
                    .eq("camera_id", str(cam_id))\
                    .eq("violation_type", v_type)\
                    .eq("plate_number", ocr_plate)\
                    .gt("detected_at", time_threshold)\
                    .execute()
                if recent.data:
                    print(f"⚠️ [DEDUP-OCR] Duplicate violation detected after OCR for {ocr_plate} ({v_type}). Deleting current.", flush=True)
                    db.table("violations").delete().eq("id", v_id).execute()
                    db.table("e_challans").delete().eq("violation_id", v_id).execute()
                    try:
                        if os.path.exists(img_path):
                            os.remove(img_path)
                    except Exception:
                        pass
                    return
                
                # Re-lookup owner
                v_res = db.table("vehicles").select("owner_id, owner_name").eq("plate_number", ocr_plate).execute()
                owner_id = v_res.data[0].get('owner_id') if v_res.data else None
                owner_name = v_res.data[0].get('owner_name', "Unregistered Vehicle") if v_res.data else "Unregistered Vehicle"
                
                db.table("violations").update({"plate_number": ocr_plate}).eq("id", v_id).execute()
                db.table("e_challans").update({
                    "vehicle_number": ocr_plate,
                    "owner_id": owner_id,
                    "owner_name": owner_name
                }).eq("violation_id", v_id).execute()
                print(f"🔤 [OCR UPDATE & LINK] {v_id[:8]} → {ocr_plate} | Owner: {owner_name}", flush=True)

    except Exception as e:
        print(f"❌ [DB SYNC ERROR] {e}", flush=True)

def _sync_telemetry_bg(cam_id, count, emergency):
    """
    Background thread: 
    1. Feeds live YOLO counts into the PPO RL agent.
    2. Updates congested_roads vehicle count + density for the UI.
    """
    try:
        cam_id_str = str(cam_id)


        # Update vehicle count and density in congested_roads (signal state is written by RL push)
        db = _get_bg_supabase()
        density = min(100, int((count / 20) * 100))
        db.table("congested_roads").update({
            "vehicle_count":    count,
            "congestion_level": density,
            "is_emergency":     emergency,
            "last_updated":     datetime.utcnow().isoformat()
        }).eq("camera_id", cam_id_str).execute()

    except Exception as e:
        print(f"⚠️ [TELEMETRY ERROR] cam={str(cam_id)[:8]}: {e}", flush=True)

# ─────────────────────────────────────────────────────────────
# 6. RESEARCH-BASED ANALYTICS (MANIT BHOPAL WSI LOGIC)
# ─────────────────────────────────────────────────────────────

def calculate_wsi_score(accident_records):
    """
    Calculates Weighted Severity Index (WSI) for a cluster of accidents.
    WSI = (Na * 6) + (Nb * 4) 
    """
    if not accident_records:
        return 0
        
    na = len(accident_records) # Number of accidents
    nb = sum(acc.get('fatalities', 0) for acc in accident_records) # Number of deaths
    
    wsi = (na * 6) + (nb * 4) # Applied WSI Formula
    return wsi

def get_danger_level(wsi_score):
    """Classifies danger level based on Bhopal research trends."""
    if wsi_score >= 80: return "CRITICAL (Rank 1/2 Zone)" # e.g. Govindpura
    if wsi_score >= 60: return "HIGH RISK (Blackspot)"
    if wsi_score >= 40: return "MODERATE"
    return "STABLE"

# 🔥 UPDATED SYNC TELEMETRY TO INCLUDE DANGER LEVEL
def sync_telemetry(cam_id, count, emergency):
    try:
        db = create_supabase_client() # Ensure DB client is active
        density = min(100, int((count / 20) * 100))
        
        # 1. Fetch historical accidents for this camera location to calculate WSI
        # (Assuming your cameras are linked to specific lat/long regions)
        acc_res = db.table("accidents").select("fatalities").eq("camera_id", cam_id).execute()
        wsi_val = calculate_wsi_score(acc_res.data)
        danger_text = get_danger_level(wsi_val)

        # 2. Update the congested_roads table with the new research metrics
        db.table("congested_roads").update({
            "vehicle_count": count, 
            "congestion_level": density,
            "is_emergency": emergency, 
            "danger_level": danger_text, # New column for your heatmap logic
            "wsi_score": wsi_val,        # New column for severity ranking
            "last_updated": datetime.utcnow().isoformat()
        }).eq("camera_id", str(cam_id)).execute()
        
    except Exception as e:
        print(f"⚠️ [TELEMETRY ERROR] {e}")
