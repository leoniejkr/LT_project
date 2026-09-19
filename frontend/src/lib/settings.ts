import { derived, writable } from 'svelte/store';
import type { Readable, Writable } from 'svelte/store';

/**
 * Unified "Decision Mode" setting. It decides which answers from the
 * classifier we accept by controlling the confidence threshold.
 *
 * - high-sensitivity:  accept more (lower threshold) -> fewer false negatives
 * - balanced:           default middle ground
 * - high-specificity:  stricter (higher threshold) -> fewer false positives
 * - custom:            free manual control of the threshold
 */
export type DecisionMode =
    | 'high-sensitivity'
    | 'balanced'
    | 'high-specificity'
    | 'custom';

export const DECISION_MODES: {
    value: DecisionMode;
    label: string;
    threshold: number; // 0-1
    description: string;
}[] = [
    {
        value: 'high-sensitivity',
        label: 'High Sensitivity',
        threshold: 0.2,
        description: 'τ = 0.20 · catches more findings.',
    },
    {
        value: 'balanced',
        label: 'Balanced',
        threshold: 0.5,
        description: 'τ = 0.50 · default.',
    },
    {
        value: 'high-specificity',
        label: 'High Specificity',
        threshold: 0.8,
        description: 'τ = 0.80 · fewer false positives.',
    },
    {
        value: 'custom',
        label: 'Custom / Free Toggle',
        threshold: 0.5,
        description: 'Manual slider control.',
    },
];

export const decisionMode: Writable<DecisionMode> =
    writable<DecisionMode>('balanced');

/** 0-100 percentage used only when mode is `custom`. */
export const customThreshold: Writable<number> = writable(50);

/**
 * Activates manual threshold control and stores a valid percentage.
 * Use this for controls that should turn a preset into a custom value.
 */
export function setCustomThreshold(value: number): void {
    const normalizedValue = Math.min(100, Math.max(0, Math.round(value)));
    customThreshold.set(normalizedValue);
    decisionMode.set('custom');
}

export const isCustom = derived(
    decisionMode,
    ($mode) => $mode === 'custom',
);

/** The currently effective threshold in percent (0-100). */
export const effectiveThreshold: Readable<number> = derived(
    [decisionMode, customThreshold],
    ([$mode, $custom]) => {
        if ($mode === 'custom') return $custom;
        const preset = DECISION_MODES.find((m) => m.value === $mode);
        return Math.round((preset?.threshold ?? 0.5) * 100);
    },
);
