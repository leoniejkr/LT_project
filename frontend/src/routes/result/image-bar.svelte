<script lang="ts">
    import { onMount } from "svelte";
    import { browser } from "$app/environment";
    import { generateThumbnail } from "$lib/cornerstone/thumbnail";
    import { Button } from "$lib/components/ui/button/index.js";
    import { Badge } from "$lib/components/ui/badge/index.js";
    import { Skeleton } from "$lib/components/ui/skeleton/index.js";
    import { ChevronLeft, ChevronRight } from "lucide-svelte";

    interface Props {
        imageIds: string[];
        activeIndex: number;
        onselect: (index: number) => void;
    }

    let { imageIds, activeIndex, onselect }: Props = $props();

    let thumbnails = $state<Map<string, string>>(new Map());
    let loading = $state(false);
    let stripElement: HTMLDivElement | undefined;
    let canScrollLeft = $state(false);
    let canScrollRight = $state(false);
    let thumbnailRequestId = 0;

    function updateScrollState() {
        if (!stripElement) return;

        const maxScrollLeft = stripElement.scrollWidth - stripElement.clientWidth;
        canScrollLeft = stripElement.scrollLeft > 1;
        canScrollRight = stripElement.scrollLeft < maxScrollLeft - 1;
    }

    function scrollStrip(direction: -1 | 1) {
        if (!stripElement) return;

        stripElement.scrollBy({
            left: direction * Math.max(stripElement.clientWidth * 0.8, 160),
            behavior: "smooth",
        });
    }

    $effect(() => {
        const requestedImageIds = [...imageIds];
        const requestId = ++thumbnailRequestId;

        updateScrollState();

        if (requestedImageIds.length > 0) {
            void loadThumbnails(requestedImageIds, requestId);
        } else {
            thumbnails = new Map();
            loading = false;
        }

        return () => {
            if (requestId === thumbnailRequestId) {
                thumbnailRequestId += 1;
            }
        };
    });

    onMount(() => {
        if (!stripElement) return;

        const resizeObserver = new ResizeObserver(updateScrollState);
        resizeObserver.observe(stripElement);
        updateScrollState();

        return () => resizeObserver.disconnect();
    });

    async function loadThumbnails(requestedImageIds: string[], requestId: number) {
        if (!browser || requestedImageIds.length === 0) return;
        loading = true;

        const results = await Promise.all(
            requestedImageIds.map(async (id) => ({
                id,
                dataUrl: await generateThumbnail(id, 160),
            })),
        );

        if (requestId !== thumbnailRequestId) return;

        const map = new Map<string, string>();
        for (const r of results) {
            if (r.dataUrl) map.set(r.id, r.dataUrl);
        }
        thumbnails = map;
        loading = false;
    }
</script>

<div class="flex w-full items-center gap-2 px-3 py-3">
    <Button
        variant="outline"
        size="icon"
        class="shrink-0 rounded-full shadow-sm"
        disabled={!canScrollLeft}
        aria-label="Scroll to previous X-rays"
        onclick={() => scrollStrip(-1)}
    >
        <ChevronLeft />
    </Button>

    <div
        bind:this={stripElement}
        class="min-w-0 flex-1 overflow-x-auto scroll-smooth [scrollbar-width:none] [&::-webkit-scrollbar]:hidden"
        role="region"
        aria-label="Uploaded X-ray images"
        onscroll={updateScrollState}
    >
        <div class="flex w-max items-center gap-3 px-1 py-1">
            {#each imageIds as imageId, index}
                <Button
                    variant="outline"
                    class="relative size-28 flex-shrink-0 overflow-hidden rounded-xl p-0 sm:size-32
                        {index === activeIndex
                        ? 'border-primary ring-2 ring-primary/30'
                        : 'hover:border-muted-foreground/50'}"
                    onclick={() => onselect(index)}
                    aria-label="Show image {index + 1}"
                    aria-pressed={index === activeIndex}
                >
                    {#if thumbnails.get(imageId)}
                        <img
                            src={thumbnails.get(imageId)}
                            alt="Image {index + 1}"
                            class="size-full bg-black object-contain"
                        />
                        <Badge
                            variant="secondary"
                            class="absolute right-2 bottom-2 h-5 min-w-5 px-1.5 text-xs shadow-sm"
                        >
                            {index + 1}
                        </Badge>
                    {:else if loading}
                        <Skeleton class="size-12" />
                    {:else}
                        <span class="text-sm text-muted-foreground">
                            {index + 1}
                        </span>
                    {/if}
                </Button>
            {/each}
        </div>
    </div>

    <Button
        variant="outline"
        size="icon"
        class="shrink-0 rounded-full shadow-sm"
        disabled={!canScrollRight}
        aria-label="Scroll to more X-rays"
        onclick={() => scrollStrip(1)}
    >
        <ChevronRight />
    </Button>
</div>
