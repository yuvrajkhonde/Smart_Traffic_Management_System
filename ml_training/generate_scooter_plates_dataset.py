import os
import glob
import cv2
import numpy as np
import random
import math
import shutil
from ultralytics import YOLO

CURRENT_DIR = os.path.dirname(os.path.abspath(__file__))
ROOT_DIR = os.path.join(CURRENT_DIR, "..")
VIDEO_PATH = os.path.join(ROOT_DIR, "backend", "test_videos", "new.mp4")
M1_PATH = os.path.join(ROOT_DIR, "ai_models", "yolov8n.pt")
M2_PATH = os.path.join(ROOT_DIR, "ai_models", "best.pt")

OUTPUT_DIR = os.path.join(ROOT_DIR, "DATASET", "scooter_front_plates_subset")
IMG_DIR = os.path.join(OUTPUT_DIR, "images")
LBL_DIR = os.path.join(OUTPUT_DIR, "labels")
VIS_DIR = os.path.join(OUTPUT_DIR, "visualizations")
ARTIFACT_DIR = r"C:\Users\OMEN\.gemini\antigravity-ide\brain\28075c5f-1de2-49dc-aae8-1ba05f868828\images"

for d in [IMG_DIR, LBL_DIR, VIS_DIR, ARTIFACT_DIR]:
    os.makedirs(d, exist_ok=True)

print("🚀 Starting Indian Front Scooter Plate Dataset Generation...")

# Authentic Indian State & City RTO Codes
RTO_CODES = [
    "MP 04", "MP 09", "MP 07", "MP 20", "MP 43",  # Madhya Pradesh (Bhopal, Indore, Gwalior, Jabalpur, Ratlam)
    "MH 04", "MH 12", "MH 02", "MH 03", "MH 14",  # Maharashtra (Thane, Pune, Mumbai, Pimpri)
    "DL 1C", "DL 3S", "DL 8S", "DL 5S",           # Delhi
    "KA 01", "KA 03", "KA 05", "KA 51",           # Karnataka (Bangalore)
    "UP 32", "UP 16", "UP 14", "UP 78",           # Uttar Pradesh (Lucknow, Noida, Ghaziabad, Kanpur)
    "RJ 14", "RJ 02", "RJ 27",                    # Rajasthan (Jaipur, Alwar, Udaipur)
    "GJ 01", "GJ 05", "GJ 27"                     # Gujarat (Ahmedabad, Surat)
]

ALPHA_SERIES = ["AB", "BC", "CD", "EZ", "BK", "CZ", "MN", "XY", "CH", "ER", "GH", "PQ"]

def generate_random_plate_text():
    line1 = random.choice(RTO_CODES)
    line2 = f"{random.choice(ALPHA_SERIES)} {random.randint(1000, 9999)}"
    return line1, line2

def draw_curved_plate_patch(w, h, line1, line2):
    """Creates a photorealistic 2-line Indian scooter apron plate patch."""
    patch = np.ones((h, w, 3), dtype=np.uint8) * 242  # off-white plate color
    
    # Octagonal/chamfered apron shape with rounded corners
    chamfer = int(min(w, h) * 0.16)
    pts = np.array([
        [chamfer, 0], [w - chamfer, 0],
        [w, chamfer], [w, h - chamfer],
        [w - chamfer, h], [chamfer, h],
        [0, h - chamfer], [0, chamfer]
    ], np.int32)
    
    # Mask outside chamfer to make transparent
    mask = np.zeros((h, w), dtype=np.uint8)
    cv2.fillPoly(mask, [pts], 255)
    
    # Outer black border
    cv2.polylines(patch, [pts], True, (20, 20, 20), max(1, int(min(w, h) * 0.035)), cv2.LINE_AA)
    
    # Inner border line
    inner_chamfer = max(1, chamfer - 2)
    inner_pts = np.array([
        [inner_chamfer + 2, 3], [w - inner_chamfer - 2, 3],
        [w - 3, inner_chamfer + 2], [w - 3, h - inner_chamfer - 2],
        [w - inner_chamfer - 2, h - 3], [inner_chamfer + 2, h - 3],
        [3, h - inner_chamfer - 2], [3, inner_chamfer + 2]
    ], np.int32)
    cv2.polylines(patch, [inner_pts], True, (40, 40, 40), 1, cv2.LINE_AA)

    # Render Two-line Text
    # Line 1: State code
    f_scale1 = (h * 0.28) / 30.0
    f_thick1 = max(1, int(f_scale1 * 2.2))
    (tw1, th1), _ = cv2.getTextSize(line1, cv2.FONT_HERSHEY_SIMPLEX, f_scale1, f_thick1)
    tx1 = (w - tw1) // 2
    ty1 = int(h * 0.42)
    cv2.putText(patch, line1, (tx1, ty1), cv2.FONT_HERSHEY_SIMPLEX, f_scale1, (10, 10, 10), f_thick1, cv2.LINE_AA)

    # Subtle separator line or badge
    cv2.line(patch, (int(w * 0.25), int(h * 0.50)), (int(w * 0.75), int(h * 0.50)), (180, 180, 180), 1)

    # Line 2: Number
    f_scale2 = (h * 0.32) / 30.0
    f_thick2 = max(1, int(f_scale2 * 2.4))
    (tw2, th2), _ = cv2.getTextSize(line2, cv2.FONT_HERSHEY_SIMPLEX, f_scale2, f_thick2)
    tx2 = (w - tw2) // 2
    ty2 = int(h * 0.86)
    cv2.putText(patch, line2, (tx2, ty2), cv2.FONT_HERSHEY_SIMPLEX, f_scale2, (10, 10, 10), f_thick2, cv2.LINE_AA)

    # Add subtle dirt/vignette gradient
    gradient = np.tile(np.linspace(0.92, 1.0, w), (h, 1))
    for c in range(3):
        patch[:, :, c] = np.clip(patch[:, :, c] * gradient, 0, 255).astype(np.uint8)

    # Convert to 4-channel BGRA with mask
    bgra = cv2.cvtColor(patch, cv2.COLOR_BGR2BGRA)
    bgra[:, :, 3] = mask
    return bgra

# ─────────────────────────────────────────────────────────────
# 1. EXTRACT REAL HIGH-RES EXAMPLES FROM SURVEILLANCE VIDEO
# ─────────────────────────────────────────────────────────────
cap = cv2.VideoCapture(VIDEO_PATH)
m1 = YOLO(M1_PATH)
m2 = YOLO(M2_PATH)

real_samples_count = 0
frames_to_extract = list(range(5, 38, 1))  # Extract frames 5 to 37

base_scooter_crops = []

for f in frames_to_extract:
    cap.set(cv2.CAP_PROP_POS_FRAMES, f)
    ret, frame = cap.read()
    if not ret: break

    # Find motorcycle
    res1 = m1(frame, verbose=False, conf=0.15)
    target_moto = None
    for b in res1[0].boxes:
        if int(b.cls[0]) == 3:
            box = list(map(int, b.xyxy[0]))
            if (box[2] - box[0]) > 200:  # Foreground scooter
                target_moto = box
                break

    if target_moto is None:
        continue

    bx1, by1, bx2, by2 = target_moto
    # Check plate detection with m2
    res2 = m2(frame, verbose=False, conf=0.05)
    plate_box = None
    for pb in res2[0].boxes:
        if int(pb.cls[0]) == 2:
            pbox = list(map(int, pb.xyxy[0]))
            if bx1 <= pbox[0] and pbox[2] <= bx2 and by1 <= pbox[1] and pbox[3] <= by2:
                plate_box = pbox
                break

    if plate_box is None:
        continue

    # Crop motorcycle envelope with padding for clean training sample
    pad_y = int((by2 - by1) * 0.4)
    cy1 = max(0, by1 - pad_y)
    cy2 = min(frame.shape[0], by2 + int((by2 - by1) * 0.05))
    cx1 = max(0, bx1 - int((bx2 - bx1) * 0.15))
    cx2 = min(frame.shape[1], bx2 + int((bx2 - bx1) * 0.15))

    crop = frame[cy1:cy2, cx1:cx2]
    if crop.shape[0] < 150 or crop.shape[1] < 150:
        continue

    ch, cw = crop.shape[:2]
    # Resize to standard model training resolution 640x640
    crop_resized = cv2.resize(crop, (640, 640), interpolation=cv2.INTER_LANCZOS4)
    scale_x = 640.0 / cw
    scale_y = 640.0 / ch

    # Bounding box of plate in cropped image
    px1, py1, px2, py2 = plate_box
    cpx1 = int((px1 - cx1) * scale_x)
    cpy1 = int((py1 - cy1) * scale_y)
    cpx2 = int((px2 - cx1) * scale_x)
    cpy2 = int((py2 - cy1) * scale_y)

    # Detect heads in this crop with m2
    res_heads = m2(crop, verbose=False, conf=0.20)
    heads = []
    for hb in res_heads[0].boxes:
        c = int(hb.cls[0])
        if c in [0, 1]:  # Helmet or Without Helmet
            hx1, hy1, hx2, hy2 = map(int, hb.xyxy[0])
            heads.append((c, int(hx1 * scale_x), int(hy1 * scale_y), int(hx2 * scale_x), int(hy2 * scale_y)))

    # Save Real Sample Image
    real_samples_count += 1
    img_name = f"scooter_front_real_{real_samples_count:03d}.jpg"
    img_save_path = os.path.join(IMG_DIR, img_name)
    cv2.imwrite(img_save_path, crop_resized)

    # Save YOLO format Label (.txt)
    # Class 2: licence plate (normalized: class cx cy w h)
    pcx = ((cpx1 + cpx2) / 2.0) / 640.0
    pcy = ((cpy1 + cpy2) / 2.0) / 640.0
    pw = (cpx2 - cpx1) / 640.0
    ph = (cpy2 - cpy1) / 640.0

    lbl_save_path = os.path.join(LBL_DIR, img_name.replace(".jpg", ".txt"))
    with open(lbl_save_path, "w") as f_lbl:
        # Save plate
        f_lbl.write(f"2 {pcx:.6f} {pcy:.6f} {pw:.6f} {ph:.6f}\n")
        # Save heads if detected
        for c, hx1, hy1, hx2, hy2 in heads:
            hcx = ((hx1 + hx2) / 2.0) / 640.0
            hcy = ((hy1 + hy2) / 2.0) / 640.0
            hw = (hx2 - hx1) / 640.0
            hh = (hy2 - hy1) / 640.0
            f_lbl.write(f"{c} {hcx:.6f} {hcy:.6f} {hw:.6f} {hh:.6f}\n")

    # Store base crop for synthesis
    base_scooter_crops.append({
        "crop": crop_resized,
        "plate_rect": (cpx1, cpy1, cpx2, cpy2),
        "heads": heads
    })

    # Visualization
    vis = crop_resized.copy()
    cv2.rectangle(vis, (cpx1, cpy1), (cpx2, cpy2), (255, 0, 255), 2)
    cv2.putText(vis, "licence (scooter front)", (cpx1, max(18, cpy1 - 5)), cv2.FONT_HERSHEY_SIMPLEX, 0.5, (255, 0, 255), 2)
    for c, hx1, hy1, hx2, hy2 in heads:
        col = (0, 255, 0) if c == 0 else (0, 0, 255)
        label = "Helmet" if c == 0 else "No-Helmet"
        cv2.rectangle(vis, (hx1, hy1), (hx2, hy2), col, 2)
        cv2.putText(vis, label, (hx1, max(18, hy1 - 5)), cv2.FONT_HERSHEY_SIMPLEX, 0.5, col, 2)
    cv2.imwrite(os.path.join(VIS_DIR, img_name), vis)

cap.release()
print(f"✅ Extracted {real_samples_count} real surveillance frames with exact annotations.")

# ─────────────────────────────────────────────────────────────
# 2. GENERATE DIVERSE INDIAN FRONT SCOOTER PLATES VIA SYNTHESIS
# ─────────────────────────────────────────────────────────────
synth_target = 60  # Generate 60 additional diverse synthetic variations
synth_count = 0

while synth_count < synth_target and base_scooter_crops:
    base = random.choice(base_scooter_crops)
    img = base["crop"].copy()
    px1, py1, px2, py2 = base["plate_rect"]
    pw = px2 - px1
    ph = py2 - py1

    # Generate random authentic Indian registration
    l1, l2 = generate_random_plate_text()

    # Scale plate slightly with random jitter (90% to 110%)
    jitter = random.uniform(0.92, 1.08)
    plate_w = max(40, int(pw * jitter))
    plate_h = max(28, int(ph * jitter))

    patch = draw_curved_plate_patch(plate_w, plate_h, l1, l2)

    # Random slight rotation / perspective warp (-6 to +6 degrees)
    angle = random.uniform(-6.0, 6.0)
    M = cv2.getRotationMatrix2D((plate_w // 2, plate_h // 2), angle, 1.0)
    patch_rot = cv2.warpAffine(patch, M, (plate_w, plate_h), flags=cv2.INTER_LINEAR, borderMode=cv2.BORDER_CONSTANT, borderValue=(0, 0, 0, 0))

    # Center position with slight jitter (+- 5px)
    cx = (px1 + px2) // 2 + random.randint(-4, 4)
    cy = (py1 + py2) // 2 + random.randint(-3, 3)
    nx1 = max(0, cx - plate_w // 2)
    ny1 = max(0, cy - plate_h // 2)
    nx2 = min(640, nx1 + plate_w)
    ny2 = min(640, ny1 + plate_h)

    # Alpha blend onto scooter apron
    crop_w = nx2 - nx1
    crop_h = ny2 - ny1
    if crop_w <= 10 or crop_h <= 10:
        continue

    p_rgb = patch_rot[:crop_h, :crop_w, :3]
    p_alpha = (patch_rot[:crop_h, :crop_w, 3] / 255.0)[:, :, np.newaxis]

    # Lighting / color temperature matching
    roi = img[ny1:ny2, nx1:nx2]
    # Match average luminance
    bg_lum = np.mean(roi)
    lum_factor = np.clip(bg_lum / 180.0, 0.75, 1.15)
    p_rgb = np.clip(p_rgb * lum_factor, 0, 255).astype(np.uint8)

    # Blend
    blended = (p_rgb * p_alpha + roi * (1.0 - p_alpha)).astype(np.uint8)
    img[ny1:ny2, nx1:nx2] = blended

    # Subtle overall noise / compression augmentation
    if random.random() > 0.5:
        # Slight blur
        img = cv2.GaussianBlur(img, (3, 3), random.uniform(0.3, 0.8))

    synth_count += 1
    s_name = f"scooter_front_synth_{synth_count:03d}.jpg"
    s_img_path = os.path.join(IMG_DIR, s_name)
    cv2.imwrite(s_img_path, img)

    # Save YOLO Label
    spcx = ((nx1 + nx2) / 2.0) / 640.0
    spcy = ((ny1 + ny2) / 2.0) / 640.0
    spw = (nx2 - nx1) / 640.0
    sph = (ny2 - ny1) / 640.0

    s_lbl_path = os.path.join(LBL_DIR, s_name.replace(".jpg", ".txt"))
    with open(s_lbl_path, "w") as f_lbl:
        f_lbl.write(f"2 {spcx:.6f} {spcy:.6f} {spw:.6f} {sph:.6f}\n")
        for c, hx1, hy1, hx2, hy2 in base["heads"]:
            hcx = ((hx1 + hx2) / 2.0) / 640.0
            hcy = ((hy1 + hy2) / 2.0) / 640.0
            hw = (hx2 - hx1) / 640.0
            hh = (hy2 - hy1) / 640.0
            f_lbl.write(f"{c} {hcx:.6f} {hcy:.6f} {hw:.6f} {hh:.6f}\n")

    # Visualization
    vis = img.copy()
    cv2.rectangle(vis, (nx1, ny1), (nx2, ny2), (255, 0, 255), 2)
    cv2.putText(vis, f"licence ({l1} {l2})", (nx1, max(18, ny1 - 5)), cv2.FONT_HERSHEY_SIMPLEX, 0.45, (255, 0, 255), 2)
    cv2.imwrite(os.path.join(VIS_DIR, s_name), vis)

print(f"✅ Generated {synth_count} photorealistic augmented Indian scooter plate examples.")
total_generated = real_samples_count + synth_count
print(f"🎉 Total Indian front scooter plate dataset created: {total_generated} images and label pairs!")

# Sync sample inspection images to brain artifact directory
all_vis = sorted(glob.glob(os.path.join(VIS_DIR, "*.jpg")))
sample_images = all_vis[:6] + all_vis[real_samples_count:real_samples_count+6]
for idx, sf in enumerate(sample_images[:8]):
    dst_name = f"scooter_plate_sample_{idx+1:02d}.jpg"
    shutil.copyfile(sf, os.path.join(ARTIFACT_DIR, dst_name))

print(f"✅ Synced {min(8, len(sample_images))} visual samples to artifact gallery for instant inspection.")
