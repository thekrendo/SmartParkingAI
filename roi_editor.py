# === FILE: roi_editor.py ===

import sys
import cv2
import pickle
import numpy as np
import os
# import yaml # Не потрібен тут напряму
from PySide6.QtWidgets import (QDialog, QVBoxLayout, QHBoxLayout, QPushButton,
                               QLabel, QFileDialog, QMessageBox, QSizePolicy,
                               QAbstractScrollArea)
from PySide6.QtGui import (QPixmap, QImage, QPainter, QPen, QColor, QPolygon, QBrush,
                           QPainterPath)
from PySide6.QtCore import Qt, Signal, QPoint, QRect, Slot, QSize


class RoiLabel(QLabel):
    point_added = Signal(QPoint)
    polygon_completed = Signal(list)
    polygon_cleared = Signal()
    roi_selected = Signal(int)
    roi_hovered = Signal(int)

    def __init__(self, parent=None):
        super().__init__(parent)
        self.parent_dialog = parent  # Це ROIDialog
        self.setMinimumSize(640, 480)
        self.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Expanding)
        self.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.setText("Load an image to start defining ROIs")
        self.setStyleSheet("border: 1px solid gray; background-color: #e0e0e0;")
        self.setMouseTracking(True)

        self.current_polygon_points = []
        self.image_pixmap = None
        self.scale_factor = 1.0
        self.offset = QPoint(0, 0)

        self.hovered_roi_index = -1
        self.selected_roi_index = -1

        self.existing_roi_color = QColor(0, 0, 255, 100)
        self.hover_roi_color = QColor(255, 255, 0, 150)
        self.selected_roi_color = QColor(0, 255, 0, 180)
        self.drawing_roi_color = QColor(255, 0, 0)
        self.number_text_color = Qt.GlobalColor.white

    def set_image(self, image_path):
        pixmap = QPixmap(image_path)
        if pixmap.isNull():
            self.setText(f"Failed to load image:\n{image_path}")
            self.image_pixmap = None
            self._update_display()
            return False
        self.image_pixmap = pixmap
        self.hovered_roi_index = -1
        self.selected_roi_index = -1
        self.roi_selected.emit(-1)
        self.roi_hovered.emit(-1)
        self._update_display()
        self.current_polygon_points = []
        self.update()
        return True

    def _update_display(self):
        if not self.image_pixmap or self.image_pixmap.isNull():
            self.setText("Load an image to start defining ROIs")
            self.setPixmap(QPixmap())
            self.scale_factor = 1.0
            self.offset = QPoint(0, 0)
            return

        self.setText("")
        label_size = self.size()
        scaled_pixmap = self.image_pixmap.scaled(label_size, Qt.AspectRatioMode.KeepAspectRatio,
                                                 Qt.TransformationMode.SmoothTransformation)
        self.setPixmap(scaled_pixmap)

        original_width = self.image_pixmap.width()
        original_height = self.image_pixmap.height()
        lw = label_size.width()
        lh = label_size.height()

        if original_width > 0 and original_height > 0 and lw > 0 and lh > 0:
            self.scale_factor = min(lw / original_width, lh / original_height)
        else:
            self.scale_factor = 1.0

        scaled_w_real = original_width * self.scale_factor
        scaled_h_real = original_height * self.scale_factor
        self.offset = QPoint(int((lw - scaled_w_real) / 2), int((lh - scaled_h_real) / 2))

    def mousePressEvent(self, event):
        if not self.image_pixmap: return
        click_pos = event.position().toPoint()

        clicked_on_existing = -1
        if self.parent_dialog and self.parent_dialog.posList:
            for i in range(len(self.parent_dialog.posList) - 1, -1, -1):
                polygon_orig = self.parent_dialog.posList[i]
                polygon_label = self.get_label_coords(polygon_orig)
                if not polygon_label: continue
                qpolygon = QPolygon(polygon_label)
                if qpolygon.containsPoint(click_pos, Qt.FillRule.OddEvenFill):
                    clicked_on_existing = i
                    break

        if event.button() == Qt.MouseButton.LeftButton:
            if clicked_on_existing != -1:
                if self.selected_roi_index != clicked_on_existing:
                    self.selected_roi_index = clicked_on_existing
                    self.roi_selected.emit(self.selected_roi_index)
                    self.current_polygon_points = []
                    self.polygon_cleared.emit()
                self.update()
            else:
                if len(self.current_polygon_points) < 4:
                    if self.selected_roi_index != -1:
                        self.selected_roi_index = -1
                        self.roi_selected.emit(-1)
                    self.current_polygon_points.append(click_pos)
                    self.point_added.emit(click_pos)
                    if len(self.current_polygon_points) == 4:
                        original_coords_poly = self.get_original_coords_tuples(self.current_polygon_points)
                        if original_coords_poly:
                            self.polygon_completed.emit(original_coords_poly)
                        else:
                            print("Error converting coordinates, polygon not added.")
                        self.current_polygon_points = []
                self.update()

        elif event.button() == Qt.MouseButton.RightButton:
            if self.current_polygon_points:
                self.current_polygon_points.pop()
                self.polygon_cleared.emit()
                self.update()
            elif self.selected_roi_index != -1:
                self.selected_roi_index = -1
                self.roi_selected.emit(-1)
                self.update()

    def mouseMoveEvent(self, event):
        if not self.image_pixmap or not self.parent_dialog or not self.parent_dialog.posList:
            if self.hovered_roi_index != -1:
                self.hovered_roi_index = -1
                self.roi_hovered.emit(-1)
                self.update()
            return

        pos = event.position().toPoint()
        current_hover = -1
        for i in range(len(self.parent_dialog.posList) - 1, -1, -1):
            polygon_orig = self.parent_dialog.posList[i]
            polygon_label = self.get_label_coords(polygon_orig)
            if not polygon_label: continue
            qpolygon = QPolygon(polygon_label)
            if qpolygon.containsPoint(pos, Qt.FillRule.OddEvenFill):
                current_hover = i
                break
        if current_hover != self.hovered_roi_index:
            self.hovered_roi_index = current_hover
            self.roi_hovered.emit(self.hovered_roi_index)
            self.update()

    def paintEvent(self, event):
        super().paintEvent(event)
        if not self.image_pixmap: return

        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)

        if self.parent_dialog and self.parent_dialog.posList:
            for i, polygon_orig in enumerate(self.parent_dialog.posList):
                polygon_label = self.get_label_coords(polygon_orig)
                if not polygon_label: continue
                qpolygon = QPolygon(polygon_label)
                pen_width = 1
                poly_brush_color = self.existing_roi_color
                poly_pen_color = Qt.GlobalColor.blue
                if i == self.selected_roi_index:
                    poly_brush_color = self.selected_roi_color
                    poly_pen_color = Qt.GlobalColor.green
                    pen_width = 2
                elif i == self.hovered_roi_index:
                    poly_brush_color = self.hover_roi_color
                    poly_pen_color = Qt.GlobalColor.yellow
                    pen_width = 2
                painter.setPen(QPen(poly_pen_color, pen_width))
                painter.setBrush(QBrush(poly_brush_color))
                painter.drawPolygon(qpolygon)
                center = qpolygon.boundingRect().center()
                font = painter.font()
                font.setPointSize(10)
                font.setBold(True)
                painter.setFont(font)
                path = QPainterPath()
                text_rect = painter.fontMetrics().boundingRect(str(i + 1))
                text_center_offset = QPoint(-text_rect.width() // 2, text_rect.height() // 4)
                path.addText(center + text_center_offset, painter.font(), str(i + 1))
                painter.setPen(QPen(Qt.GlobalColor.black, 1))
                painter.drawPath(path)
                painter.setPen(self.number_text_color)
                painter.fillPath(path, painter.pen().brush())

        if self.current_polygon_points:
            pen_points = QPen(self.drawing_roi_color, 5, Qt.PenStyle.SolidLine, Qt.PenCapStyle.RoundCap)
            pen_lines = QPen(self.drawing_roi_color, 2, Qt.PenStyle.DotLine)
            painter.setPen(pen_points)
            for point in self.current_polygon_points:
                painter.drawPoint(point)
            if len(self.current_polygon_points) > 1:
                painter.setPen(pen_lines)
                painter.drawPolyline(QPolygon(self.current_polygon_points))
            if len(self.current_polygon_points) == 3:
                painter.drawLine(self.current_polygon_points[-1], self.current_polygon_points[0])
            if self.parent_dialog:
                num_text = f"Drawing Spot {len(self.parent_dialog.posList) + 1}"
                painter.setPen(Qt.GlobalColor.black)
                painter.setFont(self.font())
                text_rect = painter.fontMetrics().boundingRect(num_text)
                bg_rect = QRect(5, 5, text_rect.width() + 10, text_rect.height() + 4)
                painter.setBrush(QColor(255, 255, 255, 180))
                painter.setPen(Qt.NoPen)
                painter.drawRect(bg_rect)
                painter.setPen(Qt.GlobalColor.black)
                painter.drawText(QPoint(10, 5 + text_rect.height()), num_text)
        painter.end()

    def resizeEvent(self, event):
        self._update_display()
        super().resizeEvent(event)

    def get_original_coords_tuples(self, label_points_qpoint):
        if not self.image_pixmap or self.image_pixmap.isNull() or self.scale_factor == 0: return []
        original_coords = []
        img_w = self.image_pixmap.width()
        img_h = self.image_pixmap.height()
        for p in label_points_qpoint:
            orig_x = int((p.x() - self.offset.x()) / self.scale_factor)
            orig_y = int((p.y() - self.offset.y()) / self.scale_factor)
            orig_x = max(0, min(orig_x, img_w - 1))
            orig_y = max(0, min(orig_y, img_h - 1))
            original_coords.append((orig_x, orig_y))
        return original_coords

    def get_label_coords(self, original_coords_tuples):
        if not self.image_pixmap or self.image_pixmap.isNull() or self.scale_factor == 0: return []
        label_points = []
        for x, y in original_coords_tuples:
            label_x = int(x * self.scale_factor + self.offset.x())
            label_y = int(y * self.scale_factor + self.offset.y())
            label_points.append(QPoint(label_x, label_y))
        return label_points

    def clear_selection_and_drawing(self):
        self.current_polygon_points = []
        self.selected_roi_index = -1
        self.hovered_roi_index = -1
        self.roi_selected.emit(-1)
        self.roi_hovered.emit(-1)
        self.polygon_cleared.emit()
        self.update()


class ROIDialog(QDialog):
    rois_saved = Signal(str)

    def __init__(self, config, current_roi_path, current_reference_image_path, parent=None):
        super().__init__(parent)
        self.roi_file_path = current_roi_path
        self.posList = []
        self.reference_image_path = current_reference_image_path
        self.selected_roi_index = -1

        self.setWindowTitle("Parking Zone Editor (ROI) - AuraPark")
        self.setMinimumSize(900, 700)

        main_layout = QVBoxLayout(self)
        self.roi_label = RoiLabel(self)
        self.roi_label.polygon_completed.connect(self.add_polygon)
        self.roi_label.roi_selected.connect(self.update_selection_state)
        self.roi_label.roi_hovered.connect(self.update_hover_state)
        self.roi_label.polygon_cleared.connect(self.handle_drawing_cleared)
        main_layout.addWidget(self.roi_label, 1)

        self.status_label = QLabel("Load image/ROIs or draw 4 points for new ROI.")
        self.status_label.setStyleSheet("padding: 5px; background-color: #f0f0f0; border: 1px solid lightgray;")
        main_layout.addWidget(self.status_label)

        button_layout = QHBoxLayout()
        btn_load_image = QPushButton("Load Reference Image")
        btn_load_rois = QPushButton("Load ROIs for Current Street")
        btn_save_rois = QPushButton("Save ROIs for Current Street")
        self.btn_clear_drawing = QPushButton("Clear Drawing Points")
        self.btn_delete_selected = QPushButton("Delete Selected ROI")
        self.btn_delete_selected.setEnabled(False)
        btn_clear_all = QPushButton("Clear All ROIs for Current Street")
        btn_close = QPushButton("Close Editor")

        btn_load_image.clicked.connect(self.load_image)
        btn_load_rois.clicked.connect(self.load_rois)
        btn_save_rois.clicked.connect(self.save_rois)
        self.btn_clear_drawing.clicked.connect(self.clear_drawing_points)
        self.btn_delete_selected.clicked.connect(self.delete_selected_roi)
        btn_clear_all.clicked.connect(self.clear_all_rois)
        btn_close.clicked.connect(self.accept)

        button_layout.addWidget(btn_load_image)
        button_layout.addWidget(btn_load_rois)
        button_layout.addWidget(btn_save_rois)
        button_layout.addWidget(self.btn_clear_drawing)
        button_layout.addWidget(self.btn_delete_selected)
        button_layout.addWidget(btn_clear_all)
        button_layout.addStretch()
        button_layout.addWidget(btn_close)
        main_layout.addLayout(button_layout)

        self.load_rois_internal()  # Завантажуємо ROI для переданого шляху
        if self.reference_image_path and os.path.exists(self.reference_image_path):
            if not self.roi_label.set_image(self.reference_image_path):
                QMessageBox.warning(self, "Image Error",
                                    f"Could not display reference image:\n{self.reference_image_path}")
        else:
            msg = f"Reference image path not set or not found: {self.reference_image_path}. Load image manually."
            self.status_label.setText(msg)
            print(msg)  # Для консолі, якщо QMessageBox не видно відразу

    def load_image(self):
        start_dir = os.path.dirname(self.reference_image_path) if self.reference_image_path else ""
        filepath, _ = QFileDialog.getOpenFileName(self, "Open Reference Image", start_dir,
                                                  "Images (*.png *.jpg *.jpeg *.bmp)")
        if filepath:
            if self.roi_label.set_image(filepath):
                self.reference_image_path = filepath
                self.posList = []
                self.roi_label.clear_selection_and_drawing()
                self.status_label.setText(
                    f"Loaded new reference: {os.path.basename(filepath)}. ROIs cleared. Redraw or load ROIs.")
            else:
                QMessageBox.warning(self, "Error", f"Failed to load image:\n{filepath}")

    def load_rois(self):
        start_dir = os.path.dirname(self.roi_file_path) if self.roi_file_path else \
            (os.path.dirname(self.reference_image_path) if self.reference_image_path else "")

        filepath, _ = QFileDialog.getOpenFileName(self, "Load ROIs for Current Street", start_dir, "ROI files (*.pkl)")
        if filepath:
            self.roi_file_path = filepath
            self.load_rois_internal()

    def load_rois_internal(self):
        if not self.roi_file_path or not os.path.exists(self.roi_file_path):
            print(f"ROI file path invalid or file not found: {self.roi_file_path}")
            self.posList = []
            self.roi_label.clear_selection_and_drawing()
            return

        try:
            with open(self.roi_file_path, 'rb') as f:
                loaded_list = pickle.load(f)
            if isinstance(loaded_list, list) and \
                    all(isinstance(p, list) and len(p) == 4 and \
                        all(isinstance(pt, tuple) and len(pt) == 2 for pt in p) for p in loaded_list):
                self.posList = loaded_list
                print(f"Loaded {len(self.posList)} ROIs from {self.roi_file_path}")
                self.status_label.setText(
                    f"Loaded {len(self.posList)} ROIs from {os.path.basename(self.roi_file_path)}. Draw or select ROIs.")
            else:
                raise TypeError("Invalid data format in ROI file.")
        except FileNotFoundError:
            pass  # Вже оброблено вище
        except Exception as e:
            QMessageBox.warning(self, "Error Loading ROIs", f"Could not load ROIs from {self.roi_file_path}:\n{e}")
            self.posList = []
            self.status_label.setText(f"Error loading ROIs: {e}. Draw new ROIs.")

        self.roi_label.clear_selection_and_drawing()

    def save_rois(self):
        if not self.posList:
            reply = QMessageBox.question(self, "Save Empty List?",
                                         "The ROI list is empty. Do you want to save an empty file?",
                                         QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
                                         QMessageBox.StandardButton.No)
            if reply == QMessageBox.StandardButton.No: return

        save_path = self.roi_file_path
        if not save_path:
            start_dir = os.path.dirname(self.reference_image_path) if self.reference_image_path else ""
            filepath, _ = QFileDialog.getSaveFileName(self, "Save ROIs As", start_dir, "ROI File (*.pkl)")
            if not filepath: return
            save_path = filepath
        
        if not save_path.lower().endswith(".pkl"):
            save_path += ".pkl"

        try:
            with open(save_path, 'wb') as f:
                pickle.dump(self.posList, f)
            print(f"ROIs temporarily saved to {save_path} by ROIDialog.")
            QMessageBox.information(self, "Success",
                                    f"ROIs saved to:\n{save_path}\nMainWindow will update the configuration.")
            self.rois_saved.emit(save_path)
        except Exception as e:
            QMessageBox.critical(self, "Error Saving ROIs", f"Could not save ROIs to {save_path}:\n{e}")

    @Slot(list)
    def add_polygon(self, polygon_points):
        if len(polygon_points) == 4:
            self.posList.append(polygon_points)
            self.status_label.setText(f"ROI {len(self.posList)} added. Draw next or select.")
            print(f"Polygon {len(self.posList)} added to ROIDialog.posList.")
            self.roi_label.update()
        else:
            print(f"Warning: ROIDialog received incomplete polygon with {len(polygon_points)} points.")

    @Slot(int)
    def update_selection_state(self, selected_index):
        self.selected_roi_index = selected_index
        self.btn_delete_selected.setEnabled(selected_index != -1)
        if selected_index != -1:
            self.status_label.setText(f"ROI {selected_index + 1} selected. Right-click to deselect or click 'Delete'.")
        else:
            # Якщо вибір знято, оновлюємо статус на основі hover або стандартного повідомлення
            self.update_hover_state(self.roi_label.hovered_roi_index)

    @Slot(int)
    def update_hover_state(self, hovered_index):
        if self.selected_roi_index == -1:
            if hovered_index != -1:
                self.status_label.setText(f"Hovering over ROI {hovered_index + 1}. Click to select.")
            else:
                if not self.roi_label.current_polygon_points:
                    self.status_label.setText("Draw 4 points for new ROI or hover/click existing ROI.")

    @Slot()
    def handle_drawing_cleared(self):
        if self.selected_roi_index == -1 and self.roi_label.hovered_roi_index == -1:
            self.status_label.setText("Drawing cancelled. Draw 4 points for new ROI or select existing.")

    def clear_drawing_points(self):
        self.roi_label.current_polygon_points = []
        self.roi_label.polygon_cleared.emit()
        self.roi_label.update()

    def delete_selected_roi(self):
        if self.selected_roi_index != -1 and 0 <= self.selected_roi_index < len(self.posList):
            reply = QMessageBox.question(self, "Delete ROI?",
                                         f"Are you sure you want to delete ROI {self.selected_roi_index + 1}?",
                                         QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
                                         QMessageBox.StandardButton.No)
            if reply == QMessageBox.StandardButton.Yes:
                removed_roi_index = self.selected_roi_index
                self.posList.pop(removed_roi_index)
                print(f"Deleted ROI {removed_roi_index + 1} from ROIDialog.posList")
                self.roi_label.clear_selection_and_drawing()
                self.status_label.setText(f"ROI {removed_roi_index + 1} deleted. {len(self.posList)} ROIs remaining.")
        else:
            print("No ROI selected or index out of bounds for deletion.")

    def clear_all_rois(self):
        if self.posList:
            reply = QMessageBox.question(self, "Clear All ROIs?",
                                         f"Are you sure you want to remove all {len(self.posList)} defined parking zones for the current street?",
                                         QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
                                         QMessageBox.StandardButton.No)
            if reply == QMessageBox.StandardButton.Yes:
                self.posList = []
                print("All ROIs cleared from ROIDialog.posList.")
                self.roi_label.clear_selection_and_drawing()
                self.status_label.setText("All ROIs cleared. Draw new ROIs.")
        else:
            self.status_label.setText("ROI list is already empty.")
            print("ROIDialog: ROI list is already empty, nothing to clear.")