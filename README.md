# 🚦 V.I.T.A.L.S. - Vision-Integrated Traffic & Autonomous Logistics System

**Bhopal Smart City AI Traffic Management System**

V.I.T.A.L.S. is an end-to-end, fully autonomous ecosystem designed to modernize city traffic infrastructure. It replaces static, timer-based traffic lights with a dynamic, AI-driven engine that processes real-time camera feeds, manages signal phases based on actual vehicle density, autonomously detects traffic violations, and flags emergency vehicles.

---

## ✨ Key Features
- **Algorithmic Demand Routing**: Uses Reinforcement Learning (PPO) to dynamically allocate green lights based on real-time traffic density across intersection lanes.
- **Emergency Vehicle Override**: Detects ambulances in real-time and grants immediate priority green signal clearance.
- **Dual-Model Computer Vision**: Simultaneous YOLOv8 multi-class object tracking and a custom YOLO enforcement model for Indian traffic violations (Helmet detection, Triple riding, and ALPR).
- **Autonomous E-Challan Generation**: Identifies Red Light Jumps, Triple Riding, and Helmetless riders. Performs Automatic License Plate Recognition (ALPR) via EasyOCR and registers challans in the cloud DBMS.
- **Officer & Citizen Command Center**: Modern React + Vite portal for traffic officers to monitor live surveillance feeds, manage e-challans, audit system health, and citizen payment self-service.

---

## 🏗️ System Architecture & Tech Stack

```text
├── backend/                  # FastAPI async REST API & AI Inference Engine
│   ├── admin/                # BTU Admin Command Center routers
│   ├── ai_engine/            # YOLO tracking, enforcement & OCR pipelines
│   ├── core/                 # Auth, JWT, dependencies & database client
│   ├── routers/              # Cameras, challans, traffic, parking, violations
│   └── main.py               # Application entrypoint
├── frontend/                 # React + Vite + Tailwind CSS command dashboard
│   ├── src/                  # Pages (Surveillance, Challans, Map, Analytics)
│   └── vite.config.ts        # Vite configuration
├── database/                 # Supabase PostgreSQL SQL schemas, RLS & triggers
├── ai_models/                # AI model weights directory & download guides
├── ml_training/              # Phase 2 YOLO fine-tuning & evaluation scripts
├── model_train/              # YOLO & PPO training pipelines & roadmap
├── scripts/                  # Diagnostic, camera test, DB verification tools
└── supabase/                 # Edge functions & Supabase CLI configuration
```

### Backend
- **FastAPI (Python 3.9+)**: High-performance async API server serving as the backbone.
- **Supabase (PostgreSQL)**: Cloud database for real-time state synchronization, authentication, and violation records.
- **Stable-Baselines3 (PPO)**: Reinforcement Learning model powering adaptive traffic light phase decisions.

### AI & Computer Vision (`backend/ai_engine/`)
- **YOLOv8**: Real-time multi-class vehicle detection & ByteTrack tracking (Cars, Buses, Trucks, Motorcycles, Persons).
- **Custom Indian Enforcement Model**: Specialized YOLO model trained to detect License Plates, Helmets, and Motorcycles.
- **EasyOCR Engine**: Optical Character Recognition engine optimized for Indian vehicle number plates.

### Web Dashboard (`frontend/`)
- **React 19 + Vite + TypeScript**: High-performance single page application.
- **Tailwind CSS + Lucide Icons**: Modern dashboard styling.
- **Leaflet & React-Leaflet**: Live GIS intersection and traffic congestion mapping.

---

## 🚀 Getting Started

Follow these step-by-step instructions to clone, configure, and boot the entire system on your local machine.

### 1. Prerequisites
Ensure your computer has the following software installed:
- **[Python 3.9+](https://www.python.org/downloads/)**: Required for the FastAPI backend and AI pipelines.
- **[Node.js v18+](https://nodejs.org/)**: Required for the React Web Dashboard (includes `npm`).
- **[Git](https://git-scm.com/downloads)**: Required for version control.
- **[Supabase Account](https://supabase.com/)**: Required for the cloud Postgres database.
- **NVIDIA GPU with CUDA** *(Optional but Highly Recommended)*: Accelerates YOLOv8 and OCR inference. If unavailable, the system automatically falls back to CPU execution.

### 2. Clone the Repository
```bash
git clone https://github.com/baadshah697/Smart_Traffic_Management_System.git
cd Smart_Traffic_Management_System
```

### 3. Configure Environment Variables
Copy the template `.env.example` to `.env` in the root folder:
```bash
cp .env.example .env
```
Fill in your Supabase credentials in `.env`:
```ini
SUPABASE_URL="https://your-project.supabase.co"
SUPABASE_SERVICE_ROLE_KEY="your-supabase-service-role-key"
JWT_SECRET_KEY="your-custom-jwt-secret"
JWT_ALGORITHM="HS256"
```

For the frontend, copy `frontend/.env.example` to `frontend/.env`:
```bash
cp frontend/.env.example frontend/.env
```

### 4. Initialize Database Tables
1. Open your [Supabase Dashboard](https://supabase.com/dashboard/projects) and select **SQL Editor**.
2. Run the SQL scripts located in the `database/` directory in this exact order:
   - `00_master_schema.sql` *(Creates all tables, vehicles registry, and ENUM types)*
   - `schema.sql` *(Helper functions and enforcement triggers)*
   - `rls_policies.sql` *(Row Level Security rules)*
   - `intersection_status.sql` *(Reinforcement Learning tables)*
   - `triggers.sql` *(Automated payments and status triggers)*

### 5. Download AI Model Weights (Critical)
Because binary model files exceed GitHub file limits, model weights are hosted on Google Drive:

👉 **[Download AI Models from Google Drive](https://drive.google.com/drive/folders/1WHVeHnA-8CUa1F0rWcdnSnSyWjpA_pYj?usp=sharing)**

Place the downloaded files into the `ai_models/` folder:
- `yolov8n.pt` - Base YOLOv8 Nano vehicle detection model
- `best.pt` - Custom trained YOLO model for Indian traffic violations
- `vitals_ppo_model.zip` - Stable-Baselines3 PPO traffic light agent
- `vitals_ppo_vecnorm.pkl` - PPO normalization parameters

---

## 💻 Running the System

You will need **two separate terminals** open: one for the Backend, and one for the Frontend.

### Step 1: Start the Backend (FastAPI + AI Engine)

**1. Create and Activate a Virtual Environment**
```bash
# Windows:
python -m venv venv
venv\Scripts\activate

# Mac / Linux:
python3 -m venv venv
source venv/bin/activate
```

**2. Install Python Dependencies**
* **NVIDIA GPU (CUDA)**: Install PyTorch with CUDA support first from [PyTorch.org](https://pytorch.org/get-started/locally/), then:
```bash
pip install -r requirements.txt
```
* **CPU-Only**:
```bash
pip install -r requirements.txt
```

**3. Boot the FastAPI Server**
```bash
python -m uvicorn backend.main:app --reload
```
The API server will launch at `http://127.0.0.1:8000`. You can inspect the interactive Swagger docs at `http://127.0.0.1:8000/docs`.

### Step 2: Start the Web Dashboard (React + Vite)

In a new terminal window:

**1. Navigate to the Frontend Directory**
```bash
cd frontend
```

**2. Install Dependencies**
```bash
npm install
```

**3. Boot Vite Dev Server**
```bash
npm run dev
```
Open your browser and navigate to **`http://localhost:5173`**.

---

## 🛠️ Testing & Verification Tools

The `scripts/` directory contains standalone utilities for testing components in isolation:
- `scripts/verify_db.py`: Verifies Supabase database connection and table integrity.
- `scripts/test_camera.py`: Validates OpenCV video capture and camera endpoints.
- `scripts/test_detection.py`: Runs a quick YOLO detection on a sample frame.
- `scripts/test_ppo.py`: Evaluates the Reinforcement Learning PPO agent.
- `scripts/benchmark_all_test_videos.py`: Benchmarks inference FPS, tracking, and violation accuracy.
- `download_videos.py`: Downloads sample CCTV traffic videos for local testing into `backend/test_videos/`.

---

## 🗄️ Database Schema Summary
- **`congested_roads`**: Live intersection telemetry (vehicle count, congestion percentage, active light phase).
- **`violations`**: Detected infractions (type, confidence score, license plate, evidence snapshot URL).
- **`e_challans`**: Generated traffic fines linked to violations (amount, status, payment timestamp).
- **`vehicles`**: Citizen registry mapping license plates to vehicle owners and contact info.
- **`accidents`**: Accident incident logs with GIS coordinates and severity tags.

---
*Developed for the Bhopal Smart City AI Traffic Management Initiative.*
