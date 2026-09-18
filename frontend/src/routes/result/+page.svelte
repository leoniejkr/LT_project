<script lang="ts">
    import {
        analysisResult,
        patientMetadata,
        imageUrls,
    } from "$lib/stores.js";
    import { patientImageUrl, withPersistedImageUrls } from "$lib/persisted-images";
    import { Button } from "$lib/components/ui/button/index.js";
    import { Badge } from "$lib/components/ui/badge/index.js";
    import { Separator } from "$lib/components/ui/separator/index.js";
    import * as Item from "$lib/components/ui/item/index.js";
    import * as Card from "$lib/components/ui/card/index.js";
    import * as Empty from "$lib/components/ui/empty/index.js";
    import { Skeleton } from "$lib/components/ui/skeleton/index.js";

    import { Progress } from "$lib/components/ui/progress/index.js";
    import * as Tooltip from "$lib/components/ui/tooltip/index.js";
    import * as Slider from "$lib/components/ui/slider/index.js";
    import { Label } from "$lib/components/ui/label/index.js";
    import { Chat } from "$lib/components/ui/chat/index.js";

    import { goto } from "$app/navigation";
    import { page } from "$app/state";
    import { onMount } from "svelte";
    import {
        Stethoscope,
        FileDigit,
        Undo2,
        RotateCcw,
        AlertTriangle,
    } from "lucide-svelte";
    import * as Alert from "$lib/components/ui/alert/index.js";
    import "../../app.css";
    import CornerstoneViewport from "./cornerstone-viewport.svelte";
    import ImageBar from "./image-bar.svelte";
    import HeatmapBar from "./heatmap-bar.svelte";
    import type {
        Prediction,
        ImageResult,
        CategorizedPrediction,
        PatientMetadata,
    } from "$lib/types.js";
    import { symptomLabelById } from "$lib/symptoms";
    import { historyLabelById } from "$lib/history";
    import { effectiveThreshold, setCustomThreshold } from "$lib/settings";
    import { classifierModel, classifierLabel } from "$lib/models";

    // Resolve mock patient data from the live tag catalogs so the
    // example view always shows current vocabulary.
    const symptomTag = (id: string): string => symptomLabelById(id) ?? id;
    const historyTag = (id: string): string => historyLabelById(id) ?? id;

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

    let hasImages = $derived($imageUrls.length > 0);
    let imageIds: string[] = $derived(
        hasImages ? $imageUrls.map((url) => `png:${url}`) : [],
    );

    // Keep the result view synchronized with the unified Decision Mode.
    // Moving this slider switches the setting to custom mode.
    let threshold = $state($effectiveThreshold);

    $effect(() => {
        threshold = $effectiveThreshold;
    });

    function updateThreshold(value: number) {
        threshold = value;
        setCustomThreshold(value);
    }

    let filteredPredictions: Prediction[] = $derived(
        predictions.filter((p) => p.confidence * 100 >= threshold),
    );

    // --- categorization of model outputs --------------------------------
    // Overlapping concepts are checked first so they never land in the
    // other two panels.
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

    function matchesAny(label: string, keys: string[]): boolean {
        return keys.some((key) => label === key || label.includes(key));
    }

    let categorizedPredictions = $derived.by(() => {
        const visual: CategorizedPrediction[] = [];
        const sickness: CategorizedPrediction[] = [];
        const overlapping: CategorizedPrediction[] = [];

        filteredPredictions.forEach((pred, rank) => {
            const label = pred.class
                .toLowerCase()
                .replace(/[_-]+/g, " ")
                .trim();
            const entry: CategorizedPrediction = { pred, rank };
            if (matchesAny(label, OVERLAPPING_KEYS)) overlapping.push(entry);
            else if (matchesAny(label, VISUAL_FINDING_KEYS)) visual.push(entry);
            else if (matchesAny(label, SICKNESS_KEYS)) sickness.push(entry);
            else visual.push(entry); // unknown labels: treat as visual finding
        });

        return { visual, sickness, overlapping };
    });

    let categoryPanels = $derived([
        {
            title: "Visual Findings",
            subtitle: "Things we can see on the scan",
            items: categorizedPredictions.visual,
        },
        {
            title: "Sicknesses & Clinical Diagnoses",
            subtitle: "Diseases and conditions",
            items: categorizedPredictions.sickness,
        },
        {
            title: "Overlapping Concepts",
            subtitle: "Both a visual feature and a condition",
            items: categorizedPredictions.overlapping,
        },
    ]);

    let filteredImageResults: ImageResult[] = $derived(
        imageResults
            .map((r) => ({
                ...r,
                predictions: r.predictions.filter(
                    (p) => p.confidence * 100 >= threshold,
                ),
            }))
            .filter((r) => r.predictions.length > 0),
    );

    let activeImageIndex = $state(0);
    let activeHeatmapIndex = $state(0);
    const historicPatientId = page.url.searchParams.get("patientId");
    let historicLoading = $state(Boolean(historicPatientId));
    let historicError = $state("");

    $effect(() => {
        if (activeImageIndex >= imageIds.length) {
            activeImageIndex = Math.max(0, imageIds.length - 1);
        }
    });

    $effect(() => {
        activeHeatmapIndex = activeImageIndex;
    });

    function getConfidenceColor(confidence: number): string {
        if (confidence >= 0.95) return "confidence-critical";
        if (confidence >= 0.9) return "confidence-high";
        if (confidence >= 0.85) return "confidence-medium";
        return "confidence-low";
    }

    function getConfidenceBarColor(confidence: number): string {
        if (confidence >= 0.95) return "confidence-critical-bar";
        if (confidence >= 0.9) return "confidence-high-bar";
        if (confidence >= 0.85) return "confidence-medium-bar";
        return "confidence-low-bar";
    }

    async function startNewAnalysis() {
        analysisResult.set(null);
        patientMetadata.set(null);
        imageUrls.set([]);
        goto("/upload");
    }

    async function loadHistoricAnalysis(patientId: string, signal?: AbortSignal) {
        historicLoading = true;
        historicError = "";
        try {
            const response = await fetch(`/api/patients/${patientId}/analysis`, {
                signal,
            });
            if (!response.ok) throw new Error(`Request failed with status ${response.status}`);
            const historicResult = withPersistedImageUrls(await response.json());
            if (signal?.aborted) return;

            analysisResult.set(historicResult);
            patientMetadata.set(historicResult.patient);
            imageUrls.set(
                (historicResult.patient?.orthancIDs ?? []).map(
                    (imageId: string) => patientImageUrl(historicResult.patient.id, imageId),
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

    onMount(() => {
        if (!historicPatientId) return;

        const controller = new AbortController();
        void loadHistoricAnalysis(historicPatientId, controller.signal);

        return () => controller.abort();
    });

    let activeImageResult = $derived(
        filteredImageResults.find((r) => r.index === activeHeatmapIndex) ??
            null,
    );

    // Context handed to the chat assistant so it knows the patient's
    // checked symptoms, medical history/risk factors and the findings.
    let chatContext = $derived({
        patient: {
            age: metadata?.age ?? null,
            gender: metadata?.gender ?? null,
            symptoms: metadata?.symptoms ?? [],
            history: metadata?.history ?? [],
        },
        analysis: {
            model_version: analysis?.model_version ?? null,
            predictions: predictions.map((p) => ({
                class: p.class,
                confidence: p.confidence,
            })),
        },
    });
</script>

<div class="mt-6 mx-auto w-full max-w-6xl flex flex-col gap-6 px-4 pb-12 sm:px-6">
    {#if $analysisResult && !historicLoading && !historicError}
        <div class="flex flex-col items-start gap-4 border-b pb-4 sm:flex-row sm:items-center sm:justify-between">
            <div>
                <h1
                    class="text-2xl font-bold tracking-tight flex items-center gap-2"
                >
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


    {#snippet findingCard(entry: CategorizedPrediction)}
        <Tooltip.Root>
            <Tooltip.Trigger>
                {#snippet child({ props })}
                    <Item.Root
                        {...props}
                        variant="outline"
                        class="flex-col items-stretch p-3 {getConfidenceColor(
                            entry.pred.confidence,
                        )}"
                    >
                        <Item.Header
                            class="mb-2 basis-auto flex-row min-w-0 shrink-0"
                        >
                            <Item.Title class="min-w-0 truncate">
                                <span
                                    class="text-xs font-bold w-6 h-6 rounded-full bg-background inline-flex items-center justify-center"
                                >
                                    {entry.rank + 1}
                                </span>
                                {entry.pred.class}
                            </Item.Title>
                            <span class="font-bold text-sm shrink-0">
                                {(entry.pred.confidence * 100).toFixed(1)}%
                            </span>
                        </Item.Header>
                        <!-- confidence bar: stays inside the card, full width -->
                        <Progress
                            value={entry.pred.confidence * 100}
                            max={100}
                            class="h-2 mb-2 w-full max-w-full shrink-0 bg-muted {getConfidenceBarColor(
                                entry.pred.confidence,
                            )}"
                        />
                        {#if entry.pred.reason}
                            <Item.Description
                                class="text-xs opacity-80 min-w-0 break-words"
                            >
                                {entry.pred.reason}
                            </Item.Description>
                        {/if}
                    </Item.Root>
                {/snippet}
            </Tooltip.Trigger>
            {#if entry.pred.reason}
                <Tooltip.Content>
                    <p>{entry.pred.reason}</p>
                </Tooltip.Content>
            {/if}
        </Tooltip.Root>
    {/snippet}

    {#if historicLoading}
        <Card.Root aria-busy="true" aria-label="Loading analysis">
            <Card.Header>
                <Skeleton class="h-5 w-40" />
                <Skeleton class="h-4 w-full max-w-md" />
            </Card.Header>
            <Card.Content class="space-y-4">
                <Skeleton class="h-28 w-full" />
                <div class="grid grid-cols-1 gap-4 md:grid-cols-3">
                    <Skeleton class="h-36 w-full md:col-span-2" />
                    <Skeleton class="h-36 w-full" />
                </div>
            </Card.Content>
        </Card.Root>
    {:else if historicError}
        <Card.Root>
            <Card.Header>
                <Card.Title><h2>Analysis Results</h2></Card.Title>
                <Card.Description>
                    The requested historic analysis is currently unavailable.
                </Card.Description>
            </Card.Header>
            <Card.Content>
                <Alert.Root variant="destructive">
                    <AlertTriangle />
                    <Alert.Title>Unable to load analysis</Alert.Title>
                    <Alert.Description>{historicError}</Alert.Description>
                    {#if historicPatientId}
                        <Alert.Action>
                            <Button
                                variant="destructive"
                                size="sm"
                                onclick={() => void loadHistoricAnalysis(historicPatientId)}
                            >
                                Try again
                            </Button>
                        </Alert.Action>
                    {/if}
                </Alert.Root>
            </Card.Content>
        </Card.Root>
    {:else if $analysisResult}
        {#if predictions.length > 0}
            <Card.Root>
                <Card.Header>
                    <Card.Title><h2>AI Diagnosis Ranking</h2></Card.Title>
                    <Card.Description>
                        Findings that meet the selected confidence threshold.
                    </Card.Description>
                    <Card.Action>
                        <Badge variant="secondary">
                            {filteredPredictions.length} detected
                        </Badge>
                    </Card.Action>
                </Card.Header>
                <Card.Content>
                    <div class="flex items-center gap-3 mb-4">
                        <Label class="whitespace-nowrap">
                            Confidence threshold
                        </Label>
                        <Slider.Root
                            type="single"
                            bind:value={threshold}
                            min={0}
                            max={100}
                            step={1}
                            onValueChange={updateThreshold}
                            class="flex-1 slider-thick"
                        />
                        <Label class="min-w-8 text-right">
                            {threshold}%
                        </Label>
                    </div>

                    <!-- three distinct category panels under the AI diagnosis section -->
                    <div class="grid grid-cols-1 lg:grid-cols-3 gap-4 min-w-0">
                        {#each categoryPanels as panel}
                            <Card.Root size="sm" class="min-w-0">
                                <Card.Header class="border-b">
                                    <Card.Title>
                                        <h3 class="truncate">{panel.title}</h3>
                                    </Card.Title>
                                    <Card.Description class="truncate">
                                        {panel.subtitle}
                                    </Card.Description>
                                    <Card.Action>
                                        <Badge variant="outline">
                                            {panel.items.length}
                                        </Badge>
                                    </Card.Action>
                                </Card.Header>
                                <Card.Content
                                    class="findings-scroll flex h-[340px] min-w-0 flex-col gap-3 overflow-y-auto pr-3"
                                >
                                    {#if panel.items.length > 0}
                                        {#each panel.items as entry (entry.rank)}
                                            {@render findingCard(entry)}
                                        {/each}
                                    {:else}
                                        <p
                                            class="text-xs text-muted-foreground italic px-2 py-3"
                                        >
                                            No findings in this category
                                        </p>
                                    {/if}
                                </Card.Content>
                            </Card.Root>
                        {/each}
                    </div>
                </Card.Content>
                <Card.Footer class="border-t text-xs text-muted-foreground">
                    Model: {classifierLabel($classifierModel)}
                    {#if analysis?.model_version}
                        · {analysis?.model_version}
                    {/if}
                </Card.Footer>
            </Card.Root>
        {:else}
            <Card.Root>
                <Card.Header>
                    <Card.Title><h2>AI Diagnosis Ranking</h2></Card.Title>
                    <Card.Description>
                        Findings that meet the selected confidence threshold.
                    </Card.Description>
                </Card.Header>
                <Card.Content>
                    <Empty.Root class="p-6">
                        <Empty.Header>
                            <Empty.Media variant="icon"><Stethoscope /></Empty.Media>
                            <Empty.Title>No significant findings</Empty.Title>
                            <Empty.Description>
                                The analysis did not detect findings above the current threshold.
                            </Empty.Description>
                        </Empty.Header>
                    </Empty.Root>
                </Card.Content>
            </Card.Root>
        {/if}

        <div class="grid grid-cols-1 lg:grid-cols-3 gap-6">
            <div class="lg:col-span-2 flex flex-col">
                <Card.Root class="relative">
                    <Card.Header>
                        <Card.Title>
                            <h2 class="flex items-center gap-2">
                                <FileDigit size={18} /> PNG Medical Viewport
                            </h2>
                        </Card.Title>
                        <Card.Description>
                            Inspect the uploaded X-Ray images interactively.
                        </Card.Description>
                        <Card.Action class="flex items-center gap-2">
                            <Badge variant="outline">
                                {$imageUrls.length} File(s) Uploaded
                            </Badge>
                            {#if imageIds.length > 1}
                                <Separator orientation="vertical" class="h-3" />
                                <Badge variant="default">
                                    {activeImageIndex + 1} / {imageIds.length}
                                </Badge>
                            {/if}
                        </Card.Action>
                    </Card.Header>
                    <Card.Content class="px-0">
                        {#if imageIds.length > 0}
                            <CornerstoneViewport
                                {imageIds}
                                viewportId="result-viewport"
                                bind:activeImageIndex
                            />
                        {/if}
                    </Card.Content>
                    {#if imageIds.length >= 1}
                        <Card.Footer class="bg-card border-t px-0">
                            <ImageBar
                                {imageIds}
                                activeIndex={activeImageIndex}
                                onselect={(i) => (activeImageIndex = i)}
                            />
                        </Card.Footer>
                    {/if}
                </Card.Root>
                <p class="italic px-2 pt-2 text-xs text-muted-foreground">
                    * Viewport: left-click = window/contrast, right-click =
                    zoom, wheel = scroll stack.
                </p>
            </div>

            <div class="flex flex-col gap-6">
                <Card.Root size="sm">
                    <Card.Header>
                        <Card.Title><h2>Patient Information</h2></Card.Title>
                    </Card.Header>
                    <Card.Content class="flex flex-col gap-1">
                        <span class="text-sm"
                            ><strong>Patient ID:</strong> {patient?.id}</span
                        >
                        <span class="text-sm"
                            ><strong>Age:</strong> {patient?.age}</span
                        >
                        <span class="text-sm"
                            ><strong>Gender:</strong> {patient?.gender}</span
                        >
                    </Card.Content>
                </Card.Root>

                <Card.Root size="sm">
                    <Card.Header>
                        <Card.Title><h2>Known Symptoms</h2></Card.Title>
                    </Card.Header>
                    <Card.Content class="flex flex-wrap gap-2">
                        {#each patient?.symptoms ?? metadata?.symptoms ?? [] as symptom}
                            <Badge variant="outline" class="symptom-badge">
                                {symptom}
                            </Badge>
                        {/each}
                    </Card.Content>
                </Card.Root>

                <Card.Root size="sm">
                    <Card.Header>
                        <Card.Title><h2>Medical History & Risk Factors</h2></Card.Title>
                    </Card.Header>
                    <Card.Content class="flex flex-wrap gap-2">
                        {#each patient?.history ?? metadata?.history ?? [] as entry}
                            <Badge variant="outline" class="symptom-badge">
                                {entry}
                            </Badge>
                        {/each}
                    </Card.Content>
                </Card.Root>
            </div>
        </div>
        <HeatmapBar {imageIds} imageResults={filteredImageResults} />
        <Chat context={chatContext} />
    {:else}
        <Card.Root>
            <Card.Header>
                <Card.Title><h2>Analysis Results</h2></Card.Title>
                <Card.Description>
                    Start an analysis to generate a detailed diagnostic report.
                </Card.Description>
            </Card.Header>
            <Card.Content>
                <Empty.Root>
                    <Empty.Header>
                        <Empty.Media variant="icon"><Stethoscope /></Empty.Media>
                        <Empty.Title>No analysis yet</Empty.Title>
                        <Empty.Description>
                            Upload an X-Ray file and enter patient metadata. Your AI
                            diagnostics report will appear here automatically.
                        </Empty.Description>
                    </Empty.Header>
                    <Empty.Content>
                        <Button href="/upload">
                            <Undo2 /> Go to Upload
                        </Button>
                    </Empty.Content>
                </Empty.Root>
            </Card.Content>
        </Card.Root>
    {/if}
</div>

<style>
    /* findings list inside AI Diagnosis Ranking: vertical scroll in a
       constrained inner panel — same scrollbar styling as the
       heatmap panel */
    :global(.findings-scroll) {
        min-width: 0;
        overscroll-behavior-y: contain;
        scrollbar-width: auto;
        scrollbar-color: var(--muted-foreground) var(--muted);
    }
    :global(.findings-scroll)::-webkit-scrollbar {
        width: 10px;
        -webkit-appearance: none;
    }
    :global(.findings-scroll)::-webkit-scrollbar-track {
        background: var(--muted);
    }
    :global(.findings-scroll)::-webkit-scrollbar-thumb {
        background: var(--muted-foreground);
        border-radius: 8px;
    }
</style>
