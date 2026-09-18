<script lang="ts">
    import { Badge } from "$lib/components/ui/badge/index.js";
    import { Button } from "$lib/components/ui/button/index.js";
    import * as Dialog from "$lib/components/ui/dialog/index.js";
    import { Skeleton } from "$lib/components/ui/skeleton/index.js";
    import { ChevronLeft, ChevronRight, X, ZoomIn } from "lucide-svelte";
    import type { ImageResult } from "$lib/types";
    import CornerstoneViewport from "./cornerstone-viewport.svelte";

    interface Props {
        imageResult: ImageResult;
        originalImageId: string;
        open: boolean;
        onclose: () => void;
    }

    let {
        imageResult,
        originalImageId,
        open = false,
        onclose = () => {},
    }: Props = $props();

    let activePredictionIndex = $state(0);
    let heatmapIdsByIndex = $state<string[]>([]);

    // Reset the selection whenever a new image is opened.
    $effect(() => {
        if (open) {
            activePredictionIndex = 0;
            heatmapIdsByIndex = [];
        }
    });

    $effect(() => {
        if (heatmapIdsByIndex.length > 0 || activePredictionIndex !== 0) return;
        if (!open) return;

        const ids = imageResult.predictions.map((p) =>
            p.heatmap ? `png:${p.heatmap}` : "",
        );
        heatmapIdsByIndex = ids;
    });
</script>

<Dialog.Root
    {open}
    onOpenChange={(isOpen) => {
        if (!isOpen) onclose();
    }}
>
    <Dialog.Content
        class="flex max-h-[90vh] max-w-6xl flex-col gap-0 overflow-hidden p-0"
        showCloseButton={false}
    >
        <!-- header -->
        <div
            class="flex items-center gap-3 px-4 py-3 border-b bg-muted/40 shrink-0"
        >
            <Badge variant="outline">{imageResult.index + 1}</Badge>
            <Dialog.Header class="min-w-0">
                <Dialog.Title class="truncate">
                    {imageResult.filename}
                </Dialog.Title>
                <Dialog.Description class="truncate text-xs">
                    {imageResult.predictions.length} finding(s) — interactive
                    view: left-click window level, right-click zoom, middle pan
                </Dialog.Description>
            </Dialog.Header>
            <Dialog.Close>
                {#snippet child({ props })}
                    <Button
                        {...props}
                        variant="ghost"
                        size="icon"
                        class="ml-auto shrink-0"
                        aria-label="Close detail view"
                    >
                        <X size={18} />
                    </Button>
                {/snippet}
            </Dialog.Close>
        </div>

        <div class="flex-1 overflow-auto p-4 min-h-0">
            {#if imageResult.predictions.length === 0}
                <p class="text-sm text-muted-foreground italic">
                    No heatmaps to display for this image.
                </p>
            {:else}
                <!-- prediction selector -->
                <div class="flex items-center justify-center gap-3 mb-4">
                    <Button
                        variant="outline"
                        size="icon"
                        aria-label="Previous finding"
                        disabled={activePredictionIndex <= 0}
                        onclick={() =>
                            (activePredictionIndex = Math.max(
                                0,
                                activePredictionIndex - 1,
                            ))}
                    >
                        <ChevronLeft size={16} />
                    </Button>
                    <div class="text-center min-w-0">
                        <div class="flex items-center justify-center gap-2">
                            <ZoomIn size={16} class="text-primary" />
                            <span class="font-semibold truncate">
                                {
                                    imageResult.predictions[
                                        activePredictionIndex
                                    ].class
                                }
                            </span>
                        </div>
                        <Badge variant="secondary" class="mt-1">
                            {(
                                imageResult.predictions[
                                    activePredictionIndex
                                ].confidence * 100
                            ).toFixed(1)}
                            % confidence · {activePredictionIndex + 1} / {
                            imageResult.predictions.length
                        }
                        </Badge>
                    </div>
                    <Button
                        variant="outline"
                        size="icon"
                        aria-label="Next finding"
                        disabled={
                            activePredictionIndex >=
                            imageResult.predictions.length - 1
                        }
                        onclick={() =>
                            (activePredictionIndex = Math.min(
                                imageResult.predictions.length - 1,
                                activePredictionIndex + 1,
                            ))}
                    >
                        <ChevronRight size={16} />
                    </Button>
                </div>

                <div class="grid grid-cols-1 md:grid-cols-2 gap-4 min-w-0">
                    <!-- unedited original -->
                    <div class="flex flex-col min-w-0">
                        <div
                            class="flex items-center justify-between mb-2 shrink-0"
                        >
                            <h3 class="text-sm font-medium">
                                Original Image
                            </h3>
                            <Badge variant="outline">unedited</Badge>
                        </div>
                        <div
                            class="border rounded-xl overflow-hidden bg-black"
                        >
                            <CornerstoneViewport
                                viewportId="detail-original-viewport"
                                renderingEngineId="detail-original-engine"
                                toolGroupId="detail-original-group"
                                imageIds={[originalImageId]}
                                activeImageIndex={0}
                            />
                        </div>
                    </div>

                    <!-- heatmap -->
                    <div class="flex flex-col min-w-0">
                        <div
                            class="flex items-center justify-between mb-2 shrink-0"
                        >
                            <h3 class="text-sm font-medium">Heatmap</h3>
                            <Badge variant="secondary">
                                {
                                    imageResult.predictions[
                                        activePredictionIndex
                                    ].class
                                }
                            </Badge>
                        </div>
                        <div
                            class="border rounded-xl overflow-hidden bg-black"
                        >
                            {#if heatmapIdsByIndex.length > 0}
                                <CornerstoneViewport
                                    viewportId="detail-heatmap-viewport"
                                    renderingEngineId="detail-heatmap-engine"
                                    toolGroupId="detail-heatmap-group"
                                    imageIds={[
                                        heatmapIdsByIndex[
                                            activePredictionIndex
                                        ],
                                    ]}
                                    activeImageIndex={0}
                                />
                            {:else}
                                <div
                                    class="space-y-3 p-4"
                                    role="status"
                                    aria-label="Loading heatmap"
                                >
                                    <Skeleton class="h-32 w-full" />
                                    <Skeleton class="h-4 w-2/3" />
                                </div>
                            {/if}
                        </div>
                    </div>
                </div>
            {/if}
        </div>
    </Dialog.Content>
</Dialog.Root>
