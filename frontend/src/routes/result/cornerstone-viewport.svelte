<script lang="ts">
    import { onMount } from "svelte";
    import { browser } from "$app/environment";
    import {
        initCornerstone,
        createToolGroup,
    } from "$lib/components/cornerstone/init";
    import * as cornerstone from "@cornerstonejs/core";
    import { Enums } from "@cornerstonejs/core";

    interface Props {
        viewportId?: string;
        renderingEngineId?: string;
        toolGroupId?: string;
        imageIds?: string[];
        activeImageIndex?: number;
    }

    let {
        viewportId = "my-viewport",
        renderingEngineId = "my-rendering-engine",
        toolGroupId = "my-tool-group",
        imageIds = [],
        activeImageIndex = $bindable(0),
    }: Props = $props();

    let element: HTMLDivElement | undefined;
    let renderingEngine: cornerstone.RenderingEngine | undefined;
    let viewportReady = $state(false);

    onMount(() => {
        if (!browser) return;

        let resizeObserver: ResizeObserver | undefined;

        const setup = async () => {
            try {
                await initCornerstone();
            } catch (e) {
                console.error(
                    "[CornerstoneViewport] initCornerstone failed:",
                    e,
                );
                return;
            }
            if (!element) {
                console.error("[CornerstoneViewport] element not bound");
                return;
            }

            const el = element;

            const existingEngine =
                cornerstone.getRenderingEngine(renderingEngineId);
            renderingEngine =
                existingEngine ??
                new cornerstone.RenderingEngine(renderingEngineId);

            const toolGroup = createToolGroup(toolGroupId);

            renderingEngine.enableElement({
                viewportId,
                type: Enums.ViewportType.STACK,
                element: el,
                defaultOptions: {
                    background: [0, 0, 0] as [number, number, number],
                },
            });

            if (toolGroup) {
                toolGroup.addViewport(viewportId, renderingEngineId);
            }

            viewportReady = true;

            resizeObserver = new ResizeObserver(() => {
                if (renderingEngine) {
                    renderingEngine.resize(true, false);
                }
            });
            resizeObserver.observe(el);

            const imageChangeHandler = (e: Event) => {
                const ce = e as CustomEvent;
                const index = ce.detail?.imageIdIndex as number | undefined;
                if (typeof index === "number") {
                    activeImageIndex = index;
                }
            };

            el.addEventListener(
                "CORNERSTONE_STACK_NEW_IMAGE",
                imageChangeHandler,
            );

            return () => {
                el.removeEventListener(
                    "CORNERSTONE_STACK_NEW_IMAGE",
                    imageChangeHandler,
                );
            };
        };

        setup().catch((e) =>
            console.error("[CornerstoneViewport] setup error:", e),
        );

        return () => {
            if (resizeObserver) resizeObserver.disconnect();
            if (renderingEngine) {
                renderingEngine.disableElement(viewportId);
            }
        };
    });

    let prevImageIdsKey = "";

    $effect(() => {
        if (!browser || !viewportReady || !renderingEngine) return;
        if (imageIds.length === 0) return;

        const viewport = renderingEngine.getViewport(
            viewportId,
        ) as cornerstone.Types.IStackViewport;
        if (!viewport) return;

        const idsKey = imageIds.join(",");
        const isNewStack = idsKey !== prevImageIdsKey;
        prevImageIdsKey = idsKey;

        if (isNewStack) {
            viewport.setStack(imageIds, activeImageIndex).then(() => {
                viewport.render();
            });
        } else {
            const currentIndex = viewport.getCurrentImageIdIndex();
            if (currentIndex !== activeImageIndex) {
                viewport.setImageIdIndex(activeImageIndex).then(() => {
                    viewport.render();
                });
            }
        }
    });
</script>

<div bind:this={element} class="viewport-container"></div>
