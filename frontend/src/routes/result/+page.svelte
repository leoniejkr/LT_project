<script lang="ts">
    import { analysisResult } from "$lib/stores.js";
    import * as Item from "$lib/components/ui/item/index.js";
    import { Button } from "$lib/components/ui/button/index.js";
    import { goto } from "$app/navigation";
    import "../../app.css";

    let result = $derived($analysisResult);
</script>

<div class="mt-6 mx-auto w-full max-w-5xl flex flex-col gap-6 px-6">
    <div>
        <header class="text-2xl font-bold tracking-tight">
            Analysis Results
        </header>
        <h2 class="text-muted-foreground mt-1">
            Detailed AI analysis and diagnostics based on the provided data
        </h2>
    </div>

    {#if result}
        <Item.Root variant="outline">
            <Item.Content>
                <Item.Title>Summary</Item.Title>
                <div class="mt-4">
                    <p><strong>Status:</strong> {result.status}</p>
                    {#if result.id}
                        <p><strong>Patient ID:</strong> {result.id}</p>
                    {/if}
                    {#if result.prediction}
                        <p><strong>Prediction:</strong> {result.prediction}</p>
                        <p>
                            <strong>Confidence:</strong>
                            {(result.confidence * 100).toFixed(2)}%
                        </p>
                    {/if}
                </div>

                <div class="mt-6">
                    <h3 class="font-semibold mb-2">Raw JSON Data:</h3>
                    <pre
                        class="bg-muted p-4 rounded-md overflow-auto text-sm">{JSON.stringify(
                            result,
                            null,
                            2,
                        )}</pre>
                </div>
            </Item.Content>
        </Item.Root>
    {:else}
        <Item.Root variant="outline">
            <Item.Content>
                <Item.Title>No result found</Item.Title>
                <Item.Description
                    >Please go back and start an analysis first.</Item.Description
                >
                <Button class="mt-4" onclick={() => goto("/upload")}
                    >Back to Upload</Button
                >
            </Item.Content>
        </Item.Root>
    {/if}

    <div class="flex justify-end">
        <Button variant="outline" onclick={() => goto("/upload")}
            >Start New Analysis</Button
        >
    </div>
</div>
