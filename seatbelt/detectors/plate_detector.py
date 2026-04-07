import logging
from pathlib import Path
from threading import Lock

import numpy as np

from ..inference import ModelRuntimeError

logger = logging.getLogger("seatbelt.services")


class PlateDetector:
    _model_root = Path(__file__).resolve().parent.parent / "assets" / "onnx"
    _model_path = _model_root / "plate_detect.onnx"
    _engine_lock = Lock()
    _session = None
    _input_name = ""
    _output_names = []
    _input_size = (640, 640)
    _conf_threshold = 0.25
    _iou_threshold = 0.45
    _class_names = ("single", "double")

    @classmethod
    def _get_engine(cls):
        if cls._session is not None:
            return cls._session

        with cls._engine_lock:
            if cls._session is not None:
                return cls._session

            if not cls._model_path.exists():
                raise ModelRuntimeError(f"Missing plate model file: {cls._model_path}")

            try:
                import onnxruntime as ort
            except Exception as exc:
                raise ModelRuntimeError(f"Failed to import onnxruntime: {exc}") from exc

            try:
                cls._session = ort.InferenceSession(
                    str(cls._model_path),
                    providers=_resolve_execution_providers(ort),
                )
            except Exception as exc:
                raise ModelRuntimeError(
                    f"Failed to load ONNX model {cls._model_path.name}: {exc}"
                ) from exc

            cls._input_name = cls._session.get_inputs()[0].name
            cls._output_names = [output.name for output in cls._session.get_outputs()]
            logger.info(
                "Model engine cached: plate model=%s providers=%s",
                cls._model_path.name,
                cls._session.get_providers(),
            )
            return cls._session

    def predict(self, image, *, parent_bbox=None, vehicle_index=None):
        if image.size == 0:
            return []

        session = self._get_engine()
        input_tensor, ratio, pad = self._preprocess(image)
        try:
            outputs = session.run(self._output_names, {self._input_name: input_tensor})
        except Exception as exc:
            raise ModelRuntimeError(f"Plate detection failed: {exc}") from exc

        detections = self._decode(
            outputs[0],
            original_shape=image.shape[:2],
            ratio=ratio,
            pad=pad,
        )
        restored = []
        for detection in detections:
            detection["source_model"] = "plate"
            if parent_bbox is not None:
                detection = self._restore_detection_to_image(
                    detection=detection,
                    parent_bbox=parent_bbox,
                    vehicle_index=vehicle_index,
                )
            elif vehicle_index is not None:
                detection["vehicle_index"] = int(vehicle_index)
            restored.append(detection)
        return restored

    def _preprocess(self, image):
        target_h, target_w = self._input_size
        origin_h, origin_w = image.shape[:2]
        ratio = min(target_w / max(origin_w, 1), target_h / max(origin_h, 1))
        resized_w = max(1, int(round(origin_w * ratio)))
        resized_h = max(1, int(round(origin_h * ratio)))

        try:
            import cv2
        except Exception as exc:
            raise ModelRuntimeError("OpenCV is required for plate detection preprocessing.") from exc

        resized = cv2.resize(image, (resized_w, resized_h), interpolation=cv2.INTER_LINEAR)
        canvas = np.full((target_h, target_w, 3), 114, dtype=np.uint8)
        pad_x = (target_w - resized_w) // 2
        pad_y = (target_h - resized_h) // 2
        canvas[pad_y:pad_y + resized_h, pad_x:pad_x + resized_w] = resized
        input_tensor = canvas.transpose(2, 0, 1).astype(np.float32) / 255.0
        return input_tensor[None, ...], ratio, (pad_x, pad_y)

    def _decode(self, output, *, original_shape, ratio, pad):
        predictions = np.asarray(output, dtype=np.float32)
        if predictions.ndim == 3:
            predictions = predictions[0]
        if predictions.ndim != 2 or predictions.shape[1] < 7:
            raise ModelRuntimeError(f"Unsupported plate output shape: {predictions.shape!r}")

        objectness = predictions[:, 4]
        class_scores = predictions[:, 13:] if predictions.shape[1] > 13 else predictions[:, 5:]
        if class_scores.ndim != 2 or class_scores.shape[1] == 0:
            class_scores = np.ones((predictions.shape[0], 1), dtype=np.float32)

        class_indices = np.argmax(class_scores, axis=1)
        class_confidences = class_scores[np.arange(len(class_scores)), class_indices]
        scores = objectness * class_confidences
        valid = scores >= self._conf_threshold
        if not np.any(valid):
            return []

        selected = predictions[valid]
        selected_scores = scores[valid]
        selected_classes = class_indices[valid]

        boxes = self._xywh_to_xyxy(selected[:, :4])
        boxes = self._scale_boxes_to_original(boxes, original_shape=original_shape, ratio=ratio, pad=pad)
        keep = _nms(boxes, selected_scores, self._iou_threshold)

        detections = []
        for index in keep:
            label_index = int(selected_classes[index])
            plate_type = (
                self._class_names[label_index]
                if 0 <= label_index < len(self._class_names)
                else str(label_index)
            )
            detections.append(
                {
                    "bbox": [round(float(value), 2) for value in boxes[index].tolist()],
                    "label": "car_num",
                    "label_index": label_index,
                    "score": round(float(selected_scores[index]), 4),
                    "plate_type": plate_type,
                }
            )
        return detections

    def _xywh_to_xyxy(self, boxes):
        converted = boxes.copy()
        converted[:, 0] = boxes[:, 0] - boxes[:, 2] / 2.0
        converted[:, 1] = boxes[:, 1] - boxes[:, 3] / 2.0
        converted[:, 2] = boxes[:, 0] + boxes[:, 2] / 2.0
        converted[:, 3] = boxes[:, 1] + boxes[:, 3] / 2.0
        return converted

    def _scale_boxes_to_original(self, boxes, *, original_shape, ratio, pad):
        origin_h, origin_w = original_shape
        pad_x, pad_y = pad
        scaled = boxes.copy()
        scaled[:, [0, 2]] -= float(pad_x)
        scaled[:, [1, 3]] -= float(pad_y)
        scaled /= max(float(ratio), 1e-6)
        scaled[:, [0, 2]] = np.clip(scaled[:, [0, 2]], 0.0, float(origin_w))
        scaled[:, [1, 3]] = np.clip(scaled[:, [1, 3]], 0.0, float(origin_h))
        return scaled

    def _restore_detection_to_image(self, *, detection, parent_bbox, vehicle_index=None):
        offset_x = float(parent_bbox[0])
        offset_y = float(parent_bbox[1])
        x1, y1, x2, y2 = [float(value) for value in detection["bbox"]]
        return {
            **detection,
            "bbox": [
                round(x1 + offset_x, 2),
                round(y1 + offset_y, 2),
                round(x2 + offset_x, 2),
                round(y2 + offset_y, 2),
            ],
            "vehicle_index": int(vehicle_index) if vehicle_index is not None else -1,
            "parent_vehicle_bbox": [round(float(value), 2) for value in parent_bbox],
        }


def _nms(boxes, scores, iou_threshold):
    if len(boxes) == 0:
        return []

    x1 = boxes[:, 0]
    y1 = boxes[:, 1]
    x2 = boxes[:, 2]
    y2 = boxes[:, 3]
    areas = np.maximum(0.0, x2 - x1 + 1.0) * np.maximum(0.0, y2 - y1 + 1.0)
    order = scores.argsort()[::-1]
    keep = []

    while order.size > 0:
        current = order[0]
        keep.append(int(current))
        if order.size == 1:
            break

        remaining = order[1:]
        xx1 = np.maximum(x1[current], x1[remaining])
        yy1 = np.maximum(y1[current], y1[remaining])
        xx2 = np.minimum(x2[current], x2[remaining])
        yy2 = np.minimum(y2[current], y2[remaining])
        width = np.maximum(0.0, xx2 - xx1 + 1.0)
        height = np.maximum(0.0, yy2 - yy1 + 1.0)
        intersection = width * height
        union = areas[current] + areas[remaining] - intersection
        iou = np.divide(intersection, union, out=np.zeros_like(intersection), where=union > 0)
        order = remaining[iou <= iou_threshold]

    return keep


def _resolve_execution_providers(runtime_module):
    import os

    available = list(runtime_module.get_available_providers())
    providers = []

    enable_trt = os.getenv("SEATBELT_ENABLE_TRT", "").lower() in {"1", "true", "yes"}
    if enable_trt and "TensorrtExecutionProvider" in available:
        providers.append("TensorrtExecutionProvider")

    if "CUDAExecutionProvider" in available:
        providers.append("CUDAExecutionProvider")

    if "CPUExecutionProvider" in available:
        providers.append("CPUExecutionProvider")

    return providers or available
