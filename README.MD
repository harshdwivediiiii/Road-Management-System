# RoadWatch AI - Automated Road Infrastructure Monitoring

![RoadWatch AI Banner](file:///C:/Users/alokp/.gemini/antigravity/brain/59f8052c-a37d-46d4-8ffb-bc476f861048/roadwatch_ai_banner_1775280563490.png)

## 🌟 Overview

**RoadWatch AI** is a state-of-the-art vision-based monitoring system designed to revolutionize urban infrastructure maintenance. Leveraging the power of deep learning and real-time geospatial data enrichment, RoadWatch AI transforms standard video feeds into actionable maintenance intelligence.

### 🚀 Key Features

*   **⚡ Real-Time Detection**: High-accuracy pothole and hazard detection using YOLOv8.
*   **📍 Precise Geotagging**: Automatic GPS coordinate attachment and reverse geocoding via Google Maps Geocoding API.
*   **📊 Insightful Dashboard**: Interactive visualization of hazard hotspots, trends, and repair metrics built with Plotly Dash.
*   **🛠️ Efficient Reporting**: Automated submission of hazard reports for city maintenance teams.

---

## 🛠️ Tech Stack & Tools

![Python](https://img.shields.io/badge/python-3670A0?style=for-the-badge&logo=python&logoColor=ffdd54)
![YOLOv8](https://img.shields.io/badge/YOLOv8-blue?style=for-the-badge&logo=ultralytics&logoColor=white)
![OpenCV](https://img.shields.io/badge/opencv-%23white.svg?style=for-the-badge&logo=opencv&logoColor=white)
![Flask](https://img.shields.io/badge/flask-%23000.svg?style=for-the-badge&logo=flask&logoColor=white)
![Plotly Dash](https://img.shields.io/badge/Plotly%20Dash-0080FF?style=for-the-badge&logo=Plotly&logoColor=white)
![MongoDB](https://img.shields.io/badge/MongoDB-%234ea94b.svg?style=for-the-badge&logo=mongodb&logoColor=white)
![Google Maps](https://img.shields.io/badge/Google%20Maps-4285F4?style=for-the-badge&logo=google-maps&logoColor=white)

---

## 🏗️ Architecture

1.  **Detection**: YOLOv8 scans video/dashcam feeds for infrastructure hazards.
2.  **Enrichment**: Detections are paired with spatial data via `google_maps.py`.
3.  **Storage**: Reports are securely pushed to MongoDB, with local fallback systems in `storage.py`.
4.  **Action**: Authorities use the `dashboard.py` interface to prioritize repairs based on density and severity.

### 📁 Project Structure

```text
Road-Management-System/
├── app.py                # Main Flask application (Server entrypoint)
├── dashboard.py          # Plotly Dash interactive frontend
├── config.py             # Global environment & project configuration
├── storage.py            # MongoDB and local storage operations
├── yolo_detect.py        # Core YOLOv8 inference wrapper
├── LiveCamera.py         # Subprocess for real-time camera handling
├── reporter.py           # Automated report formatting
├── geotagger.py          # Geographic enrichment helper
├── requirements.txt      # Python dependencies
├── .env                  # Configuration keys (API Keys, DB URIs)
└── static/               # Repository for auto-generated hazard images
```

---

## ⚙️ Setup & Installation

### 1️⃣ Clone and Prepare
```bash
# Clone the repository
git clone https://github.com/yourusername/Road-Management-System.git
cd Road-Management-System

# Install dependencies
pip install -r requirements.txt
```

### 2️⃣ Configure Environment
Create a `.env` file in the root directory:
```env
# Database Configuration
MONGO_URI=mongodb://localhost:27017
MONGO_DB=road_monitoring
MONGO_COLLECTION=potholes

# API Keys
GOOGLE_MAPS_API_KEY=your_google_maps_api_key_here

# Application Settings
FLASK_SECRET_KEY=generate_a_secure_key
FLASK_PORT=8050

# Model Sensitivity
DETECTION_INTERVAL=10
CONFIDENCE_THRESHOLD=0.5
```

---

## 🚦 Usage

1.  **Launch the System**:
    ```bash
    python app.py
    ```
2.  **Access the Analytics Dashboard**:
    Open [http://localhost:8050/dashboard/](http://localhost:8050/dashboard/)
3.  **Initiate Monitoring Loop**:
    Directly start the feed via: [http://localhost:8050/camera/start?source=0](http://localhost:8050/camera/start?source=0)

---

## 📡 API Reference

| Endpoint | Method | Purpose |
| :--- | :--- | :--- |
| `/health` | `GET` | System health and model connectivity check |
| `/api/report` | `POST` | High-level hazard reporting endpoint |
| `/api/potholes` | `GET` | Retrieve chronological detection records |
| `/api/stats` | `GET` | Dashboard data aggregation |
| `/api/hotspots` | `GET` | Clustered hazard density mapping |

---

## 📜 License
This project is licensed under the MIT License - see the LICENSE file for details.

---
*Created by [Your Name](https://github.com/yourusername)*
