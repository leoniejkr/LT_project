import { writable, derived, type Writable, type Readable } from 'svelte/store';


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
        id: 'convnext',
        label: 'ConvNeXt-Base (hybrid)',
        description: 'ConvNeXt-Base trained on NIH + MIDRC, 384px black-padded (default).',
    },
    {
        id: 'swin',
        label: 'Swin-B Transformer (hybrid)',
        description: 'Swin-B trained on NIH + MIDRC, 224px black-padded.',
    },
    {
        id: 'densenet',
        label: 'DenseNet-121 / CheXNet (hybrid)',
        description: 'DenseNet-121 trained on NIH + MIDRC, 224px black-padded.',
    },
    {
        id: 'ensemble',
        label: 'Ensemble (ConvNeXt + Swin + DenseNet)',
        description: 'Averaged predictions of ConvNeXt-Base (384px), Swin-B (224px) and DenseNet-121 (224px).',
    },
];

export const LLM_MODELS: LLMModelOption[] = [
    {
        id: 'trustai-llm:latest',
        label: 'TrustAI LLM (fine-tuned)',
        description: 'Fine-tuned clinical model served by Ollama.',
    },
    {
        id: 'phi3:mini',
        label: 'Phi-3 mini',
        description: 'Compact, fast. Great for short reasoning.',
    },
];

export const classifierModel: Writable<string> = writable('convnext');
export const llmModel: Writable<string> = writable('trustai-llm:latest');

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
