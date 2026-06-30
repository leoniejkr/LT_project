import * as cornerstone from '@cornerstonejs/core';
import * as cornerstoneTools from '@cornerstonejs/tools';
import cornerstoneDICOMImageLoader from '@cornerstonejs/dicom-image-loader';
import dicomParser from 'dicom-parser';
import { browser } from '$app/environment';

const {
    WindowLevelTool,
    PanTool,
    ZoomTool,
    StackScrollTool,
    ToolGroupManager,
    Enums: csToolsEnums,
} = cornerstoneTools;

let initialized = false;

export async function initCornerstone() {
    if (!browser || initialized) {
        return;
    }

    // 1. Initialize Core
    await cornerstone.init();

    // 2. Initialize Tools
    await cornerstoneTools.init();

    // Add tools to cornerstone
    cornerstoneTools.addTool(WindowLevelTool);
    cornerstoneTools.addTool(PanTool);
    cornerstoneTools.addTool(ZoomTool);
    cornerstoneTools.addTool(StackScrollTool);

    // 3. Configure DICOM Image Loader
    // In @cornerstonejs/dicom-image-loader v4.22.x, init() registers the
    // wadouri/dicomweb/dicomfile schemes internally via registerImageLoader
    // from @cornerstonejs/core, so no external setup is needed.
    cornerstoneDICOMImageLoader.init({
        maxWebWorkers: Math.max(navigator.hardwareConcurrency - 1, 1),
        beforeSend: (xhr, imageId, defaultHeaders, params) => {
            return { 'Cache-Control': 'no-cache' };
        },
    });

    initialized = true;
    console.log('CornerstoneJS initialized with basic tools');
}

export function createToolGroup(toolGroupId: string) {
    let toolGroup = ToolGroupManager.getToolGroup(toolGroupId);
    
    if (!toolGroup) {
        toolGroup = ToolGroupManager.createToolGroup(toolGroupId);
    }
    
    if (toolGroup) {
        toolGroup.addTool(WindowLevelTool.toolName);
        toolGroup.addTool(PanTool.toolName);
        toolGroup.addTool(ZoomTool.toolName);
        toolGroup.addTool(StackScrollTool.toolName);

        toolGroup.setToolActive(WindowLevelTool.toolName, {
            bindings: [{ mouseButton: csToolsEnums.MouseBindings.Primary }],
        });
        toolGroup.setToolActive(PanTool.toolName, {
            bindings: [{ mouseButton: csToolsEnums.MouseBindings.Auxiliary }],
        });
        toolGroup.setToolActive(ZoomTool.toolName, {
            bindings: [{ mouseButton: csToolsEnums.MouseBindings.Secondary }],
        });
        // Bind stack scroll to mouse wheel
        toolGroup.setToolActive(StackScrollTool.toolName, {
            bindings: [{ mouseButton: csToolsEnums.MouseBindings.Wheel as unknown as cornerstoneTools.Enums.MouseBindings }],
        });
    }
    
    return toolGroup;
}
