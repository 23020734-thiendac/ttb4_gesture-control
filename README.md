# TurtleBot 4 Auto Gesture Control – Tuần 6

Repository này chỉ chứa package ROS 2 của tuần 6: điều khiển TurtleBot 4
bằng cử chỉ tay, chạy trong Gazebo và quan sát bằng RViz. World AWS RoboMaker
Small House cùng các model mà world tham chiếu đã được đóng gói bên trong
`tb4_week6/simulation`, nên bản clone không phụ thuộc vào package tuần 5 hay
đường dẫn tuyệt đối của máy phát triển.

Không đưa vào repository này: `tb4_week5`, `tb4_sim`, map maze, dataset, kết
quả train, build/install/log và các file báo cáo.

## Tính năng

- Webcam → OpenCV → MediaPipe Gesture Recognizer, có landmark/skeleton.
- Lọc confidence và frame ổn định trước khi phát hành cử chỉ.
- `Military Salute`: robot xoay trái–phải để chào.
- `OK`: robot chạy hình số 8 khép kín.
- `Pointing Up`: robot tiến–lùi.
- `Victory`: robot chạy một vòng tròn đủ 360 độ.
- `Thumbs Up`: xác nhận một lần; không cần giữ tay khi robot đang thực hiện.
- `Open Palm`: dừng ngay; `Closed Fist`: hủy hành vi.

## Cấu trúc

```text
tb4_week6/
├── launch/
│   ├── week6_gesture_control.launch.py
│   └── week6_small_house_sim.launch.py
├── simulation/
│   ├── worlds/small_house.world
│   └── models/                  # model/texture được world tham chiếu
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

Nếu hệ thống đã có các package TurtleBot 4 tương đương thì không cần cài lại.
`rosdep` sẽ kiểm tra các dependency ROS còn thiếu trong package:

```bash
sudo rosdep init 2>/dev/null || true
rosdep update
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
