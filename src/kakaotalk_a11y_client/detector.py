# SPDX-License-Identifier: MIT
# Copyright 2025-2026 dnz3d4c
"""이모지 탐지 모듈 (OpenCV 템플릿 매칭)"""

import cv2
import numpy as np
import pyautogui
from pathlib import Path
from typing import Optional

from .config import TEMPLATE_DIR, EMOJIS, MATCH_THRESHOLD


def capture_region(region: tuple[int, int, int, int]) -> np.ndarray:
    """지정 영역을 캡처하여 OpenCV 이미지로 반환한다.

    Args:
        region: (left, top, right, bottom) 좌표

    Returns:
        BGR 형식의 numpy 배열
    """
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
    """템플릿 이미지들을 로드한다.

    Returns:
        {emoji_id: (이름, 템플릿 이미지)} 딕셔너리
    """
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
    """이미지에서 이모지를 탐지한다.

    Args:
        image: 검색 대상 이미지 (BGR)
        templates: 템플릿 딕셔너리 (None이면 자동 로드)
        threshold: 매칭 임계값

    Returns:
        탐지된 이모지 리스트: [{"id": 1, "name": "하트", "pos": (x, y), "confidence": 0.95}, ...]
    """
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
                boxes, confidences, threshold, nms_threshold=0.3
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
    """탐지 결과를 음성 출력용 문자열로 변환한다.

    Args:
        detections: detect_emojis() 반환값

    Returns:
        예: "하트, 엄지, 체크 발견. 1~3 숫자키로 선택"
    """
    if not detections:
        return "이모지 없음"

    names = [d["name"] for d in detections]
    emoji_list = ", ".join(names)

    count = len(detections)
    if count == 1:
        return f"{emoji_list} 발견. 1번 키로 클릭"
    else:
        return f"{emoji_list} 발견. 1~{count} 숫자키로 선택"
