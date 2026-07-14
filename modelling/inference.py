import io
import torch
import numpy as np
from PIL import Image
from torchvision import transforms

from model import get_model, ALL_CLASSES

CONFIDENCE_THRESHOLD = 0.85

preprocess = transforms.Compose([
    transforms.Resize((224, 224)),
    transforms.ToTensor(),
])

normalize = transforms.Normalize(
    mean=[0.485, 0.456, 0.406],
    std=[0.229, 0.224, 0.225],
)


def run_inference(image_bytes: bytes) -> dict:
    model = get_model()
    device = next(model.parameters()).device

    pil_img = Image.open(io.BytesIO(image_bytes)).convert("RGB")
    rgb_img_np = np.float32(pil_img.resize((224, 224))) / 255.0
    input_tensor = normalize(preprocess(pil_img)).unsqueeze(0).to(device)

    with torch.no_grad():
        raw_outputs = model(input_tensor)
        probabilities = torch.sigmoid(raw_outputs).squeeze(0).cpu().numpy()

    predictions = []
    for idx, class_name in enumerate(ALL_CLASSES):
        conf = float(probabilities[idx])
        if conf >= CONFIDENCE_THRESHOLD:
            predictions.append({
                "class": class_name,
                "confidence": round(conf, 4),
            })

    predictions.sort(key=lambda p: p["confidence"], reverse=True)

    return {
        "predictions": predictions,
        "input_tensor": input_tensor,
        "rgb_img_np": rgb_img_np,
        "probabilities": probabilities,
        "pil_img": pil_img,
    }
