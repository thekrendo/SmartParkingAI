# === FILE: main_window.py ===

import pickle
import sys
import os
import yaml

from PySide6.QtWidgets import (QMainWindow, QWidget, QHBoxLayout, QApplication,
                               QStatusBar, QMessageBox, QSizePolicy)
from PySide6.QtGui import QPixmap, QIcon
from PySide6.QtCore import Slot, QTimer, QPoint

from theme import Theme, ThemeManager
from control_panel import ControlPanel
from map_view import MapView, VideoThread

try:
    from roi_editor import ROIDialog

    ROI_EDITOR_AVAILABLE = True
except ImportError:
    ROI_EDITOR_AVAILABLE = False
    print("\n" + "=" * 50)
    print("=== WARNING: ROI Editor component (roi_editor.py) not found! ===")
    print("=== The 'Edit Parking Zones' button will not function.       ===")
    print("=" * 50 + "\n")


class ParkFinderApp(QMainWindow):
    CONFIG_FILE = "config.yaml"

    def __init__(self):
        super().__init__()
        self.config = self.load_config()
        self.setWindowIcon(QIcon("parkicon.ico"))

        self.theme_manager = ThemeManager(Theme.LIGHT)
        self.current_theme = Theme.LIGHT

        self.video_thread = None
        self.current_polygons = []
        self.assigned_spot = -1
        self.highlighted_spot = -1
        self.last_user_info = ("", "")
        self.current_street_name = None

        self.initUI()
        self._initialize_street_dependent_settings()

    def load_config(self):
        if not os.path.exists(self.CONFIG_FILE):
            print(f"WARNING: Configuration file '{self.CONFIG_FILE}' not found.")
            default_config = {
                'global_paths': {
                    'model': 'path/to/your/default_yolo.pt'
                },
                'global_detection': {
                    'car_class_id': 2,
                    'confidence_threshold': 0.35
                },
                'streets': {
                    'Main Street': {
                        'video': 'path/to/your/main_video.mp4',
                        'roi': 'path/to/your/main_rois.pkl',
                        'roi_reference_image': 'path/to/your/main_reference.png'
                    },
                }
            }
            try:
                with open(self.CONFIG_FILE, 'w', encoding='utf-8') as f:
                    yaml.dump(default_config, f, default_flow_style=False, sort_keys=False)
                msg = (f"Default configuration file '{self.CONFIG_FILE}' created.\n"
                       f"Please edit the paths and parameters inside.")
                print(msg)
                QMessageBox.information(self, "Config Created", msg)
                return default_config
            except Exception as e:
                print(f"ERROR creating default config file: {e}")
                QMessageBox.critical(self, "Config Error",
                                     f"Failed to create default config file:\n{self.CONFIG_FILE}\nError: {e}")
                return {}

        try:
            with open(self.CONFIG_FILE, 'r', encoding='utf-8') as f:
                config_data = yaml.safe_load(f)
            if not config_data:
                print(f"ERROR: Config file '{self.CONFIG_FILE}' is empty or invalid.")
                return self.load_config()

            if 'global_paths' not in config_data or \
                    'streets' not in config_data or \
                    ('detection' not in config_data and 'global_detection' not in config_data):
                QMessageBox.warning(self, "Config Error",
                                    f"Configuration file '{self.CONFIG_FILE}' is missing essential sections (global_paths, streets, global_detection/detection). Consider deleting it to regenerate a default one.")

            if 'detection' in config_data and 'global_detection' not in config_data:
                config_data['global_detection'] = config_data.pop('detection')
                print("Migrated 'detection' to 'global_detection' in config.")

            print(f"Configuration loaded from '{self.CONFIG_FILE}'.")
            return config_data
        except Exception as e:
            print(f"ERROR loading configuration from '{self.CONFIG_FILE}': {e}")
            QMessageBox.critical(self, "Config Error",
                                 f"Failed to load configuration file:\n{self.CONFIG_FILE}\nError: {e}")
            return {}

    def save_config(self):
        try:
            with open(self.CONFIG_FILE, 'w', encoding='utf-8') as f:
                yaml.dump(self.config, f, default_flow_style=False, sort_keys=False)
            self.show_status_message(f"Configuration saved to {self.CONFIG_FILE}", 3000)
            print(f"Configuration saved to {self.CONFIG_FILE}")
        except Exception as e:
            print(f"ERROR saving configuration to '{self.CONFIG_FILE}': {e}")
            QMessageBox.critical(self, "Config Save Error",
                                 f"Failed to save configuration file:\n{self.CONFIG_FILE}\nError: {e}")

    def get_street_config(self, street_name):
        return self.config.get('streets', {}).get(street_name, {})

    def get_current_street_paths(self):
        if not self.current_street_name: return {}
        street_cfg = self.get_street_config(self.current_street_name)
        return {
            'video': street_cfg.get('video'),
            'roi': street_cfg.get('roi'),
            'roi_reference_image': street_cfg.get('roi_reference_image'),
            'model': street_cfg.get('model')
        }

    def initUI(self):
        self.setWindowTitle('AuraPark')
        self.setGeometry(100, 100, 1150, 720)

        main_widget = QWidget()
        main_layout = QHBoxLayout()

        self.control_panel = ControlPanel()
        if self.config and 'streets' in self.config:
            street_names = list(self.config['streets'].keys())
            self.control_panel.populate_street_selector(street_names)
            if street_names:
                self.current_street_name = self.control_panel.get_selected_street()
            else:
                QMessageBox.warning(self, "Config Error", "No streets defined in the configuration file.")
                self.current_street_name = None
        else:
            QMessageBox.critical(self, "Config Error", "Street configurations not found in config file.")
            self.control_panel.populate_street_selector(["Error: No Streets"])
            self.current_street_name = None

        self.map_view = MapView(main_window_ref=self)
        main_layout.addWidget(self.control_panel)
        main_layout.addWidget(self.map_view, 1)
        main_widget.setLayout(main_layout)
        self.setCentralWidget(main_widget)

        self.statusBar = QStatusBar()
        self.setStatusBar(self.statusBar)
        self.show_status_message("Application started. Select street, enter info, start search.", 5000)

        self.control_panel.find_parking_requested.connect(self.handle_find_parking)
        self.control_panel.assign_spot_requested.connect(self.handle_assign_spot)
        self.control_panel.cancel_assignment_requested.connect(self.handle_cancel_assignment)
        self.control_panel.edit_rois_requested.connect(self.open_roi_editor)
        self.control_panel.close_requested.connect(self.close_application)
        self.control_panel.toggle_theme_requested.connect(self.handle_toggle_theme)
        self.control_panel.free_spot_highlight_requested.connect(self.handle_highlight_request)
        self.control_panel.street_changed_signal.connect(self.handle_street_change)

    def _initialize_street_dependent_settings(self):
        if not self.current_street_name:
            self.show_status_message("No street selected or configured.", 5000)
            self.current_polygons = []
            self.map_view.update_polygons_slot([])
            return
        self.load_initial_rois()

    @Slot(str)
    def handle_street_change(self, street_name):
        if self.current_street_name == street_name: return

        self.show_status_message(f"Street changed to: {street_name}", 3000)
        if self.video_thread and self.video_thread.isRunning():
            self.stop_video_stream()
            if self.assigned_spot != -1:
                self.handle_cancel_assignment(show_message=False)
            self.control_panel.update_free_spots({})
            self.map_view.spot_states = {}
            self.map_view.video_display.setPixmap(QPixmap())
            self.map_view.video_display.setText("Video stream stopped due to street change.")

        self.current_street_name = street_name
        self.current_polygons = []
        self.load_initial_rois()
        self.control_panel.update_assignment_buttons(is_assigned=(self.assigned_spot != -1), is_stream_running=False)

    def load_initial_rois(self):
        if not self.current_street_name:
            self.show_status_message("Cannot load ROIs: No street selected.", 3000)
            self.current_polygons = []
            self.map_view.update_polygons_slot([])
            return

        street_paths = self.get_current_street_paths()
        current_roi_path = street_paths.get('roi')

        if not current_roi_path or not os.path.exists(current_roi_path):
            msg = (f"ROI file path not set or file not found for street '{self.current_street_name}'.\n"
                   f"Expected at: {current_roi_path}\n"
                   f"Check config file or use 'Edit Parking Zones'.")
            self.show_status_message(msg, 7000)
            print(f"WARNING: {msg}")
            self.current_polygons = []
            self.map_view.update_polygons_slot([])
            return
        try:
            with open(current_roi_path, 'rb') as f:
                loaded_data = pickle.load(f)
            if isinstance(loaded_data, list) and \
                    all(isinstance(p, list) and len(p) == 4 and \
                        all(isinstance(pt, tuple) and len(pt) == 2 for pt in p) for p in loaded_data):
                self.current_polygons = loaded_data
                msg = f"Loaded {len(self.current_polygons)} ROIs for '{self.current_street_name}' from {os.path.basename(current_roi_path)}"
                self.show_status_message(msg, 3000)
                print(msg)
                self.map_view.update_polygons_slot(self.current_polygons)
                if not self.current_polygons:
                    self.show_status_message(f"WARNING: ROI file for '{self.current_street_name}' is empty.", 5000)
            else:
                raise TypeError("Invalid data format in ROI file.")
        except Exception as e:
            QMessageBox.critical(self, "Error Loading ROIs",
                                 f"Could not load ROIs for '{self.current_street_name}' from {current_roi_path}:\n{e}")
            self.current_polygons = []
            self.map_view.update_polygons_slot([])

    @Slot(str)
    def handle_find_parking(self, selected_mode):
        if selected_mode == "STOP_REQUESTED":
            self.stop_video_stream()
            if self.assigned_spot != -1: self.handle_cancel_assignment(show_message=False)
            return

        if not self.current_street_name:
            QMessageBox.warning(self, "No Street Selected", "Please select a street before starting the search.")
            return

        yolo_enabled = (selected_mode == 'YOLOV')
        video_only = (selected_mode == 'VIDEO')
        start_stream = True

        current_street_config = self.get_street_config(self.current_street_name)
        video_path = current_street_config.get('video')
        roi_path_for_checks = current_street_config.get('roi')

        model_path_to_use = current_street_config.get('model', self.config.get('global_paths', {}).get('model'))

        street_detection_cfg = current_street_config.get('detection')
        global_detection_cfg_template = self.config.get('global_detection', {})

        final_detection_cfg = {}
        if street_detection_cfg:
            final_detection_cfg['car_class_id'] = street_detection_cfg.get('car_class_id',
                                                                           global_detection_cfg_template.get(
                                                                               'car_class_id', 2))
            final_detection_cfg['confidence_threshold'] = street_detection_cfg.get('confidence_threshold',
                                                                                   global_detection_cfg_template.get(
                                                                                       'confidence_threshold', 0.35))
        else:
            final_detection_cfg = global_detection_cfg_template.copy()
            if 'car_class_id' not in final_detection_cfg: final_detection_cfg['car_class_id'] = 2
            if 'confidence_threshold' not in final_detection_cfg: final_detection_cfg['confidence_threshold'] = 0.35

        print(f"[MainWindow] For street '{self.current_street_name}', using model: '{model_path_to_use}'")
        print(
            f"[MainWindow] Detection params: CarClassID={final_detection_cfg.get('car_class_id')}, ConfThresh={final_detection_cfg.get('confidence_threshold')}")

        if not self.current_polygons and not video_only:
            QMessageBox.warning(self, "ROIs Missing",
                                f"Parking zones (ROIs) are not loaded for street '{self.current_street_name}'.\n'{selected_mode}' mode requires ROIs. Load or define them.")
            start_stream = False

        if start_stream and (not video_path or not os.path.exists(video_path)):
            QMessageBox.critical(self, "Video Error",
                                 f"Video file path for street '{self.current_street_name}' not found or invalid: {video_path}")
            start_stream = False

        if start_stream and yolo_enabled and not video_only:
            if not model_path_to_use or not os.path.exists(model_path_to_use):
                QMessageBox.critical(self, "Model Error",
                                     f"YOLO model file path not found or invalid for street '{self.current_street_name}': {model_path_to_use}")
                start_stream = False

        if start_stream and not video_only and (not roi_path_for_checks or not os.path.exists(roi_path_for_checks)):
            QMessageBox.critical(self, "ROI File Error",
                                 f"ROI file path for street '{self.current_street_name}' not found or invalid: {roi_path_for_checks}")
            start_stream = False

        is_running = self.video_thread is not None and self.video_thread.isRunning()
        self.control_panel.update_assignment_buttons(is_assigned=(self.assigned_spot != -1),
                                                     is_stream_running=is_running or start_stream)
        self.control_panel.update_search_status(is_running or start_stream)

        if start_stream:
            if self.assigned_spot != -1: self.handle_cancel_assignment(show_message=False)
            self.handle_highlight_request(-1)

            self.start_video_stream(
                video_path_street=video_path,
                roi_path_street=roi_path_for_checks,
                model_path_to_use=model_path_to_use,
                detection_cfg=final_detection_cfg,
                yolo_enabled=yolo_enabled,
                video_only=video_only
            )

    def start_video_stream(self, video_path_street, roi_path_street, model_path_to_use, detection_cfg, yolo_enabled,
                           video_only):
        if self.video_thread is not None and self.video_thread.isRunning():
            QMessageBox.information(self, "Already Running", "Search is already running.")
            return
        self.stop_video_stream()

        print(
            f"MainWindow: Starting video thread for street '{self.current_street_name}' using model '{model_path_to_use}'")
        self.video_thread = VideoThread(
            video_path=video_path_street,
            roi_path=roi_path_street,
            model_path=model_path_to_use,
            detection_config=detection_cfg,
            yolo_enabled=yolo_enabled,
            video_only_mode=video_only
        )

        self.video_thread.set_assigned_spot(self.assigned_spot)
        self.video_thread.set_highlighted_spot(self.highlighted_spot)

        self.video_thread.update_frame.connect(self.map_view.update_frame_slot)
        self.video_thread.update_spot_states.connect(self.handle_spot_states_update)
        self.video_thread.status_update.connect(self.show_status_message)
        self.video_thread.finished.connect(self.on_video_thread_finished)
        self.video_thread.start()

        self.control_panel.find_parking_btn.setText("Stop Search")
        self.show_status_message(f"Starting video processing for {self.current_street_name}...", 0)
        self.control_panel.update_assignment_buttons(is_assigned=(self.assigned_spot != -1), is_stream_running=True)
        self.control_panel.update_search_status(True)

    def stop_video_stream(self):
        if self.video_thread is not None and self.video_thread.isRunning():
            print("MainWindow: Stopping video thread...")
            self.show_status_message("Stopping video processing...", 0)
            self.video_thread.stop()
            if not self.video_thread.wait(3000):
                print("MainWindow: Video thread termination timeout. Forcing termination.")
                self.video_thread.terminate()
                self.video_thread.wait()
            print("MainWindow: Video thread stopped.")
        self.video_thread = None

    @Slot(list)
    def handle_spot_states_update(self, spot_states_list):
        spot_states = dict(spot_states_list)
        self.map_view.update_spot_states_slot(spot_states)
        self.control_panel.update_free_spots(spot_states)

        is_running = self.video_thread is not None and self.video_thread.isRunning()
        self.control_panel.update_assignment_buttons(is_assigned=(self.assigned_spot != -1),
                                                     is_stream_running=is_running)

        if self.assigned_spot != -1 and spot_states.get(self.assigned_spot) == 'occupied':
            spot_that_became_occupied = self.assigned_spot
            user_name, car_info = self.last_user_info
            self.handle_cancel_assignment(show_message=False)
            reply = QMessageBox.question(self, "Spot Taken!",
                                         f"ALERT: Your assigned spot {spot_that_became_occupied} on {self.current_street_name} was just taken!\n\n"
                                         f"Do you want to automatically assign the next available free spot?",
                                         QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
                                         QMessageBox.StandardButton.Yes)
            if reply == QMessageBox.StandardButton.Yes:
                self.show_status_message(
                    f"Spot {spot_that_became_occupied} taken. Finding a new spot for {user_name}...", 3000)
                QTimer.singleShot(100, lambda u=user_name, c=car_info: self.handle_assign_spot(u, c))
            else:
                self.show_status_message(f"Spot {spot_that_became_occupied} assignment cancelled.", 3000)
                self.control_panel.update_assigned_spot_info(
                    "<font color='red'>Assignment cancelled: Spot taken!</font>")

    @Slot()
    def on_video_thread_finished(self):
        print("MainWindow: Video thread finished signal received.")
        self.handle_highlight_request(-1)
        self.control_panel.find_parking_btn.setText("Find Parking")
        self.control_panel._update_find_parking_button_state()
        self.control_panel.update_assignment_buttons(is_assigned=(self.assigned_spot != -1), is_stream_running=False)
        self.control_panel.update_search_status(False)
        self.map_view.video_display.setText("Video stream stopped.")
        self.map_view.video_display.setPixmap(QPixmap())
        self.map_view.spot_states = {}
        self.control_panel.update_free_spots({})
        self.show_status_message("Video processing finished or stopped.", 3000)

    @Slot(str, str)
    def handle_assign_spot(self, user_name, car_info):
        if user_name and car_info: self.last_user_info = (user_name, car_info)
        print(f"MainWindow: Assign request for '{user_name}' ({car_info}) on street '{self.current_street_name}'")

        if self.assigned_spot != -1:
            QMessageBox.information(self, "Already Assigned", f"You already have spot {self.assigned_spot}.")
            return
        if not self.video_thread or not self.video_thread.isRunning():
            QMessageBox.warning(self, "Search Not Running", "Start 'Find Parking' before assigning.")
            return
        found_spot = -1
        for spot_index, status in sorted(self.map_view.spot_states.items()):
            if status == 'free':
                found_spot = spot_index
                break
        if found_spot != -1:
            self.assigned_spot = found_spot
            if self.highlighted_spot == self.assigned_spot: self.handle_highlight_request(-1)
            if self.video_thread: self.video_thread.set_assigned_spot(self.assigned_spot)
            assignment_message = f"<b>Assigned Spot: {self.assigned_spot}</b> ({self.current_street_name})<br>User: {user_name}<br>Car: {car_info}"
            self.control_panel.update_assigned_spot_info(assignment_message)
            self.control_panel.update_assignment_buttons(is_assigned=True, is_stream_running=True)
            self.show_status_message(
                f"Spot {self.assigned_spot} on {self.current_street_name} assigned to {user_name}.", 5000)
            print(f"Spot {self.assigned_spot} assigned.")
        else:
            QMessageBox.information(self, "No Free Spots",
                                    f"Sorry, no free spots are available on {self.current_street_name} right now.")
            self.control_panel.update_assigned_spot_info("Assignment failed: No free spots found.")
            self.control_panel.update_assignment_buttons(is_assigned=False, is_stream_running=True)

    @Slot(bool)
    def handle_cancel_assignment(self, show_message=True):
        if self.assigned_spot != -1:
            spot_to_cancel = self.assigned_spot
            print(f"MainWindow: Cancelling assignment for spot {spot_to_cancel} on street '{self.current_street_name}'")
            self.assigned_spot = -1
            self.last_user_info = ("", "")
            if self.video_thread and self.video_thread.isRunning(): self.video_thread.set_assigned_spot(-1)
            self.control_panel.update_assigned_spot_info("Assigned spot: -")
            is_running = self.video_thread is not None and self.video_thread.isRunning()
            self.control_panel.update_assignment_buttons(is_assigned=False, is_stream_running=is_running)
            if show_message:
                QMessageBox.information(self, "Assignment Cancelled",
                                        f"Assignment for spot {spot_to_cancel} on {self.current_street_name} has been cancelled.")
        else:
            print("MainWindow: No active assignment to cancel.")

    @Slot(int)
    def handle_highlight_request(self, spot_index):
        if self.highlighted_spot != spot_index:
            self.highlighted_spot = spot_index
            if self.video_thread and self.video_thread.isRunning():
                self.video_thread.set_highlighted_spot(self.highlighted_spot)

    @Slot()
    def open_roi_editor(self):
        if not ROI_EDITOR_AVAILABLE:
            QMessageBox.critical(self, "Error", "ROI Editor component (roi_editor.py) not available.")
            return
        if not self.current_street_name:
            QMessageBox.warning(self, "No Street Selected", "Please select a street to edit its ROIs.")
            return

        self.show_status_message(f"Opening ROI Editor for {self.current_street_name}...", 0)
        was_running = False
        if self.video_thread and self.video_thread.isRunning():
            reply = QMessageBox.question(self, "Stop Video Processing?",
                                         "Video processing must be stopped to edit parking zones.\nStop now?",
                                         QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
                                         QMessageBox.StandardButton.Yes)
            if reply == QMessageBox.StandardButton.Yes:
                self.stop_video_stream()
                QApplication.processEvents()
                was_running = True
                if self.assigned_spot != -1: self.handle_cancel_assignment(show_message=False)
            else:
                self.show_status_message("ROI editing cancelled.", 3000)
                return

        current_street_paths = self.get_current_street_paths()
        roi_path_for_street = current_street_paths.get('roi')
        ref_image_path_for_street = current_street_paths.get('roi_reference_image')

        if not ref_image_path_for_street or not os.path.exists(ref_image_path_for_street):
            QMessageBox.warning(self, "Reference Image Missing",
                                f"Reference image for street '{self.current_street_name}' not found or not configured: {ref_image_path_for_street}\nROI Editor might not function correctly.")
        try:
            dialog = ROIDialog(config=self.config, current_roi_path=roi_path_for_street,
                               current_reference_image_path=ref_image_path_for_street, parent=self)
            dialog.rois_saved.connect(self.handle_rois_saved)
            dialog.exec()
        except Exception as e:
            QMessageBox.critical(self, "ROI Editor Error",
                                 f"Failed to open ROI editor for {self.current_street_name}:\n{e}")
            return
        self.show_status_message("", 1)

    @Slot(str)
    def handle_rois_saved(self, new_roi_path):
        if not self.current_street_name:
            QMessageBox.critical(self, "Error", "ROIs saved, but could not associate with a street.")
            return
        self.show_status_message(
            f"ROIs for '{self.current_street_name}' saved to {os.path.basename(new_roi_path)}. Reloading...", 3000)
        if self.current_street_name in self.config.get('streets', {}):
            self.config['streets'][self.current_street_name]['roi'] = new_roi_path
            self.save_config()
        else:
            QMessageBox.warning(self, "Config Warning",
                                f"Could not update ROI path in config for street '{self.current_street_name}'.")
        self.load_initial_rois()

    @Slot(str, int)
    def show_status_message(self, message, timeout=3000):
        if hasattr(self, 'statusBar') and self.statusBar:
            if timeout > 0:
                self.statusBar.showMessage(message, timeout)
            else:
                self.statusBar.showMessage(message)
        else:
            print(f"[Status Bar Unavailable] {message}")

    @Slot()
    def handle_toggle_theme(self):
        new_theme = Theme.DARK if self.current_theme == Theme.LIGHT else Theme.LIGHT
        success = self.theme_manager.set_theme(new_theme)
        if success:
            self.current_theme = new_theme
            self.show_status_message(f"Theme switched to {new_theme.value.capitalize()}.", 3000)
        else:
            QMessageBox.warning(self, "Theme Error", "Failed to switch theme.")

    def close_application(self):
        print("MainWindow: Close requested.")
        self.stop_video_stream()
        self.close()

    def closeEvent(self, event):
        print("MainWindow: closeEvent triggered.")
        self.stop_video_stream()
        self.save_config()
        event.accept()