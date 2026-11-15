"""
═══════════════════════════════════════════════════════════════
  📊 V.I.T.A.L.S. — Model Evaluation & Benchmark Suite
  Evaluates YOLO models on validation datasets or video samples.
═══════════════════════════════════════════════════════════════
"""

import os
import sys
import argparse
from ultralytics import YOLO

def evaluate_on_dataset(model_path: str, data_yaml: str, imgsz: int = 640, device: str = "0"):
    """Evaluates a YOLO model on a standard YOLO data.yaml dataset."""
    print(f"\n🚀 Running validation on dataset: {data_yaml}")
    print(f"📦 Model: {model_path} | Image Size: {imgsz} | Device: {device}")
    
    model = YOLO(model_path)
    metrics = model.val(data=data_yaml, imgsz=imgsz, device=device, verbose=True)
    
    print("\n" + "="*50)
    print("📈 VALIDATION RESULTS SUMMARY:")
    print(f"  mAP50-95 (All classes) : {metrics.box.map:.4f}")
    print(f"  mAP50    (All classes) : {metrics.box.map50:.4f}")
    print(f"  mAP75    (All classes) : {metrics.box.map75:.4f}")
    print(f"  Precision (Mean)       : {metrics.box.mp:.4f}")
    print(f"  Recall    (Mean)       : {metrics.box.mr:.4f}")
    print("="*50)
    
    print("\n🔍 PER-CLASS PERFORMANCE:")
    for i, name in enumerate(model.names.values()):
        if i < len(metrics.box.maps):
            print(f"  Class [{name}]: mAP50-95 = {metrics.box.maps[i]:.4f}")
            
    return metrics

def inspect_model_metadata(model_path: str):
    """Prints architecture, class labels, and checkpoint training history."""
    print(f"\n🔍 Inspecting Checkpoint: {model_path}")
    import torch
    ckpt = torch.load(model_path, map_location="cpu", weights_only=False)
    
    print("  Keys:", list(ckpt.keys()))
    if "train_args" in ckpt:
        args = ckpt["train_args"]
        print("  Original Training Parameters:")
        for k in ["data", "epochs", "imgsz", "batch", "model", "optimizer"]:
            val = getattr(args, k, None) if hasattr(args, k) else (args.get(k) if isinstance(args, dict) else None)
            print(f"    {k}: {val}")
    if "train_metrics" in ckpt:
        print("  Training End Metrics:", ckpt["train_metrics"])

if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Evaluate V.I.T.A.L.S. YOLO Models")
    parser.add_argument("--model", type=str, default="best.pt", help="Path to .pt model")
    parser.add_argument("--data", type=str, default="", help="Path to data.yaml (optional)")
    parser.add_argument("--inspect-only", action="store_true", help="Inspect checkpoint metadata")
    parser.add_argument("--imgsz", type=int, default=640, help="Image resolution (640 or 1280)")
    parser.add_argument("--device", type=str, default="0", help="GPU index or 'cpu'")
    
    args = parser.parse_args()
    
    model_p = args.model
    if not os.path.isabs(model_p):
        model_p = os.path.join(os.path.dirname(__file__), model_p)
        
    if args.inspect_only or not args.data:
        inspect_model_metadata(model_p)
        if not args.data:
            print("\n💡 TIP: To run full validation, pass a dataset YAML: python evaluate.py --model best.pt --data path/to/data.yaml")
    else:
        evaluate_on_dataset(model_p, args.data, imgsz=args.imgsz, device=args.device)
