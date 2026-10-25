# TB4 Week 6 – Điều khiển bằng cử chỉ tay

Package này độc lập với `tb4_week5`. Nó dùng webcam laptop, MediaPipe Gesture
Recognizer và ROS 2 để điều khiển TurtleBot 4 trong Gazebo.

## Cài dependency Python

```bash
python3 -m pip install --user mediapipe opencv-python
```

Tải model MediaPipe:

```bash
cd tb4_week6/models
wget -O gesture_recognizer.task \
  https://storage.googleapis.com/mediapipe-models/gesture_recognizer/gesture_recognizer/float16/1/gesture_recognizer.task
```

## Luồng điều khiển

```text
Webcam → OpenCV → MediaPipe → /detected_gesture
                                   ↓
                              robot_behavior_node
                                   ↓
                                /cmd_vel
```

Robot chỉ chạy sau khi đã chọn hành vi và nhận `Thumbs Up` xác nhận.

| Cử chỉ | Chức năng |
|---|---|
| `Military Salute` | Chọn hành vi robot xoay trái–phải để chào |
| `OK` | Chọn quỹ đạo số 8 khép kín |
| `Pointing Up` | Chọn tiến–lùi 4 lần |
| `Victory` | Chọn chạy theo quỹ đạo tròn |
| `Thumbs Up` | Xác nhận hành vi đang chọn |
| `Open Palm` | Dừng ngay lập tức |
| `Closed Fist` | Hủy hành vi và trở về chờ |

Node có lọc cử chỉ ổn định, ngưỡng confidence, thời gian xác nhận và watchdog.
Nếu mất tín hiệu webcam hoặc topic gesture quá thời gian cho phép, robot tự
publish vận tốc bằng 0.

MediaPipe cung cấp trực tiếp các cử chỉ như `Open Palm`, `Closed Fist`,
`Pointing Up`, `Victory` và `Thumbs Up`. Lệnh chào được bổ sung bằng bộ lọc
landmark cho tư thế chào điều lệnh quân đội: một tay đưa lên vùng trán, bốn
ngón duỗi sát nhau, ngón cái thu vào và các đầu ngón hướng lên. Vì vậy một
bàn tay xòe bình thường vẫn giữ chức năng `Open Palm` để dừng robot. `OK`
được bổ sung bằng hình học landmark: ngón cái và ngón trỏ tạo vòng kín, đồng
thời ít nhất hai ngón còn lại duỗi ra.

Cửa sổ webcam có hiển thị `hand landmarks` (các điểm khớp) và `hand skeleton`
(các đường nối giữa điểm khớp) giống chế độ MediaPipe Hands. Chế độ này giúp
quan sát việc nhận diện tư thế chào, cử chỉ `OK`, hai ngón `Victory` và giảm độ trễ nhờ camera 640×480,
tần số xử lý 20 Hz, bộ đệm camera chỉ giữ frame mới nhất và cần 3 frame ổn định.

Khi chọn `Victory`, robot chờ `Thumbs Up` để xác nhận an toàn rồi chạy một vòng
đủ 360 độ. Bán kính vòng tròn xấp xỉ `linear_speed / angular_speed`; có thể
dừng ngay bằng `Open Palm`.

`Thumbs Up` chỉ là tín hiệu xác nhận một lần. Sau khi xác nhận, hành vi được
ghi nhớ và chạy đến hết nhiệm vụ; không cần giữ ngón cái trong suốt quá trình.
Mặc định mỗi đoạn tiến/lùi dài 3 giây và `circle_turns:=1.0` tương ứng đúng
một vòng 360 độ. Khi chạy circle, node tích lũy góc quay thực tế từ `/odom`
và chỉ dừng khi đủ `2π` rad; `circle_timeout_sec` chỉ là giới hạn dự phòng.
Cấu hình mặc định cho phép 60 giây và gia hạn thêm tối đa 45 giây nếu robot đã
đi được ít nhất 75% vòng, phòng trường hợp Gazebo chạy chậm hoặc odometry cập
nhật không đều.
Cử chỉ `Military Salute` chạy ba nhịp xoay trái–phải để robot chào. Cử chỉ `OK`
chạy hai vòng tròn liên tiếp: vòng đầu quay một chiều, vòng sau quay chiều
ngược lại; mỗi vòng chỉ chuyển pha sau khi odometry xác nhận đủ `2π` rad, tạo
quỹ đạo số 8 khép kín tại điểm giao giữa hai vòng. Timeout của số 8 được tính
riêng cho từng vòng; nếu một vòng đã vượt 75% mà Gazebo chạy chậm, node được
gia hạn thêm một khoảng an toàn trước khi dừng.

## Build và chạy

```bash
cd /home/thiendac/ros2_ws
source /opt/ros/humble/setup.bash

PYTHONNOUSERSITE=1 colcon build \
  --symlink-install \
  --base-paths src/TuongTacNguoi_Robot \
  --packages-select tb4_sim tb4_week5 tb4_week6

source /home/thiendac/ros2_ws/install/setup.bash
```

Chạy toàn bộ mô phỏng và điều khiển:

```bash
ros2 launch tb4_week6 week6_gesture_control.launch.py \
  ros_domain_id:=68 \
  camera_index:=0 \
  show_window:=true \
  week6_rviz:=true
```

Mặc định robot spawn tại `(x=5.5, y=-1.8)`, vùng sàn trống ở giữa gian bếp
trung tâm để có khoảng không rộng khi thực hiện các hành vi. Có thể thay đổi
vị trí bằng `x:=... y:=... yaw:=...` nếu cần.

Launch này cố ý chờ Gazebo tải Small House trước khi spawn robot và controller,
sau đó chờ TF/robot description rồi mới mở RViz. Vì vậy lần đầu có thể mất một
ít thời gian; không mở thêm RViz hoặc Gazebo bằng lệnh khác trong lúc chờ.

Nếu cần chạy không mở RViz, dùng `week6_rviz:=false`. RViz Week 6 dùng `odom`
làm fixed frame, không phụ thuộc map, AMCL hay Nav2.

Nếu webcam không phải camera số 0, thử `camera_index:=1`. Kiểm tra kết quả:

```bash
ros2 topic echo /detected_gesture
ros2 topic echo /cmd_vel
```
