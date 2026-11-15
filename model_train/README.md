# 🚦 V.I.T.A.L.S. Model Training & Evaluation Suite

This folder (`model_train/` and `model train/`) is the central workspace for auditing, training, fine-tuning, and evaluating the AI computer vision models used in the **V.I.T.A.L.S.** traffic enforcement system.

---

## 📁 Included Models

| File | Type | Description |
|---|---|---|
| **`best.pt`** | YOLOv8 (Custom) | 4-class enforcement detector: `Helmet (0)`, `Licence Plate (1)`, `Motorcycle (2)`, `Person (3)`. |
| **`yolov8n.pt`** | YOLOv8 Nano | Base COCO detector: Vehicle tracking (`car`, `truck`, `bus`, `motorcycle`), density, and pedestrians. |
| **`vitals_ppo_model.zip`** | Stable-Baselines3 PPO | Reinforcement Learning agent for adaptive traffic signal phase control. |
| **`vitals_ppo_vecnorm.pkl`** | Pickle | Observation normalization stats (running mean & variance) for the PPO agent. |

---

## 🔬 Audit Findings: Why The Current Setup Struggles in Real Videos

During our empirical diagnosis across the real test videos (`east_lane.mp4`, `north_lane.mp4`, etc.):

1. **Resolution & Scale Mismatch**:
   - `best.pt` was trained on Kaggle/Roboflow images (`imgsz=640`) where bikes and helmets occupied **50–80%** of the frame.
   - In 1080p/720p CCTV intersection feeds, a motorcycle is often only **60×70 px**, a helmet is **15×15 px**, and a plate is **20×10 px**.
   - Running `best.pt` on the entire full frame downscales those objects to single-digit pixel sizes, resulting in **< 0.09 confidence scores** and 0 detections at default thresholds (`conf=0.20`).
2. **High Validation Loss**:
   - Inspection of `best.pt`'s checkpoint revealed `val/cls_loss = 6.643` (unusually high classification error for a converged YOLO model).
3. **Rigid Spatial Assumptions in `utils.py`**:
   - `expanded_box = [bx1, max(0, by1 - int(bike_h * 0.6)), bx2, by2]`:
     In angled/overhead CCTV, riders sit backwards or leaned forward, and their heads fall outside this vertical box.
   - `box_contains(expanded_box, (pcx, pcy))`: Strict center-point containment drops pillion riders whose center sits just 2 pixels outside the box, causing Triple Riding to fail.
4. **OCR Normalization Failure**:
   - Because plates were rarely detected by `best.pt` with confidence > 0.40, EasyOCR was rarely fed high-quality crops. Even when OCR ran, strict regex matching for Indian plates discarded slightly blurred plates as `"UNKNOWN"`.

---

## 🛠️ Tooling & Scripts in this Folder

### 1. Model Checkpoint Inspector & Evaluator (`evaluate.py`)
Inspect checkpoint training metadata:
```bash
python evaluate.py --model best.pt --inspect-only
```
Evaluate on a validation dataset:
```bash
python evaluate.py --model best.pt --data path/to/data.yaml --imgsz 640 --device 0
```

### 2. Visual Video Debugger (`test_on_video.py`)
Run both models on any video footage and inspect detection bounding boxes frame-by-frame:
```bash
python test_on_video.py --video ../backend/test_videos/north_lane.mp4 --conf-m2 0.08 --frames 100
```
This saves annotated frames to `debug_output/` showing why violations triggered or didn't trigger.

### 3. Training & Fine-Tuning Script (`train_yolo.py`)
Train a new or fine-tuned model with GPU acceleration:
```bash
python train_yolo.py --data path/to/dataset/data.yaml --base yolov8s.pt --epochs 100 --imgsz 1024 --batch 8 --device 0
```
> **Tip for CCTV Traffic**: Use `--imgsz 1024` instead of `640`. Higher resolution enables the convolutional layers to retain tiny features like distant helmets and license plates.

---

## 💡 Recommended Next Steps to Improve Accuracy

1. **Two-Stage Pipeline (Crop-and-Detect)**:
   - Instead of running `best.pt` on the whole frame, use `yolov8n.pt` to detect the motorcycle/person first.
   - Crop that region, upscale it to 640×640, and feed it into `best.pt` for helmet and plate verification.
2. **Collect Real CCTV Intersection Data**:
   - Label 500–1,000 frames specifically taken from intersection CCTV angles rather than street-level close-ups.
3. **Train with YOLOv8s / YOLOv8m at 1024px**:
   - `yolov8n.pt` is lightweight, but for multi-class fine-grained detection (helmet vs cap vs bare head), `yolov8s` or `yolov8m` with higher feature depth yields significantly higher precision.
