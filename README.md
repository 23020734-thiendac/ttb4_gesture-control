# TurtleBot 4 Gesture Control – Tuần 6

Repository này **chỉ chứa code điều khiển TurtleBot 4 bằng cử chỉ tay của tuần 6**. Không đưa code tuần trước, world/map, dataset, kết quả train hoặc file báo cáo vào repository này.

## Nội dung repository

- `tb4_week6/tb4_week6/gesture_recognition_node.py`: đọc webcam, MediaPipe và publish cử chỉ.
- `tb4_week6/tb4_week6/robot_behavior_node.py`: chọn, xác nhận và thực thi hành vi robot.
- `tb4_week6/launch/week6_gesture_control.launch.py`: launch hệ thống tuần 6.
- `tb4_week6/rviz/gesture_control.rviz`: cấu hình RViz tuần 6.
- `tb4_week6/models/gesture_recognizer.task`: model MediaPipe.
- `tb4_week6/package.xml`, `setup.py`: cấu hình package ROS 2.

Các package mô phỏng và world Small House là dependency đã có sẵn trong workspace trước đó; chúng **không được sao chép hoặc upload vào repository này**. Các file báo cáo cũng không được đưa lên GitHub.

## Chức năng

- Nhận diện `Pointing Up`, `Victory`, `Thumbs Up`, `Open Palm`, `Closed Fist`.
- Nhận diện bổ sung `OK` và `Military Salute` bằng landmark bàn tay.
- `Pointing Up`: robot tiến–lùi.
- `Victory`: robot chạy một vòng tròn đủ 360 độ.
- `OK`: robot chạy hình số 8 gồm hai vòng tròn ngược chiều.
- `Military Salute`: robot xoay trái–phải để chào.
- `Thumbs Up`: xác nhận hành vi một lần.
- `Open Palm`: dừng robot.
- `Closed Fist`: hủy hành vi.

## Yêu cầu

- Ubuntu 22.04
- ROS 2 Humble
- TurtleBot 4 Simulation/Gazebo
- Python 3
- Webcam laptop hoặc webcam USB
- OpenCV và MediaPipe

Cài thư viện Python nếu cần:

```bash
python3 -m pip install --user mediapipe opencv-python
```

## Đưa package vào workspace

Repository này chỉ cung cấp package tuần 6. Hãy đặt thư mục `tb4_week6` vào workspace đang có sẵn các dependency mô phỏng từ các tuần trước:

```bash
cd /home/thiendac/ros2_ws/src/TuongTacNguoi_Robot
# Sao chép thư mục tb4_week6 từ repository này vào đây
```

Không cần đưa các package tuần trước lên repository GitHub này.

## Build

```bash
cd /home/thiendac/ros2_ws
source /opt/ros/humble/setup.bash

PYTHONNOUSERSITE=1 colcon build \
  --symlink-install \
  --base-paths src/TuongTacNguoi_Robot \
  --packages-select tb4_week6

source /home/thiendac/ros2_ws/install/setup.bash
```

## Chạy chương trình

```bash
cd /home/thiendac/ros2_ws

pkill -f 'ros2 launch tb4_week6|gesture_recognition_node|robot_behavior_node|rviz2|ign gazebo|gzserver|gzclient' 2>/dev/null || true

source /opt/ros/humble/setup.bash
source install/setup.bash

ros2 launch tb4_week6 week6_gesture_control.launch.py \
  ros_domain_id:=68 \
  x:=5.5 y:=-1.8 z:=0.0 yaw:=0.0 \
  remove_dock:=true \
  week6_rviz:=true \
  show_window:=true
```

Launch này sử dụng các dependency mô phỏng đã có trong workspace, mở Gazebo, RViz và cửa sổ webcam.

## Topic chính

| Topic | Kiểu dữ liệu | Chức năng |
|---|---|---|
| `/detected_gesture` | `std_msgs/msg/String` | Cử chỉ và confidence, dạng `Gesture|confidence` |
| `/cmd_vel` | `geometry_msgs/msg/Twist` | Lệnh vận tốc robot |
| `/odom` | `nav_msgs/msg/Odometry` | Phản hồi vị trí và góc quay |

## Kiểm tra

```bash
ros2 topic echo /detected_gesture
ros2 topic echo /cmd_vel
ros2 topic echo /odom
```

Robot chỉ thực hiện hành vi sau khi nhận `Thumbs Up`. Sau khi xác nhận, không cần giữ cử chỉ trong suốt quá trình. `Open Palm` và `Closed Fist` luôn có quyền dừng hoặc hủy hành vi.
