from flask import jsonify, send_file, request
import random
import io
import logging
from PIL import Image, ImageDraw

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

DIAGNOSES = [
    "Normal",
    "Pneumonia detected",
    "Possible pleural effusion",
    "Infiltrate observed",
    "Nodule found in lower lobe"
]

REASONS = {
    "Normal": "No significant abnormalities detected. Lung fields are clear with no opacities, consolidations, or nodules.",
    "Pneumonia detected": "Bilateral opacities observed in the lower lobes with air bronchogram signs, consistent with infectious pneumonia.",
    "Possible pleural effusion": "Blunting of the costophrenic angles with increased opacity in the lower lung zones suggestive of pleural effusion.",
    "Infiltrate observed": "Patchy opacities in the right middle lobe with interstitial markings, suggesting early infiltrative changes.",
    "Nodule found in lower lobe": "A solitary pulmonary nodule approximately 1.2cm in diameter is present in the left lower lobe with irregular margins."
}

def generate_placeholder_image():
    img = Image.new('RGB', (512, 512), color=(random.randint(50, 100),) * 3)
    draw = ImageDraw.Draw(img)
    for _ in range(5):
        x1, y1 = random.randint(0, 400), random.randint(0, 400)
        x2, y2 = x1 + random.randint(50, 100), y1 + random.randint(50, 100)
        draw.ellipse([x1, y1, x2, y2], fill=(random.randint(100, 150),) * 3)
    img_io = io.BytesIO()
    img.save(img_io, 'PNG')
    img_io.seek(0)
    return img_io

def register_mock_routes(app):
    @app.route('/predict', methods=['POST'])
    def predict():
        data = request.get_json(silent=True) or {}
        logger.info(f"Received prediction request with data: {data}")

        confidence = random.uniform(0.65, 0.99)
        diagnosis = random.choice(DIAGNOSES)
        reason = REASONS.get(diagnosis, "Analysis completed based on available imaging data.")

        return jsonify({
            "status": "success",
            "prediction": diagnosis,
            "confidence": round(confidence, 4),
            "confidence_reason": reason,
            "model_version": "mock-llm-v1.0",
            "is_mock": True
        })

    @app.route('/mock-image')
    def get_image():
        img_io = generate_placeholder_image()
        return send_file(img_io, mimetype='image/png')
