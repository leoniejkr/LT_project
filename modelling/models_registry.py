"""
Registry of available classification models.

Each entry maps a stable model id (used by the frontend settings and sent
over the wire) to a factory that returns the loaded, eval-mode model for
inference.

Extension point: to add another architecture (e.g. a transformer, or an
ensemble that averages several classifiers), implement the classifier in
model.py (it must satisfy the ChestClassifier interface) and register a
factory here. The frontend catalog in frontend/src/lib/models.ts must also
be updated so the model appears in the settings dropdown.
"""

import logging

logger = logging.getLogger(__name__)


def _convnext() -> object:
    from model import get_convnext_model
    return get_convnext_model()


# id -> factory returning an eval-mode torch model.
CLASSIFIER_REGISTRY = {
    "convnext": _convnext,
}

DEFAULT_CLASSIFIER = "convnext"


def get_classifier(model_id: str) -> object:
    """Return the model factory for `model_id`, falling back to the default."""
    if model_id not in CLASSIFIER_REGISTRY:
        logger.warning(
            "Unknown classifier '%s', falling back to '%s'",
            model_id, DEFAULT_CLASSIFIER,
        )
        model_id = DEFAULT_CLASSIFIER
    return CLASSIFIER_REGISTRY[model_id]()