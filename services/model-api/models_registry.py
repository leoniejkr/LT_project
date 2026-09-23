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
import os

logger = logging.getLogger(__name__)


def _convnext() -> object:
    from model import get_convnext_model
    return get_convnext_model()


def _swin() -> object:
    from model import get_swin_model
    return get_swin_model()


def _densenet() -> object:
    from model import get_densenet_model
    return get_densenet_model()


def _convnext224() -> object:
    from model import get_convnext224_model
    return get_convnext224_model()


def _convnext21k() -> object:
    from model import get_convnext21k_model
    return get_convnext21k_model()


def _convnext_ensemble() -> object:
    from model import REPO_ROOT
    from model import ConvNeXtChestModel, ConvNeXt224ChestModel, ConvNeXt21KChestModel
    from ensemble import build_ensemble_from_checkpoints
    # Soft-vote across all three ConvNeXt checkpoints: the original 384 px
    # torchvision model plus the two 224 px retrains (torchvision / 21K timm).
    ckpt_dir = os.path.join(REPO_ROOT, "checkpoints")
    return build_ensemble_from_checkpoints([
        (ConvNeXt224ChestModel, os.path.join(ckpt_dir, "convnext-224px_final_numero1.pth")),
        (ConvNeXt21KChestModel, os.path.join(ckpt_dir, "convnext21k-224px_final.pth")),
        (ConvNeXtChestModel, os.path.join(ckpt_dir, "covnext348.pth")),
    ])


def _ensemble() -> object:
    from ensemble import get_ensemble_model
    return get_ensemble_model()


# Ids that construct an ensemble rather than a single classifier. Memberships
# are excluded from the default cross-architecture sweep in get_ensemble_model()
# to avoid an ensemble-in-ensemble.
ENSEMBLE_IDS = {"ensemble", "convnext_ensemble"}

# id -> factory returning an eval-mode torch model.
CLASSIFIER_REGISTRY = {
    "convnext": _convnext,
    "convnext224": _convnext224,
    "convnext21k": _convnext21k,
    "swin": _swin,
    "densenet": _densenet,
    "ensemble": _ensemble,
    "convnext_ensemble": _convnext_ensemble,
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