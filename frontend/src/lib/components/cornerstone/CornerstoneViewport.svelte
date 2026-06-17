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

    let element = $state<HTMLDivElement | null>(null);
    let renderingEngine: cornerstone.RenderingEngine | undefined = undefined;

    onMount(() => {
        if (!browser) return;

        let resizeObserver: ResizeObserver | undefined;

        const setup = async () => {
            await initCornerstone();
            if (!element) return;

            // Get the rendering engine
            const existingEngine = cornerstone.getRenderingEngine(renderingEngineId);
            if (existingEngine) {
                renderingEngine = existingEngine;
            } else {
                renderingEngine = new cornerstone.RenderingEngine(renderingEngineId);
            }

            // Create tool group
            const toolGroup = createToolGroup(toolGroupId);

            const viewportInput = {
                viewportId,
                type: Enums.ViewportType.STACK,
                element,
                defaultOptions: {
                    background: [0, 0, 0] as [number, number, number],
                },
            };

            renderingEngine.enableElement(viewportInput);

            // Add viewport to tool group
            if (toolGroup) {
                toolGroup.addViewport(viewportId, renderingEngineId);
            }

            if (imageIds.length > 0) {
                const viewport = renderingEngine.getViewport(viewportId) as cornerstone.Types.IStackViewport;
                await viewport.setStack(imageIds);
                viewport.render();
            }

            // Handle window resize
            resizeObserver = new ResizeObserver(() => {
                if (renderingEngine) {
                    renderingEngine.resize(true, false);
                }
            });
            resizeObserver.observe(element);
        };

        setup();

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
