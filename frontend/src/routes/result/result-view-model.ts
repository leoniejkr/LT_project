import type {
    CategorizedPrediction,
    ImageResult,
    Prediction,
} from "$lib/types";

const OVERLAPPING_KEYS = ["fibrosis", "cardiomegaly"];
const VISUAL_FINDING_KEYS = [
    "mass",
    "nodule",
    "pleural thickening",
    "atelectasis",
    "pneumothorax",
    "effusion",
    "consolidation",
    "infiltration",
    "edema",
];
const SICKNESS_KEYS = ["covid", "pneumonia", "hernia", "emphysema"];

export interface PredictionCategories {
    visual: CategorizedPrediction[];
    sickness: CategorizedPrediction[];
    overlapping: CategorizedPrediction[];
}

export interface CategoryPanel {
    title: string;
    subtitle: string;
    items: CategorizedPrediction[];
}

function matchesAny(label: string, keys: string[]): boolean {
    return keys.some((key) => label === key || label.includes(key));
}

export function filterPredictions(
    predictions: Prediction[],
    threshold: number,
): Prediction[] {
    return predictions.filter(
        (prediction) => prediction.confidence * 100 >= threshold,
    );
}

export function categorizePredictions(
    predictions: Prediction[],
): PredictionCategories {
    const categories: PredictionCategories = {
        visual: [],
        sickness: [],
        overlapping: [],
    };

    predictions.forEach((prediction, rank) => {
        const label = prediction.class
            .toLowerCase()
            .replace(/[_-]+/g, " ")
            .trim();
        const entry: CategorizedPrediction = { pred: prediction, rank };

        if (matchesAny(label, OVERLAPPING_KEYS)) {
            categories.overlapping.push(entry);
        } else if (matchesAny(label, VISUAL_FINDING_KEYS)) {
            categories.visual.push(entry);
        } else if (matchesAny(label, SICKNESS_KEYS)) {
            categories.sickness.push(entry);
        } else {
            categories.visual.push(entry);
        }
    });

    return categories;
}

export function createCategoryPanels(
    categories: PredictionCategories,
): CategoryPanel[] {
    return [
        {
            title: "Visual Findings",
            subtitle: "Things we can see on the scan",
            items: categories.visual,
        },
        {
            title: "Sicknesses & Clinical Diagnoses",
            subtitle: "Diseases and conditions",
            items: categories.sickness,
        },
        {
            title: "Overlapping Concepts",
            subtitle: "Both a visual feature and a condition",
            items: categories.overlapping,
        },
    ];
}

export function filterImageResults(
    imageResults: ImageResult[],
    threshold: number,
): ImageResult[] {
    return imageResults
        .map((result) => ({
            ...result,
            predictions: result.predictions.filter(
                (prediction) => prediction.confidence * 100 >= threshold,
            ),
        }))
        .filter((result) => result.predictions.length > 0);
}

export function confidenceClass(confidence: number): string {
    if (confidence >= 0.95) return "confidence-critical";
    if (confidence >= 0.9) return "confidence-high";
    if (confidence >= 0.85) return "confidence-medium";
    return "confidence-low";
}

export function confidenceBarClass(confidence: number): string {
    if (confidence >= 0.95) return "confidence-critical-bar";
    if (confidence >= 0.9) return "confidence-high-bar";
    if (confidence >= 0.85) return "confidence-medium-bar";
    return "confidence-low-bar";
}
