import logging
from pathlib import Path
from threading import Lock

from ..inference import ModelRuntimeError, OnnxDamoYoloInfer, OnnxModelSpec

logger = logging.getLogger("seatbelt.services")


class PersonDetector:
    # 单车内人物检测器

    _model_root = Path(__file__).resolve().parent.parent / "assets" / "onnx"
    _engine_lock = Lock()
    _engine = None
    _spec = OnnxModelSpec(
        model_path=_model_root / "damoyolo_tinynasL25_S_person.onnx",
        class_names=("person",),
        infer_size=(512, 512),
        nms_conf_thre=0.05,
        nms_iou_thre=0.7,
    )

    @classmethod
    def _get_engine(cls):
        # 延迟加载并复用人物模型
        if cls._engine is not None:
            return cls._engine

        with cls._engine_lock:
            if cls._engine is not None:
                return cls._engine
            if not cls._spec.model_path.exists():
                raise ModelRuntimeError(f"Missing person model file: {cls._spec.model_path}")
            cls._engine = OnnxDamoYoloInfer(cls._spec)
            logger.info("Model engine cached: person")
            return cls._engine

    def predict(self, image, *, parent_bbox=None, vehicle_index=None):
        # 在车辆截图中检测人物，并按需还原到原图坐标
        detections = self._get_engine().predict(image)
        restored = []
        for detection in detections:
            detection["source_model"] = "person"
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

    def _restore_detection_to_image(self, *, detection, parent_bbox, vehicle_index=None):
        # 把局部人物框映射回原图
        offset_x = float(parent_bbox[0])
        offset_y = float(parent_bbox[1])
        x1, y1, x2, y2 = [float(value) for value in detection["bbox"]]
        restored_bbox = [
            round(x1 + offset_x, 2),
            round(y1 + offset_y, 2),
            round(x2 + offset_x, 2),
            round(y2 + offset_y, 2),
        ]
        return {
            **detection,
            "bbox": restored_bbox,
            "vehicle_index": int(vehicle_index) if vehicle_index is not None else -1,
            "parent_vehicle_bbox": [round(float(value), 2) for value in parent_bbox],
        }
