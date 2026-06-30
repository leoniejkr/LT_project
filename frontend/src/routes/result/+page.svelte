<script lang="ts">
    import { analysisResult, patientMetadata, uploadedFileUrl } from "$lib/stores.js";
    import { Button } from "$lib/components/ui/button/index.js";
    import { Badge } from "$lib/components/ui/badge/index.js";
    import { Separator } from "$lib/components/ui/separator/index.js";
    import * as Item from "$lib/components/ui/item/index.js";
    import * as Accordion from "$lib/components/ui/accordion/index.js";
    import { goto } from "$app/navigation";
    import CornerstoneViewport from "$lib/components/cornerstone/CornerstoneViewport.svelte";
    import { 
        Stethoscope,
        FileDigit,
        Undo2
    } from "lucide-svelte";
    import "../../app.css";

    const defaultResult = {
        status: "success",
        prediction: "Pneumonia",
        confidence: 0.85,
        confidence_reason: "The model detected significant opacities in the lower lobes consistent with pneumonia but there are certain uncertaincies.",
        model_version: "v1.0"
    };

    let result = $derived($analysisResult || defaultResult);
    
    const defaultMetadata = {
        id:"123",
        age: 62,
        gender: "Male",
        admittedToIcu: true,
        requiresVentilator: false,
        knownIllnesses: ["Covid", "Pneumonia"],
        symptoms: ["Cough", "Fever", "Dyspnea"],
    };

    let metadata = $derived($patientMetadata || defaultMetadata);

    let imageIds = $derived($uploadedFileUrl 
        ? [`wadouri:${$uploadedFileUrl}`] 
        : ["wadouri:/image-000001.dcm"]
    );

</script>

<div class="mt-6 mx-auto w-full max-w-5xl flex flex-col gap-6 px-6 pb-12">
    <div class="flex items-center justify-between border-b pb-4">
        <div>
            <header class="text-2xl font-bold tracking-tight flex items-center gap-2">
                Medical Analysis Dashboard
            </header>
            <h2 class="text-muted-foreground mt-1">
                Detailed AI diagnostics based on patient metadata and DICOM imaging
            </h2>
        </div>
    </div>

    {#if result}
        <Item.Root variant="outline">
            <div>Patient ID:{metadata.id}</div>
            <div>Age:{metadata.age}</div>
            <div>Gender:{metadata.gender}</div>
            <div>Admitted to ICU:{metadata.admittedToIcu ? "Yes" : "No"}</div>
            <div>Ventilator Required: {metadata.requiresVentilator ? "Yes" : "No"}</div>
        </Item.Root>

        <div class="grid grid-cols-1 lg:grid-cols-3 gap-6">
            <div class="lg:col-span-2 flex flex-col gap-2">
                <div class="border rounded-xl overflow-hidden bg-black flex flex-col relative h-[500px]">
                    <div class="bg-card px-4 py-2 border-b text-xs font-medium flex items-center justify-between text-muted-foreground z-10">
                        <span class="flex items-center gap-1.5">
                            <FileDigit size={14} /> DICOM Viewport
                        </span>
                        <span class="text-[10px] bg-muted px-2 py-0.5 rounded font-mono">
                            { $uploadedFileUrl ? "Uploaded DICOM File" : "image-000001.dcm (Mock)" }
                        </span>
                    </div>
                    <div class="flex-1 relative bg-black">
                        {#if imageIds.length > 0}
                            <CornerstoneViewport {imageIds} viewportId="result-viewport" />
                        {/if}
                    </div>
                </div>
                <div class="text-xs text-muted-foreground italic px-2">
                    * Interactive Viewport: Left-click and drag to adjust window level (contrast), right-click and drag to zoom, wheel to scroll stack.
                </div>
            </div>

            <div class="flex flex-col gap-4">
            <!-- TODO: else block einbauen (ein text), wenn es keine illnesses etc gibt -->
                 <Accordion.Root type="multiple">
                    <Accordion.Item value="illnesses">
                        <Accordion.Trigger>Known Illnesses</Accordion.Trigger>
                        <Accordion.Content class="gap-2">
                            {#each metadata.knownIllnesses as illness}
                                <Badge variant="outline" class="bg-amber-500/10 text-amber-600 border-amber-500/30">
                                    {illness}
                                </Badge>
                            {/each}
                        </Accordion.Content>
                    </Accordion.Item>

                    <Accordion.Item value="symptoms">
                        <Accordion.Trigger>Known Symptoms</Accordion.Trigger>
                        <Accordion.Content class="gap-2">
                            {#each metadata.symptoms as symptom}
                                <Badge variant="outline" class="bg-teal-500/10 text-teal-600 border-teal-500/30">
                                    {symptom}
                                </Badge>
                            {/each}
                        </Accordion.Content>
                    </Accordion.Item>
                </Accordion.Root>

                <Item.Root variant="outline">
                    <Item.Title class="flex items-center gap-2">
                        AI Diagnosis
                    </Item.Title>
                    <Separator />
                    <Item.Content class="flex-1 flex flex-col justify-between">
                        <div class="text-xs text-muted-foreground uppercase tracking-wider font-semibold">Prediction</div>
                        <div class="text-lg font-semibold flex items-center gap-2">
                            {result.prediction}
                        </div>
                    </Item.Content>
                    <Item.Footer class="text-muted-foreground">
                         Model: {result.model_version}
                    </Item.Footer>
                </Item.Root>
                
                <Item.Root variant="outline" class="border-wary/50 bg-wary/[0.03]">
                    <Item.Title class="text-wary pb-2">
                        AI Diagnostics Assessment
                    </Item.Title>
                    <Item.Content class="font-semibold text-lg">
                        {(typeof result.confidence === 'number' ? result.confidence * 100 : 0).toFixed(1)}% Confidence
                    </Item.Content>
                </Item.Root>

                <Item.Root variant="outline" class="border-primary/50 bg-primary/[0.03]">
                    <Item.Title class="text-primary font-semibold">
                        Assessement Reason
                    </Item.Title>
                    <Item.Description class="line-clamp-none">
                        {result.confidence_reason}
                    </Item.Description>
                </Item.Root>
            </div>
        </div>
        
    {:else}
        <Item.Root variant="outline" class="bg:primary">
            <Item.Content class="flex flex-col items-center justify-center p-8 text-center">
                <div class="w-12 h-12 rounded-full bg-muted flex items-center justify-center mb-4">
                    <Stethoscope size={24} class="text-muted-foreground" />
                </div>
                <Item.Title class="text-lg">No Results Available</Item.Title>
                <Item.Description class="max-w-md mt-2">
                    Please upload a DICOM chest X-ray file and enter patient metadata to generate an AI diagnostics report.
                </Item.Description>
                <Button class="mt-6 flex items-center gap-2" onclick={() => goto("/upload")}>
                    <Undo2 size={16} /> Back to Upload
                </Button>
            </Item.Content>
        </Item.Root>
    {/if}
</div>
