import { describe, expect, test } from "vitest";
import {
    createSelection,
    selectedCountOf,
    selectedLabels,
} from "./upload-utils";

const tags = [
    { id: "cough", label: "Cough" },
    { id: "fever", label: "Fever" },
];

describe("upload selection utilities", () => {
    test("creates an unchecked selection map", () => {
        expect(createSelection(tags)).toEqual({ cough: false, fever: false });
    });

    test("returns the selected count and labels", () => {
        const selection = { cough: true, fever: false };

        expect(selectedCountOf(tags, selection)).toBe(1);
        expect(selectedLabels(tags, selection)).toEqual(["Cough"]);
    });
});
