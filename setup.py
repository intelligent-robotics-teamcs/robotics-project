from setuptools import setup, find_packages
from glob import glob
import os

package_name = 'pet_robot_pkg'
world_files = [
    path for path in glob('worlds/*')
    if os.path.isfile(path)
]
model_files = [
    path for path in glob('models/**/*', recursive=True)
    if os.path.isfile(path)
]

setup(
    name=package_name,
    version='0.0.1',

    packages=find_packages(include=['script', 'script.*']),

    data_files=[
        # ROS2 패키지 인식용
        ('share/ament_index/resource_index/packages',
            ['resource/' + package_name]),

        # package.xml 설치
        ('share/' + package_name, ['package.xml']),

        # config 파일 설치
        (os.path.join('share', package_name, 'config'),
            glob('config/*.yaml')),
        (os.path.join('share', package_name, 'launch'),
            glob('launch/*.launch.py')),
        (os.path.join('share', package_name, 'worlds'),
            world_files),
        *[
            (
                os.path.join('share', package_name, os.path.dirname(path)),
                [path],
            )
            for path in model_files
        ],
    ],

    install_requires=[
        'setuptools',
        'PyYAML',
        'ultralytics',
        'openai',
        'python-dotenv',
    ],

    zip_safe=True,

    maintainer='TeamComgong',
    maintainer_email='your_email@example.com',
    description='LLM + Vision based pet robot navigation system',
    license='MIT',

    entry_points={
        'console_scripts': [
            # 실행 명령어
            'nav2_goal_sender = script.nav2_goal_sender:main',
            'sequence_executor = script.sequence_executor:main',
            'camera_image_processor = script.camera_image_processor:main',
            'vision_sequence_executor = script.vision_sequence_executor:main',
            'llm_sequence_node = script.llm.llm_sequence_node:main',
            'agent_console = script.llm.agent_console:main',
            'initial_scan_rotator = script.sanity_checks.initial_scan_rotator:main',
            'moving_pet_targets = script.sanity_checks.moving_pet_targets:main',
            'multi_target_runner = script.sanity_checks.multi_target_runner:main',
            'run_yolo_inference = script.sanity_checks.run_yolo_inference:main',
            'test_pipeline = script.sanity_checks.test_pipeline:main',
            'vision_to_executor = script.sanity_checks.vision_to_executor:main',
        ],
    },
)
