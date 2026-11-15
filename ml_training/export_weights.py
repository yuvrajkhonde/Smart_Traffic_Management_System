"""
V.I.T.A.L.S. Phase 2: Weight Export & Integration Script
1. Backs up previous ai_models/best.pt to ai_models/best_old_backup.pt
2. Copies trained runs/phase2_enforcement/weights/best.pt to ai_models/best.pt
3. Validates model classes and weights integrity
"""

import os
import shutil
from ultralytics import YOLO

CURRENT_DIR = os.path.dirname(os.path.abspath(__file__))
ROOT_DIR = os.path.join(CURRENT_DIR, "..")
SRC_WEIGHTS = os.path.join(CURRENT_DIR, "runs", "phase2_enforcement", "weights", "best.pt")
DST_WEIGHTS = os.path.join(ROOT_DIR, "ai_models", "best.pt")
BACKUP_WEIGHTS = os.path.join(ROOT_DIR, "ai_models", "best_old_backup.pt")

def export_weights(src=None):
    source = src or SRC_WEIGHTS
    if not os.path.exists(source):
        print(f"❌ Source weights not found: {source}")
        return False

    print("=" * 65)
    print("🚀 Exporting Phase 2 Trained Weights to Production")
    print(f"Source : {source}")
    print(f"Target : {DST_WEIGHTS}")
    print("=" * 65)

    # 1. Backup old weights if they exist
    if os.path.exists(DST_WEIGHTS) and not os.path.exists(BACKUP_WEIGHTS):
        print(f"📦 Backing up previous best.pt to: {BACKUP_WEIGHTS}")
        shutil.copyfile(DST_WEIGHTS, BACKUP_WEIGHTS)

    # 2. Copy new weights
    print(f"💾 Copying new best.pt to: {DST_WEIGHTS}")
    shutil.copyfile(source, DST_WEIGHTS)

    # 3. Validate exported model
    model = YOLO(DST_WEIGHTS)
    print("✅ Model loaded and verified successfully!")
    print(f"  Class Names: {model.names}")
    print("=" * 65)
    return True

if __name__ == "__main__":
    export_weights()
