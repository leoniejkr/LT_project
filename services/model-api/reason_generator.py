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

    # The fine-tuned LLM can only reliably reason about a handful of findings at
    # once — with 15 conditions it drifts into prose and returns nothing
    # parseable (→ everything falls back to the template). Chunk the request so
    # each prompt stays small, then merge per-condition in original order.
    CHUNK_SIZE = 6
    covered = {}
    for i in range(0, len(predictions), CHUNK_SIZE):
        chunk = predictions[i:i + CHUNK_SIZE]
        covered.update(_reason_chunk(chunk, patient_info, llm_model, covered))

    result = []
    for p in predictions:
        result.append({
            "class": p["class"],
            "confidence": p["confidence"],
            "reason": covered.get(p["class"]) or _fallback_reason(p),
        })
    return result


def _reason_chunk(predictions: list[dict], patient_info: str, llm_model: str,
                  covered: dict | None = None) -> dict:
    """Fetch reasons for one chunk. Small models often omit a condition from
    their JSON response or reuse the same sentence for two findings, so we
    re-ask targeted follow-ups for whatever is still missing OR duplicated
    (max 3 rounds). Returns {class: reason}."""
    covered = dict(covered or {})
    pending = list(predictions)
    previous_round = None

    for _ in range(3):
        if not pending:
            break
        round_ids = sorted(id(p) for p in pending)
        if round_ids == previous_round:
            break
        previous_round = round_ids

        prompt = _build_prompt(patient_info, pending, covered)
        text = _generate(prompt, llm_model)
        if text is None:
            break

        entries = _extract_entries(text)
        for p in pending:
            reason = _match_entry(entries, p["class"])
            if reason:
                covered[p["class"]] = reason

        pending = _uncovered_or_duplicate(predictions, covered)

    return covered


def _uncovered_or_duplicate(predictions: list[dict], covered: dict) -> list[dict]:
    """Return the predictions that still need a reason: not yet covered, or
    whose covered sentence equals another finding's sentence."""
    result = []
    for p in predictions:
        cls = p["class"]
        reason = covered.get(cls)
        if reason is None:
            result.append(p)
            continue
        if any(
            other["class"] != cls and covered.get(other["class"]) == reason
            for other in predictions
        ):
            result.append(p)
    return result


def _build_prompt(patient_info: str, predictions: list[dict], covered: dict | None = None) -> str:
    predictions_text = "\n".join(
        f"- {p['class']} (confidence: {p['confidence']:.0%})"
        for p in predictions
    )

    used_sentences = ""
    if covered:
        used_sentences = (
            "\nAlready-provided reasons that MUST NOT be reused or rephrased "
            "for the conditions below (write something new for each):\n"
            + "\n".join(f"- {u}" for u in sorted(set(r for r in covered.values() if r)))
        )

    return f"""You are a medical AI assistant explaining the results of an automated chest X-ray analysis to a clinician.

PATIENT PROFILE (CONFIRMED metadata, treat every entry as fact about this patient):
{patient_info}

The chest X-ray model detected the following conditions, each with a confidence score (higher = more certain the condition is present):
{predictions_text}

Write EXACTLY ONE short sentence per detected condition. For each condition:
  • First say what that finding means on a chest X-ray in its own right (what the lung/mediastinum pattern usually indicates), based only on the condition name.
  • Then relate it to THIS patient: explicitly tie in the patient's symptoms, age, gender and history where relevant (e.g. connect a fever/cough symptom to a detected Pneumonia, Effusion or Consolidation; note advanced age as a modifier for a Nodule or Cardiomegaly). Use the symptoms eagerly — they are available and confirmed.
  • Mention the confidence score only when it changes the clinical message (e.g. "high confidence" vs "low confidence").
  • Never repeat or rephrase a sentence you already provided or used for another condition — every finding must get its own distinct explanation.
  • Do not invent conditions, symptoms, test results or treatments beyond what is listed.
{used_sentences}

Patient metadata is CONFIRMED fact: every listed symptom and history entry really applies (e.g. if "Pregnancy" is listed, the patient IS pregnant; never write that a listed risk factor does not apply). But each assessment must CENTER on the detected finding, not only on the patient background.

Respond with nothing but this exact JSON format:
[
  {{"class": "ClassName", "reason": "One sentence."}},
  ...
]
Only include the conditions listed above."""


def _generate(prompt: str, llm_model: str) -> str | None:
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
        return response.json().get("response", "")
    except Exception as e:
        logger.warning("Ollama call failed: %s", e)
        return None


def _first_sentence(text: str) -> str:
    """Return the text up to and including the first sentence-ending period."""
    import re
    m = re.split(r"(?<=[.!?])\s+", text.strip(), maxsplit=1)
    return m[0].strip()


def _norm_key(cls: str) -> str:
    """Normalize a class name so 'Covid', 'COVID' and 'Covid-19' all match."""
    import re
    return re.sub(r"[^a-z0-9]+", " ", cls.lower()).strip()


def _extract_entries(text: str) -> list:
    """Extract (normalized class, reason) pairs from the model's JSON array."""
    import json

    try:
        start = text.index("[")
        end = text.rindex("]") + 1
        parsed = json.loads(text[start:end])
        return [
            (_norm_key(item["class"]), _first_sentence(item["reason"]))
            for item in parsed
            if item.get("class") and item.get("reason")
        ]
    except (ValueError, json.JSONDecodeError):
        return []


def _match_entry(entries: list, cls: str) -> str | None:
    key = _norm_key(cls)
    for entry_key, reason in entries:
        if key == entry_key or key in entry_key or entry_key in key:
            return reason
    return None


def _fallback_reason(p: dict) -> str:
    conf = p["confidence"]
    if conf > 0.95:
        strength = "Strong evidence"
    elif conf > 0.90:
        strength = "Clear evidence"
    else:
        strength = "Moderate evidence"
    return f"{strength} of {p['class']} detected with {conf:.0%} confidence in the chest X-ray analysis."
