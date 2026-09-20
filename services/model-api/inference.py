import io
import torch
import numpy as np
from PIL import Image

from model import ALL_CLASSES
from models_registry import get_classifier, DEFAULT_CLASSIFIER
from ensemble import EnsembleChestModel


def _preprocess_image(pil_img, model):
    """Apply the model's own preprocessing.

    ConvNeXt: ResizeLongest(384) + SquarePad(black) + dataset normalization, so
    any input geometry (square / portrait / landscape, any resolution) matches
    exactly what the model was trained on. The equivalent geometry-only pipeline
    (no normalization) is generated separately for the Grad-CAM overlay, which
    needs a plain 0..1 RGB image in the same spatial size as the input tensor.
    """
    input_tensor = model.preprocess(apply_normalize=True)(pil_img).unsqueeze(0)
    rgb_img_np = model.preprocess(apply_normalize=False)(pil_img)
    rgb_img_np = rgb_img_np.permute(1, 2, 0).numpy()
    return input_tensor, rgb_img_np


def run_inference(image_bytes: bytes, model=None) -> dict:
    model = model or get_classifier(DEFAULT_CLASSIFIER)
    device = next(model.parameters()).device

    pil_img = Image.open(io.BytesIO(image_bytes)).convert("RGB")

    if isinstance(model, EnsembleChestModel):
        # Each member gets its own tensor (its INPUT_SIZE + normalization);
        # forward() averages the member probabilities.
        inputs = model.preprocess(apply_normalize=True)(pil_img)
        with torch.no_grad():
            probs = model(inputs).squeeze(0).cpu().numpy()
        input_tensor = inputs
        rgb_img_np = None
    else:
        input_tensor, rgb_img_np = _preprocess_image(pil_img, model)
        input_tensor = input_tensor.to(device)
        with torch.no_grad():
            probabilities = torch.sigmoid(model(input_tensor)).squeeze(0).cpu().numpy()
        probs = probabilities

    predictions = []
    for idx, class_name in enumerate(ALL_CLASSES):
        predictions.append({
            "class": class_name,
            "confidence": round(float(probs[idx]), 4),
        })

    predictions.sort(key=lambda p: p["confidence"], reverse=True)

    return {
        "predictions": predictions,
        "input_tensor": input_tensor,
        "rgb_img_np": rgb_img_np,
        "probabilities": probs,
        "pil_img": pil_img,
    }