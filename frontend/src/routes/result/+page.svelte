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
    import {
        customThreshold,
        effectiveThreshold,
        isCustom,
    } from "$lib/settings";
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

    // Confidence threshold is controlled by the unified Decision Mode
    // setting ($lib/settings). Presets are read-only; only 'custom' mode
    // lets the user drag the slider (writing back into the store).
    let threshold = $state($effectiveThreshold);

    $effect(() => {
        if ($isCustom) {
            customThreshold.set(threshold);
        } else {
            threshold = $effectiveThreshold;
        }
    });

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

    onMount(async () => {
        const patientId = page.url.searchParams.get("patientId");
        if (!patientId) return;

        try {
            const response = await fetch(`/api/patients/${patientId}/analysis`);
            if (!response.ok) throw new Error(`Request failed with status ${response.status}`);
            const historicResult = withPersistedImageUrls(await response.json());
            analysisResult.set(historicResult);
            patientMetadata.set(historicResult.patient);
            imageUrls.set(
                (historicResult.patient?.orthancIDs ?? []).map(
                    (imageId: string) => patientImageUrl(historicResult.patient.id, imageId),
                ),
            );
        } catch (error) {
            console.error("Failed to load historic analysis:", error);
        }
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

<div class="mt-6 mx-auto w-full max-w-6xl flex flex-col gap-6 px-6 pb-12">
    {#if $analysisResult}
        <div class="flex items-center justify-between border-b pb-4">
            <div>
                <header
                    class="text-2xl font-bold tracking-tight flex items-center gap-2"
                >
                    Medical Analysis Dashboard
                </header>
                <h2 class="text-muted-foreground mt-1">
                    Detailed AI diagnostics based on patient metadata and X-Ray
                    imaging
                </h2>
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
            <header class="text-2xl font-bold tracking-tight flex items-center gap-2">
                <Stethoscope size={24} /> Medical Analysis Dashboard
            </header>
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

    {#if $analysisResult}
        {#if predictions.length > 0}
            <Item.Root variant="outline" class="flex-col items-stretch p-4">
                <Item.Header class="mb-2">
                    <Item.Title class="text-lg">
                        AI Diagnosis Ranking
                        <Badge variant="secondary" class="text-xs">
                            {filteredPredictions.length} detected
                        </Badge>
                    </Item.Title>
                </Item.Header>
                <Item.Content class="flex items-center gap-3 mb-4">
                    <Label class="whitespace-nowrap">
                        Confidence threshold
                    </Label>
                    <Slider.Root
                        type="single"
                        bind:value={threshold}
                        min={0}
                        max={100}
                        step={1}
                        disabled={!$isCustom}
                        class="flex-1 slider-thick"
                    />
                    <Label class="min-w-8 text-right">
                        {threshold}%
                    </Label>
                </Item.Content>

                <!-- three distinct category panels under the AI diagnosis section -->
                <div class="grid grid-cols-1 lg:grid-cols-3 gap-4 min-w-0">
                    {#each categoryPanels as panel}
                        <div
                            class="flex flex-col rounded-xl border overflow-hidden min-w-0"
                        >
                            <div
                                class="flex items-center gap-2 px-3 py-2 border-b bg-muted/40 shrink-0"
                            >
                                <div class="min-w-0">
                                    <h4 class="text-sm font-semibold truncate">
                                        {panel.title}
                                    </h4>
                                    <p
                                        class="text-xs text-muted-foreground truncate"
                                    >
                                        {panel.subtitle}
                                    </p>
                                </div>
                                <Badge
                                    variant="outline"
                                    class="ml-auto shrink-0 text-xs"
                                >
                                    {panel.items.length}
                                </Badge>
                            </div>
                            <div
                                class="findings-scroll flex flex-col gap-3 h-[340px] overflow-y-auto min-w-0 p-2 pr-3"
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
                            </div>
                        </div>
                    {/each}
                </div>
                <p class="text-xs text-muted-foreground mt-3">
                    Model: {classifierLabel($classifierModel)}
                    {#if analysis?.model_version}
                        · {analysis?.model_version}
                    {/if}
                </p>
            </Item.Root>
        {:else}
            <Item.Root
                variant="outline"
                class="flex-col items-center justify-center p-6 text-muted-foreground"
            >
                <Stethoscope size={24} class="mx-auto mb-2 opacity-50" />
                <p>No significant findings detected.</p>
            </Item.Root>
        {/if}

        <div class="grid grid-cols-1 lg:grid-cols-3 gap-6">
            <div class="lg:col-span-2 flex flex-col">
                <div
                    class="border rounded-xl flex flex-col relative overflow-hidden"
                >
                    <Item.Root>
                        <Item.Description class="flex items-center gap-1.5">
                            <FileDigit size={14} /> PNG Medical Viewport
                        </Item.Description>
                        <Item.Description class="flex items-center">
                            <Badge variant="outline">
                                {$imageUrls.length} File(s) Uploaded
                            </Badge>
                            {#if imageIds.length > 1}
                                <Separator orientation="vertical" class="h-3" />
                                <Badge variant="default">
                                    {activeImageIndex + 1} / {imageIds.length}
                                </Badge>
                            {/if}
                        </Item.Description>
                    </Item.Root>
                    <Item.Media>
                        {#if imageIds.length > 0}
                            <CornerstoneViewport
                                {imageIds}
                                viewportId="result-viewport"
                                bind:activeImageIndex
                            />
                        {/if}
                    </Item.Media>
                    {#if imageIds.length >= 1}
                        <Item.Footer class="bg-card border-t">
                            <ImageBar
                                {imageIds}
                                activeIndex={activeImageIndex}
                                onselect={(i) => (activeImageIndex = i)}
                            />
                        </Item.Footer>
                    {/if}
                </div>
                <Item.Description class="italic px-2 text-xs">
                    * Viewport: left-click = window/contrast, right-click =
                    zoom, wheel = scroll stack.
                </Item.Description>
            </div>

            <div class="flex flex-col gap-4">
                <Item.Root variant="outline">
                    <Item.Header>
                        <Item.Title>Patient Information</Item.Title>
                    </Item.Header>
                    <Item.Content class="flex flex-col gap-1">
                        <span class="text-sm"
                            ><strong>Patient ID:</strong> {patient?.id}</span
                        >
                        <span class="text-sm"
                            ><strong>Age:</strong> {patient?.age}</span
                        >
                        <span class="text-sm"
                            ><strong>Gender:</strong> {patient?.gender}</span
                        >
                    </Item.Content>
                </Item.Root>

                <Item.Root variant="outline">
                    <Item.Header>
                        <Item.Title>Known Symptoms</Item.Title>
                    </Item.Header>
                    <Item.Content class="flex flex-wrap gap-2">
                        {#each patient?.symptoms ?? metadata?.symptoms ?? [] as symptom}
                            <Badge variant="outline" class="symptom-badge">
                                {symptom}
                            </Badge>
                        {/each}
                    </Item.Content>
                </Item.Root>

                <Item.Root variant="outline">
                    <Item.Header>
                        <Item.Title>Medical History & Risk Factors</Item.Title>
                    </Item.Header>
                    <Item.Content class="flex flex-wrap gap-2">
                        {#each patient?.history ?? metadata?.history ?? [] as entry}
                            <Badge variant="outline" class="symptom-badge">
                                {entry}
                            </Badge>
                        {/each}
                    </Item.Content>
                </Item.Root>
            </div>
        </div>
        <HeatmapBar {imageIds} imageResults={filteredImageResults} />
        <Chat context={chatContext} />
    {:else}
        <Card.Root>
            <Card.Header>
                <Card.Title>Analysis Results</Card.Title>
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
    .findings-scroll {
        min-width: 0;
        overscroll-behavior-y: contain;
        scrollbar-width: auto;
        scrollbar-color: var(--muted-foreground) var(--muted);
    }
    .findings-scroll::-webkit-scrollbar {
        width: 10px;
        -webkit-appearance: none;
    }
    .findings-scroll::-webkit-scrollbar-track {
        background: var(--muted);
    }
    .findings-scroll::-webkit-scrollbar-thumb {
        background: var(--muted-foreground);
        border-radius: 8px;
    }
</style>
