<script lang="ts">
    import { onMount } from "svelte";
    import { goto } from "$app/navigation";
    import { Button } from "$lib/components/ui/button/index.js";
    import * as Card from "$lib/components/ui/card/index.js";
    import * as Empty from "$lib/components/ui/empty/index.js";
    import { ClipboardList, ChevronRight, LoaderCircle } from "lucide-svelte";
    import type { PatientSummary } from "$lib/types";

    let patients = $state<PatientSummary[]>([]);
    let loading = $state(true);
    let error = $state("");

    onMount(async () => {
        try {
            const response = await fetch("/api/patients");
            if (!response.ok) throw new Error(`Request failed with status ${response.status}`);
            patients = await response.json();
        } catch (cause) {
            console.error("Failed to load analysis history:", cause);
            error = "The analysis history could not be loaded.";
        } finally {
            loading = false;
        }
    });

    function openAnalysis(id: number) {
        goto(`/result?patientId=${id}`);
    }
</script>

<div class="mt-6 mx-auto w-full max-w-6xl px-6 pb-12">
    <div class="mb-6">
        <header class="text-2xl font-bold tracking-tight flex items-center gap-2">
            <ClipboardList size={24} /> Analysis History
        </header>
        <p class="text-muted-foreground mt-1">
            Open a completed case to review its complete diagnostic report.
        </p>
    </div>

    <Card.Root>
        <Card.Header>
            <Card.Title>Previous Analyses</Card.Title>
            <Card.Description>
                Select a patient row to open the original analysis dashboard.
            </Card.Description>
        </Card.Header>
        <Card.Content>
            {#if loading}
                <div class="flex items-center justify-center gap-2 py-12 text-muted-foreground">
                    <LoaderCircle class="animate-spin" size={18} /> Loading history…
                </div>
            {:else if error}
                <p class="py-8 text-center text-destructive">{error}</p>
            {:else if patients.length === 0}
                <Empty.Root>
                    <Empty.Header>
                        <Empty.Media variant="icon"><ClipboardList /></Empty.Media>
                        <Empty.Title>No analyses yet</Empty.Title>
                        <Empty.Description>
                            Completed analyses will appear here automatically.
                        </Empty.Description>
                    </Empty.Header>
                    <Empty.Content>
                        <Button onclick={() => goto("/upload")}>Start an analysis</Button>
                    </Empty.Content>
                </Empty.Root>
            {:else}
                <div class="overflow-hidden rounded-lg border">
                    <table class="w-full text-sm">
                        <thead class="bg-muted/50 text-muted-foreground">
                            <tr class="border-b">
                                <th class="h-11 px-4 text-left font-medium">ID</th>
                                <th class="h-11 px-4 text-left font-medium">Age</th>
                                <th class="h-11 px-4 text-left font-medium">Gender</th>
                                <th class="h-11 px-4"><span class="sr-only">Open</span></th>
                            </tr>
                        </thead>
                        <tbody>
                            {#each patients as patient (patient.id)}
                                <tr
                                    class="cursor-pointer border-b last:border-0 transition-colors hover:bg-muted/50 focus-visible:bg-muted/50"
                                    role="link"
                                    tabindex="0"
                                    aria-label="Open analysis for patient {patient.id}"
                                    onclick={() => openAnalysis(patient.id)}
                                    onkeydown={(event) => {
                                        if (event.key === "Enter" || event.key === " ") openAnalysis(patient.id);
                                    }}
                                >
                                    <td class="p-4 font-medium">{patient.id}</td>
                                    <td class="p-4">{patient.age}</td>
                                    <td class="p-4">{patient.gender}</td>
                                    <td class="p-4 text-right text-muted-foreground"><ChevronRight size={18} class="inline" /></td>
                                </tr>
                            {/each}
                        </tbody>
                    </table>
                </div>
            {/if}
        </Card.Content>
    </Card.Root>
</div>
