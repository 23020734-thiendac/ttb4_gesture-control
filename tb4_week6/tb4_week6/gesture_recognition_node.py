"""Read a laptop webcam and publish debounced MediaPipe hand gestures."""

from __future__ import annotations

import time
from pathlib import Path
from typing import Optional, Tuple

import cv2
import rclpy
from ament_index_python.packages import get_package_share_directory
from rclpy.node import Node
from std_msgs.msg import String


HAND_CONNECTIONS = (
    (0, 1), (1, 2), (2, 3), (3, 4),
    (0, 5), (5, 6), (6, 7), (7, 8),
    (5, 9), (9, 10), (10, 11), (11, 12),
    (9, 13), (13, 14), (14, 15), (15, 16),
    (13, 17), (17, 18), (18, 19), (19, 20),
    (0, 17),
)


GESTURE_NAMES = {
    'Pointing_Up': 'Pointing Up',
    'Victory': 'Victory',
    'Thumb_Up': 'Thumbs Up',
    'Open_Palm': 'Open Palm',
    'Closed_Fist': 'Closed Fist',
}


class GestureRecognitionNode(Node):
    def __init__(self) -> None:
        super().__init__('gesture_recognition_node')
        default_model = str(
            Path(get_package_share_directory('tb4_week6')) /
            'models' / 'gesture_recognizer.task')
        self.declare_parameter('camera_index', 0)
        self.declare_parameter('model_path', default_model)
        self.declare_parameter('show_window', True)
        self.declare_parameter('publish_hz', 20.0)
        self.declare_parameter('min_confidence', 0.70)
        self.declare_parameter('stable_frames', 3)
        self.declare_parameter('camera_width', 640)
        self.declare_parameter('camera_height', 480)
        self.declare_parameter('show_landmarks', True)

        self.camera_index = int(self.get_parameter('camera_index').value)
        self.model_path = str(self.get_parameter('model_path').value)
        self.show_window = bool(self.get_parameter('show_window').value)
        self.publish_hz = max(1.0, float(self.get_parameter('publish_hz').value))
        self.min_confidence = float(
            self.get_parameter('min_confidence').value)
        self.stable_frames = max(
            1, int(self.get_parameter('stable_frames').value))
        self.camera_width = int(self.get_parameter('camera_width').value)
        self.camera_height = int(self.get_parameter('camera_height').value)
        self.show_landmarks = bool(self.get_parameter('show_landmarks').value)

        self.publisher = self.create_publisher(String, '/detected_gesture', 10)
        self.capture: Optional[cv2.VideoCapture] = None
        self.recognizer = None
        self.mp_image = None
        self.mp_image_format = None
        self._last_error = ''
        self._last_error_time = 0.0
        self._candidate = 'None'
        self._candidate_count = 0
        self._stable_gesture = 'None'
        self._stable_confidence = 0.0
        self._last_frame_time = time.monotonic()
        self._window_enabled = self.show_window
        self._last_landmarks = []

        self._load_mediapipe()
        self._open_camera()
        self.timer = self.create_timer(1.0 / self.publish_hz, self.process_frame)
        self.get_logger().info(
            'Gesture node started: publish /detected_gesture, '
            f'camera={self.camera_index}, min_confidence={self.min_confidence:.2f}')

    def _warn_throttled(self, message: str, period: float = 3.0) -> None:
        now = time.monotonic()
        if message != self._last_error or now - self._last_error_time >= period:
            self.get_logger().warning(message)
            self._last_error = message
            self._last_error_time = now

    def _load_mediapipe(self) -> None:
        model = Path(self.model_path).expanduser()
        if not model.is_file():
            self._warn_throttled(
                f'Thiếu MediaPipe model: {model}. '
                'Node sẽ publish None để robot đứng an toàn.')
            return
        try:
            import mediapipe as mp
            from mediapipe.tasks import python
            from mediapipe.tasks.python import vision

            options = vision.GestureRecognizerOptions(
                base_options=python.BaseOptions(
                    model_asset_path=str(model)),
                running_mode=vision.RunningMode.IMAGE,
                # Salute and OK are single-hand commands. Keeping one hand
                # also reduces false detections from a second hand in frame.
                num_hands=1,
                min_hand_detection_confidence=self.min_confidence,
                min_hand_presence_confidence=self.min_confidence,
                min_tracking_confidence=self.min_confidence,
            )
            self.recognizer = vision.GestureRecognizer.create_from_options(
                options)
            self.mp_image = mp.Image
            self.mp_image_format = mp.ImageFormat.SRGB
        except (ImportError, OSError, ValueError, RuntimeError) as exc:
            self._warn_throttled(
                f'Không khởi tạo được MediaPipe Gesture Recognizer: {exc}')

    def _open_camera(self) -> None:
        try:
            self.capture = cv2.VideoCapture(self.camera_index)
            if not self.capture.isOpened():
                self._warn_throttled(
                    f'Không mở được webcam index {self.camera_index}.')
                self.capture.release()
                self.capture = None
                return
            self.capture.set(cv2.CAP_PROP_FRAME_WIDTH, self.camera_width)
            self.capture.set(cv2.CAP_PROP_FRAME_HEIGHT, self.camera_height)
            # Always process the newest frame instead of a delayed webcam
            # buffer. This makes gesture confirmation feel immediate.
            self.capture.set(cv2.CAP_PROP_BUFFERSIZE, 1)
        except cv2.error as exc:
            self._warn_throttled(f'Lỗi OpenCV khi mở webcam: {exc}')
            self.capture = None

    @staticmethod
    def _distance(first, second) -> float:
        return ((float(first.x) - float(second.x)) ** 2 +
                (float(first.y) - float(second.y)) ** 2) ** 0.5

    def _detect_ok(self, result) -> Tuple[bool, float]:
        """Detect an OK hand shape from landmarks.

        The stock MediaPipe gesture model has no stable OK class. We detect
        the thumb/index ring geometrically and require at least two of the
        remaining fingers to be extended, which prevents an ordinary fist or
        thumbs-up from being accepted as OK.
        """
        if not result.hand_landmarks:
            return False, 0.0
        for landmarks in result.hand_landmarks:
            if len(landmarks) < 21:
                continue
            palm_scale = self._distance(landmarks[0], landmarks[9])
            if palm_scale < 1e-4:
                continue
            thumb_index_gap = self._distance(landmarks[4], landmarks[8])
            if thumb_index_gap > 0.38 * palm_scale:
                continue
            extended = 0
            for tip, pip in ((12, 10), (16, 14), (20, 18)):
                if (self._distance(landmarks[tip], landmarks[0]) >
                        1.05 * self._distance(landmarks[pip], landmarks[0])):
                    extended += 1
            if extended >= 2:
                return True, 0.95
        return False, 0.0

    def _detect_military_salute(self, result) -> Tuple[bool, float]:
        """Detect a one-hand military salute near the forehead.

        A salute is not a reliable stock Gesture Recognizer class. The custom
        check requires four nearly aligned extended fingers, a folded thumb,
        and the fingertips/palm in the upper part of the image. That separates
        it from a normal open palm and from Pointing Up.
        """
        if not result.hand_landmarks:
            return False, 0.0
        landmarks = result.hand_landmarks[0]
        if len(landmarks) < 21:
            return False, 0.0

        palm_scale = self._distance(landmarks[0], landmarks[9])
        if palm_scale < 1e-4:
            return False, 0.0

        # Four fingers must be extended beyond their PIP joints.
        extended = 0
        for tip, pip in ((8, 6), (12, 10), (16, 14), (20, 18)):
            if (self._distance(landmarks[tip], landmarks[0]) >
                    1.04 * self._distance(landmarks[pip], landmarks[0])):
                extended += 1
        if extended != 4:
            return False, 0.0

        # In a salute the fingertips are close together, unlike an open palm.
        tips = [landmarks[index] for index in (8, 12, 16, 20)]
        max_tip_gap = max(
            self._distance(first, second)
            for first in tips for second in tips)
        if max_tip_gap > 0.62 * palm_scale:
            return False, 0.0

        # The thumb is folded across the palm, not spread away from it.
        if self._distance(landmarks[4], landmarks[9]) > 0.82 * palm_scale:
            return False, 0.0

        fingertip_y = sum(float(landmarks[index].y) for index in (8, 12, 16, 20)) / 4.0
        palm_y = float(landmarks[9].y)
        wrist_y = float(landmarks[0].y)
        # Hand points upward toward the forehead and is actually raised in the
        # webcam image. These limits tolerate a seated user while rejecting a
        # hand held at chest level.
        if fingertip_y > 0.48 or palm_y > 0.68 or fingertip_y >= wrist_y - 0.08:
            return False, 0.0
        return True, 0.95

    def _recognize(self, frame) -> Tuple[str, float]:
        if (self.recognizer is None or self.mp_image is None or
                self.mp_image_format is None):
            return 'None', 0.0
        rgb = cv2.cvtColor(frame, cv2.COLOR_BGR2RGB)
        image = self.mp_image(image_format=self.mp_image_format, data=rgb)
        result = self.recognizer.recognize(image)
        self._last_landmarks = list(result.hand_landmarks or [])

        salute_detected, salute_confidence = self._detect_military_salute(result)
        if salute_detected:
            return 'Military Salute', salute_confidence

        ok_detected, ok_confidence = self._detect_ok(result)
        if ok_detected:
            return 'OK', ok_confidence

        names = []
        confidences = []
        gestures = result.gestures or []
        for index, _ in enumerate(result.hand_landmarks or []):
            if index >= len(gestures) or not gestures[index]:
                names.append('None')
                confidences.append(0.0)
                continue
            top = result.gestures[index][0]
            names.append(GESTURE_NAMES.get(top.category_name, 'None'))
            confidences.append(float(top.score or 0.0))

        if not names:
            return 'None', 0.0
        best = max(range(len(names)), key=lambda index: confidences[index])
        return names[best], confidences[best]

    def _update_stable_gesture(self, name: str, confidence: float) -> None:
        if confidence < self.min_confidence:
            name, confidence = 'None', 0.0
        if name == self._candidate:
            self._candidate_count += 1
        else:
            self._candidate = name
            self._candidate_count = 1
        if self._candidate_count >= self.stable_frames:
            self._stable_gesture = self._candidate
            self._stable_confidence = confidence

    def _publish(self) -> None:
        message = String()
        message.data = f'{self._stable_gesture}|{self._stable_confidence:.3f}'
        self.publisher.publish(message)

    def _draw_hand_landmarks(self, frame) -> None:
        """Draw MediaPipe hand landmarks and skeleton on the webcam image."""
        if not self.show_landmarks or not self._last_landmarks:
            return
        height, width = frame.shape[:2]
        for landmarks in self._last_landmarks:
            points = []
            for landmark in landmarks:
                x = int(max(0.0, min(1.0, float(landmark.x))) * (width - 1))
                y = int(max(0.0, min(1.0, float(landmark.y))) * (height - 1))
                points.append((x, y))
            for start, end in HAND_CONNECTIONS:
                if start < len(points) and end < len(points):
                    cv2.line(frame, points[start], points[end],
                             (0, 220, 80), 2, cv2.LINE_AA)
            for index, point in enumerate(points):
                color = (255, 0, 220) if index == 9 else (0, 60, 255)
                cv2.circle(frame, point, 5 if index == 9 else 3,
                           color, -1, cv2.LINE_AA)

    def _draw_overlay(self, frame, name: str, confidence: float):
        self._draw_hand_landmarks(frame)
        text = f'{name}  {confidence:.2f}' if name != 'None' else 'No gesture'
        cv2.putText(frame, text, (20, 40), cv2.FONT_HERSHEY_SIMPLEX,
                    1.0, (0, 220, 0) if name != 'None' else (0, 180, 255),
                    2, cv2.LINE_AA)
        cv2.putText(frame, 'Military Salute: GREET | OK: FIGURE 8',
                    (20, 72), cv2.FONT_HERSHEY_SIMPLEX, 0.55,
                    (255, 255, 255), 2, cv2.LINE_AA)
        cv2.putText(frame, 'Open Palm: STOP | Fist: CANCEL | Thumbs Up: RUN',
                    (20, 102),
                    cv2.FONT_HERSHEY_SIMPLEX, 0.65, (255, 255, 255), 2,
                    cv2.LINE_AA)
        return frame

    def process_frame(self) -> None:
        frame = None
        if self.capture is not None:
            ok, frame = self.capture.read()
            if not ok:
                self._warn_throttled('Mất frame từ webcam; robot phải dừng.')
        if frame is not None:
            try:
                name, confidence = self._recognize(frame)
                self._update_stable_gesture(name, confidence)
            except (cv2.error, ValueError, RuntimeError) as exc:
                self._warn_throttled(f'Lỗi xử lý frame gesture: {exc}')
            self._last_frame_time = time.monotonic()
            if self._window_enabled:
                try:
                    display = self._draw_overlay(
                        frame, self._stable_gesture, self._stable_confidence)
                    cv2.imshow('TB4 Week 6 - Hand Gesture', display)
                    cv2.waitKey(1)
                except cv2.error as exc:
                    self._warn_throttled(f'Không hiển thị được cửa sổ webcam: {exc}')
                    self._window_enabled = False
        self._publish()

    def destroy_node(self) -> None:
        if self.capture is not None:
            self.capture.release()
        if self._window_enabled:
            cv2.destroyAllWindows()
        if self.recognizer is not None:
            close = getattr(self.recognizer, 'close', None)
            if close is not None:
                close()
        super().destroy_node()


def main(args=None) -> None:
    rclpy.init(args=args)
    node = GestureRecognitionNode()
    try:
        rclpy.spin(node)
    except KeyboardInterrupt:
        pass
    finally:
        node.destroy_node()
        rclpy.shutdown()


if __name__ == '__main__':
    main()
