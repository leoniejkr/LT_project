<script lang="ts">
    import { Badge } from "$lib/components/ui/badge/index.js";
    import { Label } from "$lib/components/ui/label/index.js";
    import * as Card from "$lib/components/ui/card/index.js";
    import * as Empty from "$lib/components/ui/empty/index.js";
    import * as Slider from "$lib/components/ui/slider/index.js";
    import { Stethoscope } from "lucide-svelte";
    import type { Prediction } from "$lib/types";
    import { classifierLabel, classifierModel } from "$lib/models";
    import { setCustomThreshold } from "$lib/settings";
    import FindingCard from "./finding-card.svelte";
    import {
        categorizePredictions,
        createCategoryPanels,
        filterPredictions,
    } from "./result-view-model";

    interface Props {
        predictions: Prediction[];
        modelVersion?: string;
        threshold: number;
    }

    let { predictions, modelVersion, threshold = $bindable() }: Props = $props();

    let filteredPredictions = $derived(
        filterPredictions(predictions, threshold),
    );
    let categoryPanels = $derived(
        createCategoryPanels(categorizePredictions(filteredPredictions)),
    );

    function updateThreshold(value: number) {
        threshold = value;
        setCustomThreshold(value);
    }
</script>

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
                <Label class="whitespace-nowrap">Confidence threshold</Label>
                <Slider.Root
                    type="single"
                    bind:value={threshold}
                    min={0}
                    max={100}
                    step={1}
                    onValueChange={updateThreshold}
                    class="flex-1 slider-thick"
                />
                <Label class="min-w-8 text-right">{threshold}%</Label>
            </div>

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
                                <Badge variant="outline">{panel.items.length}</Badge>
                            </Card.Action>
                        </Card.Header>
                        <Card.Content
                            class="findings-scroll flex h-[340px] min-w-0 flex-col gap-3 overflow-y-auto pr-3"
                        >
                            {#if panel.items.length > 0}
                                {#each panel.items as entry (entry.rank)}
                                    <FindingCard {entry} />
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
            {#if modelVersion}
                · {modelVersion}
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

<style>
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
