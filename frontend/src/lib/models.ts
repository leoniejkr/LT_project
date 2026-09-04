import { writable, derived, type Writable, type Readable } from 'svelte/store';

/**
 * Model selection settings.
 *
 * Two independent choices:
 * - classifierModel: which computer-vision model classifies the chest X-rays
 *   (produces the confidence scores + heatmaps).
 * - llmModel: which LLM generates the natural-language reasons and powers
 *   the assistant chat.
 *
 * These feed into the analysis pipeline (frontend -> backend -> modelling).
 * The catalogs are designed to grow: add an entry here and implement the
 * corresponding behaviour in the modelling service.
 */

export interface ClassifierModelOption {
    id: string;
    label: string;
    description: string;
}

export interface LLMModelOption {
    id: string;
    label: string;
    description: string;
}

/** Classification models supported by the modelling service. */
export const CLASSIFIER_MODELS: ClassifierModelOption[] = [
    {
        id: 'densenet121',
        label: 'DenseNet121 (ChestX)',
        description: 'DenseNet-121 fine-tuned on chest X-rays (default).',
    },
];

/**
 * LLM models that can be selected (static catalog — the source of truth for
 * which models the app supports). Add an entry here to offer a new model.
 */
export const LLM_MODELS: LLMModelOption[] = [
    {
        id: 'phi3:mini',
        label: 'Phi-3 mini',
        description: 'Compact, fast. Great for short reasoning.',
    },
];

export const classifierModel: Writable<string> = writable('densenet121');
export const llmModel: Writable<string> = writable('phi3:mini');

export const selectedClassifier = derived(
    classifierModel,
    ($id) =>
        CLASSIFIER_MODELS.find((m) => m.id === $id) ??
        CLASSIFIER_MODELS[0],
) as Readable<ClassifierModelOption>;

export const selectedLLM = derived(
    llmModel,
    ($id) => LLM_MODELS.find((m) => m.id === $id) ?? LLM_MODELS[0],
) as Readable<LLMModelOption>;

export function classifierLabel(id: string): string {
    return CLASSIFIER_MODELS.find((m) => m.id === id)?.label ?? id;
}

export function llmLabel(id: string): string {
    return LLM_MODELS.find((m) => m.id === id)?.label ?? id;
}
