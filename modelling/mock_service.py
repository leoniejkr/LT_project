import json
import random

from flask import jsonify, request


DIAGNOSES = [
    "Normal",
    "Pneumonia",
    "Effusion",
    "Infiltration",
    "Nodule",
    "Atelectasis",
    "Cardiomegaly",
    "Consolidation",
    "Edema",
    "Emphysema",
    "Fibrosis",
    "Pleural_Thickening",
    "Pneumothorax",
]

REASONS = {
    "Normal": "No significant abnormalities detected in the chest X-ray. Lung fields appear clear with normal cardiac silhouette.",
    "Pneumonia": "Opacities consistent with pneumonia detected. The model identified abnormal density patterns in the lung parenchyma.",
    "Effusion": "Pleural effusion detected. Fluid accumulation visible in the pleural space, potentially compressing underlying lung tissue.",
    "Infiltration": "Infiltrative changes observed in the lung tissue. May indicate infection, inflammation, or other pathological processes.",
    "Nodule": "Pulmonary nodule identified. Requires further evaluation to determine clinical significance.",
    "Atelectasis": "Atelectasis detected. Partial collapse of lung tissue identified, potentially affecting gas exchange.",
    "Cardiomegaly": "Enlarged cardiac silhouette detected. May indicate cardiac pathology or fluid overload.",
    "Consolidation": "Lung consolidation identified. Alveoli filled with fluid or inflammatory exudate.",
    "Edema": "Pulmonary edema detected. Fluid accumulation in lung tissue consistent with cardiac or renal pathology.",
    "Emphysema": "Emphysematous changes detected. Destruction of alveolar walls with air trapping.",
    "Fibrosis": "Pulmonary fibrosis detected. Scarring of lung tissue with potential restrictive pattern.",
    "Pleural_Thickening": "Pleural thickening identified. May indicate previous inflammation or occupational exposure.",
    "Pneumothorax": "Pneumothorax detected. Air in the pleural space causing partial lung collapse.",
}


def register_mock_routes(app):
    @app.route("/predict", methods=["POST"])
    def predict():
        form_data = request.form.get("formData")
        patient = {}
        if form_data:
            try:
                patient = json.loads(form_data)
            except json.JSONDecodeError:
                pass

        num_images = len(request.files.getlist("image_files")) or 1

        num_diagnoses = random.randint(1, 3)
        selected = random.sample(DIAGNOSES[1:], num_diagnoses)

        predictions = []
        for diag in selected:
            conf = random.uniform(0.85, 0.99)
            predictions.append({
                "class": diag,
                "confidence": round(conf, 4),
                "reason": REASONS.get(diag, f"Analysis detected {diag} with {conf:.0%} confidence."),
            })

        predictions.sort(key=lambda p: p["confidence"], reverse=True)

        image_results = []
        for idx in range(num_images):
            image_preds = random.sample(predictions, min(len(predictions), random.randint(1, 2)))
            image_results.append({
                "index": idx,
                "filename": f"mock_image_{idx}.png",
                "predictions": [
                    {
                        "class": p["class"],
                        "confidence": p["confidence"],
                        "heatmap": "",
                    }
                    for p in image_preds
                ],
            })

        return jsonify({
            "status": "success",
            "model_version": "mock-llm-v1.0",
            "predictions": predictions,
            "image_results": image_results,
            "is_mock": True,
        })
