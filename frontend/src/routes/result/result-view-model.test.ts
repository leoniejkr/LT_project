import { describe, expect, test } from "vitest";
import type { ImageResult, Prediction } from "$lib/types";
import {
    categorizePredictions,
    filterImageResults,
    filterPredictions,
} from "./result-view-model";

const predictions: Prediction[] = [
    { class: "Fibrosis", confidence: 0.96 },
    { class: "Pneumonia", confidence: 0.9 },
    { class: "Unknown finding", confidence: 0.7 },
];

describe("result view model", () => {
    test("filters predictions using percentage thresholds", () => {
        expect(filterPredictions(predictions, 90)).toEqual(predictions.slice(0, 2));
    });

    test("categorizes overlapping concepts before other findings", () => {
        const categories = categorizePredictions(predictions);

        expect(categories.overlapping.map((entry) => entry.pred.class)).toEqual([
            "Fibrosis",
        ]);
        expect(categories.sickness.map((entry) => entry.pred.class)).toEqual([
            "Pneumonia",
        ]);
        expect(categories.visual.map((entry) => entry.pred.class)).toEqual([
            "Unknown finding",
        ]);
    });

    test("removes image results without findings above the threshold", () => {
        const imageResults: ImageResult[] = [
            {
                index: 0,
                filename: "first.png",
                predictions: [
                    { class: "Fibrosis", confidence: 0.95 },
                    { class: "Edema", confidence: 0.5 },
                ],
            },
            {
                index: 1,
                filename: "second.png",
                predictions: [{ class: "Mass", confidence: 0.4 }],
            },
        ];

        expect(filterImageResults(imageResults, 90)).toEqual([
            {
                ...imageResults[0],
                predictions: [imageResults[0].predictions[0]],
            },
        ]);
        expect(imageResults[0].predictions).toHaveLength(2);
    });
});
