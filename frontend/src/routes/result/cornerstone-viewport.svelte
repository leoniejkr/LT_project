<script lang="ts">
    import { onMount } from "svelte";
    import { browser } from "$app/environment";
    import {
        initCornerstone,
        createToolGroup,
    } from "$lib/cornerstone/init";
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
    let renderRequestId = 0;

    onMount(() => {
        if (!browser) return;

        let disposed = false;
        let resizeObserver: ResizeObserver | undefined;
        let cleanupSetup: (() => void) | undefined;

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
            if (disposed) return;
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

            const preventContextMenu = (e: Event) => e.preventDefault();
            const preventMiddleClick = (e: MouseEvent) => {
                if (e.button === 1) e.preventDefault();
            };

            el.addEventListener("contextmenu", preventContextMenu);
            el.addEventListener("mousedown", preventMiddleClick);

            el.addEventListener(
                "CORNERSTONE_STACK_NEW_IMAGE",
                imageChangeHandler,
            );

            cleanupSetup = () => {
                el.removeEventListener("contextmenu", preventContextMenu);
                el.removeEventListener("mousedown", preventMiddleClick);
                el.removeEventListener(
                    "CORNERSTONE_STACK_NEW_IMAGE",
                    imageChangeHandler,
                );
                toolGroup?.removeViewports(renderingEngineId, viewportId);
            };
        };

        setup().catch((e) =>
            console.error("[CornerstoneViewport] setup error:", e),
        );

        return () => {
            disposed = true;
            viewportReady = false;
            renderRequestId += 1;
            cleanupSetup?.();
            resizeObserver?.disconnect();

            const engine = renderingEngine;
            if (engine?.getViewport(viewportId)) {
                engine.disableElement(viewportId);
            }
            renderingEngine = undefined;
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

        const requestId = ++renderRequestId;
        const renderWhenReady = (operation: Promise<unknown>) => {
            operation
                .then(() => {
                    if (requestId === renderRequestId && viewportReady) {
                        viewport.render();
                    }
                })
                .catch((error) => {
                    if (requestId === renderRequestId && viewportReady) {
                        console.error(
                            "[CornerstoneViewport] image rendering failed:",
                            error,
                        );
                    }
                });
        };

        if (isNewStack) {
            renderWhenReady(viewport.setStack(imageIds, activeImageIndex));
        } else {
            const currentIndex = viewport.getCurrentImageIdIndex();
            if (currentIndex !== activeImageIndex) {
                renderWhenReady(viewport.setImageIdIndex(activeImageIndex));
            }
        }
    });
</script>

<div
    bind:this={element}
    class="viewport-container"
    role="region"
    aria-label="Interactive medical image viewport"
></div>
