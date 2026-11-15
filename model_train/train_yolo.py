"""
═══════════════════════════════════════════════════════════════
  🎯 V.I.T.A.L.S. — YOLO Model Training & Fine-Tuning Pipeline
  Specialized for Indian Traffic Surveillance:
  Classes: Helmet (0), Licence Plate (1), Motorcycle (2), Person (3)
═══════════════════════════════════════════════════════════════
"""

import os
import sys
import argparse
from ultralytics import YOLO

def train(
    data_yaml: str,
    base_model: str = "yolov8s.pt",
    epochs: int = 100,
    imgsz: int = 640,
    batch: int = 16,
    device: str = "0",
    project: str = "vitals_training",
    name: str = "custom_yolo_run",
    resume: bool = False
):
    print("\n" + "="*60)
    print("🚀 STARTING V.I.T.A.L.S. MODEL TRAINING")
    print("="*60)
    print(f"  Dataset YAML   : {data_yaml}")
    print(f"  Base Weights   : {base_model}")
    print(f"  Epochs         : {epochs}")
    print(f"  Image Size     : {imgsz}px")
    print(f"  Batch Size     : {batch}")
    print(f"  Target Device  : {device}")
    print(f"  Save Project   : {project}/{name}")
    print("="*60 + "\n")

    if not os.path.exists(data_yaml):
        raise FileNotFoundError(f"data.yaml not found at: {data_yaml}")

    # Load base model or existing checkpoint for transfer learning
    model = YOLO(base_model)

    # Train model with hyperparameters tailored for traffic cameras:
    # - Higher imgsz (e.g. 640 or 1024) helps detect small license plates in wide CCTV shots
    # - Mosaic and mixup simulate occluded bikes and pillion riders
    results = model.train(
        data=data_yaml,
        epochs=epochs,
        imgsz=imgsz,
        batch=batch,
        device=device,
        project=project,
        name=name,
        resume=resume,
        # Optimization & Augmentations for Traffic
        optimizer="AdamW",
        lr0=0.001,
        lrf=0.01,
        mosaic=1.0,           # Augmentation: combines 4 scenes
        mixup=0.1,            # Blends images to recognize overlapping riders
        perspective=0.0005,   # Handles overhead camera tilt
        degrees=10.0,         # Slight rotation for angled movement
        scale=0.5,            # Scales objects up/down to handle close vs far vehicles
        save=True,
        save_period=10,
        plots=True,
        verbose=True
    )

    print("\n" + "="*60)
    print("✅ TRAINING COMPLETE!")
    print(f"Best weights saved at: {os.path.join(project, name, 'weights', 'best.pt')}")
    print("="*60)
    return results

if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Train custom YOLO enforcement model")
    parser.add_argument("--data", type=str, required=True, help="Path to data.yaml dataset config")
    parser.add_argument("--base", type=str, default="yolov8s.pt", help="Base model (yolov8n.pt, yolov8s.pt, or best.pt)")
    parser.add_argument("--epochs", type=int, default=80, help="Number of training epochs")
    parser.add_argument("--imgsz", type=int, default=640, help="Image resolution: 640 or 1024")
    parser.add_argument("--batch", type=int, default=16, help="Batch size (reduce if GPU OOM)")
    parser.add_argument("--device", type=str, default="0", help="CUDA GPU index (0) or 'cpu'")
    parser.add_argument("--name", type=str, default="bhopal_enforcement_v2", help="Run identifier")
    parser.add_argument("--resume", action="store_true", help="Resume interrupted training")

    args = parser.parse_args()

    train(
        data_yaml=args.data,
        base_model=args.base,
        epochs=args.epochs,
        imgsz=args.imgsz,
        batch=args.batch,
        device=args.device,
        name=args.name,
        resume=args.resume
    )
