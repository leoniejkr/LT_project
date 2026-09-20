import base64
import io

import numpy as np
from PIL import Image
from pytorch_grad_cam import GradCAM
from pytorch_grad_cam.utils.model_targets import ClassifierOutputTarget
from pytorch_grad_cam.utils.image import show_cam_on_image

from model import ALL_CLASSES
from models_registry import get_classifier, DEFAULT_CLASSIFIER


def _target_layers(model):
    """Pick the layer to hook for Grad-CAM.

    ConvNeXt exposes ``backbone.features`` (a Sequential, channels-first).
    Transformers (Swin) define ``model.gradcam_target_layer`` to provide a 4D
    channels-first feature map instead (see model.py), because their raw
    encoder output is channels-last and would silently produce a wrong CAM.
    """
    return [getattr(model, "gradcam_target_layer", model.backbone.features)]


def generate_heatmaps(input_tensor, rgb_img_np, probabilities, class_indices, model=None):
    model = model or get_classifier(DEFAULT_CLASSIFIER)
    target_layers = _target_layers(model)

    heatmaps = {}

    for idx in class_indices:
        class_name = ALL_CLASSES[idx]
        conf = float(probabilities[idx])
        targets = [ClassifierOutputTarget(idx)]

        with GradCAM(model=model, target_layers=target_layers) as cam:
            grayscale_cam = cam(input_tensor=input_tensor, targets=targets)[0, :]
            visualization = show_cam_on_image(rgb_img_np, grayscale_cam, use_rgb=True)

        img = Image.fromarray(visualization)
        buf = io.BytesIO()
        img.save(buf, format="PNG", optimize=True)
        b64 = base64.b64encode(buf.getvalue()).decode("utf-8")

        heatmaps[class_name] = {
            "confidence": round(conf, 4),
            "heatmap": b64,
        }

    return heatmaps


def generate_heatmap_overlay(input_tensor, rgb_img_np, class_index, model=None):
    model = model or get_classifier(DEFAULT_CLASSIFIER)
    target_layers = _target_layers(model)

    targets = [ClassifierOutputTarget(class_index)]

    with GradCAM(model=model, target_layers=target_layers) as cam:
        grayscale_cam = cam(input_tensor=input_tensor, targets=targets)[0, :]
        visualization = show_cam_on_image(rgb_img_np, grayscale_cam, use_rgb=True)

    img = Image.fromarray(visualization)
    buf = io.BytesIO()
    img.save(buf, format="PNG", optimize=True)
    return base64.b64encode(buf.getvalue()).decode("utf-8")
