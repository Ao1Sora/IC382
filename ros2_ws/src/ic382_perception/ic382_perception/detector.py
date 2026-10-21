"""Detector abstraction.

ultralytics is imported lazily inside UltralyticsDetector so the package builds
and unit tests run in CI without torch or a GPU. MockDetector returns canned
detections for offline rehearsal.
"""
from ic382_perception.decision import Detection


class Detector:
    """Base detector interface."""

    def detect(self, image):
        raise NotImplementedError


class UltralyticsDetector(Detector):
    """YOLO detection via ultralytics; the model loads on first use."""

    def __init__(self, model_path):
        self.model_path = model_path
        self._model = None

    def _load(self):
        if self._model is None:
            from ultralytics import YOLO  # lazy import
            self._model = YOLO(self.model_path)
        return self._model

    def detect(self, image):
        model = self._load()
        detections = []
        for result in model(image):
            boxes = getattr(result, "boxes", None)
            if boxes is None:
                continue
            for box in boxes:
                x_center, y_center, width, height = box.xywh[0].tolist()
                detections.append(Detection(
                    bbox=(x_center, y_center, width, height),
                    class_id=int(box.cls[0]),
                    confidence=float(box.conf[0]),
                ))
        return detections


class MockDetector(Detector):
    """Returns a fixed list of detections regardless of the input image."""

    def __init__(self, detections=None):
        self.detections = list(detections or [])

    def detect(self, image):
        return list(self.detections)


def get_detector(mode, model_path=None, detections=None):
    if mode == "mock":
        return MockDetector(detections)
    return UltralyticsDetector(model_path)
