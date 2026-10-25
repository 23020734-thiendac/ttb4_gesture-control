# TurtleBot 4 Auto Gesture Control – Tuần 6

## Tóm tắt khối xử lý tuần 6

Hệ thống tuần 6 gồm ba khối chính: khối camera thu hình từ webcam và dùng
OpenCV/MediaPipe để nhận diện cử chỉ tay; khối xử lý lọc confidence, ổn định
nhiều frame, chọn hành vi và chờ tín hiệu xác nhận; khối điều khiển chuyển
hành vi thành lệnh vận tốc `/cmd_vel` để TurtleBot 4 thực hiện trong Gazebo.
RViz dùng để quan sát robot, TF và trạng thái mô phỏng. World AWS RoboMaker
Small House cùng các model cần thiết đã được đóng gói trong `tb4_week6/simulation`.

## Bảng ánh xạ cử chỉ và hành vi

| Cử chỉ tay | Vai trò trong hệ thống | Hành vi của robot |
|---|---|---|
| `Military Salute` | Chọn hành vi chào điều lệnh | Xoay trái–phải với biên độ rộng để chào |
| `OK` | Chọn hành vi quỹ đạo số 8 | Chạy hai vòng tròn ngược chiều, tạo hình số 8 khép kín |
| `Pointing Up` | Chọn hành vi tiến–lùi | Đi thẳng tiến và lùi theo các đoạn đã cấu hình |
| `Victory` | Chọn hành vi vòng tròn | Chạy một vòng tròn đủ 360 độ |
| `Thumbs Up` | Xác nhận hành vi đã chọn | Xác nhận một lần; robot thực hiện đến khi hoàn thành |
| `Open Palm` | Lệnh an toàn tức thời | Dừng robot ngay lập tức |
| `Closed Fist` | Hủy hành vi đang chờ hoặc đang chạy | Hủy nhiệm vụ và đưa robot về trạng thái chờ |

Các hành vi `Military Salute`, `OK`, `Pointing Up` và `Victory` cần một lần
`Thumbs Up` để xác nhận. Sau khi xác nhận, không cần giữ cử chỉ trong suốt
thời gian robot thực hiện nhiệm vụ.

## Cấu trúc

```text
tb4_week6/
├── launch/
│   ├── week6_gesture_control.launch.py
│   └── week6_small_house_sim.launch.py
├── simulation/
│   ├── worlds/small_house.world
│   └── models/
├── models/gesture_recognizer.task
├── rviz/gesture_control.rviz
├── tb4_week6/                   # gesture_recognition_node và robot_behavior_node
├── package.xml
└── setup.py
```

## Yêu cầu trên máy mới

Clone không thể tự mang theo Ubuntu, ROS 2, Gazebo, driver webcam hoặc các
package hệ thống. Máy mới cần:

- Ubuntu 22.04 và ROS 2 Humble.
- TurtleBot 4 Simulator/Gazebo, IROBOT Create, `ros_gz_bridge` và
  `ros_ign_gazebo`.
- Python 3, webcam laptop/USB, OpenCV, NumPy và MediaPipe.

Sau khi cài ROS 2 Humble và source `/opt/ros/humble/setup.bash`, cài các
package phổ biến:

```bash
sudo apt update
sudo apt install python3-pip python3-opencv python3-numpy \
  ros-humble-turtlebot4-simulator ros-humble-ros-gz-bridge \
  ros-humble-ros-ign-gazebo
python3 -m pip install --user mediapipe opencv-python
```

## Clone và build

Ví dụ tạo workspace mới tại `~/ros2_ws`:

```bash
mkdir -p ~/ros2_ws/src/TuongTacNguoi_Robot
cd ~/ros2_ws/src/TuongTacNguoi_Robot
git clone https://github.com/23020734-thiendac/ttb4_gesture-control.git

cd ~/ros2_ws
source /opt/ros/humble/setup.bash
rosdep install --from-paths src/TuongTacNguoi_Robot/ttb4_gesture-control \
  --ignore-src -r -y
PYTHONNOUSERSITE=1 colcon build --symlink-install \
  --base-paths src/TuongTacNguoi_Robot/ttb4_gesture-control \
  --packages-select tb4_week6
source install/setup.bash
```

## Chạy Gazebo + RViz + điều khiển cử chỉ

```bash
cd ~/ros2_ws
export ROS_DOMAIN_ID=68
ros2 launch tb4_week6 week6_gesture_control.launch.py \
  ros_domain_id:=68 \
  x:=5.5 y:=-1.8 z:=0.0 yaw:=0.0 \
  remove_dock:=true \
  week6_rviz:=true \
  show_window:=true
```

Launch tự lấy world/model từ `tb4_week6/simulation`, đặt cấu hình render để
giảm lỗi Gazebo màn hình đen, chờ Gazebo sẵn sàng rồi mới spawn robot và mở
RViz. Không cần chạy package tuần trước hoặc mở Gazebo/RViz thủ công.

Nếu camera không phải thiết bị số 0, thêm `camera_index:=1`. Nếu chỉ muốn
kiểm tra node mà không mở RViz/camera, dùng `week6_rviz:=false` hoặc
`show_window:=false`.

## Topic kiểm tra

| Topic | Kiểu | Ý nghĩa |
|---|---|---|
| `/detected_gesture` | `std_msgs/msg/String` | Cử chỉ và confidence |
| `/cmd_vel` | `geometry_msgs/msg/Twist` | Lệnh vận tốc robot |
| `/odom` | `nav_msgs/msg/Odometry` | Phản hồi vị trí/góc quay |

```bash
ros2 topic echo /detected_gesture
ros2 topic echo /cmd_vel
ros2 topic echo /odom
```

Lưu ý: `ROS_DOMAIN_ID` của các terminal phải giống nhau; webcam cần được
phép truy cập; máy có GPU lỗi hoặc không có GPU vẫn có thể chạy nhờ cấu hình
render dự phòng bằng phần mềm trong launch.
