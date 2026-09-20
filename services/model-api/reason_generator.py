import os
import logging
import requests

OLLAMA_URL = os.getenv("OLLAMA_URL", "http://localhost:11434")
OLLAMA_MODEL = os.getenv("OLLAMA_MODEL", "phi3:mini")

logger = logging.getLogger(__name__)


def _build_patient_context(patient: dict) -> str:
    if not patient:
        return ""
    age = patient.get("age", "unknown")
    gender = patient.get("gender", "unknown")
    symptoms = patient.get("symptoms", [])
    history = patient.get("history", [])

    patient_info = f"Patient: {age} years old, {gender}."
    if symptoms:
        patient_info += f" Symptoms: {', '.join(symptoms)}."
    if history:
        patient_info += (
            f" Known conditions, relevant history and risk factors: "
            f"{', '.join(history)}."
        )

    # Explicit risk-context cues derived from the metadata, so the LLM reliably
    # recognizes special groups (age brackets, pregnancy, smoking) even when it
    # is a small local model.
    hints = []
    try:
        age_val = int(age)
        if age_val < 2:
            hints.append("the patient is an infant (under 2 years)")
        elif age_val < 18:
            hints.append("the patient is a child or adolescent")
        elif age_val >= 65:
            hints.append("the patient is an older adult (65+)")
    except (TypeError, ValueError):
        pass

    history_lower = " ".join(history).lower()
    if "pregnan" in history_lower:
        hints.append("the patient is pregnant")
    if "smok" in history_lower:
        hints.append("the patient has a smoking/exposure history")

    if hints:
        patient_info += (
            " Risk context: " + "; ".join(hints) + "."
        )

    return patient_info


def generate_reasons(predictions: list[dict], patient: dict, model: str | None = None) -> list[dict]:
    if not predictions:
        return []

    llm_model = model or OLLAMA_MODEL

    patient_info = _build_patient_context(patient)

    predictions_text = "\n".join(
        f"- {p['class']} (confidence: {p['confidence']:.0%})"
        for p in predictions
    )

    prompt = f"""You are a medical AI assistant analyzing chest X-ray findings.

{patient_info}

The AI model detected the following conditions:
{predictions_text}

For EACH condition listed above, provide a brief 1-2 sentence clinical assessment explaining what the finding means and why it is significant for THIS patient.

IMPORTANT: Pay close attention to the patient's medical history and risk factors above and factor them into every assessment. If the patient's metadata matches a known high-risk or special group (for example pregnancy, infancy or early childhood, advanced age, smoking, or immunosuppression), explicitly say how that changes the picture for this patient and what to watch for. Do not write generic statements that ignore the patient context above.

Respond in this exact JSON format:
[
  {{"class": "ClassName", "reason": "Your assessment here."}},
  ...
]
Only include the conditions listed above. Do not add extra conditions."""

    try:
        response = requests.post(
            f"{OLLAMA_URL}/api/generate",
            json={
                "model": llm_model,
                "prompt": prompt,
                "stream": False,
                "options": {
                    "temperature": 0.3,
                    "num_predict": 512,
                },
            },
            timeout=60,
        )
        response.raise_for_status()

        result_text = response.json().get("response", "")
        return _parse_reasons(result_text, predictions)

    except Exception as e:
        logger.warning("Ollama call failed, using fallback reasons: %s", e)
        return _fallback_reasons(predictions)


def _parse_reasons(text: str, predictions: list[dict]) -> list[dict]:
    import json

    try:
        start = text.index("[")
        end = text.rindex("]") + 1
        parsed = json.loads(text[start:end])

        reasons_map = {}
        for item in parsed:
            reasons_map[item["class"]] = item["reason"]

        result = []
        for p in predictions:
            result.append({
                "class": p["class"],
                "confidence": p["confidence"],
                "reason": reasons_map.get(
                    p["class"],
                    f"Condition '{p['class']}' detected with {p['confidence']:.0%} confidence.",
                ),
            })
        return result

    except (ValueError, json.JSONDecodeError):
        return _fallback_reasons(predictions)


def _fallback_reasons(predictions: list[dict]) -> list[dict]:
    result = []
    for p in predictions:
        conf = p["confidence"]
        if conf > 0.95:
            strength = "Strong evidence"
        elif conf > 0.90:
            strength = "Clear evidence"
        else:
            strength = "Moderate evidence"

        result.append({
            "class": p["class"],
            "confidence": p["confidence"],
            "reason": f"{strength} of {p['class']} detected with {conf:.0%} confidence in the chest X-ray analysis.",
        })
    return result
