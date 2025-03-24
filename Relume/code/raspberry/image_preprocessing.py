#!/usr/bin/env python3
"""
image_preprocessing.py
======================

本模块负责对采集到的图像进行全面预处理，主要功能包括：
    1. 彩色图像去噪（采用 fastNlMeansDenoisingColored 保持细节）
    2. 灰度转换，便于后续处理
    3. 对比度增强（采用自适应直方图均衡化 CLAHE 提升细节表现）
    4. 高斯平滑与 Canny 边缘检测，提取关键边缘信息
    5. 形态学处理（闭运算）去除噪点，增强目标轮廓
    6. 最终合并边缘信息与均衡图，形成稳定的预处理图像

支持动态参数调整与调试显示，可通过 debug 模式观察各处理阶段效果，便于调优。
"""

import cv2
import numpy as np
import logging

# 配置日志输出
logging.basicConfig(level=logging.INFO, format='[%(asctime)s] %(levelname)s: %(message)s')

def preprocess(image, debug=False):
    """
    主预处理流程，对输入图像进行一系列处理，得到用于目标检测的高质量图像。
    
    流程：
      1. 去噪：使用 fastNlMeansDenoisingColored 去除噪声同时保留颜色细节。
      2. 灰度转换：将去噪后的图像转换为灰度图。
      3. 对比度增强：采用 CLAHE 自适应直方图均衡化提高图像对比度。
      4. 高斯模糊与边缘检测：先平滑图像，再通过 Canny 算法提取边缘。
      5. 形态学处理：利用闭运算消除边缘检测中的小噪点。
      6. 合成：将增强后的灰度图与形态学处理结果融合，得到最终预处理图像。
    
    :param image: 输入图像，要求为 BGR 格式
    :param debug: 是否开启调试模式（显示中间处理结果）
    :return: 预处理后的图像
    """
    if image is None:
        raise ValueError("输入图像为空，请检查数据源。")

    # 1. 去噪处理
    denoised = cv2.fastNlMeansDenoisingColored(image, None, h=10, hColor=10, templateWindowSize=7, searchWindowSize=21)
    logging.info("图像去噪完成。")
    if debug:
        cv2.imshow("Step 1 - Denoised", denoised)
        cv2.waitKey(1)

    # 2. 灰度转换
    gray = cv2.cvtColor(denoised, cv2.COLOR_BGR2GRAY)
    logging.info("灰度转换完成。")
    if debug:
        cv2.imshow("Step 2 - Grayscale", gray)
        cv2.waitKey(1)

    # 3. 对比度增强 - 使用 CLAHE 自适应直方图均衡化
    clahe = cv2.createCLAHE(clipLimit=2.0, tileGridSize=(8, 8))
    equalized = clahe.apply(gray)
    logging.info("对比度增强（CLAHE）完成。")
    if debug:
        cv2.imshow("Step 3 - Equalized", equalized)
        cv2.waitKey(1)

    # 4. 高斯模糊平滑 + Canny 边缘检测
    blurred = cv2.GaussianBlur(equalized, (5, 5), 0)
    edges = cv2.Canny(blurred, threshold1=50, threshold2=150)
    logging.info("高斯平滑与边缘检测完成。")
    if debug:
        cv2.imshow("Step 4 - Edges", edges)
        cv2.waitKey(1)

    # 5. 形态学处理 - 闭运算去除小噪点，保留连续边缘
    kernel = cv2.getStructuringElement(cv2.MORPH_RECT, (3, 3))
    morphed = cv2.morphologyEx(edges, cv2.MORPH_CLOSE, kernel, iterations=1)
    logging.info("形态学处理完成。")
    if debug:
        cv2.imshow("Step 5 - Morphology", morphed)
        cv2.waitKey(1)

    # 6. 融合处理：将 CLAHE 图与形态学边缘图按比例融合
    preprocessed = cv2.addWeighted(equalized, 0.8, morphed, 0.2, 0)
    logging.info("图像预处理整体完成。")
    if debug:
        cv2.imshow("Final Preprocessed", preprocessed)
        cv2.waitKey(1)

    return preprocessed

def adjust_parameters(image, denoise_h=10, denoise_hColor=10, clipLimit=2.0, tileGridSize=(8, 8),
                      canny_thresh1=50, canny_thresh2=150, debug=False):
    """
    提供可调参数版本的预处理函数，便于通过参数调节获得最优预处理效果。
    
    :param image: 输入图像（BGR 格式）
    :param denoise_h: 彩色去噪参数 h
    :param denoise_hColor: 彩色去噪参数 hColor
    :param clipLimit: CLAHE 的 clipLimit
    :param tileGridSize: CLAHE 的 tileGridSize
    :param canny_thresh1: Canny 算法下阈值
    :param canny_thresh2: Canny 算法上阈值
    :param debug: 是否开启调试显示
    :return: 预处理后的图像
    """
    if image is None:
        raise ValueError("输入图像为空，请检查数据源。")
    
    # 1. 去噪
    denoised = cv2.fastNlMeansDenoisingColored(image, None, h=denoise_h, hColor=denoise_hColor,
                                                templateWindowSize=7, searchWindowSize=21)
    if debug:
        cv2.imshow("Adjust - Denoised", denoised)
        cv2.waitKey(1)

    # 2. 灰度转换
    gray = cv2.cvtColor(denoised, cv2.COLOR_BGR2GRAY)
    if debug:
        cv2.imshow("Adjust - Grayscale", gray)
        cv2.waitKey(1)

    # 3. 对比度增强
    clahe = cv2.createCLAHE(clipLimit=clipLimit, tileGridSize=tileGridSize)
    equalized = clahe.apply(gray)
    if debug:
        cv2.imshow("Adjust - Equalized", equalized)
        cv2.waitKey(1)

    # 4. 高斯平滑与边缘检测
    blurred = cv2.GaussianBlur(equalized, (5, 5), 0)
    edges = cv2.Canny(blurred, threshold1=canny_thresh1, threshold2=canny_thresh2)
    if debug:
        cv2.imshow("Adjust - Edges", edges)
        cv2.waitKey(1)

    # 5. 形态学处理
    kernel = cv2.getStructuringElement(cv2.MORPH_RECT, (3, 3))
    morphed = cv2.morphologyEx(edges, cv2.MORPH_CLOSE, kernel, iterations=1)
    if debug:
        cv2.imshow("Adjust - Morphology", morphed)
        cv2.waitKey(1)

    # 6. 融合
    preprocessed = cv2.addWeighted(equalized, 0.8, morphed, 0.2, 0)
    if debug:
        cv2.imshow("Adjust - Final Preprocessed", preprocessed)
        cv2.waitKey(1)

    logging.info("自定义参数图像预处理完成。")
    return preprocessed

if __name__ == '__main__':
    # 调试示例：加载指定图像，展示完整预处理流程效果
    import sys
    if len(sys.argv) > 1:
        img_path = sys.argv[1]
    else:
        img_path = 'test_image.jpg'  # 请替换为有效的测试图像路径

    image = cv2.imread(img_path)
    if image is None:
        raise Exception("无法加载图像，请检查路径或文件格式。")
    
    # 调用主预处理函数（开启调试模式显示每一步骤效果）
    result = preprocess(image, debug=True)
    
    cv2.imshow("Final Result", result)
    cv2.waitKey(0)
    cv2.destroyAllWindows()
