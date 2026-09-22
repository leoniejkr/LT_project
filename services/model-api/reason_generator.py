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

    patient_info = (
        "The following is the patient's CONFIRMED metadata, submitted by the "
        "user. Treat every entry as fact about this patient:\n"
    )
    patient_info += f"Patient: {age} years old, {gender}."
    if symptoms:
        patient_info += f"\nSymptoms: {', '.join(symptoms)}."
    if history:
        patient_info += (
            f"\nMedical history and risk factors: "
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
        patient_info += "\nRisk context: " + "; ".join(hints) + "."

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

    prompt = f"""You are a medical AI assistant explaining the results of an automated chest X-ray analysis to a clinician.

PATIENT PROFILE (CONFIRMED metadata, treat every entry as fact about this patient):
{patient_info}

The chest X-ray model detected the following conditions, each with a confidence score (higher = more certain the condition is present):
{predictions_text}

Write EXACTLY ONE short sentence per detected condition. For each condition:
  • First say what that finding means on a chest X-ray in its own right (what the lung/mediastinum pattern usually indicates), based only on the condition name.
  • Then relate it to THIS patient: explicitly tie in the patient's symptoms, age, gender and history where relevant (e.g. connect a fever/cough symptom to a detected Pneumonia, Effusion or Consolidation; note advanced age as a modifier for a Nodule or Cardiomegaly). Use the symptoms eagerly — they are available and confirmed.
  • Mention the confidence score only when it changes the clinical message (e.g. "high confidence" vs "low confidence").
  • Never repeat the same sentence for two different conditions — every finding must get its own distinct explanation.
  • Do not invent conditions, symptoms, test results or treatments beyond what is listed.

Patient metadata is CONFIRMED fact: every listed symptom and history entry really applies (e.g. if "Pregnancy" is listed, the patient IS pregnant; never write that a listed risk factor does not apply). But each assessment must CENTER on the detected finding, not only on the patient background.

Respond with nothing but this exact JSON format:
[
  {{"class": "ClassName", "reason": "One sentence."}},
  ...
]
Only include the conditions listed above."""

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


def _first_sentence(text: str) -> str:
    """Return the text up to and including the first sentence-ending period."""
    import re
    m = re.split(r"(?<=[.!?])\s+", text.strip(), maxsplit=1)
    return m[0].strip()


def _parse_reasons(text: str, predictions: list[dict]) -> list[dict]:
    import json

    try:
        start = text.index("[")
        end = text.rindex("]") + 1
        parsed = json.loads(text[start:end])

        reasons_map = {}
        for item in parsed:
            reasons_map[item["class"]] = _first_sentence(item["reason"])

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
