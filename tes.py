from ultralytics import YOLO
import cv2

model_path = "D:/PyProjects/car-parking-system/runs/detect/train5/weights/best.pt"
video_path = "D:/PyProjects/car-parking-system/trainer1.mp4"

try:
    model = YOLO(model_path)
    print(f"Model loaded successfully. Class names: {model.names}")

    cap = cv2.VideoCapture(video_path)
    if not cap.isOpened():
        print(f"Error: Could not open video {video_path}")
        exit()

    frame_count = 0
    while cap.isOpened():
        ret, frame = cap.read()
        if not ret:
            print("End of video or error reading frame.")
            break

        frame_count += 1

        results = model.predict(source=frame, conf=0.1, verbose=True)

        if results and results[0].boxes:
            num_detections = len(results[0].boxes)
            print(f"Frame {frame_count}: Found {num_detections} detections (conf=0.1, all classes)")
            if num_detections > 0:
                print(f"  Classes found: {list(set(results[0].boxes.cls.tolist()))}")
        else:
            print(f"Frame {frame_count}: No detections (conf=0.1, all classes)")

        if frame_count > 100:
            print("Reached 100 frames, stopping test.")
            break

    cap.release()
    # cv2.destroyAllWindows()

except Exception as e:
    print(f"An error occurred: {e}")
    import traceback
    traceback.print_exc()