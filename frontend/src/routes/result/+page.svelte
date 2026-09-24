<script lang="ts">
    import { goto } from "$app/navigation";
    import { page } from "$app/state";
    import { Button } from "$lib/components/ui/button/index.js";
    import { Chat } from "$lib/components/ui/chat/index.js";
    import { patientImageUrl, withPersistedImageUrls } from "$lib/persisted-images";
    import { effectiveThreshold } from "$lib/settings";
    import { analysisResult, imageUrls, patientMetadata } from "$lib/stores.js";
    import type { ChatContext, ImageResult, PatientMetadata, Prediction } from "$lib/types.js";
    import { RotateCcw, Stethoscope } from "lucide-svelte";
    import { onMount } from "svelte";
    import "../../app.css";
    import AnalysisRanking from "./analysis-ranking.svelte";
    import HeatmapBar from "./heatmap-bar.svelte";
    import MedicalViewportCard from "./medical-viewport-card.svelte";
    import PatientSummary from "./patient-summary.svelte";
    import ResultStatusCard from "./result-status-card.svelte";
    import { filterImageResults } from "./result-view-model";

    let result = $derived($analysisResult);
    let analysis = $derived(result?.analysis ?? null);
    let patient = $derived(result?.patient ?? null);
    let metadata: PatientMetadata | null = $derived(
        $patientMetadata ?? patient,
    );
    let predictions: Prediction[] = $derived(analysis?.predictions ?? []);
    let imageResults: ImageResult[] = $derived(
        analysis?.image_results ?? [],
    );
    let imageIds: string[] = $derived(
        $imageUrls.map((url) => `png:${url}`),
    );

    let threshold = $state($effectiveThreshold);
    let activeImageIndex = $state(0);
    const historicPatientId = page.url.searchParams.get("patientId");
    let historicLoading = $state(Boolean(historicPatientId));
    let historicError = $state("");

    let filteredImageResults = $derived(
        filterImageResults(imageResults, threshold),
    );
    let chatContext: ChatContext = $derived({
        patient: {
            age: metadata?.age ?? null,
            gender: metadata?.gender ?? null,
            symptoms: metadata?.symptoms ?? [],
            history: metadata?.history ?? [],
        },
        analysis: {
            model_version: analysis?.model_version ?? null,
            predictions: predictions.map((prediction) => ({
                class: prediction.class,
                confidence: prediction.confidence,
            })),
        },
    });

    $effect(() => {
        threshold = $effectiveThreshold;
    });

    $effect(() => {
        if (activeImageIndex >= imageIds.length) {
            activeImageIndex = Math.max(0, imageIds.length - 1);
        }
    });

    async function startNewAnalysis() {
        analysisResult.set(null);
        patientMetadata.set(null);
        imageUrls.set([]);
        await goto("/upload");
    }

    async function loadHistoricAnalysis(
        patientId: string,
        signal?: AbortSignal,
    ) {
        historicLoading = true;
        historicError = "";

        try {
            const response = await fetch(`/api/patients/${patientId}/analysis`, {
                signal,
            });
            if (!response.ok) {
                throw new Error(`Request failed with status ${response.status}`);
            }

            const historicResult = withPersistedImageUrls(await response.json());
            if (signal?.aborted) return;

            analysisResult.set(historicResult);
            patientMetadata.set(historicResult.patient);
            imageUrls.set(
                (historicResult.patient?.orthancIDs ?? []).map((imageId) =>
                    patientImageUrl(historicResult.patient.id, imageId),
                ),
            );
        } catch (error) {
            if (error instanceof Error && error.name === "AbortError") return;
            console.error("Failed to load historic analysis:", error);
            historicError = "The selected analysis could not be loaded.";
        } finally {
            if (!signal?.aborted) historicLoading = false;
        }
    }

    function retryHistoricAnalysis() {
        if (historicPatientId) void loadHistoricAnalysis(historicPatientId);
    }

    onMount(() => {
        if (!historicPatientId) return;

        const controller = new AbortController();
        void loadHistoricAnalysis(historicPatientId, controller.signal);

        return () => controller.abort();
    });
</script>

<div class="mt-6 mx-auto w-full max-w-6xl flex flex-col gap-6 px-4 pb-12 sm:px-6">
    {#if $analysisResult && !historicLoading && !historicError}
        <div
            class="flex flex-col items-start gap-4 border-b pb-4 sm:flex-row sm:items-center sm:justify-between"
        >
            <div>
                <h1 class="text-2xl font-bold tracking-tight">
                    Medical Analysis Dashboard
                </h1>
                <p class="text-muted-foreground mt-1">
                    Detailed AI diagnostics based on patient metadata and X-Ray
                    imaging
                </p>
            </div>
            <Button
                variant="default"
                class="flex items-center gap-2"
                onclick={startNewAnalysis}
            >
                <RotateCcw size={16} /> Start New Analysis
            </Button>
        </div>
    {:else}
        <div>
            <h1 class="text-2xl font-bold tracking-tight flex items-center gap-2">
                <Stethoscope size={24} /> Medical Analysis Dashboard
            </h1>
            <p class="text-muted-foreground mt-1">
                Detailed AI diagnostics based on patient metadata and X-Ray imaging
            </p>
        </div>
    {/if}

    {#if historicLoading}
        <ResultStatusCard state="loading" />
    {:else if historicError}
        <ResultStatusCard
            state="error"
            error={historicError}
            onretry={historicPatientId ? retryHistoricAnalysis : undefined}
        />
    {:else if $analysisResult}
        <AnalysisRanking
            {predictions}
            modelVersion={analysis?.model_version}
            bind:threshold
        />

        <div class="grid grid-cols-1 lg:grid-cols-3 gap-6">
            <MedicalViewportCard
                {imageIds}
                uploadedCount={$imageUrls.length}
                bind:activeImageIndex
            />
            <PatientSummary {patient} {metadata} />
        </div>

        <HeatmapBar {imageIds} imageResults={filteredImageResults} />
        <Chat context={chatContext} />
    {:else}
        <ResultStatusCard state="empty" />
    {/if}
</div>
