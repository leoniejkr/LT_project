import { utilities } from '@cornerstonejs/core';
import { browser } from '$app/environment';
import { initCornerstone } from './init';

const cache = new Map<string, string>();

export async function generateThumbnail(
    imageId: string,
    size = 120,
): Promise<string | null> {
    if (cache.has(imageId)) {
        return cache.get(imageId)!;
    }

    if (!browser) return null;

    try {
        await initCornerstone();

        const canvas = document.createElement('canvas');
        canvas.width = size;
        canvas.height = size;

        await utilities.loadImageToCanvas({
            canvas,
            imageId,
            thumbnail: true,
            useCPURendering: true,
        });

        const dataUrl = canvas.toDataURL();
        cache.set(imageId, dataUrl);
        return dataUrl;
    } catch (e) {
        console.error('[Thumbnail] Failed for', imageId, e);
        return null;
    }
}
