# 🧠 AI Models Directory

Due to file size limitations on GitHub, the trained model weights and checkpoints are hosted externally.

### Download Link
👉 **[Download AI Models from Google Drive](https://drive.google.com/drive/folders/1WHVeHnA-8CUa1F0rWcdnSnSyWjpA_pYj?usp=sharing)**

### Required Files
Place the following files in this directory (`ai_models/`):
- `yolov8n.pt` - Base YOLOv8 Nano vehicle detection model
- `best.pt` - Custom trained YOLO model for Indian traffic enforcement (Helmets, Plates, Riders)
- `vitals_ppo_model.zip` - Stable-Baselines3 PPO model for RL adaptive signal control
- `vitals_ppo_vecnorm.pkl` - Normalization parameters for PPO observation space

*Note: All `.pt`, `.zip`, and `.pkl` files in this directory are excluded from Git commits via `.gitignore`.*
