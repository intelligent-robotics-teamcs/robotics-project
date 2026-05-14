#!/usr/bin/env python3

try:
    from script.run_yolo_inference import main
except ImportError:
    from run_yolo_inference import main


if __name__ == "__main__":
    raise SystemExit(main())
