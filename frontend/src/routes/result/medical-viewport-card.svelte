<script lang="ts">
    import { Badge } from "$lib/components/ui/badge/index.js";
    import { Separator } from "$lib/components/ui/separator/index.js";
    import * as Card from "$lib/components/ui/card/index.js";
    import { FileDigit } from "lucide-svelte";
    import CornerstoneViewport from "./cornerstone-viewport.svelte";
    import ImageBar from "./image-bar.svelte";

    interface Props {
        imageIds: string[];
        uploadedCount: number;
        activeImageIndex: number;
    }

    let {
        imageIds,
        uploadedCount,
        activeImageIndex = $bindable(),
    }: Props = $props();
</script>

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
                <Badge variant="outline">{uploadedCount} File(s) Uploaded</Badge>
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
                    onselect={(index) => (activeImageIndex = index)}
                />
            </Card.Footer>
        {/if}
    </Card.Root>
    <p class="italic px-2 pt-2 text-xs text-muted-foreground">
        * Viewport: left-click = window/contrast, right-click = zoom, wheel = scroll
        stack.
    </p>
</div>
