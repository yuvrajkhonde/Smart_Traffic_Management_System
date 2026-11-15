"""
════════════════════════════════════════════════════════════════════════════════
  V.I.T.A.L.S. Phase 3: Production Enforcement & ANPR Engine
  Bhopal Smart Traffic Management System (Module_2_Backend)

  Key Responsibilities:
  1. Indian RTO License Plate Zonal Parser & State-Code Validator
  2. Fixed-Canvas Normalized Laplacian Sharpness Scorer
  3. Decoupled Evidence Ring-Buffer (Best Rider Frame + Best Plate Crop)
  4. 3-Panel Legal Composite Challan Image Builder with SHA-256 Integrity
  5. Multi-Frame EasyOCR Consensus Voting (Two-Line Apron Aware)
  6. Robust Vehicle Track State Machine (Evaluable-Frames Denominator)
════════════════════════════════════════════════════════════════════════════════
"""

import os
import re
import cv2
import time
import uuid
import hashlib
import numpy as np
from datetime import datetime

# 🏛️ Real Indian State & Union Territory Codes (plus BH series)
INDIAN_STATE_CODES = {
    "AN", "AP", "AR", "AS", "BR", "CG", "CH", "DD", "DL", "DN",
    "GA", "GJ", "HP", "HR", "JH", "JK", "KA", "KL", "LA", "LD",
    "MH", "ML", "MN", "MP", "MZ", "NL", "OD", "PB", "PY", "RJ",
    "SK", "TN", "TR", "TS", "UK", "UP", "WB", "BH"
}

# 🏛️ Validated Indian Registration Regex Patterns
# Standard: 2 letters (state) + 1-2 digits (RTO) + 1-3 letters (series) + 4 digits (number)
STANDARD_PLATE_REGEX = re.compile(r"^[A-Z]{2}\d{1,2}[A-Z]{1,3}\d{4}$")
# Bharat Series: 2 digits (year) + BH + 4 digits + 2 letters
BHARAT_SERIES_REGEX = re.compile(r"^\d{2}BH\d{4}[A-Z]{2}$")

# 🔤 Deterministic Character Disambiguation Maps
# Letters that OCR commonly mistakes for digits in digit zones
DIGIT_ZONE_CORRECTIONS = {
    'B': '8', 'O': '0', 'D': '0', 'Q': '0',
    'I': '1', 'L': '1', '|': '1',
    'Z': '2', 'S': '5', 'G': '6'
}

# Digits that OCR commonly mistakes for letters in letter zones
LETTER_ZONE_CORRECTIONS = {
    '8': 'B', '0': 'O', '1': 'I',
    '2': 'Z', '5': 'S', '6': 'G'
}

def correct_char_for_digit(c: str) -> str:
    """Coerces a character into a digit if in digit confusion set."""
    return DIGIT_ZONE_CORRECTIONS.get(c, c)

def correct_char_for_letter(c: str) -> str:
    """Coerces a character into a letter if in letter confusion set."""
    return LETTER_ZONE_CORRECTIONS.get(c, c)


# ─────────────────────────────────────────────────────────────────────────────
# 1. ZONAL INDIAN NUMBER PLATE PARSER & NORMALIZER
# ─────────────────────────────────────────────────────────────────────────────
def normalize_and_validate_plate(raw_text: str) -> tuple[str | None, str]:
    """
    Parses a raw OCR string using end-anchored zonal reasoning:
      Zone 1: First 2 chars -> State code (Letters)
      Zone 4: Last 4 chars  -> Vehicle registration number (Digits)
      Zone 2: Next 1-2 chars -> RTO code (Digits)
      Zone 3: Remainder     -> Series code (1-3 Letters)

    Returns:
      (normalized_plate, status_label)
      where status_label is one of: 'VALID_STANDARD', 'VALID_BH', 'INVALID'
    """
    cleaned = re.sub(r'[^A-Z0-9]', '', raw_text.upper())
    if len(cleaned) < 7:
        return None, "TOO_SHORT"

    # 1. Check Bharat (BH) Series: e.g. 22BH1234AA (length 10)
    if len(cleaned) == 10 and cleaned[2:4] in ("BH", "8H"):
        y1 = correct_char_for_digit(cleaned[0])
        y2 = correct_char_for_digit(cleaned[1])
        b_char = "B"
        h_char = "H"
        num_part = "".join(correct_char_for_digit(c) for c in cleaned[4:8])
        ser_part = "".join(correct_char_for_letter(c) for c in cleaned[8:10])
        candidate_bh = f"{y1}{y2}{b_char}{h_char}{num_part}{ser_part}"
        if BHARAT_SERIES_REGEX.match(candidate_bh):
            return candidate_bh, "VALID_BH"

    # 2. End-Anchored Standard Indian Parsing (Lengths 8 to 11)
    # Target length: 2 (state) + [1 or 2] (rto) + [1, 2, or 3] (series) + 4 (num)
    # Total characters: 8, 9, 10, or 11
    for window_len in [10, 9, 8, 11]:
        if len(cleaned) < window_len:
            continue
        for start_idx in range(len(cleaned) - window_len + 1):
            cand = cleaned[start_idx:start_idx + window_len]

            # Zone 1: First 2 characters (State Code)
            st0 = correct_char_for_letter(cand[0])
            st1 = correct_char_for_letter(cand[1])
            state_cand = f"{st0}{st1}"
            if state_cand not in INDIAN_STATE_CODES:
                continue

            # Zone 4: Last 4 characters (Digits)
            last4_raw = cand[-4:]
            last4_corrected = "".join(correct_char_for_digit(c) for c in last4_raw)
            if not last4_corrected.isdigit() or len(last4_corrected) != 4:
                continue

            # Middle segment to divide between Zone 2 (RTO digits) and Zone 3 (Series letters)
            middle = cand[2:-4]
            # middle length = window_len - 6 (can be 2, 3, 4, 5)
            for rto_len in [2, 1]:  # Try 2 digits first, then 1 (e.g. DL1)
                if len(middle) <= rto_len:
                    continue
                rto_raw = middle[:rto_len]
                series_raw = middle[rto_len:]

                if not (1 <= len(series_raw) <= 3):
                    continue

                rto_corrected = "".join(correct_char_for_digit(c) for c in rto_raw)
                series_corrected = "".join(correct_char_for_letter(c) for c in series_raw)

                if rto_corrected.isdigit() and series_corrected.isalpha():
                    plate_final = f"{state_cand}{rto_corrected}{series_corrected}{last4_corrected}"
                    if STANDARD_PLATE_REGEX.match(plate_final):
                        return plate_final, "VALID_STANDARD"

    return None, "INVALID"


# ─────────────────────────────────────────────────────────────────────────────
# 2. NORMALIZED SHARPNESS & PREPROCESSING
# ─────────────────────────────────────────────────────────────────────────────
def compute_normalized_sharpness(crop: np.ndarray) -> float:
    """
    Computes Laplacian variance on a plate crop resized to a fixed (128x64) canvas.
    This strictly normalizes for crop dimensions so larger crops do not artificially
    dominate the score.
    """
    if crop is None or crop.size == 0 or crop.shape[0] < 8 or crop.shape[1] < 12:
        return 0.0

    try:
        fixed = cv2.resize(crop, (128, 64), interpolation=cv2.INTER_AREA)
        gray = cv2.cvtColor(fixed, cv2.COLOR_BGR2GRAY)
        lap = cv2.Laplacian(gray, cv2.CV_64F)
        return float(lap.var())
    except Exception:
        return 0.0


def preprocess_plate_for_ocr(crop: np.ndarray) -> np.ndarray:
    """
    Enhances plate crop:
    - 3x bicubic upscaling for thin stroke expansion
    - Grayscale + CLAHE contrast enhancement
    - Bilateral edge-preserving noise filter
    """
    if crop is None or crop.size == 0:
        return None

    h, w = crop.shape[:2]
    target_w = max(240, int(w * 3))
    scale = target_w / float(w)
    target_h = int(h * scale)

    upscaled = cv2.resize(crop, (target_w, target_h), interpolation=cv2.INTER_CUBIC)
    gray = cv2.cvtColor(upscaled, cv2.COLOR_BGR2GRAY)

    clahe = cv2.createCLAHE(clipLimit=2.5, tileGridSize=(8, 8))
    enhanced = clahe.apply(gray)
    filtered = cv2.bilateralFilter(enhanced, 7, 50, 50)
    return filtered


# ─────────────────────────────────────────────────────────────────────────────
# 3. MULTI-FRAME CONSENSUS EASYOCR FOR 2-LINE INDIAN PLATES
# ─────────────────────────────────────────────────────────────────────────────
class IndianPlateOCREngine:
    """
    Singleton OCR Engine running EasyOCR on top-sharpness crops only.
    Handles 2-line curved apron plates (aspect ratio < 2.0) and applies
    multi-frame consensus voting.
    """
    _instance = None

    def __new__(cls, *args, **kwargs):
        if cls._instance is None:
            cls._instance = super().__new__(cls)
            cls._instance._initialized = False
        return cls._instance

    def __init__(self, reader=None):
        if self._initialized:
            return
        if reader is not None:
            self.reader = reader
        else:
            import easyocr
            import torch
            use_gpu = torch.cuda.is_available()
            self.reader = easyocr.Reader(['en'], gpu=use_gpu)
        self._initialized = True

    def ocr_single_crop(self, crop: np.ndarray) -> tuple[str, float]:
        """Runs OCR on a single plate crop, clustering into lines for 2-line scooter plates."""
        if crop is None or crop.size == 0 or crop.shape[0] < 12 or crop.shape[1] < 20:
            return "", 0.0

        # Try on raw crop first (preserves clean character boundaries)
        # If no results, try preprocessed crop
        candidates_to_try = [crop]
        prep = preprocess_plate_for_ocr(crop)
        if prep is not None:
            candidates_to_try.append(prep)

        best_text = ""
        best_conf = 0.0

        for img_in in candidates_to_try:
            try:
                results = self.reader.readtext(
                    img_in,
                    allowlist='ABCDEFGHIJKLMNOPQRSTUVWXYZ0123456789',
                    detail=1,
                    paragraph=False
                )
            except Exception:
                continue

            if not results:
                continue

            # Group bounding boxes into horizontal lines (scooter 2-line format)
            items = []
            for b in results:
                pts = b[0]
                ys = [pt[1] for pt in pts]
                xs = [pt[0] for pt in pts]
                y_cen = float(np.mean(ys))
                x_cen = float(np.mean(xs))
                h = max(1.0, float(max(ys) - min(ys)))
                clean_txt = re.sub(r'[^A-Z0-9]', '', b[1].upper())
                if clean_txt:
                    items.append({
                        "text": clean_txt,
                        "conf": float(b[2]),
                        "y_cen": y_cen,
                        "x_cen": x_cen,
                        "h": h
                    })

            if not items:
                continue

            # Cluster items into lines by vertical proximity
            items.sort(key=lambda it: it["y_cen"])
            lines = []
            for it in items:
                assigned = False
                for line in lines:
                    line_y_cen = np.mean([x["y_cen"] for x in line])
                    line_h = np.mean([x["h"] for x in line])
                    # If vertical distance is less than 50% line height, same line
                    if abs(it["y_cen"] - line_y_cen) < (line_h * 0.50):
                        line.append(it)
                        assigned = True
                        break
                if not assigned:
                    lines.append([it])

            # Sort each line from left to right (by x_cen)
            combined_pieces = []
            line_confs = []
            for line in lines:
                line.sort(key=lambda it: it["x_cen"])
                for it in line:
                    combined_pieces.append(it["text"])
                    line_confs.append(it["conf"])

            combined_str = "".join(combined_pieces)
            avg_c = float(np.mean(line_confs)) if line_confs else 0.0

            # If this produces a valid plate, prioritize immediately
            norm, stat = normalize_and_validate_plate(combined_str)
            if norm and stat.startswith("VALID"):
                return combined_str, avg_c

            if avg_c > best_conf:
                best_conf = avg_c
                best_text = combined_str

        return best_text, best_conf

    def vote_on_crop_candidates(self, candidate_crops: list[np.ndarray]) -> tuple[str, float, bool]:
        """
        Runs OCR on top candidate crops (3 to 5 crops) and performs consensus voting.
        Returns:
          (final_plate, final_conf, is_auto_verified)
          where is_auto_verified is True if the identical valid string wins in >= 3 frames.
        """
        if not candidate_crops:
            return "UNREADABLE", 0.0, False

        votes: dict[str, dict] = {}

        for crop in candidate_crops:
            raw_text, ocr_conf = self.ocr_single_crop(crop)
            if not raw_text:
                continue

            normalized_plate, status = normalize_and_validate_plate(raw_text)
            if normalized_plate and status.startswith("VALID"):
                if normalized_plate not in votes:
                    votes[normalized_plate] = {"count": 0, "conf_sum": 0.0}
                votes[normalized_plate]["count"] += 1
                votes[normalized_plate]["conf_sum"] += ocr_conf

        if not votes:
            return "UNREADABLE", 0.0, False

        # Pick candidate with most occurrences (tie-break with average confidence)
        best_plate = max(votes.keys(), key=lambda p: (votes[p]["count"], votes[p]["conf_sum"]))
        match_count = votes[best_plate]["count"]
        avg_conf = votes[best_plate]["conf_sum"] / max(1, match_count)

        # User Requirement: Auto-verified ONLY if same valid string wins in at least 3 frames
        is_auto_verified = match_count >= 3
        return best_plate, avg_conf, is_auto_verified


# ─────────────────────────────────────────────────────────────────────────────
# 4. 3-PANEL COMPOSITE CHALLAN EVIDENCE BUILDER
# ─────────────────────────────────────────────────────────────────────────────
def build_3panel_composite_evidence(
    full_frame: np.ndarray,
    best_violation_crop: np.ndarray,
    best_plate_crop: np.ndarray,
    metadata: dict
) -> tuple[np.ndarray, str]:
    """
    Assembles a legally conclusive 3-panel composite evidence image:
      Left Panel (60% width) : Full CCTV Overview Scene with official watermark
      Top Right  (40% width) : Best Rider Violation Crop (annotated)
      Bottom Right(40% width): Best Raw License Plate Crop with OCR overlay

    Returns:
      (composite_image, sha256_hash_hex)
    """
    target_canvas_w = 1600
    target_canvas_h = 900
    canvas = np.zeros((target_canvas_h, target_canvas_w, 3), dtype=np.uint8)

    left_w = int(target_canvas_w * 0.62)
    right_w = target_canvas_w - left_w
    top_right_h = int(target_canvas_h * 0.58)
    bottom_right_h = target_canvas_h - top_right_h

    # 1. Left Panel: Full Frame Scaled
    resized_scene = cv2.resize(full_frame, (left_w, target_canvas_h), interpolation=cv2.INTER_AREA)
    # Add top banner to left panel
    banner_h = 56
    cv2.rectangle(resized_scene, (0, 0), (left_w, banner_h), (20, 20, 20), -1)
    cam_title = f"BHOPAL TRAFFIC POLICE | CAM: {metadata.get('camera_id', 'CCTV-01')} | {metadata.get('timestamp', '')}"
    cv2.putText(resized_scene, cam_title, (16, 36), cv2.FONT_HERSHEY_SIMPLEX, 0.72, (255, 255, 255), 2, cv2.LINE_AA)
    canvas[:, :left_w] = resized_scene

    # 2. Top Right Panel: Best Rider Violation Zoom
    if best_violation_crop is not None and best_violation_crop.size > 0:
        scaled_rider = cv2.resize(best_violation_crop, (right_w, top_right_h), interpolation=cv2.INTER_AREA)
    else:
        scaled_rider = np.zeros((top_right_h, right_w, 3), dtype=np.uint8)
        cv2.putText(scaled_rider, "No Rider Crop", (40, 100), cv2.FONT_HERSHEY_SIMPLEX, 0.8, (150, 150, 150), 2)

    # Rider label header
    cv2.rectangle(scaled_rider, (0, 0), (right_w, 42), (0, 0, 180), -1)
    v_type = metadata.get('violation_type', 'VIOLATION')
    hit_ratio = metadata.get('hit_ratio', 1.0)
    cv2.putText(scaled_rider, f"EVIDENCE 1: {v_type.upper()} ({hit_ratio*100:.0f}% confidence)", (12, 28),
                cv2.FONT_HERSHEY_SIMPLEX, 0.62, (255, 255, 255), 2, cv2.LINE_AA)
    canvas[:top_right_h, left_w:] = scaled_rider

    # 3. Bottom Right Panel: Best Plate Crop
    if best_plate_crop is not None and best_plate_crop.size > 0:
        scaled_plate = cv2.resize(best_plate_crop, (right_w, bottom_right_h), interpolation=cv2.INTER_AREA)
    else:
        scaled_plate = np.zeros((bottom_right_h, right_w, 3), dtype=np.uint8)
        cv2.putText(scaled_plate, "Plate Unreadable", (40, 100), cv2.FONT_HERSHEY_SIMPLEX, 0.8, (150, 150, 150), 2)

    # Plate label header
    cv2.rectangle(scaled_plate, (0, 0), (right_w, 42), (180, 0, 180), -1)
    plate_str = metadata.get('plate_text', 'UNREADABLE')
    cv2.putText(scaled_plate, f"EVIDENCE 2: PLATE [{plate_str}]", (12, 28),
                cv2.FONT_HERSHEY_SIMPLEX, 0.65, (255, 255, 255), 2, cv2.LINE_AA)
    canvas[top_right_h:, left_w:] = scaled_plate

    # Divider lines
    cv2.line(canvas, (left_w, 0), (left_w, target_canvas_h), (80, 80, 80), 3)
    cv2.line(canvas, (left_w, top_right_h), (target_canvas_w, top_right_h), (80, 80, 80), 3)

    # Compute SHA-256 for integrity verification
    _, encoded_jpg = cv2.imencode(".jpg", canvas, [cv2.IMWRITE_JPEG_QUALITY, 95])
    sha256_hash = hashlib.sha256(encoded_jpg.tobytes()).hexdigest()

    return canvas, sha256_hash


# ─────────────────────────────────────────────────────────────────────────────
# 5. VEHICLE TRACK STATE MACHINE (DEFERRED FINALIZATION)
# ─────────────────────────────────────────────────────────────────────────────
class VehicleTrackState:
    """
    State machine for an individual tracked two-wheeler.
    Decouples Violation Confirmation from Violation Finalization.
    """
    def __init__(self, track_id: int, fps: float = 30.0):
        self.track_id = track_id
        self.fps = max(1.0, fps)
        self.state = "UNKNOWN"  # UNKNOWN -> SUSPECTED -> CONFIRMED -> LOGGED

        self.frames_seen = 0
        self.evaluable_frames = 0      # Only frames where bike_height >= 60px
        self.no_helmet_hits = 0
        self.triple_riding_hits = 0
        self.consecutive_lost = 0

        self.conf_history: list[float] = []
        self.confirmed_violation_type: str | None = None

        # Decoupled Evidence Ring Buffers
        self.best_violation_score: float = -1.0
        self.best_violation_frame: np.ndarray | None = None
        self.best_violation_crop: np.ndarray | None = None

        # Plate candidate crops sorted by normalized Laplacian sharpness
        self.plate_candidates: list[tuple[float, np.ndarray]] = []  # [(sharpness, crop)]

    def update_frame(
        self,
        bike_box: list[int],
        has_no_helmet: bool,
        nh_conf: float,
        has_triple_riding: bool,
        envelope_crop: np.ndarray,
        full_frame: np.ndarray,
        detected_plate_crops: list[tuple[float, np.ndarray]]
    ):
        """
        Updates the vehicle track trajectory with fresh frame detections.
        """
        self.frames_seen += 1
        self.consecutive_lost = 0

        bx1, by1, bx2, by2 = bike_box
        bike_h = by2 - by1

        # ── 1. Evaluable Frame Filtering ──
        # Far-away bikes (h < 60px) are ignored to avoid diluting the ratio
        if bike_h >= 60:
            self.evaluable_frames += 1

            if has_no_helmet:
                self.no_helmet_hits += 1
                self.conf_history.append(nh_conf)

                # Track best violation rider zoom
                v_score = nh_conf * float(bike_h)
                if v_score > self.best_violation_score:
                    self.best_violation_score = v_score
                    self.best_violation_frame = full_frame.copy()
                    self.best_violation_crop = envelope_crop.copy()

            if has_triple_riding:
                self.triple_riding_hits += 1
                if self.best_violation_crop is None:
                    self.best_violation_frame = full_frame.copy()
                    self.best_violation_crop = envelope_crop.copy()

        # ── 2. Plate Candidate Caching (Gated by width >= 60px) ──
        for pconf, pcrop in detected_plate_crops:
            if pcrop is not None and pcrop.shape[1] >= 60 and pconf >= 0.35:
                sharpness = compute_normalized_sharpness(pcrop)
                self.plate_candidates.append((sharpness, pcrop.copy()))

        # Keep only top 5 sharpest plates in buffer
        if len(self.plate_candidates) > 5:
            self.plate_candidates.sort(key=lambda x: x[0], reverse=True)
            self.plate_candidates = self.plate_candidates[:5]

        # ── 3. Life-Cycle State Machine Transition ──
        min_eval_frames = max(7, int(self.fps * 0.50))  # At least 0.50s of evaluable visibility

        if self.evaluable_frames >= 3 and self.state == "UNKNOWN":
            if self.no_helmet_hits >= 2 or self.triple_riding_hits >= 2:
                self.state = "SUSPECTED"

        if self.state == "SUSPECTED" and self.evaluable_frames >= min_eval_frames:
            nh_ratio = float(self.no_helmet_hits) / float(self.evaluable_frames)
            tr_ratio = float(self.triple_riding_hits) / float(self.evaluable_frames)
            mean_conf = float(np.mean(self.conf_history)) if self.conf_history else 0.0

            if nh_ratio >= 0.60 and mean_conf >= 0.50:
                self.state = "CONFIRMED"
                self.confirmed_violation_type = "No Helmet"
            elif tr_ratio >= 0.50:
                self.state = "CONFIRMED"
                self.confirmed_violation_type = "Triple Riding"

    def mark_lost_frame(self) -> bool:
        """Increments lost frames. Returns True if track has terminated."""
        self.consecutive_lost += 1
        return self.consecutive_lost >= 25  # Lost for ~1 second of video

    def can_finalize(self, video_ending: bool = False) -> bool:
        """Returns True if this track is CONFIRMED and ready to be finalized."""
        if self.state != "CONFIRMED":
            return False
        if video_ending:
            return True
        # Finalize when track terminates (lost for >= 15 frames)
        if self.consecutive_lost >= 15:
            return True
        return False
