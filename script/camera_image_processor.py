#!/usr/bin/env python3

import rclpy
from rclpy.node import Node
from sensor_msgs.msg import Image
from cv_bridge import CvBridge
import cv2


class CameraImageProcessor(Node):
    def __init__(self):
        super().__init__("camera_image_processor")

        self.bridge = CvBridge()
        self.latest_frame = None

        self.subscription = self.create_subscription(
            Image,
            "/camera/image_raw",
            self.image_callback,
            10,
        )

        self.get_logger().info("[CAMERA] subscribed to /camera/image_raw")

    def image_callback(self, msg):
        try:
            frame = self.bridge.imgmsg_to_cv2(msg, desired_encoding="bgr8")
        except Exception as e:
            self.get_logger().error(f"[CAMERA] cv_bridge error: {e}")
            return

        processed_frame = self.preprocess_frame(frame)
        self.latest_frame = processed_frame

        self.get_logger().info(
            f"[CAMERA] frame received: shape={processed_frame.shape}"
        )

        cv2.imshow("camera_image_processor", processed_frame)
        cv2.waitKey(1)

    def preprocess_frame(self, frame):
        resized_frame = cv2.resize(frame, (640, 640))
        return resized_frame


def main(args=None):
    rclpy.init(args=args)

    node = CameraImageProcessor()

    try:
        rclpy.spin(node)
    except KeyboardInterrupt:
        pass

    cv2.destroyAllWindows()
    node.destroy_node()
    rclpy.shutdown()


if __name__ == "__main__":
    main()