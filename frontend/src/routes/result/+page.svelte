<script lang="ts">
    import {
        analysisResult,
        patientMetadata,
        uploadedFileUrls,
    } from "$lib/stores.js";
    import { Button } from "$lib/components/ui/button/index.js";
    import { Badge } from "$lib/components/ui/badge/index.js";
    import { Separator } from "$lib/components/ui/separator/index.js";
    import * as Item from "$lib/components/ui/item/index.js";
    import * as Accordion from "$lib/components/ui/accordion/index.js";
    import { Progress } from "$lib/components/ui/progress/index.js";
    import * as Tooltip from "$lib/components/ui/tooltip/index.js";
    import { goto } from "$app/navigation";
    import { Stethoscope, FileDigit, Undo2, RotateCcw } from "lucide-svelte";
    import "../../app.css";
    import CornerstoneViewport from "./cornerstone-viewport.svelte";
    import ChangeImageBar from "./change-image-bar.svelte";
    import type { Prediction, ImageResult } from "$lib/types.js";

    const defaultResult = {
        status: "success",
        analysis: {
            model_version: "v1.0",
            predictions: [
                {
                    class: "Pneumonia",
                    confidence: 0.92,
                    reason: "Strong evidence of pneumonia detected with bilateral opacities in the lower lobes.",
                },
                {
                    class: "Effusion",
                    confidence: 0.88,
                    reason: "Moderate evidence of pleural effusion with fluid accumulation visible.",
                },
            ],
            image_results: [
                {
                    index: 0,
                    filename: "example1.png",
                    predictions: [
                        {
                            class: "Pneumonia",
                            confidence: 0.92,
                            heatmap: "",
                        },
                    ],
                },
            ],
            is_mock: true,
        },
        patient: {
            id: 123,
            age: 62,
            gender: "Male",
            knownIllnesses: ["Covid19", "Pneumonia"],
            symptoms: ["Cough", "Fever"],
            dicomPaths: [],
        },
    };

    let result = $derived($analysisResult || defaultResult);
    let analysis = $derived(result.analysis ?? {});
    let patient = $derived(result.patient ?? {});

    let metadata = $derived($patientMetadata || patient);

    let predictions: Prediction[] = $derived(analysis.predictions ?? []);
    let imageResults: ImageResult[] = $derived(analysis.image_results ?? []);

    let imageIds = $derived(
        $uploadedFileUrls.length > 0
            ? $uploadedFileUrls.map((url) => `png:${url}`)
            : [
                  "png:/example1.png",
                  "png:/example2.png",
                  "png:/example3.png",
                  "png:/example4.png",
              ],
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
        if (confidence >= 0.95) return "text-red-600 bg-red-500/10 border-red-500/30";
        if (confidence >= 0.90) return "text-orange-600 bg-orange-500/10 border-orange-500/30";
        if (confidence >= 0.85) return "text-amber-600 bg-amber-500/10 border-amber-500/30";
        return "text-muted-foreground bg-muted/50";
    }

    function getConfidenceBarColor(confidence: number): string {
        if (confidence >= 0.95) return "[&>[data-slot=progress-indicator]]:bg-red-500";
        if (confidence >= 0.90) return "[&>[data-slot=progress-indicator]]:bg-orange-500";
        if (confidence >= 0.85) return "[&>[data-slot=progress-indicator]]:bg-amber-500";
        return "[&>[data-slot=progress-indicator]]:bg-muted-foreground/30";
    }

    async function startNewAnalysis() {
        try {
            await fetch("/api/analysis", { method: "DELETE" });
        } catch (e) {
            console.error("Failed to delete previous data:", e);
        }
        analysisResult.set(null);
        patientMetadata.set(null);
        uploadedFileUrls.set([]);
        goto("/upload");
    }

    let activeImageResult = $derived(
        imageResults.find((r) => r.index === activeHeatmapIndex) ?? null,
    );
</script>

<div class="mt-6 mx-auto w-full max-w-6xl flex flex-col gap-6 px-6 pb-12">
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

    {#if result}
        <Item.Root variant="outline" class="flex">
            <Badge variant="secondary" class="h-8 text-md"
                >Patient ID: {patient.id}</Badge
            >
            <Badge variant="secondary" class="h-8 text-md">
                Age: {patient.age}
            </Badge>
            <Badge variant="secondary" class="h-8 text-md">
                Gender: {patient.gender}
            </Badge>
        </Item.Root>

        {#if predictions.length > 0}
            <Item.Root variant="outline" class="flex-col items-stretch p-4">
                <h3 class="text-lg font-semibold mb-4 flex items-center gap-2">
                    AI Diagnosis Ranking
                    <Badge variant="secondary" class="text-xs">
                        {predictions.length} detected
                    </Badge>
                </h3>
                <div class="flex flex-col gap-3">
                    {#each predictions as pred, idx}
                        <Tooltip.Root>
                            <Tooltip.Trigger>
                                {#snippet child({ props })}
                                    <Item.Root
                                        {...props}
                                        variant="outline"
                                        class="flex-col items-stretch p-3 {getConfidenceColor(
                                            pred.confidence,
                                        )}"
                                    >
                                        <Item.Header class="mb-2">
                                            <div class="flex items-center gap-2">
                                                <span
                                                    class="text-xs font-bold w-6 h-6 rounded-full bg-background flex items-center justify-center"
                                                >
                                                    {idx + 1}
                                                </span>
                                                <span class="font-semibold"
                                                    >{pred.class}</span
                                                >
                                            </div>
                                            <span class="font-bold text-sm">
                                                {(pred.confidence * 100).toFixed(1)}%
                                            </span>
                                        </Item.Header>
                                        <Progress
                                            value={pred.confidence * 100}
                                            max={100}
                                            class="h-2 mb-2 bg-background {getConfidenceBarColor(pred.confidence)}"
                                        />
                                        {#if pred.reason}
                                            <p class="text-xs opacity-80">{pred.reason}</p>
                                        {/if}
                                    </Item.Root>
                                {/snippet}
                            </Tooltip.Trigger>
                            {#if pred.reason}
                                <Tooltip.Content>
                                    <p>{pred.reason}</p>
                                </Tooltip.Content>
                            {/if}
                        </Tooltip.Root>
                    {/each}
                </div>
                {#if analysis.model_version}
                    <p class="text-xs text-muted-foreground mt-3">
                        Model: {analysis.model_version}
                    </p>
                {/if}
            </Item.Root>
        {:else}
            <Item.Root variant="outline" class="flex-col items-center justify-center p-6 text-muted-foreground">
                <Stethoscope size={24} class="mx-auto mb-2 opacity-50" />
                <p>No significant findings detected above 85% confidence.</p>
            </Item.Root>
        {/if}

        <div class="grid grid-cols-1 lg:grid-cols-3 gap-6">
            <div class="lg:col-span-2 flex flex-col">
                <div class="border rounded-xl flex flex-col relative overflow-hidden">
                    <Item.Root>
                        <Item.Description class="flex items-center gap-1.5">
                            <FileDigit size={14} /> PNG Medical Viewport
                        </Item.Description>
                        <Item.Description class="flex items-center">
                            <Badge variant="outline">
                                {#if $uploadedFileUrls.length > 0}
                                    {$uploadedFileUrls.length} File(s) Uploaded
                                {:else}
                                    Example Images (Mock)
                                {/if}
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
                            <ChangeImageBar
                                {imageIds}
                                activeIndex={activeImageIndex}
                                onselect={(i) => (activeImageIndex = i)}
                            />
                        </Item.Footer>
                    {/if}
                </div>
                <Item.Description class="italic px-2 text-xs">
                    * Interactive Viewport: Left-click and drag to adjust window
                    level (contrast), right-click and drag to zoom, wheel to
                    scroll stack.
                </Item.Description>
            </div>

            <div class="flex flex-col gap-4">
                <Accordion.Root type="multiple">
                    <Accordion.Item value="illnesses">
                        <Accordion.Trigger>Known Illnesses</Accordion.Trigger>
                        <Accordion.Content class="gap-2">
                            {#each patient.knownIllnesses ?? metadata.knownIllnesses ?? [] as illness}
                                <Badge
                                    variant="outline"
                                    class="bg-amber-500/10 text-amber-600 border-amber-500/30"
                                >
                                    {illness}
                                </Badge>
                            {/each}
                        </Accordion.Content>
                    </Accordion.Item>

                    <Accordion.Item value="symptoms">
                        <Accordion.Trigger>Known Symptoms</Accordion.Trigger>
                        <Accordion.Content class="gap-2">
                            {#each patient.symptoms ?? metadata.symptoms ?? [] as symptom}
                                <Badge
                                    variant="outline"
                                    class="bg-teal-500/10 text-teal-600 border-teal-500/30"
                                >
                                    {symptom}
                                </Badge>
                            {/each}
                        </Accordion.Content>
                    </Accordion.Item>
                </Accordion.Root>
            </div>
        </div>

        {#if imageResults.length > 0}
            <Item.Root variant="outline" class="flex-col items-stretch p-4">
                <h3 class="text-lg font-semibold mb-4">
                    Per-Image Analysis
                </h3>
                <div class="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-4">
                    {#each imageResults as imgResult}
                        <Item.Root variant="outline" class="flex-col items-stretch overflow-hidden p-0">
                            <Item.Header class="bg-muted px-3 py-2 text-sm font-medium rounded-none">
                                {imgResult.filename}
                            </Item.Header>
                            {#if imgResult.predictions.length > 0}
                                <div class="p-3 flex flex-col gap-2">
                                    {#each imgResult.predictions as pred}
                                        <div class="flex flex-col gap-1">
                                            <div
                                                class="flex items-center justify-between text-sm"
                                            >
                                                <span class="font-medium"
                                                    >{pred.class}</span
                                                >
                                                <span class="text-xs font-bold">
                                                    {(
                                                        pred.confidence * 100
                                                    ).toFixed(1)}%
                                                </span>
                                            </div>
                                            {#if pred.heatmap}
                                                <img
                                                    src="data:image/png;base64,{pred.heatmap}"
                                                    alt="Grad-CAM: {pred.class}"
                                                    class="w-full rounded border"
                                                />
                                            {/if}
                                        </div>
                                    {/each}
                                </div>
                            {:else}
                                <Item.Description class="p-3 text-center">
                                    No significant findings
                                </Item.Description>
                            {/if}
                        </Item.Root>
                    {/each}
                </div>
            </Item.Root>
        {/if}
    {:else}
        <Item.Root variant="outline" class="bg:primary">
            <Item.Content
                class="flex flex-col items-center justify-center p-8 text-center"
            >
                <div
                    class="w-12 h-12 rounded-full bg-muted flex items-center justify-center mb-4"
                >
                    <Stethoscope size={24} class="text-muted-foreground" />
                </div>
                <Item.Title class="text-lg">No Results Available</Item.Title>
                <Item.Description class="max-w-md mt-2">
                    Please upload an X-Ray file and enter patient
                    metadata to generate an AI diagnostics report.
                </Item.Description>
                <Button
                    class="mt-6 flex items-center gap-2"
                    onclick={() => goto("/upload")}
                >
                    <Undo2 size={16} /> Back to Upload
                </Button>
            </Item.Content>
        </Item.Root>
    {/if}
</div>
