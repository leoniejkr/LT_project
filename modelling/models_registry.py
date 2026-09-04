"""
Registry of available classification models.

Each entry maps a stable model id (used by the frontend settings and sent
over the wire) to a factory that returns the loaded, eval-mode model for
inference. Today only DenseNet121 is implemented; adding another model means
implementing a factory here and registering it in CLASSIFIER_REGISTRY.
"""

import logging

logger = logging.getLogger(__name__)


def _densenet121() -> object:
    from model import get_model
    return get_model()


# id -> factory returning an eval-mode torch model.
CLASSIFIER_REGISTRY = {
    "densenet121": _densenet121,
}

DEFAULT_CLASSIFIER = "densenet121"


def get_classifier(model_id: str) -> object:
    """Return the model factory for `model_id`, falling back to the default."""
    if model_id not in CLASSIFIER_REGISTRY:
        logger.warning(
            "Unknown classifier '%s', falling back to '%s'",
            model_id, DEFAULT_CLASSIFIER,
        )
        model_id = DEFAULT_CLASSIFIER
    return CLASSIFIER_REGISTRY[model_id]()
