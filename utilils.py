# === FILE: utilils.py ===

import cv2
import numpy as np

def YOLO_Detection(model, frame, conf=0.35, car_class_id=2):
    results = model.predict(frame, conf=conf, classes=[car_class_id])
    if results and results[0] and hasattr(results[0], 'boxes'):
        boxes = results[0].boxes.xyxy.tolist()
        classes = results[0].boxes.cls.tolist()
        names = results[0].names
        confidences = results[0].boxes.conf.tolist()
        return boxes, classes, names, confidences
    else:
        return [], [], {}, []

def label_detection(frame, text, left, top, bottom, right, tbox_color=(100, 100, 100),
                    fontFace=cv2.FONT_HERSHEY_SIMPLEX, fontScale=0.7, fontThickness=1):
    cv2.rectangle(frame, (int(left), int(top)), (int(bottom), int(right)), tbox_color, 1)
    textSize = cv2.getTextSize(text, fontFace, fontScale, fontThickness)
    text_w = textSize[0][0]
    text_h = textSize[0][1]
    y_adjust = 5
    cv2.rectangle(frame, (int(left), int(top) - text_h - y_adjust), (int(left) + text_w + y_adjust, int(top)),
                  tbox_color, -1)
    cv2.putText(frame, text, (int(left) + 3, int(top) - 3), fontFace, fontScale, (255, 255, 255), fontThickness,
                cv2.LINE_AA)


def drawPolygons(frame, points_list,
                 detection_centers_inside=None,
                 detected_boxes=None,
                 occupied_color=(0, 0, 255),
                 free_color=(0, 255, 0),
                 assigned_color=(255, 165, 0),
                 highlight_color=(255, 0, 255),
                 bbox_color=(0, 255, 255),
                 font_color=(255, 255, 255), font_scale=0.6, font_thickness=1,
                 show_status_text=True, assigned_spot_index=-1,
                 highlight_spot_index=-1):
    overlay = frame.copy()
    alpha = 0.35
    occupied_count = 0
    spot_states = {}
    drawn_box_indices_for_spots = set()

    if detection_centers_inside is None: detection_centers_inside = []
    if detected_boxes is None: detected_boxes = []

    for idx, area in enumerate(points_list):
        spot_index = idx + 1
        try:
            area_np = np.array(area, np.int32)
            if area_np.shape[0] < 3:
                print(f"Warning: Invalid polygon data for spot index {spot_index}. Skipping.")
                continue
        except Exception as e:
            print(f"Error processing polygon for spot index {spot_index}: {e}. Skipping.")
            continue

        occupying_box_index = -1
        is_occupied = False
        for center_x, center_y, box_idx in detection_centers_inside:
            if cv2.pointPolygonTest(area_np, (float(center_x), float(center_y)), False) >= 0:
                is_occupied = True
                occupying_box_index = box_idx
                break

        is_assigned_to_user = (spot_index == assigned_spot_index)
        is_highlighted = (spot_index == highlight_spot_index)

        status = "free"
        color = free_color
        fill_color = free_color
        status_text = "Free"
        line_thickness = 2

        if is_assigned_to_user:
            status = "assigned"
            color = assigned_color
            fill_color = assigned_color
            status_text = "YOUR SPOT"
            line_thickness = 4
        elif is_occupied:
            status = "occupied"
            color = occupied_color
            fill_color = occupied_color
            status_text = "Occupied"
            if not is_assigned_to_user:
                occupied_count += 1

        spot_states[spot_index] = status

        try:
            cv2.fillPoly(overlay, [area_np], fill_color)
            cv2.polylines(overlay, [area_np], isClosed=True, color=color, thickness=line_thickness)
        except Exception as e:
            print(f"Error drawing polygon graphics for spot index {spot_index}: {e}")
            continue

        if is_highlighted and not is_assigned_to_user:
            try:
                cv2.polylines(overlay, [area_np], isClosed=True, color=highlight_color,
                              thickness=line_thickness + 3)
            except Exception as e:
                print(f"Error drawing highlight for spot index {spot_index}: {e}")

        if status == 'occupied' and occupying_box_index != -1 and occupying_box_index < len(detected_boxes):
            drawn_box_indices_for_spots.add(occupying_box_index)
            try:
                box = detected_boxes[occupying_box_index]
                x1, y1, x2, y2 = map(int, box)
                bbox_overlay_spot = overlay.copy()
                cv2.rectangle(bbox_overlay_spot, (x1, y1), (x2, y2), bbox_color, 2)
                overlay = cv2.addWeighted(bbox_overlay_spot, 0.6, overlay, 0.4, 0)
            except Exception as e:
                print(f"Error drawing bounding box for spot index {spot_index}: {e}")

        try:
            M = cv2.moments(area_np)
            if M["m00"] != 0:
                center_x = int(M["m10"] / M["m00"])
                center_y = int(M["m01"] / M["m00"])
            else:
                center_x = int(np.mean(area_np[:, 0]))
                center_y = int(np.mean(area_np[:, 1]))

            number_y_offset = -10
            status_y_offset = 15
            bg_alpha = 0.6

            num_text = str(spot_index)
            (num_w, num_h), _ = cv2.getTextSize(num_text, cv2.FONT_HERSHEY_SIMPLEX, font_scale * 1.2,
                                                font_thickness + 1)
            num_pos = (center_x - num_w // 2, center_y + number_y_offset)

            bg_x1_n, bg_y1_n = num_pos[0] - 3, num_pos[1] - num_h - 3
            bg_x2_n, bg_y2_n = num_pos[0] + num_w + 3, num_pos[1] + 3
            if bg_x1_n >= 0 and bg_y1_n >= 0 and bg_x2_n <= overlay.shape[1] and bg_y2_n <= overlay.shape[0]:
                sub_img_n = overlay[bg_y1_n:bg_y2_n, bg_x1_n:bg_x2_n]
                black_rect_n = np.ones(sub_img_n.shape, dtype=np.uint8) * 50
                res_n = cv2.addWeighted(sub_img_n, 1 - bg_alpha, black_rect_n, bg_alpha, 1.0)
                overlay[bg_y1_n:bg_y2_n, bg_x1_n:bg_x2_n] = res_n
            cv2.putText(overlay, num_text, num_pos, cv2.FONT_HERSHEY_SIMPLEX, font_scale * 1.2, font_color,
                        font_thickness + 1, cv2.LINE_AA)

            if show_status_text:
                current_font_thickness_stat = font_thickness + (1 if is_assigned_to_user else 0)
                (stat_w, stat_h), _ = cv2.getTextSize(status_text, cv2.FONT_HERSHEY_SIMPLEX, font_scale,
                                                      current_font_thickness_stat)
                text_pos_stat = (center_x - stat_w // 2, center_y + status_y_offset)

                bg_x1_s, bg_y1_s = text_pos_stat[0] - 3, text_pos_stat[1] - stat_h - 3
                bg_x2_s, bg_y2_s = text_pos_stat[0] + stat_w + 3, text_pos_stat[1] + 3
                if bg_x1_s >= 0 and bg_y1_s >= 0 and bg_x2_s <= overlay.shape[1] and bg_y2_s <= overlay.shape[0]:
                    sub_img_s = overlay[bg_y1_s:bg_y2_s, bg_x1_s:bg_x2_s]
                    black_rect_s = np.ones(sub_img_s.shape, dtype=np.uint8) * 50
                    res_s = cv2.addWeighted(sub_img_s, 1 - bg_alpha, black_rect_s, bg_alpha, 1.0)
                    overlay[bg_y1_s:bg_y2_s, bg_x1_s:bg_x2_s] = res_s
                cv2.putText(overlay, status_text, text_pos_stat, cv2.FONT_HERSHEY_SIMPLEX, font_scale, font_color,
                            current_font_thickness_stat, cv2.LINE_AA)

            if is_assigned_to_user:
                icon_y = center_y - num_h - 15
                cv2.putText(overlay, "< >", (center_x - 10, icon_y), cv2.FONT_HERSHEY_SIMPLEX, 0.7, (255, 255, 0), 2,
                            cv2.LINE_AA)
        except Exception as e:
            print(f"Error drawing text/icon for spot index {spot_index}: {e}")

    processed_frame = cv2.addWeighted(overlay, alpha, frame, 1 - alpha, 0)
    return processed_frame, spot_states, occupied_count, drawn_box_indices_for_spots