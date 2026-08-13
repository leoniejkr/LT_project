<script lang="ts">
    import { browser } from "$app/environment";
    import { generateThumbnail } from "$lib/cornerstone/thumbnail";
    import { Button } from "$lib/components/ui/button/index.js";
    import { Badge } from "$lib/components/ui/badge/index.js";

    interface Props {
        imageIds: string[];
        activeIndex: number;
        onselect: (index: number) => void;
    }

    let { imageIds, activeIndex, onselect }: Props = $props();

    let thumbnails = $state<Map<string, string>>(new Map());
    let loading = $state(false);

    $effect(() => {
        if (imageIds.length > 0) {
            loadThumbnails();
        }
    });

    async function loadThumbnails() {
        if (!browser || imageIds.length === 0) return;
        loading = true;

        const results = await Promise.all(
            imageIds.map(async (id) => ({
                id,
                dataUrl: await generateThumbnail(id),
            })),
        );

        const map = new Map<string, string>();
        for (const r of results) {
            if (r.dataUrl) map.set(r.id, r.dataUrl);
        }
        thumbnails = map;
        loading = false;
    }
</script>

<div class="flex items-center gap-2 overflow-x-auto py-2.5 px-3">
    {#each imageIds as imageId, index}
        <Button
            variant="outline"
            class="relative flex-shrink-0 w-[88px] h-[88px] rounded-lg overflow-hidden p-0
                {index === activeIndex
                ? 'border-primary ring-2 ring-primary/30'
                : 'hover:border-muted-foreground/50'}"
            onclick={() => onselect(index)}
        >
            {#if thumbnails.get(imageId)}
                <img
                    src={thumbnails.get(imageId)}
                    alt="Image {index + 1}"
                    class="w-full h-full object-cover"
                />
                <Badge
                    variant="secondary"
                    class="absolute bottom-1 right-1 text-xs h-4 min-w-4 px-1"
                >
                    {index + 1}
                </Badge>
            {:else}
                <span class="text-xs text-muted-foreground">
                    {loading ? "..." : index + 1}
                </span>
            {/if}
        </Button>
    {/each}
</div>
