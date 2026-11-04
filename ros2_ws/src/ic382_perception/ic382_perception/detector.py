"""Detector abstraction.

ultralytics is imported lazily inside UltralyticsDetector so the package builds
and unit tests run in CI without torch or a GPU. MockDetector returns canned
detections for offline rehearsal.
"""
from ic382_perception.decision import Detection


class Detector:
    """Base detector interface."""

    names = {}

    def load(self):
        return self.names

    def detect(self, image):
        raise NotImplementedError

    def class_name(self, class_id):
        return self.names.get(int(class_id), str(class_id))


class UltralyticsDetector(Detector):
    """YOLO detection via ultralytics; the model loads on first use.

    ``model_path`` may point at a .pt, .onnx or TensorRT .engine file. Engine
    files are platform-specific and must be built on the target Jetson.
    """

    def __init__(self, model_path, conf=0.25, iou=0.45, imgsz=640, device="",
                 half=False, max_det=50, warmup=True):
        self.model_path = model_path
        self.conf = float(conf)
        self.iou = float(iou)
        self.imgsz = int(imgsz)
        self.device = str(device)
        self.half = bool(half)
        self.max_det = int(max_det)
        self.warmup = bool(warmup)
        self._model = None
        self.names = {}

    def _load(self):
        if self._model is None:
            from ultralytics import YOLO  # lazy import

            self._model = YOLO(self.model_path)
            names = getattr(self._model, "names", {}) or {}
            self.names = {int(key): str(value) for key, value in names.items()}
            if self.warmup:
                self._warmup()
        return self._model

    def load(self):
        self._load()
        return self.names

    def _predict_kwargs(self):
        kwargs = {
            "conf": self.conf,
            "iou": self.iou,
            "imgsz": self.imgsz,
            "max_det": self.max_det,
            "verbose": False,
        }
        if self.device:
            kwargs["device"] = self.device
        if self.half:
            kwargs["half"] = True
        return kwargs

    def _warmup(self):
        try:
            import numpy as np

            frame = np.zeros((self.imgsz, self.imgsz, 3), dtype=np.uint8)
            self._model.predict(source=frame, **self._predict_kwargs())
        except Exception:
            # Warmup is an optimisation; a failure must not prevent real use.
            pass

    def detect(self, image):
        model = self._load()
        detections = []
        for result in model.predict(source=image, **self._predict_kwargs()):
            boxes = getattr(result, "boxes", None)
            if boxes is None:
                continue
            for box in boxes:
                x_center, y_center, width, height = box.xywh[0].tolist()
                class_id = int(box.cls[0])
                detections.append(Detection(
                    bbox=(x_center, y_center, width, height),
                    class_id=class_id,
                    confidence=float(box.conf[0]),
                    class_name=self.class_name(class_id),
                ))
        return detections


class MockDetector(Detector):
    """Returns a fixed list of detections regardless of the input image."""

    def __init__(self, detections=None, names=None):
        self.detections = list(detections or [])
        self.names = {int(key): str(value) for key, value in (names or {}).items()}

    def detect(self, image):
        return list(self.detections)


def get_detector(mode, **kwargs):
    if mode == "mock":
        return MockDetector(kwargs.pop("detections", None), kwargs.pop("names", None))
    return UltralyticsDetector(kwargs.pop("model_path", ""), **kwargs)
