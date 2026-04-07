import logging
from pathlib import Path
from threading import Lock

from ..inference import ModelRuntimeError, OnnxDamoYoloInfer, OnnxModelSpec

logger = logging.getLogger("seatbelt.services")


class VehicleDetector:
    # 整图车辆检测器

    _model_root = Path(__file__).resolve().parent.parent / "assets" / "onnx"
    _engine_lock = Lock()
    _engine = None
    _spec = OnnxModelSpec(
        model_path=_model_root / "damoyolo_tinynasL25_S_car.onnx",
        class_names=("car", "car_num"),
        infer_size=(512, 512),
        nms_conf_thre=0.05,
        nms_iou_thre=0.7,
    )

    @classmethod
    def _get_engine(cls):
        # 延迟加载并复用车辆模型
        if cls._engine is not None:
            return cls._engine

        with cls._engine_lock:
            if cls._engine is not None:
                return cls._engine
            if not cls._spec.model_path.exists():
                raise ModelRuntimeError(f"Missing vehicle model file: {cls._spec.model_path}")
            cls._engine = OnnxDamoYoloInfer(cls._spec)
            logger.info("Model engine cached: car")
            return cls._engine

    def predict(self, image):
        # 执行整图车辆检测
        detections = self._get_engine().predict(image)
        for detection in detections:
            detection["source_model"] = "car"
        return detections
