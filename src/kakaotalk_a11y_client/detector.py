# SPDX-License-Identifier: MIT
# Copyright 2025-2026 dnz3d4c
"""이모지 탐지 모듈 (OpenCV 템플릿 매칭)"""

import cv2
import numpy as np
import pyautogui
from pathlib import Path
from typing import Optional

from .config import TEMPLATE_DIR, EMOJIS, MATCH_THRESHOLD, CV_NMS_THRESHOLD


def capture_region(region: tuple[int, int, int, int]) -> np.ndarray:
    """pyautogui로 캡처 후 BGR numpy 배열 반환."""
    left, top, right, bottom = region
    width = right - left
    height = bottom - top

    # pyautogui로 캡처 (PIL Image 반환)
    screenshot = pyautogui.screenshot(region=(left, top, width, height))

    # PIL -> numpy -> BGR 변환
    img = np.array(screenshot)
    img_bgr = cv2.cvtColor(img, cv2.COLOR_RGB2BGR)

    return img_bgr


def load_templates() -> dict[int, tuple[str, np.ndarray]]:
    """TEMPLATE_DIR에서 이모지 PNG 로드. {id: (name, img)}"""
    templates = {}

    for emoji_id, info in EMOJIS.items():
        template_path = TEMPLATE_DIR / info["file"]
        if template_path.exists():
            template = cv2.imread(str(template_path))
            if template is not None:
                templates[emoji_id] = (info["name"], template)

    return templates


def detect_emojis(
    image: np.ndarray,
    templates: Optional[dict] = None,
    threshold: float = MATCH_THRESHOLD,
) -> list[dict]:
    """템플릿 매칭 + NMS. 결과는 x좌표순 정렬."""
    if templates is None:
        templates = load_templates()

    results = []

    for emoji_id, (name, template) in templates.items():
        # 템플릿 매칭
        match_result = cv2.matchTemplate(image, template, cv2.TM_CCOEFF_NORMED)

        # 임계값 이상인 위치 찾기
        locations = np.where(match_result >= threshold)

        # 중복 제거를 위한 NMS (Non-Maximum Suppression) 적용
        h, w = template.shape[:2]
        boxes = []
        confidences = []

        for pt in zip(*locations[::-1]):  # (x, y) 형태로 변환
            confidence = match_result[pt[1], pt[0]]
            boxes.append([pt[0], pt[1], pt[0] + w, pt[1] + h])
            confidences.append(float(confidence))

        # NMS로 중복 제거
        if boxes:
            indices = cv2.dnn.NMSBoxes(
                boxes, confidences, threshold, nms_threshold=CV_NMS_THRESHOLD
            )

            # OpenCV 버전에 따라 indices 형식이 다름
            if len(indices) > 0:
                indices = indices.flatten() if hasattr(indices, 'flatten') else indices

            for idx in indices:
                box = boxes[idx]
                # 중앙 좌표 계산
                center_x = (box[0] + box[2]) // 2
                center_y = (box[1] + box[3]) // 2

                results.append(
                    {
                        "id": emoji_id,
                        "name": name,
                        "pos": (center_x, center_y),
                        "confidence": confidences[idx],
                    }
                )

    # x 좌표순 정렬 (왼쪽에서 오른쪽)
    results.sort(key=lambda x: x["pos"][0])

    return results


def format_detection_result(detections: list[dict]) -> str:
    """음성 출력용. 예: "하트, 엄지 발견. 1~2 숫자키로 선택" """
    if not detections:
        return "이모지 없음"

    names = [d["name"] for d in detections]
    emoji_list = ", ".join(names)

    count = len(detections)
    if count == 1:
        return f"{emoji_list} 발견. 1번 키로 클릭"
    else:
        return f"{emoji_list} 발견. 1~{count} 숫자키로 선택"
