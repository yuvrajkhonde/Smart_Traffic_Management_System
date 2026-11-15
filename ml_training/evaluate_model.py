"""
V.I.T.A.L.S. Phase 2: Evaluation & Validation Script
Evaluates the trained model on unseen validation and test datasets.
Reports:
  - Overall mAP@50 and mAP@50-95
  - Per-class Precision, Recall, and mAP@50
  - Confusion Matrix
"""

import os
import sys
from ultralytics import YOLO

CURRENT_DIR = os.path.dirname(os.path.abspath(__file__))
DATA_YAML = os.path.join(CURRENT_DIR, "config", "dataset.yaml")
BEST_WEIGHT = os.path.join(CURRENT_DIR, "runs", "phase2_enforcement", "weights", "best.pt")

def evaluate(weights_path=None):
    if weights_path is None:
        weights_path = BEST_WEIGHT

    if not os.path.exists(weights_path):
        print(f"❌ Weights file not found: {weights_path}")
        print("Please train the model first by running train_model.py")
        return None

    print("=" * 65)
    print("📊 Evaluating Model on Validation Split")
    print(f"📁 Weights: {weights_path}")
    print(f"📄 Config : {DATA_YAML}")
    print("=" * 65)

    model = YOLO(weights_path)

    # 1. Validation split evaluation
    print("\n🔍 Running validation on 'valid' split (309 images)...")
    metrics_val = model.val(data=DATA_YAML, split="val", imgsz=640, batch=16, verbose=True)

    print("\n" + "=" * 65)
    print("📈 VALIDATION SUMMARY (mAP@50):")
    print(f"  Overall mAP@50     : {metrics_val.box.map50 * 100:.2f}%")
    print(f"  Overall mAP@50-95  : {metrics_val.box.map * 100:.2f}%")
    
    names = metrics_val.names
    print("\n  Per-Class Metrics:")
    for idx, name in names.items():
        if idx < len(metrics_val.box.maps):
            class_map50 = metrics_val.box.map50  # Ultralytics class-level map
            print(f"    • Class {idx} ({name:14s}): mAP50 = {metrics_val.box.maps[idx] * 100:.2f}%")
    print("=" * 65)

    # 2. Test split evaluation (gold-standard unseen test)
    print("\n🔍 Running test evaluation on 'test' split (154 images)...")
    metrics_test = model.val(data=DATA_YAML, split="test", imgsz=640, batch=16, verbose=False)
    print(f"  Test Split mAP@50  : {metrics_test.box.map50 * 100:.2f}%")
    print("=" * 65)

    return metrics_val

if __name__ == "__main__":
    w_arg = sys.argv[1] if len(sys.argv) > 1 else None
    evaluate(w_arg)
