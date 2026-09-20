<script lang="ts">
    import { onMount } from "svelte";
    import { Button } from "$lib/components/ui/button/index.js";
    import { Badge } from "$lib/components/ui/badge/index.js";
    import { Skeleton } from "$lib/components/ui/skeleton/index.js";
    import * as Card from "$lib/components/ui/card/index.js";
    import * as Empty from "$lib/components/ui/empty/index.js";
    import * as Table from "$lib/components/ui/table/index.js";
    import * as Alert from "$lib/components/ui/alert/index.js";
    import * as AlertDialog from "$lib/components/ui/alert-dialog/index.js";
    import * as Tooltip from "$lib/components/ui/tooltip/index.js";
    import {
        ClipboardList,
        ChevronRight,
        LoaderCircle,
        Trash2,
        TriangleAlert,
    } from "lucide-svelte";
    import type { PatientSummary } from "$lib/types";

    let patients = $state<PatientSummary[]>([]);
    let loading = $state(true);
    let error = $state("");
    let deleteError = $state("");
    let deleteDialogOpen = $state(false);
    let deleteAllDialogOpen = $state(false);
    let selectedPatient = $state<PatientSummary>();
    let deletingPatientId = $state<number>();
    let deletingAll = $state(false);

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

    function confirmDelete(patient: PatientSummary) {
        selectedPatient = patient;
        deleteDialogOpen = true;
    }

    async function deletePatient(patient: PatientSummary) {
        deletingPatientId = patient.id;
        deleteError = "";

        try {
            const response = await fetch(`/api/patients/${patient.id}`, {
                method: "DELETE",
            });
            if (!response.ok) throw new Error(`Request failed with status ${response.status}`);
            patients = patients.filter((entry) => entry.id !== patient.id);
            deleteDialogOpen = false;
            selectedPatient = undefined;
        } catch (cause) {
            console.error(`Failed to delete patient ${patient.id}:`, cause);
            deleteError = `Analysis #${patient.id} could not be deleted.`;
        } finally {
            deletingPatientId = undefined;
        }
    }

    async function deleteAllPatients() {
        deletingAll = true;
        deleteError = "";

        try {
            const response = await fetch("/api/analysis", { method: "DELETE" });
            if (!response.ok) throw new Error(`Request failed with status ${response.status}`);
            patients = [];
            deleteAllDialogOpen = false;
        } catch (cause) {
            console.error("Failed to delete all analyses:", cause);
            deleteError = "The analysis history could not be deleted.";
        } finally {
            deletingAll = false;
        }
    }
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
                    <div class="flex items-center gap-2">
                        <Badge variant="secondary">
                            {patients.length} {patients.length === 1 ? "analysis" : "analyses"}
                        </Badge>
                        <Button
                            variant="destructive"
                            size="sm"
                            disabled={deletingAll || deletingPatientId !== undefined}
                            onclick={() => (deleteAllDialogOpen = true)}
                        >
                            {#if deletingAll}
                                <LoaderCircle class="animate-spin" />
                            {:else}
                                <Trash2 />
                            {/if}
                            Delete all
                        </Button>
                    </div>
                </Card.Action>
            {/if}
        </Card.Header>
        <Card.Content>
            {#if deleteError}
                <Alert.Root variant="destructive" class="mb-4">
                    <TriangleAlert />
                    <Alert.Title>Unable to delete analysis</Alert.Title>
                    <Alert.Description>{deleteError}</Alert.Description>
                </Alert.Root>
            {/if}
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
                                        <div class="flex justify-end gap-2">
                                            <Tooltip.Root>
                                                <Tooltip.Trigger>
                                                    {#snippet child({ props })}
                                                        <Button
                                                            {...props}
                                                            variant="outline"
                                                            size="sm"
                                                            href={`/result?patientId=${patient.id}`}
                                                            aria-label="Open analysis for patient {patient.id}"
                                                            disabled={deletingAll || deletingPatientId !== undefined}
                                                        >
                                                            Open
                                                            <ChevronRight />
                                                        </Button>
                                                    {/snippet}
                                                </Tooltip.Trigger>
                                                <Tooltip.Content>Open analysis</Tooltip.Content>
                                            </Tooltip.Root>
                                            <Tooltip.Root>
                                                <Tooltip.Trigger>
                                                    {#snippet child({ props })}
                                                        <Button
                                                            {...props}
                                                            variant="destructive"
                                                            size="icon-sm"
                                                            aria-label="Delete analysis for patient {patient.id}"
                                                            disabled={deletingAll || deletingPatientId !== undefined}
                                                            onclick={() => confirmDelete(patient)}
                                                        >
                                                            {#if deletingPatientId === patient.id}
                                                                <LoaderCircle class="animate-spin" />
                                                            {:else}
                                                                <Trash2 />
                                                            {/if}
                                                        </Button>
                                                    {/snippet}
                                                </Tooltip.Trigger>
                                                <Tooltip.Content>Delete analysis</Tooltip.Content>
                                            </Tooltip.Root>
                                        </div>
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

<AlertDialog.Root bind:open={deleteDialogOpen}>
    <AlertDialog.Content size="sm">
        <AlertDialog.Header>
            <AlertDialog.Title>Delete analysis?</AlertDialog.Title>
            <AlertDialog.Description>
                Analysis #{selectedPatient?.id} and all associated patient data and images will
                be permanently deleted. This action cannot be undone.
            </AlertDialog.Description>
        </AlertDialog.Header>
        <AlertDialog.Footer>
            <AlertDialog.Cancel>Cancel</AlertDialog.Cancel>
            <AlertDialog.Action
                variant="destructive"
                disabled={deletingPatientId !== undefined}
                onclick={() => selectedPatient && void deletePatient(selectedPatient)}
            >
                {#if deletingPatientId !== undefined}
                    <LoaderCircle class="animate-spin" /> Deleting
                {:else}
                    <Trash2 /> Delete
                {/if}
            </AlertDialog.Action>
        </AlertDialog.Footer>
    </AlertDialog.Content>
</AlertDialog.Root>

<AlertDialog.Root bind:open={deleteAllDialogOpen}>
    <AlertDialog.Content size="sm">
        <AlertDialog.Header>
            <AlertDialog.Title>Delete all analyses?</AlertDialog.Title>
            <AlertDialog.Description>
                All {patients.length} analyses, patient data, original images, and heatmaps will be
                permanently deleted. This action cannot be undone.
            </AlertDialog.Description>
        </AlertDialog.Header>
        <AlertDialog.Footer>
            <AlertDialog.Cancel>Cancel</AlertDialog.Cancel>
            <AlertDialog.Action
                variant="destructive"
                disabled={deletingAll}
                onclick={() => void deleteAllPatients()}
            >
                {#if deletingAll}
                    <LoaderCircle class="animate-spin" /> Deleting
                {:else}
                    <Trash2 /> Delete all
                {/if}
            </AlertDialog.Action>
        </AlertDialog.Footer>
    </AlertDialog.Content>
</AlertDialog.Root>
