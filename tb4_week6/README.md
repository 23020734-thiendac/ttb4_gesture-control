# TB4 Week 6 – Điều khiển TurtleBot 4 bằng cử chỉ tay

## Bảng ánh xạ cử chỉ và hành vi

| Cử chỉ tay | Vai trò | Hành vi robot |
|---|---|---|
| `Military Salute` | Chọn hành vi chào điều lệnh | Xoay trái–phải để chào |
| `OK` | Chọn quỹ đạo số 8 | Hai vòng tròn ngược chiều, khép kín |
| `Pointing Up` | Chọn tiến–lùi | Tiến và lùi theo đoạn đã cấu hình |
| `Victory` | Chọn vòng tròn | Một vòng đủ 360 độ |
| `Thumbs Up` | Xác nhận | Xác nhận một lần, không cần giữ tay |
| `Open Palm` | Dừng khẩn cấp | Dừng ngay lập tức |
| `Closed Fist` | Hủy hành vi | Hủy nhiệm vụ và chờ lệnh mới |

## Nội dung package

- `launch/week6_gesture_control.launch.py`: khởi động toàn bộ hệ thống.
- `launch/week6_small_house_sim.launch.py`: launch Gazebo độc lập cho Small House.
- `simulation/worlds/small_house.world`: world mô phỏng.
- `simulation/models/`: model và texture của môi trường.
- `models/gesture_recognizer.task`: model MediaPipe đã dùng.
- `rviz/gesture_control.rviz`: cấu hình RViz dùng `odom` làm fixed frame.
- `tb4_week6/gesture_recognition_node.py`: nhận diện cử chỉ.
- `tb4_week6/robot_behavior_node.py`: chọn, xác nhận và thực thi hành vi.

## Phụ thuộc trên máy mới

GitHub chứa mã nguồn và tài nguyên của bài tuần 6, nhưng không thể chứa hệ
điều hành, ROS 2 hoặc driver Gazebo. Máy mới cần có:

- Ubuntu 22.04 và ROS 2 Humble.
- TurtleBot 4 Simulator/Gazebo cùng các package TurtleBot 4/IROBOT Create.
- Webcam hoạt động.
- Python 3, OpenCV, NumPy và MediaPipe.

Sau khi source ROS 2, cài các thư viện cần thiết:

```bash
sudo apt update
sudo apt install python3-pip python3-opencv python3-numpy \
  ros-humble-turtlebot4-simulator ros-humble-ros-gz-bridge \
  ros-humble-ros-ign-gazebo
python3 -m pip install --user mediapipe opencv-python
```

## Clone, build và chạy trên máy khác

Ví dụ workspace là `~/ros2_ws`:

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

Khởi động Gazebo, robot, RViz và cửa sổ nhận diện:

```bash
export ROS_DOMAIN_ID=68
ros2 launch tb4_week6 week6_gesture_control.launch.py \
  ros_domain_id:=68 \
  x:=5.5 y:=-1.8 z:=0.0 yaw:=0.0 \
  remove_dock:=true week6_rviz:=true show_window:=true
```

## Topic chính

| Topic | Kiểu dữ liệu | Chức năng |
|---|---|---|
| `/detected_gesture` | `std_msgs/msg/String` | Cử chỉ và confidence |
| `/cmd_vel` | `geometry_msgs/msg/Twist` | Lệnh vận tốc robot |
| `/odom` | `nav_msgs/msg/Odometry` | Phản hồi vị trí và góc quay |

Kiểm tra khi hệ thống đang chạy:

```bash
ros2 topic echo /detected_gesture
ros2 topic echo /cmd_vel
ros2 topic echo /odom
```

Các thư mục `build/`, `install/`, `log/`, `__pycache__/`, dataset, kết quả
train và file báo cáo không thuộc repository tuần 6.
