#!/usr/bin/env python3
"""
cinema_driver.py
================

本模块用于 Raspberry Pi 4 上的摄像头采集，并针对机器人竞赛需求进行了全面扩展：
  - 支持摄像头初始化及动态参数设置（分辨率、帧率、曝光、白平衡、亮度等）
  - 实现连续图像采集，采用独立线程运行，并支持回调机制联动后续模块
  - 异常检测与自动重启，保证长时间运行的稳定性
  - 调试模式支持实时显示采集图像，便于现场调试

注意：部分高级参数的设置依赖于摄像头硬件和驱动支持情况，请根据实际硬件进行调整。
"""

import cv2
import time
import threading
import logging

# 配置日志输出
logging.basicConfig(level=logging.INFO, format='[%(asctime)s] %(levelname)s: %(message)s')

class CinemaDriver:
    def __init__(self, camera_id=0, width=640, height=480, fps=30):
        """
        初始化摄像头参数，设置默认分辨率、帧率等参数。
        :param camera_id: 摄像头ID，默认 0
        :param width: 图像宽度
        :param height: 图像高度
        :param fps: 帧率
        """
        self.camera_id = camera_id
        self.width = width
        self.height = height
        self.fps = fps

        # 高级参数（部分参数需摄像头支持）
        self.exposure = -4         # 曝光值，-1表示自动曝光，数值根据硬件支持调整
        self.white_balance = 4000  # 白平衡（色温），单位K，根据摄像头实际支持情况调整
        self.brightness = 150      # 亮度
        self.contrast = 50         # 对比度

        self.cap = None
        self.running = False
        self.capture_thread = None
        self.callback = None       # 外部注册回调，处理每帧图像
        self.fail_count = 0        # 连续采集失败计数

    def initialize_camera(self):
        """
        初始化摄像头，设置基础与高级参数，并预热摄像头。
        """
        logging.info("初始化摄像头...")
        self.cap = cv2.VideoCapture(self.camera_id)
        if not self.cap.isOpened():
            raise Exception("无法打开摄像头，请检查连接或更换摄像头ID。")

        # 设置基本参数
        self.cap.set(cv2.CAP_PROP_FRAME_WIDTH, self.width)
        self.cap.set(cv2.CAP_PROP_FRAME_HEIGHT, self.height)
        self.cap.set(cv2.CAP_PROP_FPS, self.fps)
        
        # 设置高级参数（部分参数可能需要根据摄像头型号验证是否生效）
        self.cap.set(cv2.CAP_PROP_EXPOSURE, float(self.exposure))
        self.cap.set(cv2.CAP_PROP_WHITE_BALANCE_BLUE_U, float(self.white_balance))
        self.cap.set(cv2.CAP_PROP_BRIGHTNESS, float(self.brightness))
        self.cap.set(cv2.CAP_PROP_CONTRAST, float(self.contrast))
        
        # 预热摄像头，确保图像稳定输出
        time.sleep(2)
        logging.info(f"摄像头初始化完成：ID={self.camera_id}, 分辨率={self.width}x{self.height}, FPS={self.fps}")
        self.fail_count = 0

    def set_camera_parameters(self, **params):
        """
        动态设置摄像头参数，支持分辨率、帧率、曝光、白平衡、亮度、对比度等。
        :param params: 键值对参数，如 width=1280, height=720, exposure=-3, white_balance=4500
        """
        if self.cap is None:
            logging.warning("摄像头未初始化，无法设置参数。")
            return

        for key, value in params.items():
            if key == 'width':
                self.width = value
                self.cap.set(cv2.CAP_PROP_FRAME_WIDTH, value)
            elif key == 'height':
                self.height = value
                self.cap.set(cv2.CAP_PROP_FRAME_HEIGHT, value)
            elif key == 'fps':
                self.fps = value
                self.cap.set(cv2.CAP_PROP_FPS, value)
            elif key == 'exposure':
                self.exposure = value
                self.cap.set(cv2.CAP_PROP_EXPOSURE, float(value))
            elif key == 'white_balance':
                self.white_balance = value
                self.cap.set(cv2.CAP_PROP_WHITE_BALANCE_BLUE_U, float(value))
            elif key == 'brightness':
                self.brightness = value
                self.cap.set(cv2.CAP_PROP_BRIGHTNESS, float(value))
            elif key == 'contrast':
                self.contrast = value
                self.cap.set(cv2.CAP_PROP_CONTRAST, float(value))
            else:
                logging.warning(f"未知参数：{key}")
        logging.info("摄像头参数更新完成。")

    def register_callback(self, callback_func):
        """
        注册回调函数，每采集一帧时调用该函数进行后续处理。
        :param callback_func: 接受单帧图像（numpy数组）的函数
        """
        if not callable(callback_func):
            raise ValueError("回调函数必须是可调用的。")
        self.callback = callback_func
        logging.info("回调函数注册成功。")

    def start_capture(self):
        """
        启动连续采集线程，持续采集图像并调用回调函数处理。
        """
        if self.cap is None:
            self.initialize_camera()
        self.running = True
        self.capture_thread = threading.Thread(target=self._capture_loop, daemon=True)
        self.capture_thread.start()
        logging.info("连续采集线程已启动。")

    def _capture_loop(self):
        """
        内部采集主循环：连续采集图像，调用回调函数，同时处理采集异常。
        """
        while self.running:
            ret, frame = self.cap.read()
            if not ret or frame is None:
                self.fail_count += 1
                logging.error(f"图像采集失败，当前失败次数：{self.fail_count}")
                time.sleep(0.1)
                if self.fail_count >= 5:
                    logging.warning("连续采集失败次数过多，尝试重新初始化摄像头...")
                    self.release_camera()
                    try:
                        self.initialize_camera()
                    except Exception as e:
                        logging.error(f"重新初始化失败：{e}")
                continue
            self.fail_count = 0  # 成功采集后重置计数

            # 调用回调函数进行后续处理
            if self.callback:
                try:
                    self.callback(frame)
                except Exception as e:
                    logging.error(f"回调函数处理帧时出错：{e}")
            # 控制采集速率，尽可能接近设定帧率
            time.sleep(1 / self.fps)

    def stop_capture(self):
        """
        停止连续采集线程，并等待线程结束。
        """
        self.running = False
        if self.capture_thread is not None:
            self.capture_thread.join()
            logging.info("连续采集线程已停止。")

    def get_frame(self):
        """
        单帧采集接口，适用于同步模式调用。
        :return: 单帧图像（numpy数组）
        """
        if self.cap is None:
            raise Exception("摄像头未初始化，请先调用 initialize_camera()。")
        ret, frame = self.cap.read()
        if not ret or frame is None:
            raise Exception("单帧采集失败。")
        return frame

    def release_camera(self):
        """
        释放摄像头资源，关闭 VideoCapture 对象。
        """
        if self.cap is not None:
            self.cap.release()
            self.cap = None
            logging.info("摄像头资源已释放。")


# 示例：如何集成其他模块联动使用（请根据实际需求导入相应模块）
if __name__ == '__main__':
    # 示例回调函数：仅显示采集图像，并检测 'q' 键退出
    def process_frame(frame):
        cv2.imshow("Cinema Driver - Processed Frame", frame)
        if cv2.waitKey(1) & 0xFF == ord('q'):
            driver.stop_capture()

    driver = CinemaDriver(camera_id=0, width=640, height=480, fps=30)
    try:
        driver.initialize_camera()
        # 可通过 set_camera_parameters 动态调整参数（例如在弱光环境下调低曝光）
        driver.set_camera_parameters(exposure=-3, brightness=160)
        driver.register_callback(process_frame)
        driver.start_capture()
        # 主线程等待采集线程结束，此处可整合其他任务调度逻辑
        while driver.running:
            time.sleep(1)
    except Exception as ex:
        logging.error(f"系统异常：{ex}")
    finally:
        driver.stop_capture()
        driver.release_camera()
        cv2.destroyAllWindows()
