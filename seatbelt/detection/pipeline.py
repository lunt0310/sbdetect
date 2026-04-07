import io
import logging
import uuid
from pathlib import Path

import numpy as np
from django.conf import settings
from django.db import transaction
from django.utils import timezone
from PIL import Image, ImageFile

from ..business.models import DetectObject, DetectResult, ViolationRecord
from ..detectors import BeltDetector, PersonDetector, PlateDetector, PlateOcrDetector, VehicleDetector
from ..inference import ModelRuntimeError

ImageFile.LOAD_TRUNCATED_IMAGES = True
logger = logging.getLogger("seatbelt.services")


class SeatbeltDetectionService:
    # 车到人到安全带
    _person_score_threshold = 0.4
    _vehicle_score_threshold = 0.65
    _belt_score_threshold = 0.8
    _vehicle_track_iou_threshold = 0.3
    _person_track_iou_threshold = 0.35
    _track_max_gap_frames = 8

    def __init__(self):
        # 初始化检测器
        self.vehicle_detector = VehicleDetector()
        self.person_detector = PersonDetector()
        self.plate_detector = PlateDetector()
        self.belt_detector = BeltDetector()
        self.plate_ocr_detector = PlateOcrDetector()
        self._video_tracking_state = self._new_video_tracking_state()

    @transaction.atomic
    def analyze(self, task):
        # 统一检测入口
        if task.task_type == task.TaskType.VIDEO:
            return self._analyze_video(task)
        return self._analyze_image(task)

    def _analyze_image(self, task):
        # 处理图片任务
        image_path = Path(task.source_file.path)
        image = np.array(Image.open(image_path).convert("RGB")).copy()
        frame_summary = self._analyze_frame(
            task=task,
            image=image,
            result_index=1,
        )
        summary = self._build_task_summary(
            task=task,
            frame_summaries=[frame_summary],
            total_frames=1,
            processed_frames=1,
            duration_ms=None,
            extra_metadata={"source_kind": "image"},
        )
        summary["result_id"] = frame_summary["result_id"]
        return summary

    def _analyze_video(self, task):
        # 处理视频任务
        cv2 = self._get_cv2()
        video_path = str(Path(task.source_file.path))
        capture = cv2.VideoCapture(video_path)
        if not capture.isOpened():
            raise ModelRuntimeError("Failed to open video file.")

        fps = float(capture.get(cv2.CAP_PROP_FPS) or 0.0)
        total_frames = int(capture.get(cv2.CAP_PROP_FRAME_COUNT) or 0)
        if total_frames < 0:
            total_frames = 0

        frame_summaries = []
        frame_index = 0
        self._video_tracking_state = self._new_video_tracking_state()

        try:
            while True:
                ok, frame_bgr = capture.read()
                if not ok:
                    break

                frame_index += 1
                image = cv2.cvtColor(frame_bgr, cv2.COLOR_BGR2RGB)
                frame_time_ms = int(((frame_index - 1) / fps) * 1000) if fps > 0 else None
                frame_summary = self._analyze_frame(
                    task=task,
                    image=image,
                    result_index=len(frame_summaries) + 1,
                    frame_index=frame_index,
                    frame_time_ms=frame_time_ms,
                )
                frame_summaries.append(frame_summary)
        finally:
            capture.release()

        if not frame_summaries:
            raise ModelRuntimeError("Video contains no readable frames.")

        duration_ms = int((len(frame_summaries) / fps) * 1000) if fps > 0 else None
        tracking_state = self._video_tracking_state
        return self._build_task_summary(
            task=task,
            frame_summaries=frame_summaries,
            total_frames=total_frames or len(frame_summaries),
            processed_frames=len(frame_summaries),
            duration_ms=duration_ms,
            extra_metadata={
                "source_kind": "video",
                "fps": fps,
                "result_ids": [item["result_id"] for item in frame_summaries],
                "tracked_vehicle_count": len(tracking_state["vehicle_tracks"]),
                "tracked_person_count": len(tracking_state["person_tracks"]),
                "unique_violation_count": len(tracking_state["violation_track_ids"]),
            },
        )

    def _analyze_frame(self, *, task, image, result_index, frame_index=None, frame_time_ms=None):
        # 处理单帧
        raw_vehicle_detections = self.vehicle_detector.predict(image)
        vehicle_detections = self._filter_detections(raw_vehicle_detections, self._vehicle_score_threshold)
        car_detections = [item for item in vehicle_detections if item["label"] == "car"]

        raw_person_detections = self._detect_persons_in_cars(
            image=image,
            car_detections=car_detections,
            task_id=task.id,
        )
        raw_plate_detections = self._detect_plates_in_cars(
            image=image,
            car_detections=car_detections,
            task_id=task.id,
        )
        person_detections = self._filter_detections(raw_person_detections, self._person_score_threshold)
        car_num_detections = self._filter_detections(raw_plate_detections, 0.25)
        plate_assignments = self._prepare_plate_assignments(
            image=image,
            car_detections=car_detections,
            car_num_detections=car_num_detections,
        )
        if task.task_type == task.TaskType.VIDEO and frame_index is not None:
            self._assign_video_tracks(
                task=task,
                frame_index=frame_index,
                car_detections=car_detections,
                person_detections=person_detections,
                plate_assignments=plate_assignments,
            )
        person_detections = self.belt_detector.classify_person_detections(
            image=image,
            detections=person_detections,
            record_id=task.id,
        )
        belt_detections = self.belt_detector.to_belt_detections(person_detections)

        all_detections = [*car_detections, *car_num_detections, *belt_detections]
        result_image = self._save_result_image(
            task=task,
            image=image,
            detections=all_detections,
            frame_index=frame_index,
        )
        result = self._create_result(
            task=task,
            image=image,
            result_index=result_index,
            frame_index=frame_index,
            frame_time_ms=frame_time_ms,
            result_image=result_image,
        )

        vehicle_map = self._save_vehicle_objects(
            task=task,
            result=result,
            image=image,
            car_detections=car_detections,
            person_detections=person_detections,
        )
        self._save_plate_objects(
            task=task,
            result=result,
            image=image,
            car_detections=car_detections,
            car_num_detections=car_num_detections,
            vehicle_map=vehicle_map,
            plate_assignments=plate_assignments,
        )
        violation_summary = self._save_person_and_violation_objects(
            task=task,
            result=result,
            image=image,
            person_detections=person_detections,
            vehicle_map=vehicle_map,
        )
        frame_violation_count = int(violation_summary["frame_violation_count"])

        object_count = result.detect_objects.count()
        best_score = max((item["score"] for item in all_detections), default=0.0)
        result.object_count = object_count
        result.vehicle_count = len(car_detections)
        result.person_count = len(person_detections)
        result.plate_count = len(car_num_detections)
        result.violation_count = frame_violation_count
        result.has_violation = frame_violation_count > 0
        result.max_confidence = best_score
        result.notes = self._build_notes(
            car_detections=car_detections,
            car_num_detections=car_num_detections,
            person_detections=person_detections,
            violation_count=frame_violation_count,
            frame_index=frame_index,
        )
        result.metadata = {
            "engine": "cascade-vehicle-person-belt-ocr-onnxruntime",
            "runtime": "onnxruntime",
            "models": {
                "car": self.vehicle_detector._spec.model_path.name,
                "person": self.person_detector._spec.model_path.name,
                "belt": self.belt_detector._spec.model_path.name,
                "plate_text": "plate_text.onnx",
            },
        }
        result.save(
            update_fields=[
                "object_count",
                "vehicle_count",
                "person_count",
                "plate_count",
                "violation_count",
                "has_violation",
                "max_confidence",
                "notes",
                "metadata",
                "updated_at",
            ]
        )

        return {
            "confidence": float(best_score),
            "result_id": result.id,
            "violation_count": frame_violation_count,
            "object_count": object_count,
            "person_count": len(person_detections),
            "has_violation": frame_violation_count > 0,
            "frame_index": frame_index,
            "result_image": result_image,
        }

    def _build_task_summary(
        self,
        *,
        task,
        frame_summaries,
        total_frames,
        processed_frames,
        duration_ms,
        extra_metadata,
    ):
        # 汇总任务结果
        violation_count = sum(item["violation_count"] for item in frame_summaries)
        violation_count = int(extra_metadata.get("unique_violation_count", violation_count))
        best_confidence = max((item["confidence"] for item in frame_summaries), default=0.0)
        has_violation = any(item["has_violation"] for item in frame_summaries)
        metadata = {
            "duration_ms": duration_ms,
            "processed_frames": processed_frames,
            "result_count": len(frame_summaries),
            **extra_metadata,
        }
        if frame_summaries:
            metadata["cover_result_image"] = frame_summaries[0]["result_image"]

        task.progress = 100
        task.total_frames = total_frames
        task.result_count = len(frame_summaries)
        task.processed_frames = processed_frames
        task.duration_ms = duration_ms
        task.violation_count = violation_count
        task.has_violation = has_violation
        task.finished_at = timezone.now()
        task.notes = self._build_task_notes(task.task_type, processed_frames, violation_count)
        task.metadata = metadata
        return {
            "confidence": float(best_confidence),
            "violation_count": violation_count,
            "object_count": sum(item["object_count"] for item in frame_summaries),
            "person_count": sum(item["person_count"] for item in frame_summaries),
            "has_violation": has_violation,
            "result_count": len(frame_summaries),
            "processed_frames": processed_frames,
            "total_frames": total_frames,
            "duration_ms": duration_ms,
            "result_ids": [item["result_id"] for item in frame_summaries],
        }

    def _build_task_notes(self, task_type, processed_frames, violation_count):
        # 生成任务说明
        if task_type == "video":
            return f"Video processed: {processed_frames} frame(s), {violation_count} violation(s)."
        return f"Image processed: {violation_count} violation(s)."

    def _create_result(self, task, image, result_index, frame_index, frame_time_ms, result_image):
        # 创建结果记录
        return DetectResult.objects.create(
            task=task,
            result_index=result_index,
            frame_index=frame_index,
            frame_time_ms=frame_time_ms,
            image_width=int(image.shape[1]),
            image_height=int(image.shape[0]),
            result_image=result_image,
        )

    def _detect_persons_in_cars(self, *, image, car_detections, task_id=None):
        # 逐车检测人物
        person_detections = []
        for vehicle_index, car_detection in enumerate(car_detections, start=1):
            vehicle_bbox = self._clip_bbox(car_detection["bbox"], image.shape[:2])
            vehicle_crop = self._crop_image(image, vehicle_bbox)
            if vehicle_crop.size == 0:
                logger.warning(
                    "Skip empty vehicle crop task_id=%s vehicle_index=%s bbox=%s",
                    task_id,
                    vehicle_index,
                    vehicle_bbox,
                )
                continue

            car_person_detections = self.person_detector.predict(
                vehicle_crop,
                parent_bbox=vehicle_bbox,
                vehicle_index=vehicle_index,
            )
            person_detections.extend(car_person_detections)
        return person_detections

    def _detect_plates_in_cars(self, *, image, car_detections, task_id=None):
        plate_detections = []
        for vehicle_index, car_detection in enumerate(car_detections, start=1):
            vehicle_bbox = self._clip_bbox(car_detection["bbox"], image.shape[:2])
            vehicle_crop = self._crop_image(image, vehicle_bbox)
            if vehicle_crop.size == 0:
                logger.warning(
                    "Skip empty plate crop task_id=%s vehicle_index=%s bbox=%s",
                    task_id,
                    vehicle_index,
                    vehicle_bbox,
                )
                continue

            car_plate_detections = self.plate_detector.predict(
                vehicle_crop,
                parent_bbox=vehicle_bbox,
                vehicle_index=vehicle_index,
            )
            plate_detections.extend(car_plate_detections)
        return plate_detections

    def _save_vehicle_objects(self, *, task, result, image, car_detections, person_detections):
        # 保存车辆目标
        vehicle_map = {}
        for vehicle_index, car_detection in enumerate(car_detections, start=1):
            bbox = self._clip_bbox(car_detection["bbox"], image.shape[:2])
            crop = self._crop_image(image, bbox)
            track_id = str(car_detection.get("track_id", "") or "")
            vehicle_object = DetectObject.objects.create(
                task=task,
                result=result,
                object_index=vehicle_index,
                object_type=DetectObject.ObjectType.VEHICLE,
                object_label=car_detection["label"],
                source_model=car_detection.get("source_model", "car"),
                track_id=track_id,
                confidence=car_detection["score"],
                bbox_xmin=bbox[0],
                bbox_ymin=bbox[1],
                bbox_xmax=bbox[2],
                bbox_ymax=bbox[3],
                crop_data=self._encode_image_bytes(crop),
                extra_data={
                    "person_count": sum(
                        1 for item in person_detections if int(item.get("vehicle_index", -1)) == vehicle_index
                    )
                },
            )
            vehicle_map[vehicle_index] = {
                "object": vehicle_object,
                "plate_text": "",
                "plate_score": 0.0,
                "track_id": track_id,
            }
        return vehicle_map

    def _save_plate_objects(
        self,
        *,
        task,
        result,
        image,
        car_detections,
        car_num_detections,
        vehicle_map,
        plate_assignments,
    ):
        # 保存车牌目标
        for plate_index, plate_detection in enumerate(car_num_detections, start=1):
            vehicle_index = int(plate_detection.get("vehicle_index", -1))
            if vehicle_index <= 0:
                vehicle_index = self._match_plate_to_vehicle(plate_detection, car_detections)
            if vehicle_index <= 0 or vehicle_index not in vehicle_map:
                continue

            bbox = self._clip_bbox(plate_detection["bbox"], image.shape[:2])
            crop = self._crop_image(image, bbox)
            assignment = plate_assignments.get(vehicle_index, {})
            if assignment.get("plate_index") == plate_index:
                ocr_result = assignment.get("ocr_result", {"text": "", "score": 0.0, "candidates": []})
            else:
                ocr_result = plate_detection.get("ocr_result")
                if not ocr_result:
                    ocr_result = self.plate_ocr_detector.recognize(crop)
            plate_text = str(ocr_result.get("text", "") or "")
            plate_score = float(ocr_result.get("score", 0.0) or 0.0)
            DetectObject.objects.create(
                task=task,
                result=result,
                parent_object=vehicle_map[vehicle_index]["object"],
                object_index=1000 + plate_index,
                object_type=DetectObject.ObjectType.LICENSE_PLATE,
                object_label=plate_detection["label"],
                source_model=plate_detection.get("source_model", "car"),
                track_id=vehicle_map[vehicle_index]["track_id"],
                confidence=plate_detection["score"],
                bbox_xmin=bbox[0],
                bbox_ymin=bbox[1],
                bbox_xmax=bbox[2],
                bbox_ymax=bbox[3],
                crop_data=self._encode_image_bytes(crop),
                plate_text=plate_text,
                plate_score=plate_score if plate_text else None,
                extra_data={
                    "plate_type": plate_detection.get("plate_type", ""),
                    "ocr_candidates": ocr_result.get("candidates", []),
                },
            )
            if plate_text and plate_score >= vehicle_map[vehicle_index]["plate_score"]:
                vehicle_map[vehicle_index]["plate_text"] = plate_text
                vehicle_map[vehicle_index]["plate_score"] = plate_score

        for vehicle_info in vehicle_map.values():
            vehicle_object = vehicle_info["object"]
            vehicle_object.plate_text = vehicle_info["plate_text"]
            vehicle_object.plate_score = vehicle_info["plate_score"] or None
            vehicle_object.save(update_fields=["plate_text", "plate_score", "updated_at"])

    def _save_person_and_violation_objects(self, *, task, result, image, person_detections, vehicle_map):
        # 保存人物和违规
        violation_count = 0
        new_violation_count = 0
        for person_index, person_detection in enumerate(person_detections, start=1):
            bbox = [int(round(float(value))) for value in person_detection["bbox"]]
            vehicle_index = int(person_detection.get("vehicle_index", -1))
            parent_vehicle = vehicle_map.get(vehicle_index, {}).get("object")
            vehicle_plate_text = str(vehicle_map.get(vehicle_index, {}).get("plate_text", "") or "")
            vehicle_plate_score = vehicle_map.get(vehicle_index, {}).get("plate_score", 0.0)
            track_id = str(person_detection.get("track_id", "") or "")
            export_bbox = self._expand_person_export_bbox(bbox, image.shape[:2])
            crop = self._crop_image(image, export_bbox)
            self._save_person_image(
                task=task,
                result=result,
                crop=crop,
                person_index=person_index,
            )
            person_object = DetectObject.objects.create(
                task=task,
                result=result,
                parent_object=parent_vehicle,
                object_index=2000 + person_index,
                object_type=DetectObject.ObjectType.PERSON,
                object_label=person_detection.get("label", "person"),
                source_model=person_detection.get("source_model", "person"),
                track_id=track_id,
                confidence=person_detection.get("score", 0.0),
                bbox_xmin=bbox[0],
                bbox_ymin=bbox[1],
                bbox_xmax=bbox[2],
                bbox_ymax=bbox[3],
                plate_text=vehicle_plate_text,
                plate_score=float(vehicle_plate_score) if vehicle_plate_text else None,
                seatbelt_status=person_detection.get("belt_label", "uncertain"),
                is_violation=person_detection.get("belt_label") == "not_wearing",
                extra_data={
                    "belt_score": float(person_detection.get("belt_score", 0.0)),
                    "crop_bbox": person_detection.get("crop_bbox", bbox),
                },
            )

            belt_label = person_detection.get("belt_label", "uncertain")
            belt_object = DetectObject.objects.create(
                task=task,
                result=result,
                parent_object=person_object,
                object_index=3000 + person_index,
                object_type=DetectObject.ObjectType.SEATBELT,
                object_label=belt_label,
                source_model="belt",
                track_id=track_id,
                confidence=person_detection.get("belt_score", 0.0),
                bbox_xmin=bbox[0],
                bbox_ymin=bbox[1],
                bbox_xmax=bbox[2],
                bbox_ymax=bbox[3],
                plate_text=vehicle_plate_text,
                plate_score=float(vehicle_plate_score) if vehicle_plate_text else None,
                seatbelt_status=belt_label,
                is_violation=belt_label == "not_wearing",
            )

            if belt_label == "not_wearing":
                violation_count += 1
                violation_track_id = track_id or str(person_detection.get("vehicle_track_id", "") or "")
                should_create_record = True
                if task.task_type == task.TaskType.VIDEO and violation_track_id:
                    violation_track_ids = self._video_tracking_state["violation_track_ids"]
                    should_create_record = violation_track_id not in violation_track_ids
                    if should_create_record:
                        violation_track_ids.add(violation_track_id)
                if should_create_record:
                    new_violation_count += 1
                    ViolationRecord.objects.create(
                        violation_no=self._build_violation_no(),
                        task=task,
                        result=result,
                        object=belt_object,
                        user=task.user,
                        plate_text=vehicle_map.get(vehicle_index, {}).get("plate_text", ""),
                        status=ViolationRecord.Status.PROCESSED,
                    )
        return {
            "frame_violation_count": violation_count,
            "new_violation_count": new_violation_count,
        }

    def _build_notes(self, car_detections, car_num_detections, person_detections, violation_count, frame_index=None):
        # 生成结果说明
        prefix = f"Frame {frame_index}: " if frame_index is not None else ""
        if person_detections or car_detections:
            return (
                f"{prefix}Cascade pipeline completed: {len(car_detections)} vehicle(s), "
                f"{len(car_num_detections)} plate region(s), "
                f"{len(person_detections)} person(s), {violation_count} violation(s)."
            )
        return f"{prefix}No vehicle/person target passed the score thresholds."

    def _save_result_image(self, task, image, detections, frame_index=None):
        # 保存结果图
        cv2 = self._get_cv2()
        canvas = image.copy()
        colors = {
            "car": (255, 140, 0),
            "car_num": (0, 180, 255),
            "wearing": (0, 255, 0),
            "not_wearing": (0, 0, 255),
            "uncertain": (255, 255, 0),
        }
        for detection in self._order_for_drawing(detections):
            x1, y1, x2, y2 = [int(value) for value in detection["bbox"]]
            label = detection["label"]
            score = detection["score"]
            color = colors.get(label, (255, 255, 255))
            cv2.rectangle(canvas, (x1, y1), (x2, y2), color, 2)
            cv2.putText(
                canvas,
                f"{label} {score:.2f}",
                (x1, max(20, y1 - 8)),
                cv2.FONT_HERSHEY_SIMPLEX,
                0.6,
                color,
                2,
            )

        file_name = f"{task.task_no}.jpg"
        if frame_index is not None:
            file_name = f"{task.task_no}_frame_{frame_index:06d}.jpg"
        result_relative_path = Path("seatbelt") / "results" / file_name
        result_absolute_path = Path(settings.MEDIA_ROOT) / result_relative_path
        result_absolute_path.parent.mkdir(parents=True, exist_ok=True)
        cv2.imwrite(str(result_absolute_path), cv2.cvtColor(canvas, cv2.COLOR_RGB2BGR))
        return result_relative_path.as_posix()

    def _save_person_image(self, *, task, result, crop, person_index):
        if crop.size == 0:
            return

        cv2 = self._get_cv2()
        file_name = f"{task.task_no}_person_{person_index:03d}.jpg"
        if result.frame_index is not None:
            file_name = f"{task.task_no}_frame_{result.frame_index:06d}_person_{person_index:03d}.jpg"
        person_relative_path = Path("seatbelt") / "person" / file_name
        person_absolute_path = Path(settings.MEDIA_ROOT) / person_relative_path
        person_absolute_path.parent.mkdir(parents=True, exist_ok=True)
        cv2.imwrite(str(person_absolute_path), cv2.cvtColor(crop, cv2.COLOR_RGB2BGR))

    def _expand_person_export_bbox(self, bbox, image_shape):
        return self.belt_detector._expand_person_crop_bbox(bbox, image_shape)

    def _filter_detections(self, detections, threshold):
        # 按阈值过滤
        return [item for item in detections if float(item.get("score", 0.0)) > threshold]

    def _order_for_drawing(self, detections):
        # 控制绘制顺序
        draw_priority = {
            "not_wearing": 0,
            "uncertain": 1,
            "wearing": 2,
            "car": 3,
            "car_num": 4,
        }
        return sorted(
            detections,
            key=lambda item: (
                draw_priority.get(item.get("label"), 99),
                float(item.get("score", 0.0)),
            ),
        )

    def _clip_bbox(self, bbox, image_shape):
        # 限制检测框
        height, width = image_shape
        x1, y1, x2, y2 = [int(round(float(value))) for value in bbox]
        x1 = max(0, min(width, x1))
        y1 = max(0, min(height, y1))
        x2 = max(0, min(width, x2))
        y2 = max(0, min(height, y2))
        return [x1, y1, x2, y2]

    def _crop_image(self, image, bbox):
        # 按框裁图
        x1, y1, x2, y2 = bbox
        if x2 <= x1 or y2 <= y1:
            return np.empty((0, 0, 3), dtype=image.dtype)
        return image[y1:y2, x1:x2].copy()

    def _encode_image_bytes(self, image):
        # 编码图片
        if image.size == 0:
            return None
        buffer = io.BytesIO()
        Image.fromarray(image).save(buffer, format="JPEG")
        return buffer.getvalue()

    def _match_plate_to_vehicle(self, plate_detection, car_detections):
        # 归属车牌
        best_vehicle_index = -1
        best_overlap = 0.0
        plate_bbox = [float(value) for value in plate_detection["bbox"]]
        plate_center_x = (plate_bbox[0] + plate_bbox[2]) / 2.0
        plate_center_y = (plate_bbox[1] + plate_bbox[3]) / 2.0

        for vehicle_index, car_detection in enumerate(car_detections, start=1):
            car_bbox = [float(value) for value in car_detection["bbox"]]
            if not self._point_in_bbox(plate_center_x, plate_center_y, car_bbox):
                continue
            overlap = self._intersection_area(plate_bbox, car_bbox)
            if overlap > best_overlap:
                best_overlap = overlap
                best_vehicle_index = vehicle_index
        return best_vehicle_index

    def _point_in_bbox(self, x, y, bbox):
        # 判断点位
        return bbox[0] <= x <= bbox[2] and bbox[1] <= y <= bbox[3]

    def _intersection_area(self, bbox_a, bbox_b):
        # 计算相交面积
        left = max(float(bbox_a[0]), float(bbox_b[0]))
        top = max(float(bbox_a[1]), float(bbox_b[1]))
        right = min(float(bbox_a[2]), float(bbox_b[2]))
        bottom = min(float(bbox_a[3]), float(bbox_b[3]))
        return max(0.0, right - left) * max(0.0, bottom - top)

    def _new_video_tracking_state(self):
        return {
            "next_vehicle_track_seq": 1,
            "next_person_track_seq": 1,
            "vehicle_tracks": {},
            "person_tracks": {},
            "violation_track_ids": set(),
        }

    def _prepare_plate_assignments(self, *, image, car_detections, car_num_detections):
        assignments = {}
        for plate_index, plate_detection in enumerate(car_num_detections, start=1):
            vehicle_index = int(plate_detection.get("vehicle_index", -1))
            if vehicle_index <= 0:
                vehicle_index = self._match_plate_to_vehicle(plate_detection, car_detections)
            plate_detection["vehicle_index"] = vehicle_index
            if vehicle_index <= 0:
                continue

            bbox = self._clip_bbox(plate_detection["bbox"], image.shape[:2])
            crop = self._crop_image(image, bbox)
            if crop.size == 0:
                ocr_result = {"text": "", "score": 0.0, "candidates": []}
            else:
                ocr_result = self.plate_ocr_detector.recognize(crop)
            current = {
                "plate_index": plate_index,
                "plate_text": str(ocr_result.get("text", "") or ""),
                "plate_score": float(ocr_result.get("score", 0.0) or 0.0),
                "ocr_result": ocr_result,
            }
            plate_detection["ocr_result"] = ocr_result
            best = assignments.get(vehicle_index)
            if best is None or self._is_better_plate_assignment(current, best):
                assignments[vehicle_index] = current
        return assignments

    def _is_better_plate_assignment(self, current, best):
        current_has_text = bool(current.get("plate_text"))
        best_has_text = bool(best.get("plate_text"))
        if current_has_text != best_has_text:
            return current_has_text
        return float(current.get("plate_score", 0.0)) > float(best.get("plate_score", 0.0))

    def _assign_video_tracks(self, *, task, frame_index, car_detections, person_detections, plate_assignments):
        vehicle_track_map = self._assign_vehicle_tracks(
            task=task,
            frame_index=frame_index,
            car_detections=car_detections,
            plate_assignments=plate_assignments,
        )
        for person_detection in person_detections:
            vehicle_index = int(person_detection.get("vehicle_index", -1))
            person_detection["vehicle_track_id"] = vehicle_track_map.get(vehicle_index, "")
        self._assign_person_tracks(
            task=task,
            frame_index=frame_index,
            person_detections=person_detections,
        )

    def _assign_vehicle_tracks(self, *, task, frame_index, car_detections, plate_assignments):
        track_map = {}
        active_tracks = self._get_active_tracks("vehicle_tracks", frame_index)
        matched_track_ids = set()
        for vehicle_index, car_detection in enumerate(car_detections, start=1):
            bbox = [float(value) for value in car_detection["bbox"]]
            assignment = plate_assignments.get(vehicle_index, {})
            plate_text = str(assignment.get("plate_text", "") or "")
            plate_score = float(assignment.get("plate_score", 0.0) or 0.0)
            best_track_id = ""
            best_rank = (-1, -1.0)
            for track_id, track in active_tracks.items():
                if track_id in matched_track_ids:
                    continue
                track_plate_text = str(track.get("plate_text", "") or "")
                if plate_text and track_plate_text and plate_text != track_plate_text:
                    continue
                iou = self._bbox_iou(bbox, track["bbox"])
                if plate_text and track_plate_text == plate_text:
                    rank = (2, iou)
                elif iou >= self._vehicle_track_iou_threshold:
                    rank = (1, iou)
                else:
                    continue
                if rank > best_rank:
                    best_rank = rank
                    best_track_id = track_id

            previous_track = self._video_tracking_state["vehicle_tracks"].get(best_track_id, {})
            if not best_track_id:
                sequence = self._video_tracking_state["next_vehicle_track_seq"]
                self._video_tracking_state["next_vehicle_track_seq"] = sequence + 1
                best_track_id = self._build_track_id(task, "V", sequence)
                previous_track = {}

            matched_track_ids.add(best_track_id)
            car_detection["track_id"] = best_track_id
            self._video_tracking_state["vehicle_tracks"][best_track_id] = {
                "bbox": bbox,
                "last_frame_index": frame_index,
                "plate_text": plate_text or str(previous_track.get("plate_text", "") or ""),
                "plate_score": max(plate_score, float(previous_track.get("plate_score", 0.0) or 0.0)),
            }
            track_map[vehicle_index] = best_track_id

        self._cleanup_stale_tracks("vehicle_tracks", frame_index)
        return track_map

    def _assign_person_tracks(self, *, task, frame_index, person_detections):
        active_tracks = self._get_active_tracks("person_tracks", frame_index)
        matched_track_ids = set()
        for person_detection in person_detections:
            bbox = [float(value) for value in person_detection["bbox"]]
            vehicle_track_id = str(person_detection.get("vehicle_track_id", "") or "")
            best_track_id = ""
            best_iou = -1.0
            for track_id, track in active_tracks.items():
                if track_id in matched_track_ids:
                    continue
                track_vehicle_track_id = str(track.get("vehicle_track_id", "") or "")
                if vehicle_track_id and track_vehicle_track_id and vehicle_track_id != track_vehicle_track_id:
                    continue
                iou = self._bbox_iou(bbox, track["bbox"])
                if iou < self._person_track_iou_threshold:
                    continue
                if iou > best_iou:
                    best_iou = iou
                    best_track_id = track_id

            if not best_track_id:
                sequence = self._video_tracking_state["next_person_track_seq"]
                self._video_tracking_state["next_person_track_seq"] = sequence + 1
                best_track_id = self._build_track_id(task, "P", sequence)

            matched_track_ids.add(best_track_id)
            person_detection["track_id"] = best_track_id
            self._video_tracking_state["person_tracks"][best_track_id] = {
                "bbox": bbox,
                "last_frame_index": frame_index,
                "vehicle_track_id": vehicle_track_id,
            }

        self._cleanup_stale_tracks("person_tracks", frame_index)

    def _build_track_id(self, task, prefix, sequence):
        task_no = getattr(task, "task_no", "task") or "task"
        return f"{task_no}-{prefix}{int(sequence):04d}"

    def _get_active_tracks(self, track_key, frame_index):
        tracks = self._video_tracking_state[track_key]
        return {
            track_id: track
            for track_id, track in tracks.items()
            if frame_index - int(track.get("last_frame_index", frame_index)) <= self._track_max_gap_frames
        }

    def _cleanup_stale_tracks(self, track_key, frame_index):
        tracks = self._video_tracking_state[track_key]
        stale_track_ids = [
            track_id
            for track_id, track in tracks.items()
            if frame_index - int(track.get("last_frame_index", frame_index)) > self._track_max_gap_frames
        ]
        for track_id in stale_track_ids:
            tracks.pop(track_id, None)

    def _bbox_iou(self, bbox_a, bbox_b):
        intersection = self._intersection_area(bbox_a, bbox_b)
        if intersection <= 0:
            return 0.0
        area_a = max(0.0, float(bbox_a[2]) - float(bbox_a[0])) * max(0.0, float(bbox_a[3]) - float(bbox_a[1]))
        area_b = max(0.0, float(bbox_b[2]) - float(bbox_b[0])) * max(0.0, float(bbox_b[3]) - float(bbox_b[1]))
        union = area_a + area_b - intersection
        if union <= 0:
            return 0.0
        return intersection / union

    def _build_violation_no(self):
        # 生成违规号
        return f"V{timezone.now().strftime('%Y%m%d%H%M%S')}{uuid.uuid4().hex[:6].upper()}"

    def _get_cv2(self):
        # 获取cv2
        try:
            import cv2
        except Exception as exc:
            raise ModelRuntimeError("OpenCV is required for image/video rendering.") from exc
        return cv2
