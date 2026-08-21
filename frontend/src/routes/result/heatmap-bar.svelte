<script lang="ts">
    import * as Item from "$lib/components/ui/item/index.js";
    import { Badge } from "$lib/components/ui/badge/index.js";
    import type { ImageResult } from "$lib/types";

    interface Props {
        imageResults: ImageResult[];
    }

    let { imageResults }: Props = $props();
</script>

{#if imageResults.length > 0}
    <Item.Root variant="outline" class="flex-col items-stretch p-4">
        <div class="flex items-center justify-between mb-4 shrink-0">
            <h3 class="text-lg font-semibold">Per-Image Heatmap Analysis</h3>
            <span class="text-xs text-muted-foreground whitespace-nowrap">
                Scroll down for more images, sideways for more findings
            </span>
        </div>
        <div
            class="h-[420px] overflow-y-auto flex flex-col gap-6 pr-1"
        >
            {#each imageResults as imgResult}
                <div class="flex flex-col gap-2 min-w-0">
                    <div class="flex items-center gap-2 text-sm shrink-0">
                        <Badge variant="outline">{imgResult.index + 1}</Badge>
                        <span class="font-medium truncate">
                            {imgResult.filename}
                        </span>
                        <span class="text-xs text-muted-foreground">
                            {imgResult.predictions.length} finding(s)
                        </span>
                    </div>
                    {#if imgResult.predictions.length > 0}
                        <div class="overflow-x-auto pb-2">
                            <div class="flex gap-4 w-max">
                                {#each imgResult.predictions as pred, index}
                                    <div
                                        class="flex flex-col gap-1 w-52 shrink-0"
                                    >
                                        <div
                                            class="flex items-center justify-between text-sm"
                                        >
                                            <span class="font-medium truncate">
                                                {pred.class}
                                            </span>
                                            <span
                                                class="text-xs font-bold shrink-0 ml-2"
                                            >
                                                {(pred.confidence * 100).toFixed(1)}%
                                            </span>
                                        </div>
                                        <div class="relative">
                                            <img
                                                src="data:image/png;base64,{pred.heatmap}"
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
                        </div>
                    {:else}
                        <p class="text-xs text-muted-foreground italic px-1">
                            No significant findings for this image
                        </p>
                    {/if}
                </div>
            {/each}
        </div>
    </Item.Root>
{:else}
    <Item.Description class="p-3 text-center">
        No significant findings
    </Item.Description>
{/if}
