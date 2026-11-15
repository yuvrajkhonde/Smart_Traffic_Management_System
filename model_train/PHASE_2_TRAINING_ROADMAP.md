# 🚦 Phase 2: Custom Model Training Roadmap & Progress Tracker

> **Repository:** `Module_2_Backend` | **Subsystem:** Computer Vision Enforcement Engine (Stage 2)  
> **Target Device:** Local Dedicated GPU  
> **Status:** Phase 1 Complete (Algorithmic Pipeline Validated) ➔ Phase 2 Commencing

---

## 📌 Alignment with Phase 1

### What Phase 1 Successfully Established
* **Full-Frame Vehicle & Person Detection:** `yolov8n.pt` reliably tracks all background traffic (`car`, `bus`, `truck`, `motorcycle`, `person`).
* **Trajectory Stability:** ByteTrack with continuous frame tracking (`persist=True`) maintains consistent track IDs across frames without jumping.
* **Two-Stage Enforcement Envelope:** Geometric union envelope $(\text{Motorcycle} \cup \text{Assigned Riders})$ with $15\%$ padding isolates each vehicle into a sharp crop.
* **Temporal Multi-Frame Voting:** Validates riders across time; compliant riders are granted `HELMET OK` benefit of the doubt.
* **Resolution Gating:** Far-field bikes ($<75\text{px}$) are suppressed from noisy OCR attempts.
* **Triple Riding Logic:** Solved at the geometric layer via overlap ($IoP \ge 0.15$) and nearest-bike association (no new vision class required).

### Gaps from Phase 1 That Phase 2 Solves
1. **Absence of `no_helmet` class:** Existing `best.pt` only detects `Helmet`, falsely penalizing riders when single-frame detection fails. Phase 2 introduces explicit `no_helmet` (bare head) detection.
2. **Model Scale & Angle Mismatch:** `best.pt` was trained on close-up selfies with high classification loss (`cls_loss = 6.643`). Phase 2 trains on CCTV surveillance perspectives.
3. **License Plate Recall:** Existing model has near-zero plate recall on CCTV video. Phase 2 trains high-precision bounding box localization for vehicle registration plates.

---

## 🧩 Architectural Pipeline Flow

```
[Full CCTV Frame: 1080p / 720p]
             │
             ▼
┌────────────────────────────────────────────────────────┐
│ STAGE 1: Detection & Tracking (yolov8n.pt + ByteTrack) │
│ • Detects: Motorcycle (3), Person (0), Other Vehicles  │
│ • Assigns Riders to Bikes (IoP >= 0.15 + Proximity)    │
│ • Resolves Triple Riding (>= 3 Riders over 5+ frames)  │
│ • Extracts Dynamic Envelope Crop (Motorcycle + Riders) │
└────────────────────────────────────────────────────────┘
             │
             ▼ [High-Res Envelope Crop: 640×640]
┌────────────────────────────────────────────────────────┐
│ STAGE 2: Enforcement Detector (NEW PHASE 2 MODEL)      │
│ • Class 0: helmet                                      │
│ • Class 1: no_helmet (Explicit Bare Head / Cap)        │
│ • Class 2: license_plate                               │
└────────────────────────────────────────────────────────┘
             │
             ▼
┌────────────────────────────────────────────────────────┐
│ POST-PROCESSING & VERIFICATION                         │
│ • Temporal Multi-Frame Voting (Confirm Violation)      │
│ • Near-Field Resolution Gating (bh >= 75px)            │
│ • Plate Crop Extraction ➔ EasyOCR Fallback Pipeline    │
│ • Composite E-Challan Evidence Dispatch to Supabase/DB │
└────────────────────────────────────────────────────────┘
```

---

## 📋 The 7 Step-by-Step Training Phases & Checklist

### [ ] Step 1: Dataset Acquisition & Class Alignment
- [ ] Acquire high-quality traffic CCTV motorcycle dataset (Roboflow / Kaggle Traffic Surveillance).
- [ ] Align target classes strictly to:
  - `0: helmet`
  - `1: no_helmet`
  - `2: license_plate`
- [ ] Structure into standard YOLO format (`images/train`, `images/val`, `labels/train`, `labels/val`, `data.yaml`).
- [ ] Verify dataset contains diverse angles: rear-view, 45° angle, bright sunlight, shadows, and pillion riders.

### [ ] Step 2: Data Quality & Augmentation Strategy
- [ ] Audit class balance (ensure `no_helmet` is well-represented, avoiding 10:1 skew).
- [ ] Configure traffic-appropriate augmentations in training YAML:
  - `fliplr=0.5`: Horizontal flip enabled (traffic drives both directions).
  - `flipud=0.0`: **Vertical flip disabled** (riders/helmets are never upside down).
  - `mosaic=1.0`: Mosaic augmentation to learn multi-scale contexts.
  - `hsv_h=0.015`, `hsv_s=0.7`, `hsv_v=0.4`: Color and lighting robustness for sunny vs overcast CCTV.

### [x] Step 3: Local GPU Hardware & Memory Tuning (VERIFIED)
- [x] Check local dedicated GPU model: **NVIDIA GeForce RTX 4060 Laptop GPU** (CUDA Available: `True`).
- [x] Total VRAM: **8.0 GB GDDR6** (Ada Lovelace Tensor Cores).
- [ ] Enable Automatic Mixed Precision (`amp=True`, FP16) for $2\times$ training speed and $50\%$ memory reduction.
- [ ] Select optimal batch size: **`batch=16`** (comfortably fits inside 8GB VRAM with headroom).
- [ ] Configure `workers=4` for multi-threaded dataloading from local disk.

### [ ] Step 4: Model Architecture & Transfer Learning Setup
- [ ] Base Architecture: **YOLOv8s** (Small) — optimal accuracy-to-speed balance for small object detection on surveillance feeds.
- [ ] Transfer Learning: Initialize from `yolov8s.pt` pretrained weights (retains pre-learned edge/texture/shape filters from COCO).
- [ ] Replace final detection head to output exactly 3 classes (`helmet`, `no_helmet`, `license_plate`).

### [ ] Step 5: Training Execution & Optimization Loop
- [ ] Optimizer: **AdamW** with initial learning rate `lr0=0.001` and cosine decay scheduler (`lrf=0.01`).
- [ ] Epochs: Set to **40 epochs** with early stopping patience of 10 epochs.
- [ ] Loss weights:
  - Classification Loss (BCE) for class accuracy.
  - Box Loss (CIoU) for bounding box tightness.
  - DFL (Distribution Focal Loss) for sharp boundary localization.
- [ ] Monitor train/val loss curves in real-time (`results.csv`).

### [ ] Step 6: Validation & Precision Metrics Audit
- [ ] Target validation metrics:
  - Overall `mAP@50` $\ge 85\%$.
  - `no_helmet` class recall $\ge 80\%$ (minimizes missed offenders).
  - `no_helmet` class precision $\ge 85\%$ (prevents false penalties on compliant riders).
  - `license_plate` `mAP@50` $\ge 85\%$.
- [ ] Inspect Confusion Matrix to confirm zero cross-contamination between `helmet` and `no_helmet`.

### [ ] Step 7: Plug-and-Play Integration & Verification
- [ ] Copy trained `best.pt` to `ai_models/best.pt` in the project root.
- [ ] Update `backend/ai_engine/utils.py` class mapping:
  - `CUSTOM_CLS_HELMET = 0`
  - `CUSTOM_CLS_NO_HELMET = 1`
  - `CUSTOM_CLS_PLATE = 2`
- [ ] Update violation trigger logic: fire `No Helmet` **only when `no_helmet` is positively detected with $\ge 0.50$ confidence**.
- [ ] Re-run `scripts/export_debug_frames.py` and inspect fresh visual outputs to confirm zero false alarms.

---

## 📍 Current Progress

| Step | Description | Status |
|---|---|---|
| **Phase 1** | Two-stage pipeline, ByteTrack trajectory, temporal voting | **✅ Completed** |
| **Step 1** | Dataset Acquisition & Class Alignment (Dataset 1: 1,533 images) | **✅ Completed** |
| **Step 2** | Data Quality & Augmentation Strategy configured in `train_model.py` | **✅ Completed** |
| **Step 3** | Local GPU Hardware & Memory Tuning (RTX 4060, 8GB VRAM verified) | **✅ Completed** |
| **Step 4** | Model Architecture & Transfer Learning Setup (`ml_training/`) | **✅ Completed** |
| **Step 5** | Training Execution (40 Epochs completed in 14.5 min on RTX 4060) | **✅ Completed** |
| **Step 6** | Validation & Metrics Audit (mAP@50 = 85.98%, Test mAP@50 = 82.13%) | **✅ Completed** |
| **Step 7** | Two-Stage Pipeline Integration & Weight Deployment (`ai_models/best.pt`) | **✅ Completed** |
