<script lang="ts">
    import { Badge } from "$lib/components/ui/badge/index.js";
    import * as Card from "$lib/components/ui/card/index.js";
    import type { PatientData, PatientMetadata } from "$lib/types";

    interface Props {
        patient: PatientData | null;
        metadata: PatientMetadata | null;
    }

    let { patient, metadata }: Props = $props();
</script>

<div class="flex flex-col gap-6">
    <Card.Root size="sm">
        <Card.Header>
            <Card.Title><h2>Patient Information</h2></Card.Title>
        </Card.Header>
        <Card.Content class="flex flex-col gap-1">
            <span class="text-sm"><strong>Patient ID:</strong> {patient?.id}</span>
            <span class="text-sm"><strong>Age:</strong> {patient?.age}</span>
            <span class="text-sm"><strong>Gender:</strong> {patient?.gender}</span>
        </Card.Content>
    </Card.Root>

    <Card.Root size="sm">
        <Card.Header>
            <Card.Title><h2>Known Symptoms</h2></Card.Title>
        </Card.Header>
        <Card.Content class="flex flex-wrap gap-2">
            {#each patient?.symptoms ?? metadata?.symptoms ?? [] as symptom}
                <Badge variant="outline" class="symptom-badge">{symptom}</Badge>
            {/each}
        </Card.Content>
    </Card.Root>

    <Card.Root size="sm">
        <Card.Header>
            <Card.Title><h2>Medical History & Risk Factors</h2></Card.Title>
        </Card.Header>
        <Card.Content class="flex flex-wrap gap-2">
            {#each patient?.history ?? metadata?.history ?? [] as entry}
                <Badge variant="outline" class="symptom-badge">{entry}</Badge>
            {/each}
        </Card.Content>
    </Card.Root>
</div>
