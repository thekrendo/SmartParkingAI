# === FILE: control_panel.py ===

from PySide6.QtWidgets import (QWidget, QVBoxLayout, QLabel, QLineEdit,
                               QComboBox, QRadioButton, QPushButton, QButtonGroup,
                               QListWidget, QSizePolicy, QSpacerItem, QHBoxLayout,
                               QMessageBox, QListWidgetItem, QAbstractItemView)
from PySide6.QtCore import Signal, Slot, Qt
from PySide6.QtGui import QColor, QPalette

class ControlPanel(QWidget):
    # Signals
    assign_spot_requested = Signal(str, str)
    cancel_assignment_requested = Signal()
    edit_rois_requested = Signal()
    find_parking_requested = Signal(str)
    close_requested = Signal()
    toggle_theme_requested = Signal()
    free_spot_highlight_requested = Signal(int)
    street_changed_signal = Signal(str)

    def __init__(self):
        super().__init__()
        self.setFixedWidth(300)
        self.layout = QVBoxLayout()

        # User Input Fields
        self.layout.addWidget(QLabel('Your Name:'))
        self.name_input = QLineEdit()
        self.name_input.setPlaceholderText("Enter your name")
        self.layout.addWidget(self.name_input)
        self.layout.addWidget(QLabel('Car Make & Model:'))
        self.car_input = QLineEdit()
        self.car_input.setPlaceholderText("e.g., Toyota Camry")
        self.layout.addWidget(self.car_input)

        # Street Selection
        self.layout.addWidget(QLabel('Select Street'))
        self.street_select = QComboBox()
        self.street_select.addItem("Main Street")
        self.street_select.addItem("Visual Street")
        self.street_select.currentIndexChanged.connect(self._on_street_changed)
        self.layout.addWidget(self.street_select)

        # Search Mode Selection
        self.layout.addWidget(QLabel('Search Mode'))
        self.search_mode_group = QButtonGroup(self)
        self.yolo_radio = QRadioButton('YOLOV')
        self.math_radio = QRadioButton('MATH')
        self.video_radio = QRadioButton('VIDEO')
        self.yolo_radio.setChecked(True)
        self.search_mode_group.addButton(self.yolo_radio)
        self.search_mode_group.addButton(self.math_radio)
        self.search_mode_group.addButton(self.video_radio)
        self.search_mode_group.buttonClicked.connect(self._update_find_parking_button_state)
        h_layout_modes = QHBoxLayout()
        h_layout_modes.addWidget(self.yolo_radio)
        h_layout_modes.addWidget(self.video_radio)
        self.layout.addLayout(h_layout_modes)

        # Search Status Indicator
        self.search_status_indicator = QLabel("Status: Idle")
        self.search_status_indicator.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.search_status_indicator.setAutoFillBackground(True)
        self.search_status_indicator.setStyleSheet("padding: 3px; border-radius: 5px;")
        self.update_search_status(False)
        self.layout.addWidget(self.search_status_indicator)

        # Assigned Spot Information
        self.assigned_spot_info_label = QLabel("Assigned spot: -")
        self.assigned_spot_info_label.setWordWrap(True)
        self.assigned_spot_info_label.setStyleSheet("padding: 3px; border: 1px solid gray;")
        self.layout.addWidget(self.assigned_spot_info_label)

        # Available Spots List
        self.layout.addWidget(QLabel("Available Spots:"))
        self.free_spots_display = QListWidget()
        self.free_spots_display.setFixedHeight(100)
        self.free_spots_display.setToolTip("Click on a free spot to highlight it on the map.")
        self.free_spots_display.setSelectionMode(QAbstractItemView.SelectionMode.SingleSelection)
        self.free_spots_display.itemClicked.connect(self.on_free_spot_selected)
        self.layout.addWidget(self.free_spots_display)

        self.layout.addSpacerItem(QSpacerItem(20, 20, QSizePolicy.Policy.Minimum, QSizePolicy.Policy.Expanding))

        # Control Buttons
        self.find_parking_btn = QPushButton('Find Parking')
        self.find_parking_btn.setStyleSheet('background-color: #2196F3; color: white; padding: 5px; border-radius: 3px;')
        self.find_parking_btn.clicked.connect(self.on_find_parking_clicked)

        self.assign_spot_btn = QPushButton('Assign Free Spot')
        self.assign_spot_btn.setStyleSheet('background-color: #4CAF50; color: white; padding: 5px; border-radius: 3px;')
        self.assign_spot_btn.clicked.connect(self.on_assign_spot_clicked)
        self.assign_spot_btn.setEnabled(False)
        self.assign_spot_btn.setToolTip("Start search first. Enter name and car.")

        self.cancel_assignment_btn = QPushButton('Cancel Assignment')
        self.cancel_assignment_btn.setStyleSheet('background-color: #ff9800; color: white; padding: 5px; border-radius: 3px;')
        self.cancel_assignment_btn.clicked.connect(self.on_cancel_assignment_clicked)
        self.cancel_assignment_btn.setVisible(False)
        self.cancel_assignment_btn.setEnabled(False)

        self.edit_rois_btn = QPushButton('Edit Parking Zones')
        self.edit_rois_btn.setStyleSheet('padding: 5px; border-radius: 3px;')
        self.edit_rois_btn.clicked.connect(self.on_edit_rois_clicked)

        self.theme_toggle_btn = QPushButton('Toggle Theme')
        self.theme_toggle_btn.setStyleSheet('padding: 5px; border-radius: 3px;')
        self.theme_toggle_btn.clicked.connect(self.on_toggle_theme_clicked)

        self.close_btn = QPushButton('Close')
        self.close_btn.setStyleSheet('background-color: #9E9E9E; color: white; padding: 5px; border-radius: 3px;')
        self.close_btn.clicked.connect(self.on_close_clicked)

        self.layout.addWidget(self.find_parking_btn)
        self.layout.addWidget(self.assign_spot_btn)
        self.layout.addWidget(self.cancel_assignment_btn)
        self.layout.addWidget(self.edit_rois_btn)
        self.layout.addWidget(self.theme_toggle_btn)
        self.layout.addWidget(self.close_btn)
        self.setLayout(self.layout)

        self._has_free_spots = False
        self._update_find_parking_button_state()

    def populate_street_selector(self, street_names):
        self.street_select.blockSignals(True)
        current_selection = self.street_select.currentText()
        self.street_select.clear()
        self.street_select.addItems(street_names)
        
        index = self.street_select.findText(current_selection)
        if index != -1:
            self.street_select.setCurrentIndex(index)
        elif street_names:
            self.street_select.setCurrentIndex(0)
            
        self.street_select.blockSignals(False)
        self._on_street_changed(self.street_select.currentIndex())

    @Slot(int)
    def _on_street_changed(self, index):
        selected_street = self.street_select.itemText(index)
        self._update_find_parking_button_state()
        self.street_changed_signal.emit(selected_street)

    def get_selected_mode(self) -> str:
        if self.yolo_radio.isChecked(): return 'YOLOV'
        if self.math_radio.isChecked(): return 'MATH'
        if self.video_radio.isChecked(): return 'VIDEO'
        return 'YOLOV'

    def get_selected_street(self) -> str:
        return self.street_select.currentText()

    @Slot()
    def _update_find_parking_button_state(self):
        is_running = "Stop" in self.find_parking_btn.text()
        self.find_parking_btn.setEnabled(True)
        if is_running:
            self.find_parking_btn.setToolTip("Click to stop the current parking search.")
        else:
            self.find_parking_btn.setToolTip("Click to start searching for parking spots.")


    @Slot(dict)
    def update_free_spots(self, spot_states):
        current_selection_index = -1
        selected_items = self.free_spots_display.selectedItems()
        if selected_items:
             try:
                 current_selection_index = int(selected_items[0].text().split(" ")[1])
             except (ValueError, IndexError): pass

        self.free_spots_display.clear()
        free_spots_indices = []
        has_free = False
        item_to_select = None

        for spot_index, status in sorted(spot_states.items()):
            if status == 'free':
                item_text = f"Spot {spot_index} (Free)"
                list_item = QListWidgetItem(item_text)
                list_item.setToolTip(f"Click to highlight spot {spot_index} on the map")
                self.free_spots_display.addItem(list_item)
                free_spots_indices.append(spot_index)
                has_free = True
                if spot_index == current_selection_index:
                    item_to_select = list_item

        if not has_free:
             no_spots_item = QListWidgetItem("No free spots")
             no_spots_item.setFlags(no_spots_item.flags() & ~Qt.ItemFlag.ItemIsSelectable)
             self.free_spots_display.addItem(no_spots_item)
             if current_selection_index != -1:
                 self.free_spot_highlight_requested.emit(-1)

        self._has_free_spots = has_free

        if item_to_select:
            self.free_spots_display.setCurrentItem(item_to_select)
        elif current_selection_index != -1 and current_selection_index not in free_spots_indices:
             self.free_spot_highlight_requested.emit(-1)

    @Slot(str)
    def update_assigned_spot_info(self, message):
        self.assigned_spot_info_label.setText(message)

    @Slot(bool, bool)
    def update_assignment_buttons(self, is_assigned, is_stream_running):
        self.name_input.setEnabled(not is_assigned)
        self.car_input.setEnabled(not is_assigned)

        if is_assigned:
             self.assign_spot_btn.setEnabled(False)
             self.assign_spot_btn.setVisible(False)
             self.cancel_assignment_btn.setEnabled(True)
             self.cancel_assignment_btn.setVisible(True)
        else:
             can_assign = is_stream_running and self._has_free_spots
             self.assign_spot_btn.setEnabled(can_assign)
             self.assign_spot_btn.setVisible(True)
             self.cancel_assignment_btn.setEnabled(False)
             self.cancel_assignment_btn.setVisible(False)

             if not is_stream_running:
                 self.assign_spot_btn.setToolTip("Start 'Find Parking' first.")
             elif not self._has_free_spots:
                 self.assign_spot_btn.setToolTip("No free spots currently available.")
             else:
                 self.assign_spot_btn.setToolTip("Click to be assigned the next available free spot.\nEnter name and car first.")

    @Slot(bool)
    def update_search_status(self, is_running):
        palette = self.search_status_indicator.palette()
        if is_running:
             self.search_status_indicator.setText("Status: Running")
             palette.setColor(QPalette.ColorRole.Window, QColor(Qt.GlobalColor.darkGreen))
             palette.setColor(QPalette.ColorRole.WindowText, Qt.GlobalColor.white)
        else:
             self.search_status_indicator.setText("Status: Idle")
             palette.setColor(QPalette.ColorRole.Window, QColor(Qt.GlobalColor.lightGray))
             palette.setColor(QPalette.ColorRole.WindowText, Qt.GlobalColor.black)
        self.search_status_indicator.setPalette(palette)

    @Slot(QListWidgetItem)
    def on_free_spot_selected(self, item):
        if not item or not item.flags() & Qt.ItemFlag.ItemIsSelectable:
            self.free_spot_highlight_requested.emit(-1)
            return
        item_text = item.text()
        try:
            spot_number = int(item_text.split(" ")[1])
            self.free_spot_highlight_requested.emit(spot_number)
        except (IndexError, ValueError):
            self.free_spot_highlight_requested.emit(-1)

    def on_find_parking_clicked(self):
        current_text = self.find_parking_btn.text()
        if "Stop" in current_text:
            print("ControlPanel: Stop requested")
            self.find_parking_requested.emit("STOP_REQUESTED")
        else:
             selected_mode = self.get_selected_mode()
             print(f"ControlPanel: Emitting find_parking_requested (Mode={selected_mode})")
             self.find_parking_requested.emit(selected_mode)

    def on_assign_spot_clicked(self):
        user_name = self.name_input.text().strip()
        car_info = self.car_input.text().strip()
        if not user_name:
            QMessageBox.warning(self, "Input Missing", "Please enter your name before assigning a spot.")
            self.name_input.setFocus()
            return
        if not car_info:
            QMessageBox.warning(self, "Input Missing", "Please enter car make and model before assigning a spot.")
            self.car_input.setFocus()
            return
        print(f"ControlPanel: Emitting assign_spot_requested for '{user_name}' ('{car_info}')")
        self.assign_spot_requested.emit(user_name, car_info)

    def on_cancel_assignment_clicked(self):
        print("ControlPanel: Emitting cancel_assignment_requested")
        self.cancel_assignment_requested.emit()

    def on_edit_rois_clicked(self):
        print("ControlPanel: Emitting edit_rois_requested")
        self.edit_rois_requested.emit()

    def on_close_clicked(self):
        print("ControlPanel: Emitting close_requested")
        self.close_requested.emit()

    def on_toggle_theme_clicked(self):
        print("ControlPanel: Emitting toggle_theme_requested")
        self.toggle_theme_requested.emit()