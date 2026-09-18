<script lang="ts">
    import { onMount } from "svelte";
    import { Button } from "$lib/components/ui/button/index.js";
    import { Badge } from "$lib/components/ui/badge/index.js";
    import { Skeleton } from "$lib/components/ui/skeleton/index.js";
    import * as Card from "$lib/components/ui/card/index.js";
    import * as Empty from "$lib/components/ui/empty/index.js";
    import * as Table from "$lib/components/ui/table/index.js";
    import * as Alert from "$lib/components/ui/alert/index.js";
    import * as Tooltip from "$lib/components/ui/tooltip/index.js";
    import {
        ClipboardList,
        ChevronRight,
        TriangleAlert,
    } from "lucide-svelte";
    import type { PatientSummary } from "$lib/types";

    let patients = $state<PatientSummary[]>([]);
    let loading = $state(true);
    let error = $state("");

    async function loadPatients(signal?: AbortSignal) {
        loading = true;
        error = "";

        try {
            const response = await fetch("/api/patients", { signal });
            if (!response.ok) throw new Error(`Request failed with status ${response.status}`);
            patients = await response.json();
        } catch (cause) {
            if (cause instanceof Error && cause.name === "AbortError") return;
            console.error("Failed to load analysis history:", cause);
            error = "The analysis history could not be loaded.";
        } finally {
            if (!signal?.aborted) loading = false;
        }
    }

    onMount(() => {
        const controller = new AbortController();
        void loadPatients(controller.signal);

        return () => controller.abort();
    });
</script>

<div class="mt-6 mx-auto w-full max-w-6xl px-4 pb-12 sm:px-6">
    <div class="mb-6">
        <h1 class="text-2xl font-bold tracking-tight flex items-center gap-2">
            <ClipboardList size={24} /> Analysis History
        </h1>
        <p class="text-muted-foreground mt-1">
            Open a completed case to review its complete diagnostic report.
        </p>
    </div>

    <Card.Root>
        <Card.Header>
            <Card.Title><h2>Previous Analyses</h2></Card.Title>
            <Card.Description>
                Open a patient analysis to view its original dashboard.
            </Card.Description>
            {#if !loading && !error && patients.length > 0}
                <Card.Action>
                    <Badge variant="secondary">
                        {patients.length} {patients.length === 1 ? "analysis" : "analyses"}
                    </Badge>
                </Card.Action>
            {/if}
        </Card.Header>
        <Card.Content>
            {#if loading}
                <div
                    class="overflow-hidden rounded-lg border"
                    role="status"
                    aria-label="Loading analysis history"
                    aria-busy="true"
                >
                    <Table.Root>
                        <Table.Header class="bg-muted/50">
                            <Table.Row>
                                <Table.Head class="px-4">ID</Table.Head>
                                <Table.Head class="px-4">Age</Table.Head>
                                <Table.Head class="px-4">Gender</Table.Head>
                                <Table.Head class="px-4">
                                    <span class="sr-only">Open</span>
                                </Table.Head>
                            </Table.Row>
                        </Table.Header>
                        <Table.Body>
                            {#each Array(3) as _}
                                <Table.Row>
                                    <Table.Cell class="p-4">
                                        <Skeleton class="h-5 w-14" />
                                    </Table.Cell>
                                    <Table.Cell class="p-4">
                                        <Skeleton class="h-4 w-10" />
                                    </Table.Cell>
                                    <Table.Cell class="p-4">
                                        <Skeleton class="h-5 w-20" />
                                    </Table.Cell>
                                    <Table.Cell class="p-4">
                                        <Skeleton class="ml-auto size-8" />
                                    </Table.Cell>
                                </Table.Row>
                            {/each}
                        </Table.Body>
                    </Table.Root>
                </div>
            {:else if error}
                <Alert.Root variant="destructive">
                    <TriangleAlert />
                    <Alert.Title>Unable to load analysis history</Alert.Title>
                    <Alert.Description>{error}</Alert.Description>
                    <Alert.Action>
                        <Button
                            variant="destructive"
                            size="sm"
                            onclick={() => void loadPatients()}
                        >
                            Try again
                        </Button>
                    </Alert.Action>
                </Alert.Root>
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
                        <Button href="/upload">Start an analysis</Button>
                    </Empty.Content>
                </Empty.Root>
            {:else}
                <div class="overflow-hidden rounded-lg border">
                    <Table.Root>
                        <Table.Caption class="sr-only">
                            Completed patient analyses
                        </Table.Caption>
                        <Table.Header class="bg-muted/50 text-muted-foreground">
                            <Table.Row>
                                <Table.Head class="px-4">ID</Table.Head>
                                <Table.Head class="px-4">Age</Table.Head>
                                <Table.Head class="px-4">Gender</Table.Head>
                                <Table.Head class="px-4 text-right">
                                    <span class="sr-only">Open</span>
                                </Table.Head>
                            </Table.Row>
                        </Table.Header>
                        <Table.Body>
                            {#each patients as patient (patient.id)}
                                <Table.Row>
                                    <Table.Cell class="p-4 font-medium">
                                        <Badge variant="outline">#{patient.id}</Badge>
                                    </Table.Cell>
                                    <Table.Cell class="p-4">{patient.age}</Table.Cell>
                                    <Table.Cell class="p-4">
                                        <Badge variant="secondary">{patient.gender}</Badge>
                                    </Table.Cell>
                                    <Table.Cell class="p-4 text-right">
                                        <Tooltip.Root>
                                            <Tooltip.Trigger>
                                                {#snippet child({ props })}
                                                    <Button
                                                        {...props}
                                                        variant="outline"
                                                        size="sm"
                                                        href={`/result?patientId=${patient.id}`}
                                                        aria-label="Open analysis for patient {patient.id}"
                                                    >
                                                        Open
                                                        <ChevronRight />
                                                    </Button>
                                                {/snippet}
                                            </Tooltip.Trigger>
                                            <Tooltip.Content>Open analysis</Tooltip.Content>
                                        </Tooltip.Root>
                                    </Table.Cell>
                                </Table.Row>
                            {/each}
                        </Table.Body>
                    </Table.Root>
                </div>
            {/if}
        </Card.Content>
    </Card.Root>
</div>
