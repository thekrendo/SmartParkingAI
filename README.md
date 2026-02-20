# SmartParkingAI (AuraPark) 🚗💡

SmartParkingAI is a desktop application for automated real-time monitoring and management of parking lots. The main goal of the system is to recognize the occupancy of parking spaces using CCTV cameras and computer vision, minimizing the need for manual control.

## ✨ Features

- **Real-time AI Object Detection:** Built with **YOLOv11** (`yolo11n.pt`) to detect cars accurately and efficiently from video streams.
- **Smart Region of Interest (ROI) Mapping:** Draw custom polygons over parking spots using an intuitive GUI editor. The system calculates intersecting bounding boxes and centers of mass to determine occupancy.
- **Multi-threaded Video Processing:** Asynchronous video handling ensures a smooth, non-blocking User Interface.
- **Interactive UI Dashboard:** Built with PySide6 (Qt for Python). It includes:
  - Visual status for each parking spot (Free, Occupied, Assigned).
  - A control panel for operators to manage user spaces.
  - Light and Dark theme modes utilizing `qdarktheme`.
- **Resource Optimized:** Uses Ultralytics *Nano* model weights for high FPS execution even on hardware without dedicated high-end GPUs.

## 🛠️ Technology Stack

- **Artificial Intelligence & Computer Vision:** 
  - [Ultralytics YOLOv11](https://github.com/ultralytics/ultralytics) (Neural Networks)
  - [OpenCV](https://opencv.org/) & NumPy (Math & Polygon Intersections)
- **Frontend & Backend (GUI):**
  - Python
  - [PySide6](https://doc.qt.io/qtforpython/) (Qt framework)

## 🚀 How It Works Under the Hood

1. **Object Detection:** The neural network receives the video stream and performs detection, looking specifically for the `car` class.
2. **Intersection Analysis:** The AI returns bounding box coordinates. OpenCV calculates the center of mass for these objects and checks if they fall inside the operator-defined parking zone polygons (ROIs).
3. **State Management:** Depending on the mathematical crossover, spots dynamically change their UI state (Green = Free, Red = Occupied, Orange = User Assigned) and update the dashboard statistics.

## 📦 Installation & Setup

1. Clone the repository:
   ```bash
   git clone https://github.com/thekrendo/SmartParkingAI.git
   cd SmartParkingAI
   ```
2. Install the necessary dependencies (ensure you have Python 3.9+):
   ```bash
   pip install ultralytics opencv-python numpy PySide6 pyqtdarktheme pyyaml
   ```
3. Run the application:
   ```bash
   python main.py
   ```

*Note: You need to configure a video source (`.mp4` or camera feed) and define ROIs using the built-in "Edit Parking Zones" tool on first launch.*

## 📸 Screenshots

*(To be added)*

## 📄 License & Restrictions

**© 2024-2026 Dmytro Fraire (thekrendo). All Rights Reserved.**

This repository and its contents are provided strictly for **portfolio demonstration and educational viewing purposes only**. 

You are **NOT** permitted to:
- Copy, clone, or distribute this code.
- Use it for any commercial or non-commercial projects.
- Modify, adapt, or create derivative works from it.

Any unauthorized use, reproduction, or distribution of this software, its algorithms, or UI design is strictly prohibited.
