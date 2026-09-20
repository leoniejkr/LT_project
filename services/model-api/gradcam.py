import base64
import io

import numpy as np
import torch
from PIL import Image
from pytorch_grad_cam import GradCAM
from pytorch_grad_cam.utils.model_targets import ClassifierOutputTarget
from pytorch_grad_cam.utils.image import show_cam_on_image

from model import ALL_CLASSES
from models_registry import get_classifier, DEFAULT_CLASSIFIER
from ensemble import EnsembleChestModel


def _target_layers(model):
    """Pick the layer to hook for Grad-CAM.

    ConvNeXt exposes ``backbone.features`` (a Sequential, channels-first).
    Transformers (Swin) define ``model.gradcam_target_layer`` to provide a 4D
    channels-first feature map instead (see model.py), because their raw
    encoder output is channels-last and would silently produce a wrong CAM.
    """
    return [getattr(model, "gradcam_target_layer", model.backbone.features)]


def _resolve_member(model, inputs, class_index):
    """For an ensemble, pick the member that contributed most to `class_index`.

    Its own tensor + rgb map (already in the EnsembleInputs) are used so the
    heatmap reflects the image geometry that actually drove the vote.
    """
    if not isinstance(model, EnsembleChestModel):
        return model, inputs, None
    if inputs.member_confs is None:
        raise RuntimeError("ensemble inputs carry no member confidences; run forward first")
    confs = inputs.member_confs[:, 0, class_index]  # (num_members,)
    member = model.models[int(torch.argmax(confs).item())]
    return member, inputs.tensor_for(member), inputs.rgb_for(member)


def generate_heatmaps(input_tensor, rgb_img_np, probabilities, class_indices, model=None):
    model = model or get_classifier(DEFAULT_CLASSIFIER)

    heatmaps = {}

    for idx in class_indices:
        class_name = ALL_CLASSES[idx]
        conf = float(probabilities[idx])
        member, member_tensor, member_rgb = _resolve_member(model, input_tensor, idx)
        if member_rgb is None:
            member_rgb = rgb_img_np
        target_layers = _target_layers(member)
        targets = [ClassifierOutputTarget(idx)]

        with GradCAM(model=member, target_layers=target_layers) as cam:
            grayscale_cam = cam(input_tensor=member_tensor, targets=targets)[0, :]
            visualization = show_cam_on_image(member_rgb, grayscale_cam, use_rgb=True)

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
    member, member_tensor, member_rgb = _resolve_member(model, input_tensor, class_index)
    if member_rgb is None:
        member_rgb = rgb_img_np
    target_layers = _target_layers(member)

    targets = [ClassifierOutputTarget(class_index)]

    with GradCAM(model=member, target_layers=target_layers) as cam:
        grayscale_cam = cam(input_tensor=member_tensor, targets=targets)[0, :]
        visualization = show_cam_on_image(member_rgb, grayscale_cam, use_rgb=True)

    img = Image.fromarray(visualization)
    buf = io.BytesIO()
    img.save(buf, format="PNG", optimize=True)
    return base64.b64encode(buf.getvalue()).decode("utf-8")
