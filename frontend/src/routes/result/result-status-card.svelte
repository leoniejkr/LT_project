<script lang="ts">
    import { Button } from "$lib/components/ui/button/index.js";
    import { Skeleton } from "$lib/components/ui/skeleton/index.js";
    import * as Alert from "$lib/components/ui/alert/index.js";
    import * as Card from "$lib/components/ui/card/index.js";
    import * as Empty from "$lib/components/ui/empty/index.js";
    import { AlertTriangle, Stethoscope, Undo2 } from "lucide-svelte";

    interface Props {
        state: "loading" | "error" | "empty";
        error?: string;
        onretry?: () => void;
    }

    let { state, error = "", onretry }: Props = $props();
</script>

{#if state === "loading"}
    <Card.Root aria-busy="true" aria-label="Loading analysis">
        <Card.Header>
            <Skeleton class="h-5 w-40" />
            <Skeleton class="h-4 w-full max-w-md" />
        </Card.Header>
        <Card.Content class="space-y-4">
            <Skeleton class="h-28 w-full" />
            <div class="grid grid-cols-1 gap-4 md:grid-cols-3">
                <Skeleton class="h-36 w-full md:col-span-2" />
                <Skeleton class="h-36 w-full" />
            </div>
        </Card.Content>
    </Card.Root>
{:else if state === "error"}
    <Card.Root>
        <Card.Header>
            <Card.Title><h2>Analysis Results</h2></Card.Title>
            <Card.Description>
                The requested historic analysis is currently unavailable.
            </Card.Description>
        </Card.Header>
        <Card.Content>
            <Alert.Root variant="destructive">
                <AlertTriangle />
                <Alert.Title>Unable to load analysis</Alert.Title>
                <Alert.Description>{error}</Alert.Description>
                {#if onretry}
                    <Alert.Action>
                        <Button variant="destructive" size="sm" onclick={onretry}>
                            Try again
                        </Button>
                    </Alert.Action>
                {/if}
            </Alert.Root>
        </Card.Content>
    </Card.Root>
{:else}
    <Card.Root>
        <Card.Header>
            <Card.Title><h2>Analysis Results</h2></Card.Title>
            <Card.Description>
                Start an analysis to generate a detailed diagnostic report.
            </Card.Description>
        </Card.Header>
        <Card.Content>
            <Empty.Root>
                <Empty.Header>
                    <Empty.Media variant="icon"><Stethoscope /></Empty.Media>
                    <Empty.Title>No analysis yet</Empty.Title>
                    <Empty.Description>
                        Upload an X-Ray file and enter patient metadata. Your AI
                        diagnostics report will appear here automatically.
                    </Empty.Description>
                </Empty.Header>
                <Empty.Content>
                    <Button href="/upload"><Undo2 /> Go to Upload</Button>
                </Empty.Content>
            </Empty.Root>
        </Card.Content>
    </Card.Root>
{/if}
