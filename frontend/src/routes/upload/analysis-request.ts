import { withPersistedImageUrls } from "$lib/persisted-images";
import type { AnalysisResult, PatientMetadata } from "$lib/types";

interface SubmitAnalysisOptions {
    files: FileList;
    metadata: PatientMetadata;
    classifierModel: string;
    llmModel: string;
    signal: AbortSignal;
}

type AnalysisApiResponse = AnalysisResult & {
    analysis?: AnalysisResult["analysis"] & { error?: string };
};

export class AnalysisRequestError extends Error {}

export async function submitAnalysis({
    files,
    metadata,
    classifierModel,
    llmModel,
    signal,
}: SubmitAnalysisOptions): Promise<AnalysisResult> {
    const formData = new FormData();

    for (const file of files) {
        formData.append("image_files", file);
    }

    formData.append("formData", JSON.stringify(metadata));
    formData.append("classifier_model", classifierModel);
    formData.append("llm_model", llmModel);

    const response = await fetch("/api/analysis", {
        method: "POST",
        body: formData,
        signal,
    });
    const result = (await response.json()) as AnalysisApiResponse;

    if (!response.ok || result.status === "error") {
        throw new AnalysisRequestError(
            result.analysis?.error ??
                `Analysis failed with status ${response.status}.`,
        );
    }

    return withPersistedImageUrls(result);
}
