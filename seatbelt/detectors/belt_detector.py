import logging
from pathlib import Path
from threading import Lock

import numpy as np

from ..inference import ModelRuntimeError, OnnxClassificationSpec, OnnxImageClassifierInfer

logger = logging.getLogger("seatbelt.services")


class BeltDetector:
    # 人物安全带分类器

    _model_root = Path(__file__).resolve().parent.parent / "assets" / "onnx"
    _engine_lock = Lock()
    _engine = None
    _top_expand_ratio = 0.05
    _bottom_expand_ratio = 0.10
    _spec = OnnxClassificationSpec(
        model_path=_model_root / "resnet18_seatbelt_128.onnx",
        class_names=("belt_off", "belt_on"),
        infer_size=(128, 128),
        image_mean=(0.485, 0.456, 0.406),
        image_std=(0.229, 0.224, 0.225),
        score_threshold=0.6,
        keep_ratio=True,
        center_pad=True,
        normalize_to_unit=True,
    )

    @classmethod
    def _get_engine(cls):
        # 延迟加载并复用安全带分类模型
        if cls._engine is not None:
            return cls._engine

        with cls._engine_lock:
            if cls._engine is not None:
                return cls._engine
            if not cls._spec.model_path.exists():
                raise ModelRuntimeError(f"Missing belt model file: {cls._spec.model_path}")
            cls._engine = OnnxImageClassifierInfer(cls._spec)
            logger.info("Model engine cached: belt")
            return cls._engine

    def classify_person_detections(self, *, image, detections, record_id=None):
        # 按人物框裁图并补充安全带分类结果
        engine = self._get_engine()
        classified = []
        for index, detection in enumerate(detections, start=1):
            crop_bbox = self._clip_bbox(detection["bbox"], image.shape[:2])
            crop_bbox = self._expand_person_crop_bbox(crop_bbox, image.shape[:2])
            crop_image = self._crop_image(image, crop_bbox)
            if crop_image.size == 0:
                logger.warning(
                    "Skip empty person crop record_id=%s person_index=%s bbox=%s",
                    record_id,
                    index,
                    crop_bbox,
                )
                classified.append(
                    {
                        **detection,
                        "person_index": index,
                        "crop_bbox": crop_bbox,
                        "belt_label": "uncertain",
                        "belt_score": 0.0,
                        "belt_scores": [],
                        "belt_label_index": -1,
                    }
                )
                continue

            belt_result = engine.predict(crop_image)
            threshold_passed = bool(belt_result["threshold_passed"])
            belt_label = self._map_belt_label(belt_result["label"])
            classified.append(
                {
                    **detection,
                    "person_index": index,
                    "crop_bbox": crop_bbox,
                    "belt_label": belt_label if threshold_passed else "uncertain",
                    "belt_score": belt_result["score"],
                    "belt_scores": belt_result["scores"],
                    "belt_label_index": belt_result["label_index"] if threshold_passed else -1,
                }
            )
        return classified

    def to_belt_detections(self, person_detections):
        # 把分类结果转成可绘制的安全带框
        belt_detections = []
        for detection in person_detections:
            belt_detections.append(
                {
                    "bbox": list(detection["bbox"]),
                    "label": detection.get("belt_label", "uncertain"),
                    "label_index": int(detection.get("belt_label_index", -1)),
                    "score": round(float(detection.get("belt_score", 0.0)), 4),
                    "source_model": "belt",
                    "person_index": int(detection.get("person_index", 0)),
                }
            )
        return belt_detections

    def _clip_bbox(self, bbox, image_shape):
        # 限制人物框到图片边界内
        height, width = image_shape
        x1, y1, x2, y2 = [int(round(float(value))) for value in bbox]
        x1 = max(0, min(width, x1))
        y1 = max(0, min(height, y1))
        x2 = max(0, min(width, x2))
        y2 = max(0, min(height, y2))
        return [x1, y1, x2, y2]

    def _crop_image(self, image, bbox):
        # 根据人物框裁出分类图片
        x1, y1, x2, y2 = bbox
        if x2 <= x1 or y2 <= y1:
            return np.empty((0, 0, 3), dtype=image.dtype)
        return image[y1:y2, x1:x2].copy()

    @classmethod
    def _expand_person_crop_bbox(cls, bbox, image_shape):
        height, width = image_shape
        x1, y1, x2, y2 = [int(round(float(value))) for value in bbox]
        box_height = max(0, y2 - y1)
        if box_height <= 0:
            return [x1, y1, x2, y2]

        top_expand = int(round(box_height * cls._top_expand_ratio))
        bottom_expand = int(round(box_height * cls._bottom_expand_ratio))
        expanded_y1 = max(0, y1 - top_expand)
        expanded_y2 = min(height, y2 + bottom_expand)
        return [max(0, x1), max(0, expanded_y1), min(width, x2), max(0, expanded_y2)]

    def _map_belt_label(self, label):
        if label == "belt_on":
            return "wearing"
        if label == "belt_off":
            return "not_wearing"
        return str(label or "uncertain")
