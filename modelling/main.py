import json
import logging
import os
import time

from flask import Flask, jsonify, request

from model import ALL_CLASSES
from inference import run_inference
from gradcam import generate_heatmaps
from reason_generator import generate_reasons
from models_registry import get_classifier, DEFAULT_CLASSIFIER

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

app = Flask(__name__)

USE_MOCK = os.getenv("USE_MOCK", "false").lower() == "true"

if USE_MOCK:
    from mock_service import register_mock_routes
    register_mock_routes(app)
    logger.info("Running in MOCK mode")
else:
    @app.route("/predict", methods=["POST"])
    def predict():
        start = time.time()

        form_data = request.form.get("formData")
        if not form_data:
            return jsonify({"status": "error", "message": "Missing formData"}), 400

        try:
            patient = json.loads(form_data)
        except json.JSONDecodeError:
            return jsonify({"status": "error", "message": "Invalid JSON in formData"}), 400

        image_files = request.files.getlist("image_files")
        if not image_files:
            return jsonify({"status": "error", "message": "No image files uploaded"}), 400

        # Model selections forwarded from the frontend settings.
        classifier_model = request.form.get("classifier_model", "").strip() or DEFAULT_CLASSIFIER
        llm_model = request.form.get("llm_model", "").strip() or None

        # Load / validate the selected classifier. This instance is what
        # run_inference / generate_heatmaps actually use.
        classifier = get_classifier(classifier_model)

        all_class_scores = {cls: [] for cls in ALL_CLASSES}
        image_results = []

        for idx, file in enumerate(image_files):
            image_bytes = file.read()
            filename = file.filename or f"image_{idx}.png"

            logger.info("Processing image %d/%d: %s", idx + 1, len(image_files), filename)

            result = run_inference(image_bytes, model=classifier)

            top_class_indices = []
            for pred in result["predictions"]:
                class_idx = ALL_CLASSES.index(pred["class"])
                top_class_indices.append(class_idx)
                all_class_scores[pred["class"]].append(pred["confidence"])

            heatmaps = {}
            if top_class_indices:
                heatmaps = generate_heatmaps(
                    result["input_tensor"],
                    result["rgb_img_np"],
                    result["probabilities"],
                    top_class_indices,
                    model=classifier,
                )

            image_pred_with_reasons = []
            for pred in result["predictions"]:
                hm_data = heatmaps.get(pred["class"], {})
                image_pred_with_reasons.append({
                    "class": pred["class"],
                    "confidence": pred["confidence"],
                    "heatmap": hm_data.get("heatmap", ""),
                })

            image_results.append({
                "index": idx,
                "filename": filename,
                "predictions": image_pred_with_reasons,
            })

        aggregated = []
        for cls, confs in all_class_scores.items():
            if confs:
                avg_conf = sum(confs) / len(confs)
                aggregated.append({
                    "class": cls,
                    "confidence": round(avg_conf, 4),
                })

        aggregated.sort(key=lambda p: p["confidence"], reverse=True)

        aggregated_with_reasons = generate_reasons(aggregated, patient, model=llm_model)

        logger.info(
            "Prediction complete: %d images, %d diagnoses (%.2fs)",
            len(image_files), len(aggregated_with_reasons), time.time() - start,
        )

        return jsonify({
            "status": "success",
            "predictions": aggregated_with_reasons,
            "image_results": image_results,
        })


@app.route("/health")
def health():
    return jsonify({
        "status": "healthy",
        "mode": "mock" if USE_MOCK else "production",
    })


if __name__ == "__main__":
    port = int(os.getenv("PORT", 5000))
    app.run(host="0.0.0.0", port=port)
