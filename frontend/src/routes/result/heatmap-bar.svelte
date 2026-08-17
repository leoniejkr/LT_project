<script lang="ts">
    import * as Item from "$lib/components/ui/item/index.js";
    import { Badge } from "$lib/components/ui/badge/index.js";
    import type { ImageResult } from "$lib/types";

    interface Props {
        imageResults: ImageResult[];
    }

    let { imageResults }: Props = $props();
</script>

<Item.Root variant="outline" class="flex-col items-stretch p-4">
    <h3 class="text-lg font-semibold mb-4">Per-Image Heatmap Analysis</h3>
    <div class="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-4">
        {#each imageResults as imgResult}
            <Item.Root
                variant="outline"
                class="flex-col items-stretch overflow-hidden p-0"
            >
                {#if imgResult.predictions.length > 0}
                    <div class="p-3 flex flex-col gap-2">
                        {#each imgResult.predictions as pred, index}
                            <div class="flex flex-col gap-1">
                                <div
                                    class="flex items-center justify-between text-sm"
                                >
                                    <span class="font-medium">{pred.class}</span
                                    >
                                    <span class="text-xs font-bold">
                                        {(pred.confidence * 100).toFixed(1)}%
                                    </span>
                                </div>
                                {#if pred.heatmap}
                                    <img
                                        src="data:image/png;base64,{pred.heatmap}"
                                        alt="Grad-CAM: {pred.class} {index + 1}"
                                        class="w-full rounded border"
                                    />
                                    <Badge
                                        variant="secondary"
                                        class="absolute bottom-1 right-1 text-xs h-4 min-w-4 px-1"
                                    >
                                        {index + 1}
                                    </Badge>
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
