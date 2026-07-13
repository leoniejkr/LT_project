import * as cornerstone from '@cornerstonejs/core';
import * as cornerstoneTools from '@cornerstonejs/tools';
import { browser } from '$app/environment';
import { registerPNGLoader } from './image-loader';

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

    cornerstone.init();
    cornerstoneTools.init();

    cornerstoneTools.addTool(WindowLevelTool);
    cornerstoneTools.addTool(PanTool);
    cornerstoneTools.addTool(ZoomTool);
    cornerstoneTools.addTool(StackScrollTool);

    registerPNGLoader();

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

        // TODO: bindings ändern zu speziellen buttons.
        // konkurrieren mit browserfunktionen
        toolGroup.setToolActive(WindowLevelTool.toolName, {
            bindings: [{ mouseButton: csToolsEnums.MouseBindings.Primary }],
        });
        toolGroup.setToolActive(PanTool.toolName, {
            bindings: [{ mouseButton: csToolsEnums.MouseBindings.Auxiliary }],
        });
        toolGroup.setToolActive(ZoomTool.toolName, {
            bindings: [{ mouseButton: csToolsEnums.MouseBindings.Secondary }],
        });
        toolGroup.setToolActive(StackScrollTool.toolName, {
            bindings: [{ mouseButton: csToolsEnums.MouseBindings.Wheel as cornerstoneTools.Enums.MouseBindings }],
        });
    }

    return toolGroup;
}
