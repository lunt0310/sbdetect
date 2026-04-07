import logging
from dataclasses import dataclass
from importlib import util as importlib_util
from pathlib import Path

import numpy as np
from PIL import Image

logger = logging.getLogger("seatbelt.inference")


class ModelRuntimeError(RuntimeError):
    pass


@dataclass(frozen=True)
class OnnxModelSpec:
    model_path: Path
    class_names: tuple[str, ...] = ()
    infer_size: tuple[int, int] = (512, 512)
    nms_conf_thre: float = 0.05
    nms_iou_thre: float = 0.7
    image_mean: tuple[float, float, float] = (0.0, 0.0, 0.0)
    image_std: tuple[float, float, float] = (1.0, 1.0, 1.0)
    keep_ratio: bool = False
    center_pad: bool = False
    normalize_to_unit: bool = False


@dataclass(frozen=True)
class OnnxClassificationSpec:
    model_path: Path
    class_names: tuple[str, ...] = ()
    infer_size: tuple[int, int] = (224, 224)
    image_mean: tuple[float, float, float] = (0.485, 0.456, 0.406)
    image_std: tuple[float, float, float] = (0.229, 0.224, 0.225)
    score_threshold: float = 0.6
    keep_ratio: bool = False
    center_pad: bool = False
    normalize_to_unit: bool = True


def preprocess_image(origin_image, spec):
    if origin_image.ndim != 3 or origin_image.shape[2] != 3:
        raise ModelRuntimeError(f"Expected an RGB image array, got shape={origin_image.shape!r}")

    target_h, target_w = spec.infer_size
    origin_h, origin_w = origin_image.shape[:2]

    if spec.keep_ratio:
        scale = min(target_w / max(origin_w, 1), target_h / max(origin_h, 1))
        resized_w = max(1, int(round(origin_w * scale)))
        resized_h = max(1, int(round(origin_h * scale)))
    else:
        resized_w = target_w
        resized_h = target_h

    resized_image = Image.fromarray(origin_image.astype(np.uint8), mode="RGB").resize(
        (resized_w, resized_h),
        resample=Image.BILINEAR,
    )
    resized_array = np.asarray(resized_image, dtype=np.float32)
    if getattr(spec, "normalize_to_unit", False):
        resized_array = resized_array / 255.0

    canvas = np.zeros((target_h, target_w, 3), dtype=np.float32)
    pad_top = 0
    pad_left = 0
    if getattr(spec, "center_pad", False):
        pad_top = max(0, (target_h - resized_h) // 2)
        pad_left = max(0, (target_w - resized_w) // 2)
    canvas[pad_top:pad_top + resized_h, pad_left:pad_left + resized_w, :] = resized_array

    chw_image = canvas.transpose(2, 0, 1)
    mean = np.asarray(spec.image_mean, dtype=np.float32).reshape(3, 1, 1)
    std = np.asarray(spec.image_std, dtype=np.float32).reshape(3, 1, 1)
    std = np.where(std == 0, 1.0, std)
    input_tensor = ((chw_image - mean) / std)[None, ...].astype(np.float32, copy=False)
    return input_tensor, (resized_h, resized_w)


def decode_standard_outputs(cls_scores, bbox_preds, spec, original_shape, resized_shape):
    scores = np.asarray(cls_scores)
    boxes = np.asarray(bbox_preds)

    if scores.ndim == 3:
        scores = scores[0]
    if boxes.ndim == 3:
        boxes = boxes[0]

    if scores.ndim != 2 or boxes.ndim != 2:
        raise ModelRuntimeError(
            f"Unexpected ONNX output shapes: scores={scores.shape!r}, boxes={boxes.shape!r}"
        )

    if scores.shape[0] != boxes.shape[0]:
        raise ModelRuntimeError(
            f"ONNX outputs are misaligned: scores={scores.shape!r}, boxes={boxes.shape!r}"
        )

    num_classes = scores.shape[1]
    if boxes.shape[1] not in (4, num_classes * 4):
        raise ModelRuntimeError(
            f"Unsupported bbox output shape {boxes.shape!r} for {num_classes} class(es)"
        )

    detections = []
    for class_index in range(num_classes):
        class_scores = scores[:, class_index]
        valid_mask = class_scores > spec.nms_conf_thre
        if not np.any(valid_mask):
            continue

        if boxes.shape[1] == 4:
            class_boxes = boxes[valid_mask, :4]
        else:
            start = class_index * 4
            class_boxes = boxes[valid_mask, start:start + 4]

        filtered_scores = class_scores[valid_mask]
        keep_indices = nms(class_boxes, filtered_scores, spec.nms_iou_thre)
        for keep_index in keep_indices:
            detections.append(
                _make_detection(
                    bbox=class_boxes[keep_index],
                    score=filtered_scores[keep_index],
                    label_index=class_index,
                    class_names=spec.class_names,
                    original_shape=original_shape,
                    resized_shape=resized_shape,
                )
            )

    detections.sort(key=lambda item: item["score"], reverse=True)
    return detections


def decode_end2end_outputs(num_dets, boxes, scores, labels, spec, original_shape, resized_shape):
    total = int(np.asarray(num_dets).reshape(-1)[0])
    box_array = np.asarray(boxes)
    score_array = np.asarray(scores)
    label_array = np.asarray(labels)

    if box_array.ndim == 3:
        box_array = box_array[0]
    if score_array.ndim >= 2:
        score_array = score_array.reshape(-1)
    if label_array.ndim >= 2:
        label_array = label_array.reshape(-1)

    total = min(total, len(box_array), len(score_array), len(label_array))
    detections = []
    for index in range(total):
        score = float(score_array[index])
        if score <= spec.nms_conf_thre:
            continue
        detections.append(
            _make_detection(
                bbox=box_array[index],
                score=score,
                label_index=int(label_array[index]),
                class_names=spec.class_names,
                original_shape=original_shape,
                resized_shape=resized_shape,
            )
        )

    detections.sort(key=lambda item: item["score"], reverse=True)
    return detections


def nms(boxes, scores, iou_threshold):
    box_array = np.asarray(boxes, dtype=np.float32)
    score_array = np.asarray(scores, dtype=np.float32)
    if len(box_array) == 0:
        return []

    x1 = box_array[:, 0]
    y1 = box_array[:, 1]
    x2 = box_array[:, 2]
    y2 = box_array[:, 3]

    areas = np.maximum(0.0, x2 - x1 + 1.0) * np.maximum(0.0, y2 - y1 + 1.0)
    order = score_array.argsort()[::-1]
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


def _make_detection(*, bbox, score, label_index, class_names, original_shape, resized_shape):
    scaled_bbox = _scale_bbox_to_original(bbox, original_shape, resized_shape)
    label_name = class_names[label_index] if 0 <= label_index < len(class_names) else str(label_index)
    return {
        "bbox": scaled_bbox,
        "label": label_name,
        "label_index": int(label_index),
        "score": round(float(score), 4),
    }


def _scale_bbox_to_original(bbox, original_shape, resized_shape):
    original_h, original_w = original_shape
    resized_h, resized_w = resized_shape
    if resized_h <= 0 or resized_w <= 0:
        raise ModelRuntimeError(f"Invalid resized image shape: {resized_shape!r}")

    box = np.asarray(bbox, dtype=np.float32).copy()
    box[[0, 2]] = np.clip(box[[0, 2]], 0.0, float(resized_w))
    box[[1, 3]] = np.clip(box[[1, 3]], 0.0, float(resized_h))

    scale_x = float(original_w) / float(resized_w)
    scale_y = float(original_h) / float(resized_h)
    box[0] *= scale_x
    box[2] *= scale_x
    box[1] *= scale_y
    box[3] *= scale_y

    box[[0, 2]] = np.clip(box[[0, 2]], 0.0, float(original_w))
    box[[1, 3]] = np.clip(box[[1, 3]], 0.0, float(original_h))
    return [round(float(value), 2) for value in box.tolist()]


class OnnxDamoYoloInfer:
    def __init__(self, spec):
        self.spec = spec
        self._runtime = self._import_runtime()
        self.session = self._build_session()
        self.input_name = self.session.get_inputs()[0].name
        self.output_names = [output.name for output in self.session.get_outputs()]

    def _import_runtime(self):
        if importlib_util.find_spec("onnxruntime") is None:
            raise ModelRuntimeError(
                "Missing inference dependency: onnxruntime. Install onnxruntime or onnxruntime-gpu before calling /api/detections/."
            )

        try:
            import onnxruntime as ort
        except Exception as exc:
            raise ModelRuntimeError(f"Failed to import onnxruntime: {exc}") from exc
        return ort

    def _build_session(self):
        providers = _resolve_execution_providers(self._runtime)
        session_options = self._runtime.SessionOptions()
        session_options.log_severity_level = 3

        try:
            session = self._runtime.InferenceSession(
                str(self.spec.model_path),
                sess_options=session_options,
                providers=providers,
            )
        except Exception as exc:
            raise ModelRuntimeError(
                f"Failed to load ONNX model {self.spec.model_path.name}: {exc}"
            ) from exc

        self.providers = session.get_providers()
        self.device = "cuda" if any("CUDA" in provider.upper() for provider in self.providers) else "cpu"
        logger.info(
            "Initialized ONNX engine model=%s providers=%s infer_size=%s",
            self.spec.model_path.name,
            self.providers,
            self.spec.infer_size,
        )
        return session

    def predict(self, origin_image):
        logger.info(
            "Running ONNX inference with %s on image shape=%s",
            self.spec.model_path.name,
            origin_image.shape,
        )
        input_tensor, resized_shape = preprocess_image(origin_image, self.spec)

        try:
            outputs = self.session.run(None, {self.input_name: input_tensor})
        except Exception as exc:
            raise ModelRuntimeError(
                f"ONNX inference failed for {self.spec.model_path.name}: {exc}"
            ) from exc

        detections = self._parse_outputs(
            outputs,
            original_shape=origin_image.shape[:2],
            resized_shape=resized_shape,
        )
        logger.info(
            "Inference finished for %s, detections=%s",
            self.spec.model_path.name,
            len(detections),
        )
        return detections

    def _parse_outputs(self, outputs, *, original_shape, resized_shape):
        named_outputs = list(zip(self.output_names, outputs))

        num_dets, boxes, scores, labels = self._select_end2end_outputs(named_outputs)
        if num_dets is not None:
            return decode_end2end_outputs(
                num_dets=num_dets,
                boxes=boxes,
                scores=scores,
                labels=labels,
                spec=self.spec,
                original_shape=original_shape,
                resized_shape=resized_shape,
            )

        cls_scores, bbox_preds = self._select_standard_outputs(named_outputs)
        if cls_scores is not None:
            return decode_standard_outputs(
                cls_scores=cls_scores,
                bbox_preds=bbox_preds,
                spec=self.spec,
                original_shape=original_shape,
                resized_shape=resized_shape,
            )

        output_shapes = {name: np.asarray(value).shape for name, value in named_outputs}
        raise ModelRuntimeError(
            f"Unsupported ONNX output signature for {self.spec.model_path.name}: {output_shapes}"
        )

    def _select_standard_outputs(self, named_outputs):
        outputs = [(name.lower(), np.asarray(value)) for name, value in named_outputs]
        bbox_index = next(
            (
                index
                for index, (name, value) in enumerate(outputs)
                if ("bbox" in name or "box" in name) and value.ndim >= 2 and value.shape[-1] == 4
            ),
            None,
        )
        score_index = next(
            (
                index
                for index, (name, value) in enumerate(outputs)
                if ("score" in name or "cls" in name) and value.ndim >= 2
            ),
            None,
        )

        if bbox_index is None:
            bbox_candidates = [
                index for index, (_, value) in enumerate(outputs) if value.ndim >= 2 and value.shape[-1] == 4
            ]
            if len(bbox_candidates) == 1:
                bbox_index = bbox_candidates[0]

        if score_index is None and bbox_index is not None:
            score_candidates = [
                index
                for index, (_, value) in enumerate(outputs)
                if index != bbox_index and value.ndim >= 2
            ]
            if len(score_candidates) == 1:
                score_index = score_candidates[0]

        if bbox_index is None or score_index is None:
            return None, None

        return outputs[score_index][1], outputs[bbox_index][1]

    def _select_end2end_outputs(self, named_outputs):
        outputs = [(name.lower(), np.asarray(value)) for name, value in named_outputs]
        num_index = next((index for index, (name, _) in enumerate(outputs) if "num" in name), None)
        box_index = next((index for index, (name, _) in enumerate(outputs) if "box" in name), None)
        score_index = next((index for index, (name, _) in enumerate(outputs) if "score" in name), None)
        label_index = next(
            (index for index, (name, _) in enumerate(outputs) if "class" in name or "label" in name),
            None,
        )

        if None not in (num_index, box_index, score_index, label_index):
            return (
                outputs[num_index][1],
                outputs[box_index][1],
                outputs[score_index][1],
                outputs[label_index][1],
            )

        if len(outputs) == 4:
            scalar_like = [index for index, (_, value) in enumerate(outputs) if value.size == 1]
            box_like = [index for index, (_, value) in enumerate(outputs) if value.ndim >= 2 and value.shape[-1] == 4]
            if len(scalar_like) == 1 and len(box_like) == 1:
                remaining = [index for index in range(4) if index not in {scalar_like[0], box_like[0]}]
                return (
                    outputs[scalar_like[0]][1],
                    outputs[box_like[0]][1],
                    outputs[remaining[0]][1],
                    outputs[remaining[1]][1],
                )

        return None, None, None, None


class OnnxImageClassifierInfer:
    def __init__(self, spec):
        self.spec = spec
        self._runtime = self._import_runtime()
        self.session = self._build_session()
        self.input_name = self.session.get_inputs()[0].name
        self.output_names = [output.name for output in self.session.get_outputs()]
        self.infer_size = self._resolve_infer_size()

    def _import_runtime(self):
        if importlib_util.find_spec("onnxruntime") is None:
            raise ModelRuntimeError(
                "Missing inference dependency: onnxruntime. Install onnxruntime or onnxruntime-gpu before calling /api/detections/."
            )

        try:
            import onnxruntime as ort
        except Exception as exc:
            raise ModelRuntimeError(f"Failed to import onnxruntime: {exc}") from exc
        return ort

    def _build_session(self):
        providers = _resolve_execution_providers(self._runtime)
        session_options = self._runtime.SessionOptions()
        session_options.log_severity_level = 3

        try:
            session = self._runtime.InferenceSession(
                str(self.spec.model_path),
                sess_options=session_options,
                providers=providers,
            )
        except Exception as exc:
            raise ModelRuntimeError(
                f"Failed to load ONNX model {self.spec.model_path.name}: {exc}"
            ) from exc

        self.providers = session.get_providers()
        self.device = "cuda" if any("CUDA" in provider.upper() for provider in self.providers) else "cpu"
        logger.info(
            "Initialized ONNX classifier model=%s providers=%s infer_size=%s",
            self.spec.model_path.name,
            self.providers,
            self.spec.infer_size,
        )
        return session

    def _resolve_infer_size(self):
        input_shape = list(self.session.get_inputs()[0].shape)
        if len(input_shape) >= 4:
            height = input_shape[-2]
            width = input_shape[-1]
            if isinstance(height, int) and isinstance(width, int) and height > 0 and width > 0:
                return (height, width)
        return self.spec.infer_size

    def predict(self, origin_image):
        logger.info(
            "Running ONNX classification with %s on crop shape=%s",
            self.spec.model_path.name,
            origin_image.shape,
        )
        preprocess_spec = OnnxModelSpec(
            model_path=self.spec.model_path,
            class_names=self.spec.class_names,
            infer_size=self.infer_size,
            image_mean=self.spec.image_mean,
            image_std=self.spec.image_std,
            keep_ratio=self.spec.keep_ratio,
            normalize_to_unit=self.spec.normalize_to_unit,
        )
        input_tensor, _ = preprocess_image(origin_image, preprocess_spec)

        try:
            outputs = self.session.run(None, {self.input_name: input_tensor})
        except Exception as exc:
            raise ModelRuntimeError(
                f"ONNX classification failed for {self.spec.model_path.name}: {exc}"
            ) from exc

        result = self._parse_outputs(outputs)
        logger.info(
            "Classification finished for %s label=%s score=%.4f",
            self.spec.model_path.name,
            result["label"],
            result["score"],
        )
        return result

    def _parse_outputs(self, outputs):
        if not outputs:
            raise ModelRuntimeError(f"No outputs returned by classifier {self.spec.model_path.name}")

        logits = np.asarray(outputs[0]).astype(np.float32).reshape(-1)
        if logits.size == 0:
            raise ModelRuntimeError(f"Empty classifier output from {self.spec.model_path.name}")

        if logits.size == 1:
            positive_prob = float(_sigmoid(logits[0]))
            probabilities = np.asarray([1.0 - positive_prob, positive_prob], dtype=np.float32)
        else:
            probabilities = _softmax(logits)

        label_index = int(np.argmax(probabilities))
        score = float(probabilities[label_index])
        label_name = (
            self.spec.class_names[label_index]
            if 0 <= label_index < len(self.spec.class_names)
            else str(label_index)
        )

        return {
            "label": label_name,
            "label_index": label_index,
            "score": round(score, 4),
            "scores": [round(float(value), 4) for value in probabilities.tolist()],
            "threshold_passed": bool(score >= self.spec.score_threshold),
        }


def _softmax(logits):
    shifted = logits - np.max(logits)
    exps = np.exp(shifted)
    denom = np.sum(exps)
    if not np.isfinite(denom) or denom <= 0:
        raise ModelRuntimeError("Invalid classifier logits: softmax denominator is not positive")
    return exps / denom


def _sigmoid(value):
    if value >= 0:
        exp_value = np.exp(-value)
        return 1.0 / (1.0 + exp_value)
    exp_value = np.exp(value)
    return exp_value / (1.0 + exp_value)


def _resolve_execution_providers(runtime_module):
    available_providers = list(runtime_module.get_available_providers())

    if "CUDAExecutionProvider" in available_providers:
        providers = ["CUDAExecutionProvider"]
        if "CPUExecutionProvider" in available_providers:
            providers.append("CPUExecutionProvider")
        logger.info("ONNX runtime provider selection: %s", providers)
        return providers

    if "CPUExecutionProvider" in available_providers:
        logger.info("ONNX runtime provider selection: ['CPUExecutionProvider']")
        return ["CPUExecutionProvider"]

    logger.info("ONNX runtime provider selection fallback: %s", available_providers)
    return available_providers
