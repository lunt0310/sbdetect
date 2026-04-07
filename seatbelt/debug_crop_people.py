import argparse
from pathlib import Path

import numpy as np
from PIL import Image

from seatbelt.detectors.person_detector import PersonDetector
from seatbelt.detectors.vehicle_detector import VehicleDetector


VEHICLE_SCORE_THRESHOLD = 0.65
PERSON_SCORE_THRESHOLD = 0.4


def parse_args():
    parser = argparse.ArgumentParser(description="Crop people inside detected vehicles from images.")
    parser.add_argument(
        "--input",
        default=r"F:\毕设\safe\datasets\pic",
        help="Input image file or directory.",
    )
    parser.add_argument(
        "--output",
        default=r"D:\Desktop\allimg",
        help="Output directory for cropped person images.",
    )
    return parser.parse_args()


def iter_images(input_path):
    suffixes = {".jpg", ".jpeg", ".png", ".bmp", ".webp"}
    if input_path.is_file():
        return [input_path]
    return sorted([path for path in input_path.iterdir() if path.is_file() and path.suffix.lower() in suffixes])


def load_rgb_image(path):
    return np.array(Image.open(path).convert("RGB"))


def clip_bbox(bbox, image_shape):
    height, width = image_shape
    x1, y1, x2, y2 = [int(round(float(value))) for value in bbox]
    x1 = max(0, min(width, x1))
    y1 = max(0, min(height, y1))
    x2 = max(0, min(width, x2))
    y2 = max(0, min(height, y2))
    return [x1, y1, x2, y2]


def crop_image(image, bbox):
    x1, y1, x2, y2 = bbox
    if x2 <= x1 or y2 <= y1:
        return np.empty((0, 0, 3), dtype=image.dtype)
    return image[y1:y2, x1:x2].copy()


def filter_detections(detections, threshold):
    return [item for item in detections if float(item.get("score", 0.0)) > threshold]


def main():
    args = parse_args()
    input_path = Path(args.input)
    output_path = Path(args.output)
    if not input_path.exists():
        raise SystemExit(f"Input path does not exist: {input_path}")

    output_path.mkdir(parents=True, exist_ok=True)

    vehicle_detector = VehicleDetector()
    person_detector = PersonDetector()

    total_images = 0
    total_crops = 0

    for image_path in iter_images(input_path):
        total_images += 1
        image = load_rgb_image(image_path)

        vehicle_detections = filter_detections(vehicle_detector.predict(image), VEHICLE_SCORE_THRESHOLD)
        car_detections = [item for item in vehicle_detections if item.get("label") == "car"]

        image_crop_count = 0
        for vehicle_index, car_detection in enumerate(car_detections, start=1):
            vehicle_bbox = clip_bbox(car_detection["bbox"], image.shape[:2])
            vehicle_crop = crop_image(image, vehicle_bbox)
            if vehicle_crop.size == 0:
                continue

            person_detections = filter_detections(
                person_detector.predict(
                    vehicle_crop,
                    parent_bbox=vehicle_bbox,
                    vehicle_index=vehicle_index,
                ),
                PERSON_SCORE_THRESHOLD,
            )

            for person_index, person_detection in enumerate(person_detections, start=1):
                person_bbox = clip_bbox(person_detection["bbox"], image.shape[:2])
                person_crop = crop_image(image, person_bbox)
                if person_crop.size == 0:
                    continue

                image_crop_count += 1
                total_crops += 1
                output_name = (
                    f"{image_path.stem}_car{vehicle_index:02d}_person{person_index:02d}.jpg"
                )
                Image.fromarray(person_crop).save(output_path / output_name, format="JPEG", quality=95)

        print(f"{image_path.name}\tvehicles={len(car_detections)}\tcrops={image_crop_count}")

    print(f"TOTAL_IMAGES\t{total_images}")
    print(f"TOTAL_CROPS\t{total_crops}")
    print(f"OUTPUT_DIR\t{output_path}")


if __name__ == "__main__":
    main()
