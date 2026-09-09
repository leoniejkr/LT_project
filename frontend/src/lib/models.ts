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
        id: 'densenet121',
        label: 'DenseNet121 (ChestX)',
        description: 'DenseNet-121 fine-tuned on chest X-rays (default).',
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

export const classifierModel: Writable<string> = writable('densenet121');
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
