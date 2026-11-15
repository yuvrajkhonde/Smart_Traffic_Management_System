"""
V.I.T.A.L.S. Phase 2: Custom Enforcement Model Training Script
Targets:
  - 0: 'With Helmet'
  - 1: 'Without Helmet'
  - 2: 'licence' (License Plate)

Optimized for:
  - Hardware: NVIDIA GeForce RTX 4060 Laptop GPU (8.0 GB VRAM)
  - Framework: Ultralytics YOLOv8s (Small)
  - Acceleration: CUDA + FP16 Automatic Mixed Precision (AMP)
"""

import os
import sys
import torch
from ultralytics import YOLO

CURRENT_DIR = os.path.dirname(os.path.abspath(__file__))
DATA_YAML = os.path.join(CURRENT_DIR, "config", "dataset.yaml")
RUNS_DIR = os.path.join(CURRENT_DIR, "runs")

def check_environment():
    print("=" * 65)
    print("🚀 V.I.T.A.L.S. Phase 2: Enforcement Model Training")
    print("=" * 65)
    print(f"Python Version : {sys.version.split()[0]}")
    print(f"PyTorch Version: {torch.__version__}")
    
    if not torch.cuda.is_available():
        print("❌ WARNING: CUDA is NOT available! Training on CPU will be extremely slow.")
        device = "cpu"
    else:
        gpu_name = torch.cuda.get_device_name(0)
        vram_gb = round(torch.cuda.get_device_properties(0).total_memory / (1024**3), 2)
        print(f"✅ GPU Detected  : {gpu_name}")
        print(f"✅ Available VRAM: {vram_gb} GB")
        device = 0

    if not os.path.exists(DATA_YAML):
        raise FileNotFoundError(f"Dataset config not found at: {DATA_YAML}")
    print(f"✅ Dataset Config: {DATA_YAML}")
    print("=" * 65)
    return device

ROOT_DIR = os.path.join(CURRENT_DIR, "..")
INITIAL_WEIGHTS = os.path.join(ROOT_DIR, "ai_models", "best.pt") if os.path.exists(os.path.join(ROOT_DIR, "ai_models", "best.pt")) else "yolov8s.pt"

def train():
    device = check_environment()

    print(f"\n📦 Loading backbone weights for transfer learning from: {INITIAL_WEIGHTS}...")
    model = YOLO(INITIAL_WEIGHTS)

    # Attach Epoch Progress Tracker Callback
    def on_fit_epoch_end(trainer):
        epoch = trainer.epoch + 1
        epochs = trainer.epochs
        metrics = getattr(trainer, "metrics", {})
        m50 = metrics.get("metrics/mAP50(B)", 0.0)
        m5095 = metrics.get("metrics/mAP50-95(B)", 0.0)
        print(f"\n📈 [TRACKER] Epoch {epoch:02d}/{epochs:02d} Finished | mAP@50 = {m50*100:.2f}% | mAP@50-95 = {m5095*100:.2f}%\n", flush=True)

    model.add_callback("on_fit_epoch_end", on_fit_epoch_end)

    print("\n🔥 Starting training on RTX 4060 GPU (35 epochs, batch=16, FP16, with 88 added scooter plate samples)...")
    results = model.train(
        data=DATA_YAML,
        epochs=35,
        patience=10,             # Early stopping if no improvement for 10 epochs
        imgsz=640,               # Standard high-resolution input size
        batch=16,                # Tuned for 8GB VRAM
        device=device,
        workers=4,
        optimizer="AdamW",
        lr0=0.0008,              # Fine-tuning learning rate
        lrf=0.01,                # Cosine learning rate decay down to 0.01 * lr0
        weight_decay=0.0005,
        warmup_epochs=2.0,
        
        # Traffic-specific augmentation tuning:
        fliplr=0.5,              # Horizontal flip (vehicles drive in both directions)
        flipud=0.0,              # NO vertical flip (riders/helmets are never upside-down)
        mosaic=1.0,              # Combine 4 images for multi-scale object detection
        mixup=0.05,              # Subtle mixup for occlusion robustness
        hsv_h=0.015,             # Hue adjustment
        hsv_s=0.7,               # Saturation jitter
        hsv_v=0.4,               # Brightness jitter for sun/shadow resilience
        
        # Performance & Output
        amp=True,                # Automatic Mixed Precision (FP16)
        project=RUNS_DIR,
        name="phase2_enforcement",
        exist_ok=True,
        verbose=True
    )

    best_weight = os.path.join(RUNS_DIR, "phase2_enforcement", "weights", "best.pt")
    print("\n" + "=" * 65)
    print("🎉 Training Completed Successfully!")
    print(f"📁 Best Model Saved At: {best_weight}")
    print("=" * 65)

    # Automatically export to production ai_models/best.pt
    prod_target = os.path.join(ROOT_DIR, "ai_models", "best.pt")
    if os.path.exists(best_weight):
        import shutil
        shutil.copyfile(best_weight, prod_target)
        print(f"✅ Exported new best weights to production: {prod_target}")

    return best_weight

if __name__ == "__main__":
    train()
