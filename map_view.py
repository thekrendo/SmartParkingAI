# === FILE: map_view.py ===

from PySide6.QtWidgets import QLabel, QVBoxLayout, QWidget, QSizePolicy
from PySide6.QtWidgets import QAbstractItemView
from PySide6.QtCore import QThread, Signal, Qt, Slot, QPoint, QRect
from PySide6.QtGui import QImage, QPixmap, QPainter, QPen, QColor, QPolygon
import cv2
import torch
import pickle
import numpy as np
from ultralytics import YOLO
import time
import os
import traceback

try:
    from utilils import YOLO_Detection, drawPolygons

    print("Successfully imported functions from utilils.py for map_view")
except ImportError as e:
    print(f"ERROR: Could not import from utilils.py in map_view. {e}")


    def YOLO_Detection(model, frame, conf=0.35, car_class_id=2):
        return [], [], {}, []


    def drawPolygons(frame, points_list, **kwargs):
        return frame, {}, 0, set()


class VideoThread(QThread):
    update_frame = Signal(QImage)
    update_spot_states = Signal(list)
    status_update = Signal(str)

    def __init__(self, video_path, roi_path, model_path, detection_config,
                 yolo_enabled=False, video_only_mode=False):
        super().__init__()
        self.running = True
        try:
            self.device = torch.device('cuda' if torch.cuda.is_available() else 'cpu')
        except Exception as e:
            print(f"ERROR initializing torch device: {e}. Defaulting to CPU.")
            traceback.print_exc()
            self.device = torch.device('cpu')

        self.frame_width = 0
        self.frame_height = 0
        self.model = None
        self.posList = []
        self.assigned_spot_index = -1
        self.highlighted_spot_index = -1

        self.video_path_street = video_path
        self.roi_path_street = roi_path
        self.model_path_global = model_path

        self.car_class_id = detection_config.get('car_class_id', 2)
        self.confidence_threshold = detection_config.get('confidence_threshold', 0.35)

        self.effective_yolo_enabled = (yolo_enabled and
                                       not video_only_mode and
                                       self.model_path_global and
                                       os.path.exists(self.model_path_global))
        self.effective_video_only_mode = video_only_mode

        self.class_names = {}

        self.status_update.emit(f"Initializing video thread... Device: {self.device}")
        print(f"[VideoThread INIT DEBUG] For video: {self.video_path_street}")
        print(f"[VideoThread INIT DEBUG] Using ROI path: {self.roi_path_street}")
        print(f"[VideoThread INIT DEBUG] Using model path: {self.model_path_global}")
        print(
            f"[VideoThread INIT DEBUG] Effective YOLO: {self.effective_yolo_enabled}, Video Only: {self.effective_video_only_mode}")
        print(f"[VideoThread INIT DEBUG] Using CarClassID: {self.car_class_id}, Using ConfThresh: {self.confidence_threshold}")

        try:
            if self.effective_yolo_enabled:
                self.status_update.emit(f"Loading YOLO model from: {self.model_path_global}")
                self.model = YOLO(self.model_path_global).to(self.device)
                if hasattr(self.model, 'names'):
                    self.class_names = self.model.names
                    self.status_update.emit(f"YOLO model loaded. Class names: {self.class_names}")
                    print(f"[VideoThread INIT DEBUG] Model loaded. Class names: {self.class_names}")
                else:
                    self.status_update.emit("YOLO model loaded, but class names attribute not found.")
                    print("[VideoThread INIT DEBUG] Model loaded, but 'names' attribute missing from model object.")
            elif yolo_enabled and not video_only_mode:
                self.status_update.emit(
                    f"WARNING: YOLO mode requested but model path invalid/missing ('{self.model_path_global}'). YOLO disabled.")

            if not self.effective_video_only_mode:
                if self.roi_path_street and os.path.exists(self.roi_path_street):
                    self.status_update.emit(f"Loading parking positions from: {self.roi_path_street}")
                    try:
                        with open(self.roi_path_street, 'rb') as f:
                            self.posList = pickle.load(f)
                        self.status_update.emit(f"Loaded {len(self.posList)} parking positions for current street.")
                        print(f"[VideoThread INIT DEBUG] Loaded {len(self.posList)} ROIs from {self.roi_path_street}")
                        if not self.posList:
                            print(f"[VideoThread INIT DEBUG] WARNING: ROI file {self.roi_path_street} is empty.")
                    except Exception as e:
                        self.status_update.emit(
                            f"ERROR loading ROI file '{os.path.basename(self.roi_path_street or '')}': {e}")
                        self.posList = []
                else:
                    self.status_update.emit(
                        f"WARNING: ROI file for current street not found or path not set ('{self.roi_path_street}'). Parking zones disabled for detection.")
                    print(
                        f"[VideoThread INIT DEBUG] WARNING: ROI file not found or path not set: {self.roi_path_street}")
                    self.posList = []
            else:
                self.status_update.emit("Running in VIDEO only mode. Parking zones (ROIs) disabled.")
                self.posList = []

            if not self.video_path_street or not os.path.exists(self.video_path_street):
                self.status_update.emit(
                    f"ERROR: Video file for current street not found or path not set: '{self.video_path_street}'")
                self.running = False
            else:
                self.status_update.emit(f"Opening video source: {self.video_path_street}")
                self.cap = cv2.VideoCapture(self.video_path_street)
                if not self.cap.isOpened():
                    self.status_update.emit(f"ERROR: Could not open video file: {self.video_path_street}")
                    self.running = False
                else:
                    self.frame_width = int(self.cap.get(cv2.CAP_PROP_FRAME_WIDTH))
                    self.frame_height = int(self.cap.get(cv2.CAP_PROP_FRAME_HEIGHT))
                    self.status_update.emit(f"Video opened. Frame: {self.frame_width}x{self.frame_height}")
        except Exception as e:
            self.status_update.emit(f"CRITICAL ERROR during VideoThread initialization: {e}")
            traceback.print_exc()
            self.running = False

    @Slot(int)
    def set_assigned_spot(self, spot_index):
        self.assigned_spot_index = spot_index

    @Slot(int)
    def set_highlighted_spot(self, spot_index):
        self.highlighted_spot_index = spot_index

    def run(self):
        if not self.running or not hasattr(self, 'cap') or not self.cap.isOpened():
            self.status_update.emit("Video capture failed or thread stopped before starting.")
            if hasattr(self, 'cap') and self.cap: self.cap.release()
            return

        frame_count = 0
        start_time = time.time()
        self.status_update.emit("Video processing started.")

        is_visual_street = self.video_path_street and "trainer1.mp4" in self.video_path_street

        while self.running:
            ret, frame = self.cap.read()
            if not ret:
                self.status_update.emit("End of video or read error. Stopping thread.")
                self.running = False
                break

            try:
                processed_frame = frame.copy()
                spot_states = {}
                occupied_count = 0
                all_detected_boxes = []
                detected_classes = []
                detected_confidences = []
                detection_centers_inside = []
                drawn_spot_box_indices = set()

                if self.effective_yolo_enabled and self.model:
                    if is_visual_street:
                        debug_conf_thresh = 0.1
                        print(
                            f"[VideoThread RUN DEBUG VisualStreet] === RAW MODEL PREDICT (conf={debug_conf_thresh}, ALL CLASSES) ===")
                        raw_results_debug = self.model.predict(frame, conf=debug_conf_thresh)
                        if raw_results_debug and raw_results_debug[0] and hasattr(raw_results_debug[0],
                                                                                  'boxes') and len(
                                raw_results_debug[0].boxes) > 0:
                            print(
                                f"[VideoThread RUN DEBUG VisualStreet] Raw Boxes Found: {len(raw_results_debug[0].boxes)}")
                            print(
                                f"[VideoThread RUN DEBUG VisualStreet] Raw Classes IDs Found: {list(set(raw_results_debug[0].boxes.cls.tolist()))}")
                        else:
                            print(
                                f"[VideoThread RUN DEBUG VisualStreet] Raw model predict (all classes, low conf={debug_conf_thresh}) returned no detections.")
                        print(f"[VideoThread RUN DEBUG VisualStreet] === END RAW MODEL PREDICT ===")

                    boxes, classes, _, confidences = YOLO_Detection(
                        self.model,
                        frame,
                        conf=self.confidence_threshold,
                        car_class_id=self.car_class_id
                    )
                    all_detected_boxes = boxes
                    detected_classes = classes
                    detected_confidences = confidences
                    if is_visual_street:
                        print(
                            f"[VideoThread RUN DEBUG VisualStreet] YOLO_Detection Output - Boxes Found: {len(all_detected_boxes)}, Classes Detected: {detected_classes}, CarClassID used: {self.car_class_id}, ConfThresh: {self.confidence_threshold}")

                    if self.posList and all_detected_boxes:
                        for i_box, box_coords in enumerate(all_detected_boxes):
                            x1, y1, x2, y2 = box_coords
                            center_x = int((x1 + x2) / 2)
                            center_y = int((y1 + y2) / 2)
                            center_point = (center_x, center_y)
                            for area_idx, area_points in enumerate(self.posList):
                                try:
                                    if isinstance(area_points, list) and len(area_points) >= 3:
                                        area_np = np.array(area_points, dtype=np.int32)
                                        if cv2.pointPolygonTest(area_np, center_point, False) >= 0:
                                            detection_centers_inside.append((center_x, center_y, i_box))
                                except Exception as poly_err:
                                    print(f"Error checking point in polygon ROI idx {area_idx}: {poly_err}")
                        if is_visual_street:
                            print(
                                f"[VideoThread RUN DEBUG VisualStreet] Detection centers inside ROIs: {detection_centers_inside}")

                if not self.effective_video_only_mode and self.posList:
                    processed_frame, spot_states, occupied_count, drawn_spot_box_indices = drawPolygons(
                        frame=processed_frame,
                        points_list=self.posList,
                        detection_centers_inside=detection_centers_inside,
                        detected_boxes=all_detected_boxes,
                        assigned_spot_index=self.assigned_spot_index,
                        highlight_spot_index=self.highlighted_spot_index,
                        show_status_text=True
                    )
                    if is_visual_street:
                        print(f"[VideoThread RUN DEBUG VisualStreet] Spot states from drawPolygons: {spot_states}")
                elif not self.effective_video_only_mode and not self.posList:
                    cv2.putText(processed_frame, "ROIs not loaded for this street", (50, 50),
                                cv2.FONT_HERSHEY_SIMPLEX, 1, (0, 0, 255), 2, cv2.LINE_AA)
                    spot_states = {}
                    occupied_count = 0

                if self.effective_yolo_enabled and all_detected_boxes:
                    general_bbox_color = (0, 150, 255)
                    for i, box in enumerate(all_detected_boxes):
                        if i not in drawn_spot_box_indices:
                            x1, y1, x2, y2 = map(int, box)
                            cv2.rectangle(processed_frame, (x1, y1), (x2, y2), general_bbox_color, 2)
                            if i < len(detected_classes) and i < len(detected_confidences) and self.class_names:
                                class_id = int(detected_classes[i])
                                class_name = self.class_names.get(class_id, f"ID:{class_id}")
                                conf = detected_confidences[i]
                                label = f"{class_name} {conf:.2f}"
                                cv2.putText(processed_frame, label, (x1, y1 - 10),
                                            cv2.FONT_HERSHEY_SIMPLEX, 0.5, general_bbox_color, 1, cv2.LINE_AA)

                if not self.effective_video_only_mode:
                    total_spots = len(self.posList) if self.posList else 0
                    assigned_count = 1 if self.assigned_spot_index != -1 and total_spots > 0 else 0
                    available_count = max(0, total_spots - occupied_count - assigned_count)

                    text_color_cnt = (0, 0, 0)
                    bg_color_cnt = (240, 240, 240)
                    cv2.rectangle(processed_frame, (10, 5), (150, 40), bg_color_cnt, -1)
                    cv2.putText(processed_frame, f"Occupied: {occupied_count}", (20, 30), cv2.FONT_HERSHEY_SIMPLEX, 0.6,
                                (0, 0, 200), 1, cv2.LINE_AA)
                    cv2.rectangle(processed_frame, (170, 5), (320, 40), bg_color_cnt, -1)
                    cv2.putText(processed_frame, f"Available: {available_count}", (180, 30), cv2.FONT_HERSHEY_SIMPLEX,
                                0.6, (0, 150, 0), 1, cv2.LINE_AA)
                    cv2.rectangle(processed_frame, (340, 5), (500, 40), bg_color_cnt, -1)
                    cv2.putText(processed_frame, f"Assigned: {assigned_count}", (350, 30), cv2.FONT_HERSHEY_SIMPLEX,
                                0.6, (200, 0, 0), 1, cv2.LINE_AA)

                frame_rgb = cv2.cvtColor(processed_frame, cv2.COLOR_BGR2RGB)
                h, w, ch = frame_rgb.shape
                bytes_per_line = ch * w
                qt_image = QImage(frame_rgb.data, w, h, bytes_per_line, QImage.Format.Format_RGB888)

                self.update_frame.emit(qt_image.copy())
                if not self.effective_video_only_mode:
                    self.update_spot_states.emit(list(spot_states.items()) if spot_states else [])

                frame_count += 1
                if frame_count % 30 == 0:
                    current_time = time.time()
                    elapsed_time = current_time - start_time
                    fps = frame_count / elapsed_time if elapsed_time > 0 else 0
                    self.status_update.emit(f"Processing... FPS: {fps:.1f}")

            except Exception as e:
                current_frame_num = self.cap.get(cv2.CAP_PROP_POS_FRAMES) if hasattr(self, 'cap') and self.cap else -1
                self.status_update.emit(f"ERROR processing frame #{int(current_frame_num)}: {e}")
                traceback.print_exc()
                continue

        self.status_update.emit("Video processing stopped.")
        if hasattr(self, 'cap') and self.cap:
            self.cap.release()
            print("Video capture released.")

    def stop(self):
        print("VideoThread: Stop requested.")
        self.running = False
        self.set_highlighted_spot(-1)


class InteractiveLabel(QLabel):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.parent_map_view = parent
        self.setMouseTracking(True)

    def mousePressEvent(self, event):
        if self.parent_map_view:
            self.parent_map_view.map_mouse_press(event)
        else:
            super().mousePressEvent(event)

    def paintEvent(self, event):
        super().paintEvent(event)
        if self.parent_map_view:
            self.parent_map_view.custom_paint_event(event)

class MapView(QWidget):
    def __init__(self, main_window_ref):
        super().__init__(main_window_ref)
        self.main_window = main_window_ref
        self.layout = QVBoxLayout()
        self.video_display = InteractiveLabel(self)
        self.video_display.setText("Parking map / video stream will appear here")
        self.video_display.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.video_display.setMinimumSize(640, 480)
        self.video_display.setStyleSheet("border: 1px solid lightgray; background-color: #f0f0f0;")
        self.video_display.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Expanding)
        self.layout.addWidget(self.video_display)
        self.setLayout(self.layout)

        self.current_pixmap = None
        self.original_frame_size = (0, 0)
        self.display_rect = QRect()
        self.posList = []
        self.spot_states = {}

    @Slot(QImage)
    def update_frame_slot(self, image: QImage):
        if image is not None and not image.isNull():
            self.original_frame_size = (image.width(), image.height())
            label_size = self.video_display.size()
            scaled_pixmap = QPixmap.fromImage(image).scaled(
                label_size, Qt.AspectRatioMode.KeepAspectRatio, Qt.TransformationMode.SmoothTransformation
            )
            self.current_pixmap = scaled_pixmap
            self.video_display.setPixmap(self.current_pixmap)
            pixmap_size = self.current_pixmap.size()
            x_offset = (label_size.width() - pixmap_size.width()) / 2
            y_offset = (label_size.height() - pixmap_size.height()) / 2
            self.display_rect = QRect(int(x_offset), int(y_offset), pixmap_size.width(), pixmap_size.height())
        else:
            self.current_pixmap = None
            self.video_display.setText("No video stream")
            self.display_rect = QRect()

    @Slot(dict)
    def update_spot_states_slot(self, states: dict):
        self.spot_states = states

    @Slot(list)
    def update_polygons_slot(self, poly_list: list):
        self.posList = poly_list

    def map_mouse_press(self, event):
        pass

    def custom_paint_event(self, event):
        pass