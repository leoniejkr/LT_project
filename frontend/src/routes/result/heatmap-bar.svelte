<script lang="ts">
    import * as Item from "$lib/components/ui/item/index.js";
    import { Badge } from "$lib/components/ui/badge/index.js";
    import { Button } from "$lib/components/ui/button/index.js";
    import { Search } from "lucide-svelte";
    import { ChevronLeft, ChevronRight } from "lucide-svelte";
    import type { ImageResult } from "$lib/types";
    import HeatmapDetail from "./heatmap-detail.svelte";

    interface Props {
        imageResults: ImageResult[];
        imageIds: string[];
    }

    let { imageResults, imageIds }: Props = $props();

    let stripEls: Record<number, HTMLDivElement | null> = {};

    // Which image's detail view is open (matched by index), if any.
    let openDetailIndex = $state<number | null>(null);

    function scrollStrip(index: number, direction: number) {
        stripEls[index]?.scrollBy({
            left: direction * 220,
            behavior: "smooth",
        });
    }

    function originalImageIdFor(index: number): string | undefined {
        return imageIds[index];
    }

</script>

{#if imageResults.length > 0}
    <Item.Root
        variant="outline"
        class="flex-col items-stretch p-4 overflow-hidden heatmap-root"
    >
        <div class="flex items-center justify-between mb-4 shrink-0 pr-3">
            <h3 class="text-lg font-semibold">Per-Image Heatmap Analysis</h3>
            <span class="text-xs text-muted-foreground whitespace-nowrap">
                {imageResults.length} image(s), use the bar or arrows in each
                panel to see all findings
            </span>
        </div>

        <!-- big fixed-size panel: images stacked under each other -->
        <div
            class="h-[340px] overflow-y-auto panel-scroll min-w-0 py-1 pl-1 pr-8"
        >
            {#each imageResults as imgResult}
                <!-- per-image panel: max 85% of the SURROUNDING panel's width -->
                <div
                    class="heatmap-image-panel min-w-0 mb-4 last:mb-0 border rounded-xl bg-card overflow-hidden flex flex-col"
                >
                    <div
                        class="flex items-center gap-2 text-sm px-3 py-2 border-b shrink-0 min-w-0"
                    >
                        <Badge variant="outline">{imgResult.index + 1}</Badge>
                        <span class="font-medium truncate min-w-0">
                            {imgResult.filename}
                        </span>
                        <Button
                            variant="ghost"
                            size="icon-xs"
                            class="shrink-0"
                            aria-label="Open detail view for {imgResult.filename}"
                            onclick={() => (openDetailIndex = imgResult.index)}
                        >
                            <Search size={14} />
                        </Button>
                        <span
                            class="text-xs text-muted-foreground ml-auto shrink-0 mr-1"
                        >
                            {imgResult.predictions.length} finding(s)
                        </span>
                        {#if imgResult.predictions.length > 1}
                            <Button
                                variant="ghost"
                                size="icon-xs"
                                aria-label="Scroll heatmaps left"
                                onclick={() => scrollStrip(imgResult.index, -1)}
                            >
                                <ChevronLeft size={14} />
                            </Button>
                            <Button
                                variant="ghost"
                                size="icon-xs"
                                aria-label="Scroll heatmaps right"
                                onclick={() => scrollStrip(imgResult.index, 1)}
                            >
                                <ChevronRight size={14} />
                            </Button>
                        {/if}
                    </div>

                    {#if imgResult.predictions.length > 0}
                        <!-- internal left/right scroll through heatmaps -->
                        <div
                            class="heatmap-strip flex items-start gap-3 p-3 min-w-0 max-w-full overflow-x-auto overflow-y-hidden"
                            bind:this={stripEls[imgResult.index]}
                        >
                            {#each imgResult.predictions as pred, index}
                                <div class="flex flex-col gap-1 w-52 shrink-0">
                                    <div
                                        class="flex items-center justify-between gap-2 text-sm"
                                    >
                                        <span class="font-medium truncate">
                                            {pred.class}
                                        </span>
                                        <span
                                            class="text-xs font-bold shrink-0"
                                        >
                                            {(pred.confidence * 100).toFixed(1)}%
                                        </span>
                                    </div>
                                    <div class="relative">
                                        <img
                                            src={pred.heatmap}
                                            alt="Grad-CAM: {pred.class} {index + 1}"
                                            class="w-full h-40 rounded border object-cover"
                                        />
                                        <Badge
                                            variant="secondary"
                                            class="absolute bottom-1 right-1 text-xs h-4 min-w-4 px-1"
                                        >
                                            {index + 1}
                                        </Badge>
                                    </div>
                                </div>
                            {/each}
                        </div>
                    {:else}
                        <p class="text-xs text-muted-foreground italic px-3 py-3">
                            No significant findings for this image
                        </p>
                    {/if}
                </div>
            {/each}
        </div>
    </Item.Root>

    {#if openDetailIndex !== null}
        {@const detail = imageResults.find(
            (r) => r.index === openDetailIndex,
        )}
        {#if detail}
            <HeatmapDetail
                imageResult={detail}
                originalImageId={originalImageIdFor(detail.index) ?? ""}
                open={true}
                onclose={() => (openDetailIndex = null)}
            />
        {/if}
    {/if}
{:else}
    <Item.Description class="p-3 text-center">
        No significant findings
    </Item.Description>
{/if}

<style>
    /* the surrounding panel is the size reference for the inner panels
       (:global because the class goes through Item.Root's class prop,
       so Svelte would otherwise strip the rule as "unused") */
    :global(.heatmap-root) {
        container-type: inline-size;
    }

    /* hard cap: 99% of the surrounding panel's width (cqw = 1% of
       the nearest size container = .heatmap-root). The plain %
       declaration is a fallback for browsers without cq support. */
    .heatmap-image-panel {
        max-width: 99%;
        max-width: 99cqw;
        min-width: 0;
    }

    /* internal per-image horizontal strip: same pattern as the working
       image bar — the flex container itself is the scroll container */
    .heatmap-strip {
        overflow-x: auto;
        overflow-y: hidden;
        overscroll-behavior-x: contain;
        scrollbar-width: auto;
        scrollbar-color: var(--muted-foreground) var(--muted);
    }
    .heatmap-strip::-webkit-scrollbar {
        height: 12px;
        -webkit-appearance: none;
    }
    .heatmap-strip::-webkit-scrollbar-track {
        background: var(--muted);
    }
    .heatmap-strip::-webkit-scrollbar-thumb {
        background: var(--muted-foreground);
        border-radius: 8px;
        border: 2px solid var(--muted);
    }

    .panel-scroll {
        scrollbar-width: auto;
        scrollbar-color: var(--muted-foreground) var(--muted);
    }
    .panel-scroll::-webkit-scrollbar {
        width: 10px;
        -webkit-appearance: none;
    }
    .panel-scroll::-webkit-scrollbar-track {
        background: var(--muted);
    }
    .panel-scroll::-webkit-scrollbar-thumb {
        background: var(--muted-foreground);
        border-radius: 8px;
    }
</style>
