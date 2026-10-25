from glob import glob
import os

from setuptools import setup


package_name = 'tb4_week6'

setup(
    name=package_name,
    version='0.1.0',
    packages=[package_name],
    data_files=[
        ('share/ament_index/resource_index/packages',
         ['resource/' + package_name]),
        ('share/' + package_name, ['package.xml', 'README.md']),
        (os.path.join('share', package_name, 'launch'),
         glob('launch/*.launch.py')),
        (os.path.join('share', package_name, 'models'),
         glob('models/*')),
        (os.path.join('share', package_name, 'rviz'),
         glob('rviz/*.rviz')),
    ],
    install_requires=['setuptools'],
    zip_safe=True,
    maintainer='TurtleBot 4 student',
    maintainer_email='student@example.com',
    description='Gesture recognition and safe behavior control for TurtleBot 4.',
    license='Apache-2.0',
    entry_points={
        'console_scripts': [
            'gesture_recognition_node = '
            'tb4_week6.gesture_recognition_node:main',
            'robot_behavior_node = '
            'tb4_week6.robot_behavior_node:main',
        ],
    },
)
