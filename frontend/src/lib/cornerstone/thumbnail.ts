import { utilities } from '@cornerstonejs/core';
import { browser } from '$app/environment';
import { initCornerstone } from './init';

const cache = new Map<string, string>();

export async function generateThumbnail(
    imageId: string,
    size = 120,
): Promise<string | null> {
    const cacheKey = `${size}:${imageId}`;

    if (cache.has(cacheKey)) {
        return cache.get(cacheKey)!;
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
        cache.set(cacheKey, dataUrl);
        return dataUrl;
    } catch (e) {
        console.error('[Thumbnail] Failed for', imageId, e);
        return null;
    }
}
