import json
import shutil
from pathlib import Path
from unittest.mock import patch

import numpy as np
from django.core.files.uploadedfile import SimpleUploadedFile
from django.test import SimpleTestCase, TestCase, override_settings
from django.urls import reverse
from django.utils import timezone

from .detection.pipeline import SeatbeltDetectionService
from .detectors.belt_detector import BeltDetector
from .detectors.plate_detector import PlateDetector
from .inference import OnnxClassificationSpec
from .inference.onnx_runtime import preprocess_image
from .models import (
    DailyDetectionStat,
    DetectObject,
    DetectResult,
    DetectTask,
    OperationLog,
    QueryLog,
    User,
    UserPlateBinding,
    ViolationRecord,
)


TEMP_MEDIA_ROOT = Path(__file__).resolve().parent.parent / "test_media"
TEMP_MEDIA_ROOT.mkdir(exist_ok=True)


@override_settings(MEDIA_ROOT=TEMP_MEDIA_ROOT)
class DetectionApiTests(TestCase):
    @classmethod
    def tearDownClass(cls):
        super().tearDownClass()
        shutil.rmtree(TEMP_MEDIA_ROOT, ignore_errors=True)

    def setUp(self):
        # 鍑嗗鐢ㄦ埛
        self.user = User.objects.create_user(
            username="tester",
            password="pass123456",
        )
        self.auditor = User.objects.create_user(
            username="auditor",
            password="pass123456",
            role=User.Role.AUDITOR,
        )
        self.admin = User.objects.create_user(
            username="admin",
            password="pass123456",
            role=User.Role.ADMIN,
        )
        self.access_token = self.login_and_get_token("tester", "pass123456")
        self.auditor_token = self.login_and_get_token("auditor", "pass123456")
        self.admin_token = self.login_and_get_token("admin", "pass123456")
        self.auth_headers = {"HTTP_AUTHORIZATION": f"Bearer {self.access_token}"}
        self.auditor_headers = {"HTTP_AUTHORIZATION": f"Bearer {self.auditor_token}"}
        self.admin_headers = {"HTTP_AUTHORIZATION": f"Bearer {self.admin_token}"}

    def login_and_get_token(self, username, password):
        response = self.client.post(
            reverse("seatbelt-login"),
            data=json.dumps({"username": username, "password": password}),
            content_type="application/json",
        )
        self.assertEqual(response.status_code, 200)
        return response.json()["data"]["access_token"]

    def create_violation_fixture(self, status=ViolationRecord.Status.PROCESSED):
        # 鍒涘缓杩濊鏁版嵁
        task = DetectTask.objects.create(
            task_no="T202604020002BB",
            user=self.user,
            task_type=DetectTask.TaskType.IMAGE,
            source_name="scene.jpg",
            source_file=SimpleUploadedFile("scene.jpg", b"abc", content_type="image/jpeg"),
            status=DetectTask.Status.COMPLETED,
            result_count=1,
            violation_count=1,
            has_violation=True,
        )
        result = DetectResult.objects.create(
            task=task,
            result_index=1,
            image_width=1280,
            image_height=720,
            has_violation=True,
            violation_count=1,
        )
        vehicle = DetectObject.objects.create(
            task=task,
            result=result,
            object_index=1,
            object_type=DetectObject.ObjectType.VEHICLE,
            object_label="car",
            confidence=0.9,
            bbox_xmin=1,
            bbox_ymin=2,
            bbox_xmax=3,
            bbox_ymax=4,
            plate_text="绮12345",
        )
        seatbelt = DetectObject.objects.create(
            task=task,
            result=result,
            parent_object=vehicle,
            object_index=2,
            object_type=DetectObject.ObjectType.SEATBELT,
            object_label="not_wearing",
            confidence=0.95,
            bbox_xmin=5,
            bbox_ymin=6,
            bbox_xmax=7,
            bbox_ymax=8,
            is_violation=True,
            seatbelt_status="not_wearing",
        )
        violation = ViolationRecord.objects.create(
            violation_no="V202604020001AA",
            task=task,
            result=result,
            object=seatbelt,
            user=self.user,
            violation_type=ViolationRecord.ViolationType.NO_SEATBELT,
            plate_text="绮12345",
            status=status,
        )
        return task, result, vehicle, seatbelt, violation

    def test_health_check(self):
        response = self.client.get(reverse("seatbelt-health"))
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json()["data"]["status"], "ok")

    def test_auth_options(self):
        # 娴嬭瘯棰勬璇锋眰
        response = self.client.options(reverse("seatbelt-register"))
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response["Access-Control-Allow-Origin"], "*")

    def test_register(self):
        # 娴嬭瘯娉ㄥ唽
        response = self.client.post(
            reverse("seatbelt-register"),
            data=json.dumps(
                {
                    "username": "tester_new",
                    "password": "pass123456",
                    "confirm_password": "pass123456",
                    "phone": "13800000000",
                }
            ),
            content_type="application/json",
        )

        self.assertEqual(response.status_code, 201)
        self.assertTrue(User.objects.filter(username="tester_new").exists())
        self.assertIn("access_token", response.json()["data"])

    def test_login(self):
        # 娴嬭瘯鐧诲綍
        response = self.client.post(
            reverse("seatbelt-login"),
            data=json.dumps({"username": "tester", "password": "pass123456"}),
            content_type="application/json",
        )

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json()["data"]["username"], "tester")
        self.assertIn("access_token", response.json()["data"])
        self.assertIn("refresh_token", response.json()["data"])

    def test_login_with_phone(self):
        self.user.phone = "13800000000"
        self.user.save(update_fields=["phone"])

        response = self.client.post(
            reverse("seatbelt-login"),
            data=json.dumps({"phone": "13800000000", "password": "pass123456"}),
            content_type="application/json",
        )

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json()["data"]["username"], "tester")
        self.assertIn("access_token", response.json()["data"])

    def test_me(self):
        # 娴嬭瘯褰撳墠鐢ㄦ埛
        response = self.client.get(reverse("seatbelt-me"), **self.auth_headers)
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json()["data"]["username"], "tester")

    def test_change_password(self):
        # 娴嬭瘯淇敼瀵嗙爜
        response = self.client.post(
            reverse("seatbelt-change-password"),
            data=json.dumps(
                {
                    "old_password": "pass123456",
                    "new_password": "newpass123",
                    "confirm_password": "newpass123",
                }
            ),
            content_type="application/json",
            **self.auth_headers,
        )

        self.assertEqual(response.status_code, 200)
        relogin = self.client.post(
            reverse("seatbelt-login"),
            data=json.dumps({"username": "tester", "password": "newpass123"}),
            content_type="application/json",
        )
        self.assertEqual(relogin.status_code, 200)

    def test_create_detection_task(self):
        # 娴嬭瘯鍥剧墖璇嗗埆
        upload = SimpleUploadedFile("test_scene.jpg", b"fake-image-content", content_type="image/jpeg")
        mocked_result = {
            "confidence": 0.91,
            "result_id": 1,
            "result_count": 1,
            "processed_frames": 1,
            "total_frames": 1,
            "violation_count": 0,
            "object_count": 3,
            "person_count": 1,
            "has_violation": False,
        }

        with patch("seatbelt.api.views.SeatbeltDetectionService.analyze", return_value=mocked_result):
            response = self.client.post(
                reverse("seatbelt-detection-list"),
                {"file": upload, "notes": "test image"},
                **self.auth_headers,
            )

        self.assertEqual(response.status_code, 201)
        payload = response.json()["data"]
        self.assertEqual(payload["status"], DetectTask.Status.COMPLETED)
        self.assertEqual(payload["violation_count"], 0)
        self.assertEqual(payload["task_type"], DetectTask.TaskType.IMAGE)
        self.assertEqual(payload["user"], "tester")
        stat = DailyDetectionStat.objects.get(user=self.user, stat_date=timezone.localdate())
        self.assertEqual(stat.detection_count, 1)

    def test_create_video_detection_task(self):
        # 娴嬭瘯瑙嗛璇嗗埆
        upload = SimpleUploadedFile("test_video.mp4", b"fake-video-content", content_type="video/mp4")
        mocked_result = {
            "confidence": 0.88,
            "result_count": 3,
            "processed_frames": 3,
            "total_frames": 3,
            "duration_ms": 120,
            "violation_count": 1,
            "object_count": 9,
            "person_count": 3,
            "has_violation": True,
            "result_ids": [1, 2, 3],
        }

        with patch("seatbelt.api.views.SeatbeltDetectionService.analyze", return_value=mocked_result):
            response = self.client.post(
                reverse("seatbelt-detection-list"),
                {"file": upload, "notes": "test video"},
                **self.auth_headers,
            )

        self.assertEqual(response.status_code, 201)
        payload = response.json()["data"]
        self.assertEqual(payload["status"], DetectTask.Status.COMPLETED)
        self.assertEqual(payload["task_type"], DetectTask.TaskType.VIDEO)
        self.assertEqual(payload["result_count"], 3)
        self.assertEqual(payload["violation_count"], 1)
        self.assertTrue(payload["has_violation"])

    def test_list_detection_tasks(self):
        # 娴嬭瘯浠诲姟鏌ヨ
        DetectTask.objects.create(
            task_no="T202604020001AA",
            user=self.user,
            task_type=DetectTask.TaskType.IMAGE,
            source_name="safe.jpg",
            source_file=SimpleUploadedFile("safe.jpg", b"abc", content_type="image/jpeg"),
            status=DetectTask.Status.COMPLETED,
        )

        response = self.client.get(reverse("seatbelt-detection-list"), **self.auth_headers)
        self.assertEqual(response.status_code, 200)
        self.assertEqual(len(response.json()["data"]), 1)

    def test_list_detection_tasks_only_returns_current_user_uploads(self):
        DetectTask.objects.create(
            task_no="T202604020001AB",
            user=self.user,
            task_type=DetectTask.TaskType.IMAGE,
            source_name="mine.jpg",
            source_file=SimpleUploadedFile("mine.jpg", b"abc", content_type="image/jpeg"),
            status=DetectTask.Status.COMPLETED,
        )
        other_user = User.objects.create_user(username="other_user", password="pass123456")
        DetectTask.objects.create(
            task_no="T202604020001AC",
            user=other_user,
            task_type=DetectTask.TaskType.IMAGE,
            source_name="other.jpg",
            source_file=SimpleUploadedFile("other.jpg", b"abc", content_type="image/jpeg"),
            status=DetectTask.Status.COMPLETED,
        )

        response = self.client.get(reverse("seatbelt-detection-list"), **self.auth_headers)
        self.assertEqual(response.status_code, 200)
        payload = response.json()["data"]
        self.assertEqual(len(payload), 1)
        self.assertEqual(payload[0]["user"], "tester")

    def test_detection_detail_contains_results_and_violations(self):
        # 娴嬭瘯浠诲姟璇︽儏
        task, _, _, _, _ = self.create_violation_fixture()

        response = self.client.get(reverse("seatbelt-detection-detail", args=[task.id]), **self.auth_headers)
        self.assertEqual(response.status_code, 200)
        payload = response.json()["data"]
        self.assertEqual(payload["task_result"], "not_wearing")
        self.assertEqual(len(payload["results"]), 1)
        self.assertEqual(len(payload["results"][0]["objects"]), 2)
        self.assertEqual(len(payload["results"][0]["violations"]), 1)

    def test_violation_list_and_review(self):
        _, _, _, _, violation = self.create_violation_fixture(
            status=ViolationRecord.Status.PENDING_REVIEW
        )

        response = self.client.get(reverse("seatbelt-violation-list"), **self.auth_headers)
        self.assertEqual(response.status_code, 200)
        self.assertEqual(len(response.json()["data"]), 1)
        self.assertEqual(response.json()["data"][0]["plate_text"], "绮12345")

        review_response = self.client.post(
            reverse("seatbelt-violation-review", args=[violation.id]),
            data=json.dumps({"status": 2, "audit_remark": "纭杩濊"}),
            content_type="application/json",
            **self.auditor_headers,
        )
        self.assertEqual(review_response.status_code, 200)
        violation.refresh_from_db()
        self.assertEqual(violation.status, ViolationRecord.Status.CONFIRMED)
        self.assertEqual(violation.auditor_id, self.auditor.id)

    def test_dashboard(self):
        # 娴嬭瘯棣栭〉缁熻
        self.create_violation_fixture()
        DailyDetectionStat.objects.create(
            user=self.user,
            stat_date=timezone.localdate(),
            detection_count=2,
        )

        response = self.client.get(reverse("seatbelt-dashboard"), **self.auth_headers)
        self.assertEqual(response.status_code, 200)
        data = response.json()["data"]
        self.assertEqual(data["task_total"], 1)
        self.assertEqual(data["violation_total"], 1)
        self.assertEqual(data["today_user_detection_total"], 2)
        self.assertEqual(data["today_detection_total"], 2)
        self.assertEqual(data["user_task_total"], 1)
        self.assertNotIn("today_system_detection_total", data)
        self.assertNotIn("system_task_total", data)
        self.assertEqual(len(data["recent_tasks"]), 1)

    def test_dashboard_for_admin_contains_today_system_detection_total(self):
        self.create_violation_fixture()
        DailyDetectionStat.objects.create(
            user=self.user,
            stat_date=timezone.localdate(),
            detection_count=2,
        )
        DailyDetectionStat.objects.create(
            user=self.auditor,
            stat_date=timezone.localdate(),
            detection_count=3,
        )

        response = self.client.get(reverse("seatbelt-dashboard"), **self.admin_headers)
        self.assertEqual(response.status_code, 200)
        data = response.json()["data"]
        self.assertEqual(data["today_user_detection_total"], 0)
        self.assertEqual(data["today_system_detection_total"], 5)
        self.assertEqual(data["today_detection_total"], 5)
        self.assertEqual(data["user_task_total"], 0)
        self.assertEqual(data["system_task_total"], 1)

    def test_dashboard_returns_frontend_summary_fields(self):
        self.create_violation_fixture()
        DailyDetectionStat.objects.create(
            user=self.user,
            stat_date=timezone.localdate(),
            detection_count=2,
        )

        response = self.client.get(reverse("seatbelt-dashboard"), **self.auth_headers)
        self.assertEqual(response.status_code, 200)
        data = response.json()["data"]
        self.assertEqual(data["total_count"], 1)
        self.assertEqual(data["today_count"], 2)
        self.assertEqual(data["pending_violation_count"], 0)
        self.assertEqual(data["violation_count"], 1)
        self.assertEqual(data["wear_count"], 0)
        self.assertEqual(data["no_wear_count"], 1)
        self.assertEqual(data["recent_tasks"][0]["task_no"], "T202604020002BB")
        self.assertEqual(data["recent_violations"][0]["task_no"], "T202604020002BB")

    def test_admin_dashboard_returns_system_frontend_summary_fields(self):
        self.create_violation_fixture()
        DailyDetectionStat.objects.create(
            user=self.user,
            stat_date=timezone.localdate(),
            detection_count=2,
        )
        DailyDetectionStat.objects.create(
            user=self.auditor,
            stat_date=timezone.localdate(),
            detection_count=3,
        )

        response = self.client.get(reverse("seatbelt-dashboard"), **self.admin_headers)
        self.assertEqual(response.status_code, 200)
        data = response.json()["data"]
        self.assertEqual(data["total_count"], 1)
        self.assertEqual(data["today_count"], 5)
        self.assertEqual(data["pending_violation_count"], 0)
        self.assertEqual(data["violation_count"], 1)
        self.assertEqual(data["wear_count"], 0)
        self.assertEqual(data["no_wear_count"], 1)

    def test_dashboard_violation_count_only_includes_status_zero_or_three(self):
        _, _, _, _, violation = self.create_violation_fixture()
        DailyDetectionStat.objects.create(
            user=self.user,
            stat_date=timezone.localdate(),
            detection_count=1,
        )
        ViolationRecord.objects.create(
            violation_no="V202604020001CC",
            task=violation.task,
            result=violation.result,
            object=violation.object,
            user=self.user,
            plate_text=violation.plate_text,
            status=ViolationRecord.Status.REJECTED,
        )
        ViolationRecord.objects.create(
            violation_no="V202604020001DD",
            task=violation.task,
            result=violation.result,
            object=violation.object,
            user=self.user,
            plate_text=violation.plate_text,
            status=ViolationRecord.Status.PROCESSED,
        )
        ViolationRecord.objects.create(
            violation_no="V202604020001EE",
            task=violation.task,
            result=violation.result,
            object=violation.object,
            user=self.user,
            plate_text=violation.plate_text,
            status=ViolationRecord.Status.CONFIRMED,
        )

        response = self.client.get(reverse("seatbelt-dashboard"), **self.auth_headers)
        self.assertEqual(response.status_code, 200)
        data = response.json()["data"]
        self.assertEqual(data["pending_violation_count"], 0)
        self.assertEqual(data["violation_count"], 3)
        self.assertEqual(data["violation_total"], 3)

    def test_violation_detail_and_review_accept_frontend_fields(self):
        _, _, _, _, violation = self.create_violation_fixture(
            status=ViolationRecord.Status.PENDING_REVIEW
        )

        list_response = self.client.get(
            reverse("seatbelt-violation-list") + "?status=1",
            **self.auditor_headers,
        )
        self.assertEqual(list_response.status_code, 200)
        list_payload = list_response.json()["data"]
        self.assertEqual(list_payload[0]["status"], 1)
        self.assertEqual(list_payload[0]["task_id"], violation.task_id)
        self.assertEqual(list_payload[0]["result_id"], violation.result_id)
        self.assertEqual(list_payload[0]["object_id"], violation.object_id)

        pending_response = self.client.get(
            reverse("seatbelt-violation-list") + "?status=1",
            **self.auditor_headers,
        )
        self.assertEqual(pending_response.status_code, 200)
        self.assertEqual(len(pending_response.json()["data"]), 1)
        self.assertEqual(pending_response.json()["data"][0]["id"], violation.id)

        detail_response = self.client.get(reverse("seatbelt-violation-detail", args=[violation.id]), **self.auditor_headers)
        self.assertEqual(detail_response.status_code, 200)
        detail_payload = detail_response.json()["data"]
        self.assertEqual(detail_payload["status"], 1)
        self.assertEqual(detail_payload["task_no"], violation.task.task_no)

        review_response = self.client.post(
            reverse("seatbelt-violation-review", args=[violation.id]),
            data=json.dumps({"status": 2, "audit_remark": "椹冲洖"}),
            content_type="application/json",
            **self.auditor_headers,
        )
        self.assertEqual(review_response.status_code, 200)
        violation.refresh_from_db()
        self.assertEqual(violation.status, ViolationRecord.Status.CONFIRMED)
        self.assertEqual(violation.audit_remark, "椹冲洖")

    def test_log_endpoints_for_staff(self):
        # 娴嬭瘯鏃ュ織鏌ヨ
        self.create_violation_fixture()
        self.client.get(reverse("seatbelt-detection-list"), **self.auth_headers)

        query_response = self.client.get(reverse("seatbelt-query-log-list"), **self.auditor_headers)
        operation_response = self.client.get(reverse("seatbelt-operation-log-list"), **self.auditor_headers)

        self.assertEqual(query_response.status_code, 200)
        self.assertEqual(operation_response.status_code, 200)
        self.assertGreaterEqual(QueryLog.objects.count(), 1)
        self.assertGreaterEqual(OperationLog.objects.count(), 1)

    def test_system_user_management(self):
        # 娴嬭瘯鐢ㄦ埛绠＄悊
        create_response = self.client.post(
            reverse("seatbelt-user-list"),
            data=json.dumps(
                {
                    "username": "staff_new",
                    "password": "pass123456",
                    "confirm_password": "pass123456",
                    "role": "auditor",
                }
            ),
            content_type="application/json",
            **self.admin_headers,
        )
        self.assertEqual(create_response.status_code, 201)
        user_id = create_response.json()["data"]["id"]

        list_response = self.client.get(reverse("seatbelt-user-list"), **self.auditor_headers)
        self.assertEqual(list_response.status_code, 200)
        self.assertGreaterEqual(len(list_response.json()["data"]), 4)

        update_response = self.client.put(
            reverse("seatbelt-user-detail", args=[user_id]),
            data=json.dumps({"is_active": False}),
            content_type="application/json",
            **self.admin_headers,
        )
        self.assertEqual(update_response.status_code, 200)
        self.assertFalse(update_response.json()["data"]["is_active"])

        reset_response = self.client.post(
            reverse("seatbelt-user-reset-password", args=[user_id]),
            data=json.dumps({"new_password": "reset123456", "confirm_password": "reset123456"}),
            content_type="application/json",
            **self.admin_headers,
        )
        self.assertEqual(reset_response.status_code, 200)

    def test_object_image_endpoint(self):
        # 娴嬭瘯鐩爣鎴浘
        task = DetectTask.objects.create(
            task_no="T202604020003CC",
            user=self.user,
            task_type=DetectTask.TaskType.IMAGE,
            source_name="scene.jpg",
            source_file=SimpleUploadedFile("scene.jpg", b"abc", content_type="image/jpeg"),
            status=DetectTask.Status.COMPLETED,
        )
        result = DetectResult.objects.create(task=task, result_index=1)
        detect_object = DetectObject.objects.create(
            task=task,
            result=result,
            object_index=1,
            object_type=DetectObject.ObjectType.VEHICLE,
            object_label="car",
            confidence=0.8,
            bbox_xmin=1,
            bbox_ymin=2,
            bbox_xmax=3,
            bbox_ymax=4,
            crop_data=b"object-image",
        )

        response = self.client.get(reverse("seatbelt-object-image", args=[detect_object.id]), **self.auth_headers)
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.content, b"object-image")


@override_settings(MEDIA_ROOT=TEMP_MEDIA_ROOT)
class VideoTrackingTests(TestCase):
    def setUp(self):
        self.user = User.objects.create_user(
            username="tracker",
            password="pass123456",
        )

    def test_prepare_plate_assignments_uses_plate_text_model(self):
        service = SeatbeltDetectionService()
        image = np.zeros((120, 240, 3), dtype=np.uint8)
        car_detections = [
            {"bbox": [10, 10, 110, 110], "label": "car", "score": 0.95},
        ]
        car_num_detections = [
            {
                "bbox": [20, 40, 90, 70],
                "label": "car_num",
                "score": 0.91,
                "vehicle_index": 1,
            }
        ]

        with patch.object(
            service.plate_ocr_detector,
            "recognize",
            return_value={"text": "绮12345", "score": 0.98, "candidates": [{"text": "绮12345", "score": 0.98}]},
        ):
            assignments = service._prepare_plate_assignments(
                image=image,
                car_detections=car_detections,
                car_num_detections=car_num_detections,
            )

        self.assertEqual(assignments[1]["plate_text"], "绮12345")
        self.assertEqual(assignments[1]["plate_score"], 0.98)

    def test_assign_video_tracks_reuses_vehicle_and_person_track_ids(self):
        service = SeatbeltDetectionService()
        task = DetectTask(task_no="TTRACK001", task_type=DetectTask.TaskType.VIDEO)

        frame1_cars = [
            {"bbox": [10, 10, 110, 110], "label": "car", "score": 0.95},
            {"bbox": [210, 10, 310, 110], "label": "car", "score": 0.94},
        ]
        frame1_people = [
            {"bbox": [20, 20, 50, 95], "label": "person", "score": 0.91, "vehicle_index": 1},
            {"bbox": [55, 18, 85, 96], "label": "person", "score": 0.9, "vehicle_index": 1},
            {"bbox": [220, 18, 250, 96], "label": "person", "score": 0.89, "vehicle_index": 2},
        ]
        service._assign_video_tracks(
            task=task,
            frame_index=1,
            car_detections=frame1_cars,
            person_detections=frame1_people,
            plate_assignments={
                1: {"plate_text": "A12345", "plate_score": 0.97},
                2: {"plate_text": "B67890", "plate_score": 0.96},
            },
        )

        frame1_vehicle_tracks = [item["track_id"] for item in frame1_cars]
        frame1_person_tracks = [item["track_id"] for item in frame1_people]

        frame2_cars = [
            {"bbox": [14, 12, 114, 112], "label": "car", "score": 0.93},
            {"bbox": [214, 12, 314, 112], "label": "car", "score": 0.92},
        ]
        frame2_people = [
            {"bbox": [24, 22, 54, 97], "label": "person", "score": 0.9, "vehicle_index": 1},
            {"bbox": [58, 20, 88, 98], "label": "person", "score": 0.89, "vehicle_index": 1},
            {"bbox": [224, 20, 254, 98], "label": "person", "score": 0.88, "vehicle_index": 2},
        ]
        service._assign_video_tracks(
            task=task,
            frame_index=2,
            car_detections=frame2_cars,
            person_detections=frame2_people,
            plate_assignments={
                1: {"plate_text": "A12345", "plate_score": 0.98},
                2: {"plate_text": "B67890", "plate_score": 0.95},
            },
        )

        self.assertEqual([item["track_id"] for item in frame2_cars], frame1_vehicle_tracks)
        self.assertEqual([item["track_id"] for item in frame2_people], frame1_person_tracks)
        self.assertEqual(len(set(frame1_person_tracks)), 3)

    def test_video_violations_are_deduplicated_by_person_track(self):
        service = SeatbeltDetectionService()
        task = DetectTask.objects.create(
            task_no="TTRACK002",
            user=self.user,
            task_type=DetectTask.TaskType.VIDEO,
            source_name="video.mp4",
            source_file=SimpleUploadedFile("video.mp4", b"video", content_type="video/mp4"),
            status=DetectTask.Status.RUNNING,
        )
        result1 = DetectResult.objects.create(task=task, result_index=1, frame_index=1)
        result2 = DetectResult.objects.create(task=task, result_index=2, frame_index=2)
        vehicle = DetectObject.objects.create(
            task=task,
            result=result1,
            object_index=1,
            object_type=DetectObject.ObjectType.VEHICLE,
            object_label="car",
            track_id="TTRACK002-V0001",
            confidence=0.95,
            bbox_xmin=10,
            bbox_ymin=10,
            bbox_xmax=110,
            bbox_ymax=110,
        )
        vehicle_map = {
            1: {
                "object": vehicle,
                "plate_text": "A12345",
                "plate_score": 0.98,
                "track_id": "TTRACK002-V0001",
            }
        }
        image = np.ones((120, 120, 3), dtype=np.uint8) * 255

        first = service._save_person_and_violation_objects(
            task=task,
            result=result1,
            image=image,
            person_detections=[
                {
                    "bbox": [20, 20, 50, 90],
                    "label": "person",
                    "score": 0.9,
                    "vehicle_index": 1,
                    "track_id": "TTRACK002-P0001",
                    "vehicle_track_id": "TTRACK002-V0001",
                    "belt_label": "not_wearing",
                    "belt_score": 0.93,
                }
            ],
            vehicle_map=vehicle_map,
        )
        second = service._save_person_and_violation_objects(
            task=task,
            result=result2,
            image=image,
            person_detections=[
                {
                    "bbox": [22, 22, 52, 92],
                    "label": "person",
                    "score": 0.89,
                    "vehicle_index": 1,
                    "track_id": "TTRACK002-P0001",
                    "vehicle_track_id": "TTRACK002-V0001",
                    "belt_label": "not_wearing",
                    "belt_score": 0.91,
                }
            ],
            vehicle_map=vehicle_map,
        )

        self.assertEqual(first["frame_violation_count"], 1)
        self.assertEqual(first["new_violation_count"], 1)
        self.assertEqual(second["frame_violation_count"], 1)
        self.assertEqual(second["new_violation_count"], 0)
        self.assertEqual(ViolationRecord.objects.count(), 1)
        person_tracks = list(
            DetectObject.objects.filter(task=task, object_type=DetectObject.ObjectType.PERSON)
            .order_by("id")
            .values_list("track_id", flat=True)
        )
        belt_tracks = list(
            DetectObject.objects.filter(task=task, object_type=DetectObject.ObjectType.SEATBELT)
            .order_by("id")
            .values_list("track_id", flat=True)
        )
        person_plates = list(
            DetectObject.objects.filter(task=task, object_type=DetectObject.ObjectType.PERSON)
            .order_by("id")
            .values_list("plate_text", flat=True)
        )
        belt_plates = list(
            DetectObject.objects.filter(task=task, object_type=DetectObject.ObjectType.SEATBELT)
            .order_by("id")
            .values_list("plate_text", flat=True)
        )
        self.assertEqual(person_tracks, ["TTRACK002-P0001", "TTRACK002-P0001"])
        self.assertEqual(belt_tracks, ["TTRACK002-P0001", "TTRACK002-P0001"])
        self.assertEqual(person_plates, ["A12345", "A12345"])
        self.assertEqual(belt_plates, ["A12345", "A12345"])
        self.assertTrue((TEMP_MEDIA_ROOT / "seatbelt" / "person" / "TTRACK002_frame_000001_person_001.jpg").exists())
        self.assertTrue((TEMP_MEDIA_ROOT / "seatbelt" / "person" / "TTRACK002_frame_000002_person_001.jpg").exists())


@override_settings(MEDIA_ROOT=TEMP_MEDIA_ROOT)
class MiniAppApiTests(TestCase):
    def setUp(self):
        self.password = "pass123456"
        self.phone = "13800000000"
        self.user = User.objects.create_user(
            username="u_13800000000",
            password=self.password,
            phone=self.phone,
            role=User.Role.USER,
        )
        self.binding = UserPlateBinding.objects.create(user=self.user, plate_text="绮12345", is_active=True)
        self.task = DetectTask.objects.create(
            task_no="T202604040001AA",
            user=self.user,
            task_type=DetectTask.TaskType.IMAGE,
            source_name="scene.jpg",
            source_file=SimpleUploadedFile("scene.jpg", b"abc", content_type="image/jpeg"),
            status=DetectTask.Status.COMPLETED,
        )
        self.result = DetectResult.objects.create(
            task=self.task,
            result_index=1,
            result_image="seatbelt/results/demo.jpg",
        )
        self.object = DetectObject.objects.create(
            task=self.task,
            result=self.result,
            object_index=1,
            object_type=DetectObject.ObjectType.SEATBELT,
            object_label="not_wearing",
            confidence=0.95,
            bbox_xmin=1,
            bbox_ymin=2,
            bbox_xmax=3,
            bbox_ymax=4,
            is_violation=True,
            crop_data=b"img",
        )
        self.violation = ViolationRecord.objects.create(
            violation_no="V202604040001AA",
            task=self.task,
            result=self.result,
            object=self.object,
            user=self.user,
            plate_text="绮12345",
        )

    def miniapp_login_headers(self):
        response = self.client.post(
            reverse("seatbelt-miniapp-login"),
            data=json.dumps({"account": self.phone, "password": self.password}),
            content_type="application/json",
        )
        self.assertEqual(response.status_code, 200)
        token = response.json()["data"]["access_token"]
        return {"HTTP_AUTHORIZATION": f"Bearer {token}"}

    def test_miniapp_register(self):
        response = self.client.post(
            reverse("seatbelt-miniapp-register"),
            data=json.dumps(
                {
                    "phone": "13900000000",
                    "password": self.password,
                    "confirm_password": self.password,
                }
            ),
            content_type="application/json",
        )
        self.assertEqual(response.status_code, 201)
        payload = response.json()["data"]
        self.assertEqual(payload["phone"], "13900000000")
        self.assertEqual(payload["bound_plates"], [])
        self.assertTrue(payload["username"].startswith("u_13900000000"))

    @patch("seatbelt.api.views.wechat_code_to_session")
    def test_miniapp_wx_login_creates_user_and_returns_password_state(self, mock_wechat_code_to_session):
        mock_wechat_code_to_session.return_value = {"openid": "wx-openid-001"}

        response = self.client.post(
            reverse("seatbelt-miniapp-wx-login"),
            data=json.dumps({"code": "wx-login-code"}),
            content_type="application/json",
        )

        self.assertEqual(response.status_code, 200)
        payload = response.json()["data"]
        self.assertEqual(payload["wx_openid"], "wx-openid-001")
        self.assertFalse(payload["has_password"])
        self.assertFalse(payload["is_password_set"])
        self.assertTrue(payload["need_bind_phone"])
        self.assertFalse(payload["phone_bound"])
        self.assertTrue(User.objects.filter(wx_openid="wx-openid-001").exists())

    @patch("seatbelt.api.views.wechat_code_to_phone_info")
    @patch("seatbelt.api.views.wechat_code_to_session")
    def test_miniapp_bind_phone_with_wechat_code_sets_phone_and_password(
        self,
        mock_wechat_code_to_session,
        mock_wechat_code_to_phone_info,
    ):
        mock_wechat_code_to_session.return_value = {"openid": "wx-openid-002"}
        login_response = self.client.post(
            reverse("seatbelt-miniapp-wx-login"),
            data=json.dumps({"code": "wx-login-code"}),
            content_type="application/json",
        )
        self.assertEqual(login_response.status_code, 200)
        token = login_response.json()["data"]["access_token"]

        mock_wechat_code_to_phone_info.return_value = {"phone": "13900000000", "country_code": "86"}
        bind_response = self.client.post(
            reverse("seatbelt-miniapp-bind-phone"),
            data=json.dumps(
                {
                    "phone_code": "phone-code",
                    "password": "newpass123",
                    "confirm_password": "newpass123",
                }
            ),
            content_type="application/json",
            HTTP_AUTHORIZATION=f"Bearer {token}",
        )

        self.assertEqual(bind_response.status_code, 200)
        payload = bind_response.json()["data"]
        self.assertEqual(payload["phone"], "13900000000")
        self.assertTrue(payload["has_password"])
        self.assertTrue(payload["is_password_set"])
        self.assertTrue(payload["phone_bound"])
        self.assertFalse(payload["need_bind_phone"])

        user = User.objects.get(wx_openid="wx-openid-002")
        self.assertEqual(user.phone, "13900000000")
        self.assertTrue(user.check_password("newpass123"))

    @patch("seatbelt.api.views.wechat_code_to_phone_info")
    @patch("seatbelt.api.views.wechat_code_to_session")
    def test_miniapp_bind_phone_merges_into_existing_phone_account(
        self,
        mock_wechat_code_to_session,
        mock_wechat_code_to_phone_info,
    ):
        existing_user = User.objects.create_user(
            username="u_13911112222",
            password="oldpass123",
            phone="13911112222",
            role=User.Role.USER,
        )

        mock_wechat_code_to_session.return_value = {"openid": "wx-openid-merge"}
        login_response = self.client.post(
            reverse("seatbelt-miniapp-wx-login"),
            data=json.dumps({"code": "wx-login-code"}),
            content_type="application/json",
        )
        self.assertEqual(login_response.status_code, 200)
        token = login_response.json()["data"]["access_token"]
        temp_user_id = login_response.json()["data"]["id"]

        mock_wechat_code_to_phone_info.return_value = {"phone": "13911112222", "country_code": "86"}
        bind_response = self.client.post(
            reverse("seatbelt-miniapp-bind-phone"),
            data=json.dumps(
                {
                    "phone_code": "phone-code",
                    "password": "newpass999",
                    "confirm_password": "newpass999",
                }
            ),
            content_type="application/json",
            HTTP_AUTHORIZATION=f"Bearer {token}",
        )

        self.assertEqual(bind_response.status_code, 200)
        payload = bind_response.json()["data"]
        self.assertEqual(payload["id"], existing_user.id)
        self.assertEqual(payload["phone"], "13911112222")
        self.assertTrue(payload["phone_bound"])
        self.assertTrue(payload["has_password"])
        self.assertFalse(payload["need_bind_phone"])

        existing_user.refresh_from_db()
        self.assertEqual(existing_user.wx_openid, "wx-openid-merge")
        self.assertTrue(existing_user.check_password("oldpass123"))
        self.assertFalse(User.objects.filter(pk=temp_user_id).exists())

    def test_miniapp_me_and_plate_list(self):
        headers = self.miniapp_login_headers()
        me_response = self.client.get(reverse("seatbelt-miniapp-me"), **headers)
        list_response = self.client.get(reverse("seatbelt-miniapp-plate-list"), **headers)

        self.assertEqual(me_response.status_code, 200)
        self.assertEqual(list_response.status_code, 200)
        self.assertEqual(me_response.json()["data"]["user"]["phone"], self.phone)
        self.assertEqual(len(me_response.json()["data"]["bound_plates"]), 1)
        self.assertEqual(list_response.json()["data"][0]["plate_text"], "绮12345")

    def test_miniapp_bind_and_unbind_plate(self):
        headers = self.miniapp_login_headers()
        create_response = self.client.post(
            reverse("seatbelt-miniapp-plate-list"),
            data=json.dumps({"plate_text": "绮88888"}),
            content_type="application/json",
            **headers,
        )
        self.assertEqual(create_response.status_code, 201)
        binding_id = create_response.json()["data"]["id"]

        delete_response = self.client.delete(
            reverse("seatbelt-miniapp-plate-delete", args=[binding_id]),
            **headers,
        )
        self.assertEqual(delete_response.status_code, 200)
        self.assertFalse(delete_response.json()["data"]["is_active"])

    def test_miniapp_violation_list_only_returns_bound_plates(self):
        other_user = User.objects.create_user(
            username="u_13911111111",
            password=self.password,
            phone="13911111111",
            role=User.Role.USER,
        )
        other_task = DetectTask.objects.create(
            task_no="T202604040001BB",
            user=other_user,
            task_type=DetectTask.TaskType.IMAGE,
            source_name="other.jpg",
            source_file=SimpleUploadedFile("other.jpg", b"abc", content_type="image/jpeg"),
            status=DetectTask.Status.COMPLETED,
        )
        other_result = DetectResult.objects.create(task=other_task, result_index=1)
        other_object = DetectObject.objects.create(
            task=other_task,
            result=other_result,
            object_index=1,
            object_type=DetectObject.ObjectType.SEATBELT,
            object_label="not_wearing",
            confidence=0.95,
            bbox_xmin=1,
            bbox_ymin=2,
            bbox_xmax=3,
            bbox_ymax=4,
            is_violation=True,
        )
        ViolationRecord.objects.create(
            violation_no="V202604040001BB",
            task=other_task,
            result=other_result,
            object=other_object,
            user=other_user,
            plate_text="绮99999",
        )

        headers = self.miniapp_login_headers()
        response = self.client.get(reverse("seatbelt-miniapp-violation-list"), **headers)
        self.assertEqual(response.status_code, 200)
        payload = response.json()["data"]
        self.assertEqual(payload["total"], 1)
        self.assertEqual(payload["items"][0]["status"], 0)
        self.assertEqual(payload["items"][0]["plate_text"], "绮12345")
        self.assertEqual(payload["bound_plates"], ["绮12345"])


    def test_miniapp_violation_detail_and_review(self):
        headers = self.miniapp_login_headers()

        detail_response = self.client.get(
            reverse("seatbelt-miniapp-violation-detail", args=[self.violation.id]),
            **headers,
        )
        self.assertEqual(detail_response.status_code, 200)
        detail_payload = detail_response.json()["data"]
        self.assertEqual(detail_payload["id"], self.violation.id)
        self.assertEqual(detail_payload["status"], 0)

        self.violation.status = ViolationRecord.Status.PROCESSED
        self.violation.audit_remark = "old"
        self.violation.handled_remark = "done"
        self.violation.save(update_fields=["status", "audit_remark", "handled_remark"])

        review_response = self.client.post(
            reverse("seatbelt-miniapp-violation-review", args=[self.violation.id]),
            data=json.dumps({}),
            content_type="application/json",
            **headers,
        )
        self.assertEqual(review_response.status_code, 200)
        review_payload = review_response.json()["data"]
        self.assertEqual(review_payload["id"], self.violation.id)
        self.assertEqual(review_payload["status"], 1)

        self.violation.refresh_from_db()
        self.assertEqual(self.violation.status, ViolationRecord.Status.PENDING_REVIEW)
        self.assertEqual(self.violation.audit_remark, "")
        self.assertEqual(self.violation.handled_remark, "")


class PlateDetectorTests(SimpleTestCase):
    def test_belt_detector_maps_export_labels_to_business_labels(self):
        detector = BeltDetector()
        self.assertEqual(detector._map_belt_label("belt_off"), "not_wearing")
        self.assertEqual(detector._map_belt_label("belt_on"), "wearing")

    def test_belt_detector_expands_person_crop_bbox(self):
        expanded = BeltDetector._expand_person_crop_bbox([10, 20, 50, 80], (200, 200))
        self.assertEqual(expanded, [10, 17, 50, 86])

    def test_person_export_bbox_expands_top_and_bottom_only(self):
        service = SeatbeltDetectionService()
        expanded = service._expand_person_export_bbox([10, 20, 50, 80], (200, 200))
        self.assertEqual(expanded, [10, 17, 50, 86])

    def test_belt_preprocess_keeps_ratio_and_center_pads(self):
        spec = OnnxClassificationSpec(
            model_path=Path("dummy.onnx"),
            infer_size=(128, 128),
            image_mean=(0.485, 0.456, 0.406),
            image_std=(0.229, 0.224, 0.225),
            keep_ratio=True,
            center_pad=True,
            normalize_to_unit=True,
        )
        image = np.ones((100, 50, 3), dtype=np.uint8) * 255
        input_tensor, resized_shape = preprocess_image(image, spec)

        self.assertEqual(resized_shape, (128, 64))
        self.assertEqual(input_tensor.shape, (1, 3, 128, 128))

        pad_value = (0.0 - 0.485) / 0.229
        self.assertAlmostEqual(float(input_tensor[0, 0, 0, 0]), pad_value, places=4)
        center_value = (1.0 - 0.485) / 0.229
        self.assertAlmostEqual(float(input_tensor[0, 0, 64, 64]), center_value, places=4)

    def test_decode_plate_output(self):
        detector = PlateDetector()
        output = np.zeros((1, 2, 15), dtype=np.float32)
        output[0, 0, :4] = [320, 320, 160, 80]
        output[0, 0, 4] = 0.9
        output[0, 0, 13:] = [0.8, 0.2]
        output[0, 1, :4] = [100, 100, 40, 20]
        output[0, 1, 4] = 0.1
        output[0, 1, 13:] = [0.9, 0.1]

        detections = detector._decode(
            output,
            original_shape=(320, 640),
            ratio=1.0,
            pad=(0, 0),
        )

        self.assertEqual(len(detections), 1)
        self.assertEqual(detections[0]["label"], "car_num")
        self.assertEqual(detections[0]["plate_type"], "single")
        self.assertAlmostEqual(detections[0]["score"], 0.72, places=2)

