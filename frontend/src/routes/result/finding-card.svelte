<script lang="ts">
    import { Progress } from "$lib/components/ui/progress/index.js";
    import * as Item from "$lib/components/ui/item/index.js";
    import * as Tooltip from "$lib/components/ui/tooltip/index.js";
    import type { CategorizedPrediction } from "$lib/types";
    import {
        confidenceBarClass,
        confidenceClass,
    } from "./result-view-model";

    let { entry }: { entry: CategorizedPrediction } = $props();
</script>

<Tooltip.Root>
    <Tooltip.Trigger>
        {#snippet child({ props })}
            <Item.Root
                {...props}
                variant="outline"
                class="flex-col items-stretch p-3 {confidenceClass(
                    entry.pred.confidence,
                )}"
            >
                <Item.Header class="mb-2 basis-auto flex-row min-w-0 shrink-0">
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
                <Progress
                    value={entry.pred.confidence * 100}
                    max={100}
                    class="h-2 mb-2 w-full max-w-full shrink-0 bg-muted {confidenceBarClass(
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
