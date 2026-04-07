import logging
import re
from pathlib import Path
from threading import Lock

import numpy as np

from ..inference import ModelRuntimeError
from .plate_detector import _resolve_execution_providers

logger = logging.getLogger("seatbelt.services")


class PlateOcrDetector:
    # 基于 CRNN ONNX 的车牌文字识别器
    _model_root = Path(__file__).resolve().parent.parent / "assets" / "onnx"
    _model_path = _model_root / "plate_text.onnx"
    _engine_lock = Lock()
    _session = None
    _input_name = ""
    _output_names = []
    _input_size = (48, 168)
    _image_mean = 0.588
    _image_std = 0.193
    _blank_index = 0
    _chars = "#京沪津渝冀晋蒙辽吉黑苏浙皖闽赣鲁豫鄂湘粤桂琼川贵云藏陕甘青宁新学警港澳挂使领民航危0123456789ABCDEFGHJKLMNPQRSTUVWXYZ险品"

    @classmethod
    def _get_engine(cls):
        if cls._session is not None:
            return cls._session

        with cls._engine_lock:
            if cls._session is not None:
                return cls._session

            if not cls._model_path.exists():
                raise ModelRuntimeError(f"Missing plate text model file: {cls._model_path}")

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
                "Model engine cached: plate_text model=%s providers=%s",
                cls._model_path.name,
                cls._session.get_providers(),
            )
            return cls._session

    def recognize(self, image):
        if image is None or getattr(image, "size", 0) == 0:
            return {"text": "", "score": 0.0, "candidates": []}

        session = self._get_engine()
        input_tensor = self._preprocess(image)
        try:
            outputs = session.run(self._output_names, {self._input_name: input_tensor})
        except Exception as exc:
            raise ModelRuntimeError(f"Plate text recognition failed: {exc}") from exc

        return self._decode(outputs[0])

    def _preprocess(self, image):
        try:
            import cv2
        except Exception as exc:
            raise ModelRuntimeError("OpenCV is required for plate text preprocessing.") from exc

        target_h, target_w = self._input_size
        # The original demo/onnx_infer pipeline reads images with OpenCV in BGR.
        bgr_image = cv2.cvtColor(image, cv2.COLOR_RGB2BGR)
        resized = cv2.resize(bgr_image, (target_w, target_h), interpolation=cv2.INTER_LINEAR)
        normalized = resized.astype(np.float32)
        normalized = (normalized / 255.0 - self._image_mean) / self._image_std
        chw = normalized.transpose(2, 0, 1)
        return chw[None, ...].astype(np.float32, copy=False)

    def _decode(self, output):
        predictions = np.asarray(output, dtype=np.float32)
        if predictions.ndim != 3:
            raise ModelRuntimeError(f"Unsupported plate text output shape: {predictions.shape!r}")

        logits = predictions[0]
        if logits.ndim != 2 or logits.shape[1] != len(self._chars):
            raise ModelRuntimeError(
                f"Unexpected plate text logits shape: {logits.shape!r}, chars={len(self._chars)}"
            )

        indices = np.argmax(logits, axis=1)
        confidences = self._softmax(logits)
        decoded_chars = []
        decoded_scores = []
        previous_index = None

        for step, index in enumerate(indices.tolist()):
            if index == self._blank_index:
                previous_index = index
                continue
            if index == previous_index:
                continue
            if not 0 <= index < len(self._chars):
                previous_index = index
                continue

            decoded_chars.append(self._chars[index])
            decoded_scores.append(float(confidences[step, index]))
            previous_index = index

        text = self._normalize_text("".join(decoded_chars))
        score = round(float(sum(decoded_scores) / len(decoded_scores)), 4) if decoded_scores and text else 0.0
        return {
            "text": text,
            "score": score,
            "candidates": [{"text": text, "score": score}] if text else [],
        }

    def _softmax(self, logits):
        shifted = logits - np.max(logits, axis=1, keepdims=True)
        exp = np.exp(shifted)
        total = np.sum(exp, axis=1, keepdims=True)
        total = np.where(total == 0, 1.0, total)
        return exp / total

    def _normalize_text(self, text):
        value = str(text).strip().upper()
        value = re.sub(r"\s+", "", value)
        value = re.sub(r"[^0-9A-Z\u4e00-\u9fff]", "", value)
        return value
