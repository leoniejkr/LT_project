from flask import jsonify, send_file
import random
import io
from PIL import Image, ImageDraw

# Liste von fiktiven Diagnosen für das Mockup
DIAGNOSES = [
    "Normal",
    "Pneumonia detected",
    "Possible pleural effusion",
    "Infiltrate observed",
    "Nodule found in lower lobe"
]

def generate_placeholder_image():
    # Erstellt ein graues Bild mit zufälligem Rauschen als Mock-Röntgenbild
    img = Image.new('RGB', (512, 512), color=(random.randint(50, 100),) * 3)
    draw = ImageDraw.Draw(img)
    
    # Zeichne ein paar zufällige "Schatten"
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
        confidence = random.uniform(0.65, 0.99)
        diagnosis = random.choice(DIAGNOSES)
        return jsonify({
            "status": "success",
            "prediction": diagnosis,
            "confidence": round(confidence, 4),
            "model_version": "mock-llm-v1.0",
            "is_mock": True
        })

    @app.route('/mock-image')
    def get_image():
        img_io = generate_placeholder_image()
        return send_file(img_io, mimetype='image/png')
