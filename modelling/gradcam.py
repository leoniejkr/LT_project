import base64
import io

import numpy as np
from PIL import Image
from pytorch_grad_cam import GradCAM
from pytorch_grad_cam.utils.model_targets import ClassifierOutputTarget
from pytorch_grad_cam.utils.image import show_cam_on_image

from model import get_model, ALL_CLASSES


def generate_heatmaps(input_tensor, rgb_img_np, probabilities, class_indices):
    model = get_model()
    target_layers = [model.backbone.features]

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


def generate_heatmap_overlay(input_tensor, rgb_img_np, class_index):
    model = get_model()
    target_layers = [model.backbone.features]

    targets = [ClassifierOutputTarget(class_index)]

    with GradCAM(model=model, target_layers=target_layers) as cam:
        grayscale_cam = cam(input_tensor=input_tensor, targets=targets)[0, :]
        visualization = show_cam_on_image(rgb_img_np, grayscale_cam, use_rgb=True)

    img = Image.fromarray(visualization)
    buf = io.BytesIO()
    img.save(buf, format="PNG", optimize=True)
    return base64.b64encode(buf.getvalue()).decode("utf-8")
