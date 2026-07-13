import * as cornerstone from '@cornerstonejs/core';
import { Enums } from '@cornerstonejs/core';

function loadImage(
    imageId: string,
): { promise: Promise<cornerstone.Types.IImage>; cancelFn?: () => void } {
    const url = imageId.replace(/^png:/, '');

    const promise = new Promise<cornerstone.Types.IImage>((resolve, reject) => {
        const img = new Image();
        img.crossOrigin = 'anonymous';
        img.onload = () => {
            const canvas = document.createElement('canvas');
            canvas.width = img.naturalWidth;
            canvas.height = img.naturalHeight;
            const ctx = canvas.getContext('2d')!;
            ctx.drawImage(img, 0, 0);

            const imageData = ctx.getImageData(0, 0, canvas.width, canvas.height);
            const numPixels = canvas.width * canvas.height;
            const pixelData = new Float32Array(numPixels);

            for (let i = 0; i < numPixels; i++) {
                const r = imageData.data[i * 4];
                const g = imageData.data[i * 4 + 1];
                const b = imageData.data[i * 4 + 2];
                pixelData[i] = 0.299 * r + 0.587 * g + 0.114 * b;
            }

            const windowCenter = 127.5;
            const windowWidth = 255;

            const image: cornerstone.Types.IImage = {
                imageId,
                minPixelValue: 0,
                maxPixelValue: 255,
                slope: 1,
                intercept: 0,
                windowCenter,
                windowWidth,
                voiLUTFunction: Enums.VOILUTFunctionType.LINEAR,
                getPixelData: () => pixelData,
                getCanvas: () => canvas,
                rows: canvas.height,
                columns: canvas.width,
                height: canvas.height,
                width: canvas.width,
                color: false,
                rgba: false,
                numberOfComponents: 1,
                columnPixelSpacing: 1,
                rowPixelSpacing: 1,
                invert: false,
                sizeInBytes: pixelData.byteLength,
                dataType: 'Float32Array' as cornerstone.Types.PixelDataTypedArrayString,
                photometricInterpretation: 'MONOCHROME2',
            };

            resolve(image);
        };
        img.onerror = () => reject(new Error(`Failed to load image: ${url}`));
        img.src = url;
    });

    return { promise };
}

export function registerPNGLoader() {
    cornerstone.registerImageLoader('png', loadImage);
}
