"""Safe gesture-to-motion state machine for TurtleBot 4."""

from __future__ import annotations

import math
import time
from typing import Dict, List, Optional, Tuple

import rclpy
from geometry_msgs.msg import Twist
from nav_msgs.msg import Odometry
from rclpy.node import Node
from std_msgs.msg import String


class RobotBehaviorNode(Node):
    def __init__(self) -> None:
        super().__init__('robot_behavior_node')
        self.declare_parameter('cmd_vel_topic', '/cmd_vel')
        self.declare_parameter('gesture_topic', '/detected_gesture')
        self.declare_parameter('watchdog_sec', 1.5)
        self.declare_parameter('confirmation_timeout_sec', 8.0)
        self.declare_parameter('linear_speed', 0.18)
        self.declare_parameter('angular_speed', 0.45)
        self.declare_parameter('straight_segment_sec', 3.00)
        self.declare_parameter('wave_repetitions', 3)
        # Longer left/right phases give the salute response a wider angle
        # without changing the circle or figure-eight motion.
        self.declare_parameter('wave_segment_sec', 0.90)
        self.declare_parameter('circle_turns', 1.0)
        self.declare_parameter('odom_topic', '/odom')
        self.declare_parameter('circle_timeout_sec', 60.0)
        self.declare_parameter('circle_timeout_grace_sec', 45.0)
        self.declare_parameter('figure_eight_timeout_sec', 70.0)
        self.declare_parameter('figure_eight_timeout_grace_sec', 45.0)

        cmd_topic = str(self.get_parameter('cmd_vel_topic').value)
        gesture_topic = str(self.get_parameter('gesture_topic').value)
        self.watchdog_sec = float(self.get_parameter('watchdog_sec').value)
        self.confirmation_timeout = float(
            self.get_parameter('confirmation_timeout_sec').value)
        self.linear_speed = abs(float(self.get_parameter('linear_speed').value))
        # A zero angular speed can never complete a circle; keep a small safe
        # lower bound so a bad parameter does not create a silent deadlock.
        self.angular_speed = max(
            0.05, abs(float(self.get_parameter('angular_speed').value)))
        self.straight_segment_sec = max(
            0.1, float(self.get_parameter('straight_segment_sec').value))
        self.wave_repetitions = max(
            1, int(self.get_parameter('wave_repetitions').value))
        self.wave_segment_sec = max(
            0.2, float(self.get_parameter('wave_segment_sec').value))
        self.circle_turns = max(
            0.1, float(self.get_parameter('circle_turns').value))
        odom_topic = str(self.get_parameter('odom_topic').value)
        self.circle_timeout_sec = max(
            5.0, float(self.get_parameter('circle_timeout_sec').value))
        self.circle_timeout_grace_sec = max(
            10.0,
            float(self.get_parameter('circle_timeout_grace_sec').value))
        self.figure_eight_timeout_sec = max(
            10.0,
            float(self.get_parameter('figure_eight_timeout_sec').value))
        self.figure_eight_timeout_grace_sec = max(
            10.0,
            float(self.get_parameter('figure_eight_timeout_grace_sec').value))

        self.cmd_pub = self.create_publisher(Twist, cmd_topic, 10)
        self.gesture_sub = self.create_subscription(
            String, gesture_topic, self.gesture_callback, 10)
        self.odom_sub = self.create_subscription(
            Odometry, odom_topic, self.odom_callback, 10)
        self.timer = self.create_timer(0.05, self.control_loop)

        self.last_message_time = time.monotonic()
        self.last_gesture = 'None'
        self.pending_behavior: Optional[str] = None
        self.pending_since = 0.0
        self.active_behavior: Optional[str] = None
        self.phase = 0
        self.phase_deadline = 0.0
        self._logged_watchdog = False
        self._zero = Twist()
        self.circle_accumulated_rad = 0.0
        self.circle_last_yaw: Optional[float] = None
        self.circle_timeout_extended = False
        self.figure_eight_accumulated_rad = 0.0
        self.figure_eight_last_yaw: Optional[float] = None
        self.figure_eight_timeout_extended = False

        self.get_logger().info(
            'Behavior node ready. Chọn Pointing Up/Victory/Military Salute/OK, '
            'sau đó dùng Thumbs Up để xác nhận.')

    def _publish(self, linear: float = 0.0, angular: float = 0.0) -> None:
        command = Twist()
        command.linear.x = float(linear)
        command.angular.z = float(angular)
        self.cmd_pub.publish(command)

    def _stop(self, reason: str = '') -> None:
        self._publish()
        if reason:
            self.get_logger().info(f'Robot dừng: {reason}')

    @staticmethod
    def _parse_message(data: str) -> Tuple[str, float]:
        parts = data.split('|', 1)
        name = parts[0].strip() or 'None'
        try:
            confidence = float(parts[1]) if len(parts) > 1 else 0.0
        except ValueError:
            confidence = 0.0
        return name, confidence

    def gesture_callback(self, message: String) -> None:
        name, confidence = self._parse_message(message.data)
        self.last_message_time = time.monotonic()
        self._logged_watchdog = False
        edge = name != self.last_gesture
        self.last_gesture = name

        # Safety gestures are always accepted, even during an action.
        if edge and name == 'Open Palm':
            if self.active_behavior is not None:
                self.active_behavior = None
                self.pending_behavior = None
                self._stop('nhận Open Palm')
            elif self.pending_behavior is not None:
                # Open Palm is also the base pose while the recognizer
                # detects a wave. Do not erase the selected behavior before
                # the user can confirm it with Thumbs Up.
                self.get_logger().info(
                    f'Giữ lựa chọn {self.pending_behavior}; '
                    'chờ Thumbs Up để xác nhận.')
            return
        if edge and name == 'Closed Fist':
            self.active_behavior = None
            self.pending_behavior = None
            self._stop('nhận Closed Fist, hủy hành vi')
            return

        if not edge:
            return
        if self.active_behavior is not None:
            return

        choices: Dict[str, str] = {
            'Military Salute': 'wave',
            'OK': 'figure_eight',
            'Pointing Up': 'forward_backward',
            'Victory': 'circle',
        }
        if name in choices:
            self.pending_behavior = choices[name]
            self.pending_since = time.monotonic()
            display_name = {
                'wave': 'chào điều lệnh',
                'forward_backward': 'tiến-lùi',
                'circle': 'circle',
                'figure_eight': 'figure-eight',
            }.get(self.pending_behavior, self.pending_behavior)
            self.get_logger().info(
                f'Đã chọn hành vi {display_name}.  '
                'Giơ Thumbs Up để xác nhận.')
        elif name == 'Thumbs Up' and self.pending_behavior is not None:
            if time.monotonic() - self.pending_since <= self.confirmation_timeout:
                self._start_behavior(self.pending_behavior)
            else:
                self.get_logger().warning(
                    'Xác nhận quá muộn; hãy chọn lại hành vi.')
                self.pending_behavior = None

    def _start_behavior(self, behavior: str) -> None:
        self.pending_behavior = None
        self.active_behavior = behavior
        self.phase = 0
        phases = self._phases()
        now = time.monotonic()
        if behavior == 'circle':
            self.circle_accumulated_rad = 0.0
            self.circle_last_yaw = None
            self.circle_timeout_extended = False
        elif behavior == 'figure_eight':
            self.figure_eight_accumulated_rad = 0.0
            self.figure_eight_last_yaw = None
            self.figure_eight_timeout_extended = False
        # Keep phase 0 active immediately. The previous implementation set
        # the deadline to ``now`` and skipped the first phase, so the one-phase
        # circle behavior ended before publishing any velocity command.
        if behavior == 'circle':
            self.phase_deadline = now + self.circle_timeout_sec
            expected_sec = (2.0 * math.pi * self.circle_turns /
                            self.angular_speed)
            self.get_logger().info(
                f'Circle dung odometry: muc tieu '
                f'{2.0 * math.pi * self.circle_turns:.2f} rad, '
                f'thoi gian du kien {expected_sec:.1f}s, '
                f'timeout an toan {self.circle_timeout_sec:.1f}s.')
        elif behavior == 'figure_eight':
            self.phase_deadline = now + self.figure_eight_timeout_sec
            expected_sec = (4.0 * math.pi / self.angular_speed)
            self.get_logger().info(
                f'Figure-eight dung odometry: 2 vong tron, '
                f'thoi gian du kien {expected_sec:.1f}s moi vong, '
                f'timeout moi vong {self.figure_eight_timeout_sec:.1f}s.')
        else:
            self.phase_deadline = now + (phases[0][2] if phases else 0.0)
        self.get_logger().info(f'Xác nhận thành công, bắt đầu: {behavior}')

    @staticmethod
    def _yaw_from_quaternion(q) -> float:
        siny_cosp = 2.0 * (q.w * q.z + q.x * q.y)
        cosy_cosp = 1.0 - 2.0 * (q.y * q.y + q.z * q.z)
        return math.atan2(siny_cosp, cosy_cosp)

    def odom_callback(self, message: Odometry) -> None:
        """Accumulate real yaw change for circle and figure-eight paths."""
        if self.active_behavior not in ('circle', 'figure_eight'):
            return
        yaw = self._yaw_from_quaternion(message.pose.pose.orientation)
        if self.active_behavior == 'circle':
            last_yaw = self.circle_last_yaw
        else:
            last_yaw = self.figure_eight_last_yaw
        if last_yaw is not None:
            delta = math.atan2(
                math.sin(yaw - last_yaw),
                math.cos(yaw - last_yaw))
            # Absolute delta handles +/-pi wrap-around and small simulator
            # noise. Direction is controlled by the active path phase.
            if self.active_behavior == 'circle':
                self.circle_accumulated_rad += abs(delta)
            else:
                self.figure_eight_accumulated_rad += abs(delta)
        if self.active_behavior == 'circle':
            self.circle_last_yaw = yaw
        else:
            self.figure_eight_last_yaw = yaw

    def _phases(self) -> List[Tuple[float, float, float]]:
        if self.active_behavior == 'wave':
            one_wave = [(0.0, self.angular_speed, self.wave_segment_sec),
                        (0.0, -self.angular_speed, self.wave_segment_sec)]
            return one_wave * self.wave_repetitions
        if self.active_behavior == 'forward_backward':
            return [(self.linear_speed, 0.0, self.straight_segment_sec),
                    (-self.linear_speed, 0.0,
                     self.straight_segment_sec)] * 4
        if self.active_behavior == 'circle':
            # Circle is handled from odometry in control_loop(), not by a
            # fixed duration. This prevents an early stop when Gazebo or the
            # controller runs slower than expected.
            return []
        return []

    def control_loop(self) -> None:
        now = time.monotonic()
        # Once Thumbs Up has confirmed a behavior, the mission is latched and
        # continues until its phases finish. The user does not need to keep
        # holding Thumbs Up. Open Palm and Closed Fist remain emergency/cancel
        # gestures through gesture_callback().
        if self.active_behavior is None and (
                now - self.last_message_time > self.watchdog_sec):
            if not self._logged_watchdog:
                self.pending_behavior = None
                self._stop('mất tín hiệu gesture/webcam')
                self._logged_watchdog = True
            return

        if self.active_behavior is None:
            self._publish()
            return

        if self.active_behavior == 'circle':
            target_rad = 2.0 * math.pi * self.circle_turns
            if self.circle_accumulated_rad >= target_rad:
                self.active_behavior = None
                self._stop(
                    f'hoàn thành circle {self.circle_accumulated_rad:.2f} rad')
                return
            if now >= self.phase_deadline:
                # Gazebo can temporarily run below real time, so a fixed wall
                # clock timeout may fire just before the final part of the
                # circle. If odometry already confirms most of the turn,
                # grant one bounded extension instead of stopping mid-circle.
                if (not self.circle_timeout_extended and
                        self.circle_accumulated_rad >= 0.75 * target_rad):
                    self.circle_timeout_extended = True
                    self.phase_deadline = now + self.circle_timeout_grace_sec
                    self.get_logger().warning(
                        f'Circle da dat {self.circle_accumulated_rad:.2f}/'
                        f'{target_rad:.2f} rad; gia han them '
                        f'{self.circle_timeout_grace_sec:.1f}s de hoan tat.')
                    self._publish(self.linear_speed, self.angular_speed)
                    return
                self.active_behavior = None
                self._stop(
                    'circle timeout: không nhận đủ odometry 360 độ')
                self.get_logger().warning(
                    f'Circle mới quay được {self.circle_accumulated_rad:.2f}/'
                    f'{target_rad:.2f} rad.')
                return
            self._publish(self.linear_speed, self.angular_speed)
            return

        if self.active_behavior == 'figure_eight':
            target_rad = 2.0 * math.pi
            if self.figure_eight_accumulated_rad >= target_rad:
                if self.phase == 0:
                    self.phase = 1
                    self.figure_eight_accumulated_rad = 0.0
                    self.figure_eight_last_yaw = None
                    self.figure_eight_timeout_extended = False
                    self.phase_deadline = now + self.figure_eight_timeout_sec
                    self.get_logger().info(
                        'Da hoan thanh vong 1/2 cua so 8; '
                        'doi chieu de chay vong 2/2, reset timeout vong 2.')
                    return
                self.active_behavior = None
                self._stop(
                    f'hoan thanh figure-eight '
                    f'{2.0 * math.pi:.2f} + {2.0 * math.pi:.2f} rad')
                return
            if now >= self.phase_deadline:
                # Each loop gets its own timeout. If Gazebo slows down after
                # the direction change but odometry already shows most of
                # this loop, grant one bounded extension instead of stopping
                # the figure-eight at an open arc.
                if (not self.figure_eight_timeout_extended and
                        self.figure_eight_accumulated_rad >=
                        0.75 * target_rad):
                    self.figure_eight_timeout_extended = True
                    self.phase_deadline = (
                        now + self.figure_eight_timeout_grace_sec)
                    self.get_logger().warning(
                        f'Figure-eight vong {self.phase + 1}/2 da dat '
                        f'{self.figure_eight_accumulated_rad:.2f}/'
                        f'{target_rad:.2f} rad; gia han them '
                        f'{self.figure_eight_timeout_grace_sec:.1f}s.')
                    angular = (self.angular_speed if self.phase == 0
                               else -self.angular_speed)
                    self._publish(self.linear_speed, angular)
                    return
                self.active_behavior = None
                self._stop(
                    'figure-eight timeout: khong nhan du odometry 2 vong')
                self.get_logger().warning(
                    f'Figure-eight moi quay {self.figure_eight_accumulated_rad:.2f}/'
                    f'{target_rad:.2f} rad o vong {self.phase + 1}/2.')
                return
            angular = self.angular_speed if self.phase == 0 else -self.angular_speed
            self._publish(self.linear_speed, angular)
            return

        phases = self._phases()
        if self.phase >= len(phases):
            finished = self.active_behavior
            self.active_behavior = None
            self._stop(f'hoàn thành {finished}')
            return

        linear, angular, duration = phases[self.phase]
        if now >= self.phase_deadline:
            self.phase += 1
            self.phase_deadline = now + duration
            if self.phase >= len(phases):
                self.active_behavior = None
                self._stop('hoàn thành hành vi')
                return
            linear, angular, _ = phases[self.phase]
        self._publish(linear, angular)

    def destroy_node(self) -> None:
        self._publish()
        super().destroy_node()


def main(args=None) -> None:
    rclpy.init(args=args)
    node = RobotBehaviorNode()
    try:
        rclpy.spin(node)
    except KeyboardInterrupt:
        pass
    finally:
        node.destroy_node()
        rclpy.shutdown()


if __name__ == '__main__':
    main()
