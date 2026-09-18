<script lang="ts">
    import { goto } from "$app/navigation";
    import { Button } from "$lib/components/ui/button/index.js";
    import { Separator } from "$lib/components/ui/separator/index.js";
    import { ALL_HISTORY_TAGS, HISTORY_TOPICS } from "$lib/history";
    import { classifierModel, llmModel } from "$lib/models";
    import { patientImageUrl } from "$lib/persisted-images";
    import { analysisResult, imageUrls, patientMetadata } from "$lib/stores.js";
    import { ALL_SYMPTOM_TAGS, SYMPTOM_TOPICS } from "$lib/symptoms";
    import type { PatientMetadata } from "$lib/types";
    import { Cpu } from "lucide-svelte";
    import { onDestroy } from "svelte";
    import "../../app.css";
    import AnalysisDialogs from "./analysis-dialogs.svelte";
    import {
        AnalysisRequestError,
        submitAnalysis,
    } from "./analysis-request";
    import ClinicalChecklistCard from "./clinical-checklist-card.svelte";
    import PatientMetadataCard from "./patient-metadata-card.svelte";
    import ScanUploadCard from "./scan-upload-card.svelte";
    import { createSelection, selectedLabels } from "./upload-utils";

    let files = $state<FileList | undefined>();
    let patientAge = $state("");
    let gender = $state("");
    let selectedSymptoms = $state<Record<string, boolean>>(
        createSelection(ALL_SYMPTOM_TAGS),
    );
    let selectedHistory = $state<Record<string, boolean>>(
        createSelection(ALL_HISTORY_TAGS),
    );

    let showErrorDialog = $state(false);
    let errorMessage = $state("");
    let showAnalysisPanel = $state(false);
    let analysisController: AbortController | null = null;

    function showError(message: string) {
        errorMessage = message;
        showErrorDialog = true;
    }

    function abortAnalysis() {
        analysisController?.abort();
        showAnalysisPanel = false;
    }

    async function startAnalysis() {
        if (!files || files.length === 0) {
            showError("Please upload at least one X-Ray file.");
            return;
        }
        if (!patientAge || !gender) {
            showError("Please fill in age and gender.");
            return;
        }

        const metadata: PatientMetadata = {
            age: Number.parseInt(patientAge, 10),
            gender,
            symptoms: selectedLabels(ALL_SYMPTOM_TAGS, selectedSymptoms),
            history: selectedLabels(ALL_HISTORY_TAGS, selectedHistory),
        };
        const controller = new AbortController();
        analysisController = controller;
        showAnalysisPanel = true;

        try {
            const result = await submitAnalysis({
                files,
                metadata,
                classifierModel: $classifierModel,
                llmModel: $llmModel,
                signal: controller.signal,
            });

            analysisResult.set(result);
            patientMetadata.set(result.patient ?? metadata);
            imageUrls.set(
                (result.patient?.orthancIDs ?? []).map((imageId) =>
                    patientImageUrl(result.patient.id, imageId),
                ),
            );
            await goto("/result");
        } catch (error) {
            if (error instanceof DOMException && error.name === "AbortError") {
                return;
            }
            if (error instanceof AnalysisRequestError) {
                showError(error.message);
                return;
            }

            console.error("Analysis failed:", error);
            const reason =
                error instanceof Error ? error.message : "Unknown error";
            showError(
                `Analysis failed: ${reason}. Check if all services are running.`,
            );
        } finally {
            if (analysisController === controller) {
                showAnalysisPanel = false;
                analysisController = null;
            }
        }
    }

    onDestroy(() => analysisController?.abort());
</script>

<div class="mt-6 mx-auto w-full max-w-6xl flex flex-col gap-6 px-4 sm:px-6">
    <div>
        <h1 class="text-2xl font-bold tracking-tight">
            Case Input & Initialization
        </h1>
        <p class="text-muted-foreground mt-1">
            Upload X-Ray images and contextualize patient metadata for AI analysis
        </p>
    </div>

    <div class="grid grid-cols-1 items-start gap-6 lg:grid-cols-7">
        <ScanUploadCard bind:files />
        <PatientMetadataCard bind:age={patientAge} bind:gender />
    </div>

    <ClinicalChecklistCard
        kind="symptoms"
        title="Symptom Checklist"
        description="Select current symptoms that may provide relevant clinical context."
        contentId="symptom-checklist"
        topics={SYMPTOM_TOPICS}
        bind:selected={selectedSymptoms}
    />

    <ClinicalChecklistCard
        kind="history"
        title="Medical History & Risk Factors"
        description="Add known conditions, exposures, and other relevant risk factors."
        contentId="history-checklist"
        topics={HISTORY_TOPICS}
        bind:selected={selectedHistory}
    />

    <Separator orientation="horizontal" class="self-stretch mt-1" />
    <div class="flex justify-end w-full pb-5">
        <Button type="button" onclick={startAnalysis}>
            <Cpu /> Start Analysis
        </Button>
    </div>
</div>

<AnalysisDialogs
    bind:errorOpen={showErrorDialog}
    {errorMessage}
    bind:progressOpen={showAnalysisPanel}
    onabort={abortAnalysis}
/>
