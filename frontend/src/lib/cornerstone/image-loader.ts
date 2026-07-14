import * as cornerstone from '@cornerstonejs/core';
import { Enums } from '@cornerstonejs/core';

const canvas = document.createElement('canvas');
let lastImageIdDrawn = '';

function loadImage(
    imageId: string,
): { promise: Promise<cornerstone.Types.IImage>; cancelFn?: () => void } {
    const url = imageId.replace(/^png:/, '');

    const promise = new Promise<cornerstone.Types.IImage>((resolve, reject) => {
        const img = new Image();
        img.crossOrigin = 'anonymous';
        img.onload = () => {
            const rows = img.naturalHeight;
            const columns = img.naturalWidth;

            canvas.width = columns;
            canvas.height = rows;
            const ctx = canvas.getContext('2d')!;
            ctx.drawImage(img, 0, 0);
            lastImageIdDrawn = imageId;

            const imageData = ctx.getImageData(0, 0, columns, rows);

            const pixelData = new Uint8Array(columns * rows * 3);
            for (let i = 0, j = 0; i < imageData.data.length; i += 4, j += 3) {
                pixelData[j] = imageData.data[i];
                pixelData[j + 1] = imageData.data[i + 1];
                pixelData[j + 2] = imageData.data[i + 2];
            }

            function getPixelData(targetBuffer?: {
                arrayBuffer: ArrayBuffer;
                offset: number;
                length: number;
            }) {
                if (targetBuffer) {
                    const target = new Uint8Array(
                        targetBuffer.arrayBuffer,
                        targetBuffer.offset,
                        targetBuffer.length,
                    );
                    for (
                        let i = 0, j = 0;
                        i < imageData.data.length;
                        i += 4, j += 3
                    ) {
                        target[j] = imageData.data[i];
                        target[j + 1] = imageData.data[i + 1];
                        target[j + 2] = imageData.data[i + 2];
                    }
                    return target;
                }
                return pixelData;
            }

            function getCanvas() {
                if (lastImageIdDrawn === imageId) return canvas;
                canvas.width = columns;
                canvas.height = rows;
                const c = canvas.getContext('2d')!;
                c.drawImage(img, 0, 0);
                lastImageIdDrawn = imageId;
                return canvas;
            }

            const image: cornerstone.Types.IImage = {
                imageId,
                minPixelValue: 0,
                maxPixelValue: 255,
                slope: 1,
                intercept: 0,
                windowCenter: [128],
                windowWidth: [255],
                voiLUTFunction: Enums.VOILUTFunctionType.LINEAR,
                getPixelData,
                getCanvas,
                rows,
                columns,
                height: rows,
                width: columns,
                color: true,
                rgba: false,
                numberOfComponents: 3,
                columnPixelSpacing: 1,
                rowPixelSpacing: 1,
                invert: false,
                sizeInBytes: columns * rows * 3,
                dataType:
                    'Uint8Array' as cornerstone.Types.PixelDataTypedArrayString,
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

export function registerMetaDataProvider() {
    cornerstone.metaData.addProvider((type, imageId) => {
        if (!imageId.startsWith('png:')) return undefined;

        if (type === 'imagePixelModule') {
            return {
                pixelRepresentation: 0,
                bitsAllocated: 24,
                bitsStored: 24,
                highBit: 24,
                photometricInterpretation: 'RGB',
                samplesPerPixel: 3,
            };
        }
        if (type === 'generalSeriesModule') {
            return { modality: 'SC', seriesNumber: 1 };
        }
        if (type === 'voiLutModule') {
            return { windowWidth: [256], windowCenter: [128] };
        }
        if (type === 'modalityLutModule') {
            return { rescaleSlope: 1, rescaleIntercept: 0 };
        }
        return undefined;
    }, 1000);
}
