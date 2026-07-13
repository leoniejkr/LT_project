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
    import { goto } from "$app/navigation";
    import { Stethoscope, FileDigit, Undo2, RotateCcw } from "lucide-svelte";
    import "../../app.css";
    import CornerstoneViewport from "./cornerstone-viewport.svelte";
    import ChangeImageBar from "./change-image-bar.svelte";

    const defaultResult = {
        status: "success",
        analysis: {
            prediction: "Pneumonia",
            confidence: 0.85,
            confidence_reason:
                "The model detected significant opacities in the lower lobes consistent with pneumonia but there are certain uncertaincies.",
            model_version: "v1.0",
        },
        patient: {
            id: "123",
            age: 62,
            gender: "Male",
            knownIllnesses: ["Covid", "Pneumonia"],
            symptoms: ["Cough", "Fever", "Dyspnea"],
        },
    };

    let result = $derived($analysisResult || defaultResult);
    let analysis = $derived(result.analysis ?? {});
    let patient = $derived(result.patient ?? {});

    let metadata = $derived($patientMetadata || patient);

    let imageIds = $derived(
        $uploadedFileUrls.length > 0
            ? $uploadedFileUrls.map((url) => `png:${url}`)
            : ["png:/image-000001.png"],
    );

    let activeImageIndex = $state(0);

    $effect(() => {
        if (activeImageIndex >= imageIds.length) {
            activeImageIndex = Math.max(0, imageIds.length - 1);
        }
    });

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
</script>

<div class="mt-6 mx-auto w-full max-w-5xl flex flex-col gap-6 px-6 pb-12">
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
                                {#if $uploadedFileUrls.length > 0}
                                    {$uploadedFileUrls.length} File(s) Uploaded
                                {:else}
                                    image-000001.png (Mock)
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
                <!-- TODO: else block einbauen (ein text), wenn es keine illnesses etc gibt -->
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

                <Item.Root variant="outline">
                    <Item.Title class="flex items-center gap-2">
                        AI Diagnosis
                    </Item.Title>
                    <Separator />
                    <Item.Content class="flex-1 flex flex-col justify-between">
                        <div
                            class="text-xs text-muted-foreground uppercase tracking-wider font-semibold"
                        >
                            Prediction
                        </div>
                        <div
                            class="text-lg font-semibold flex items-center gap-2"
                        >
                            {analysis.prediction}
                        </div>
                    </Item.Content>
                    <Item.Footer class="text-muted-foreground">
                        Model: {analysis.model_version}
                    </Item.Footer>
                </Item.Root>

                <Item.Root
                    variant="outline"
                    class="border-wary/50 bg-wary/[0.03]"
                >
                    <Item.Title class="text-wary pb-2">
                        AI Diagnostics Assessment
                    </Item.Title>
                    <Item.Content class="font-semibold text-lg">
                        {(typeof analysis.confidence === "number"
                            ? analysis.confidence * 100
                            : 0
                        ).toFixed(1)}% Confidence
                    </Item.Content>
                </Item.Root>

                <Item.Root
                    variant="outline"
                    class="border-primary/50 bg-primary/[0.03]"
                >
                    <Item.Title class="text-primary font-semibold">
                        Assessement Reason
                    </Item.Title>
                    <Item.Description class="line-clamp-none">
                        {analysis.confidence_reason}
                    </Item.Description>
                </Item.Root>
            </div>
        </div>
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
