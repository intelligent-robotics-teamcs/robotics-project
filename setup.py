from setuptools import setup
from glob import glob
import os

package_name = 'pet_robot_pkg'

setup(
    name=package_name,
    version='0.0.1',

    # scripts 폴더 사용
    packages=[
    'scripts',
  ],

    data_files=[
        # ROS2 패키지 인식용
        ('share/ament_index/resource_index/packages',
            ['resource/' + package_name]),

        # package.xml 설치
        ('share/' + package_name, ['package.xml']),

        # config 파일 설치
        (os.path.join('share', package_name, 'config'),
            glob('config/*.yaml')),
    ],

    install_requires=[
        'setuptools',
        'PyYAML',
    ],

    zip_safe=True,

    maintainer='TeamComgong',
    maintainer_email='your_email@example.com',
    description='LLM + Vision based pet robot navigation system',
    license='MIT',

    entry_points={
        'console_scripts': [
            # 실행 명령어
            'nav2_goal_sender = scripts.nav2_goal_sender:main',
        ],
    },
)