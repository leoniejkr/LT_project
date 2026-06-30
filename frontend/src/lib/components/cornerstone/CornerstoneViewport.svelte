<script lang="ts">
    import { onMount } from 'svelte';
    import { browser } from '$app/environment';
    import { initCornerstone, createToolGroup } from '$lib/cornerstone/init';
    import * as cornerstone from '@cornerstonejs/core';
    import { Enums } from '@cornerstonejs/core';

    interface Props {
        viewportId?: string;
        renderingEngineId?: string;
        toolGroupId?: string;
        imageIds?: string[];
    }

    let { 
        viewportId = 'my-viewport', 
        renderingEngineId = 'my-rendering-engine', 
        toolGroupId = 'my-tool-group', 
        imageIds = [] 
    }: Props = $props();

    let element: HTMLDivElement | undefined;
    let renderingEngine: cornerstone.RenderingEngine | undefined;

    console.log(`[CornerstoneViewport] Created with imageIds:`, imageIds);

    onMount(() => {
        if (!browser) return;

        console.log(`[CornerstoneViewport] onMount started, imageIds:`, imageIds);

        let resizeObserver: ResizeObserver | undefined;

        const setup = async () => {
            try {
                await initCornerstone();
            } catch (e) {
                console.error('[CornerstoneViewport] initCornerstone failed:', e);
                return;
            }
            if (!element) {
                console.error('[CornerstoneViewport] element not bound');
                return;
            }

            const existingEngine = cornerstone.getRenderingEngine(renderingEngineId);
            renderingEngine = existingEngine ?? new cornerstone.RenderingEngine(renderingEngineId);

            const toolGroup = createToolGroup(toolGroupId);

            renderingEngine.enableElement({
                viewportId,
                type: Enums.ViewportType.STACK,
                element,
                defaultOptions: {
                    background: [0, 0, 0] as [number, number, number],
                },
            });

            if (toolGroup) {
                toolGroup.addViewport(viewportId, renderingEngineId);
            }

            console.log(`[CornerstoneViewport] Viewport enabled, calling setStack with:`, imageIds);

            if (imageIds.length > 0) {
                try {
                    const viewport = renderingEngine.getViewport(viewportId) as cornerstone.Types.IStackViewport;
                    if (!viewport) {
                        console.error(`[CornerstoneViewport] getViewport returned undefined`);
                        return;
                    }
                    await viewport.setStack(imageIds);
                    viewport.render();
                    console.log(`[CornerstoneViewport] setStack + render completed`);
                } catch (e) {
                    console.error(`[CornerstoneViewport] setStack failed:`, e);
                }
            } else {
                console.warn(`[CornerstoneViewport] No imageIds provided`);
            }

            resizeObserver = new ResizeObserver(() => {
                if (renderingEngine) {
                    renderingEngine.resize(true, false);
                }
            });
            resizeObserver.observe(element);
        };

        setup().catch((e) => console.error('[CornerstoneViewport] setup error:', e));

        return () => {
            if (resizeObserver) resizeObserver.disconnect();
            if (renderingEngine) {
                renderingEngine.disableElement(viewportId);
            }
        };
    });
</script>

<div bind:this={element} class="cornerstone-viewport"></div>

<style>
    .cornerstone-viewport {
        width: 100%;
        height: 100%;
        min-height: 400px;
        background-color: #000;
        position: relative;
    }
</style>
