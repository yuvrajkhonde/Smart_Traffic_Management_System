# 🧠 V.I.T.A.L.S. Machine Learning Engineering Hub (`ml_training/`)

This directory is the dedicated workspace for training, evaluating, and exporting custom Computer Vision models for the V.I.T.A.L.S. Smart Traffic Enforcement Engine.

---

## 📁 Directory Structure

```text
ml_training/
├── config/
│   └── dataset.yaml              # Points directly to Dataset 1 (balanced 3 classes)
├── train_model.py                # Main training script (YOLOv8s, FP16, RTX 4060 GPU tuned)
├── evaluate_model.py             # Validation benchmark on unseen val & test splits
├── test_on_surveillance.py       # Live CCTV inference test on north_lane.mp4
├── export_weights.py             # Deploys best.pt to ai_models/ with automatic backup
├── test_outputs/                 # Annotated frames and crops from surveillance test
└── runs/                         # YOLO training outputs, checkpoints, and metrics
```

---

## 🎯 Target Classes

| Class ID | Label | Enforcement Role |
|---|---|---|
| `0` | `With Helmet` | Verified compliant rider (`HELMET OK`) |
| `1` | `Without Helmet` | High-confidence positive violation (`NO HELMET`) |
| `2` | `licence` | License plate bounding box for ALPR OCR |

---

## 🚀 Execution Commands

All commands run inside the virtual environment: `.\venv\Scripts\python.exe`

### 1. Start Training (Local RTX 4060 GPU)
```powershell
.\venv\Scripts\python.exe ml_training\train_model.py
```
* Trains for 40 epochs with AdamW optimizer and cosine learning rate decay.
* Estimated time on RTX 4060: **~6 to 8 minutes**.

### 2. Evaluate on Unseen Validation Data
```powershell
.\venv\Scripts\python.exe ml_training\evaluate_model.py
```

### 3. Test on CCTV Surveillance Video
```powershell
.\venv\Scripts\python.exe ml_training\test_on_surveillance.py
```

### 4. Deploy Weights to Production
```powershell
.\venv\Scripts\python.exe ml_training\export_weights.py
```
