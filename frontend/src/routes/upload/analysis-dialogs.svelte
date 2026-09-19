<script lang="ts">
    import { Button } from "$lib/components/ui/button/index.js";
    import * as AlertDialog from "$lib/components/ui/alert-dialog/index.js";
    import { LoaderCircle, X } from "lucide-svelte";

    interface Props {
        errorOpen: boolean;
        errorMessage: string;
        progressOpen: boolean;
        onabort: () => void;
    }

    let {
        errorOpen = $bindable(),
        errorMessage,
        progressOpen = $bindable(),
        onabort,
    }: Props = $props();
</script>

<AlertDialog.Root bind:open={errorOpen}>
    <AlertDialog.Content size="sm">
        <AlertDialog.Header>
            <AlertDialog.Title>Analysis not Started</AlertDialog.Title>
            <AlertDialog.Description>{errorMessage}</AlertDialog.Description>
        </AlertDialog.Header>
        <AlertDialog.Footer>
            <div class="col-span-2 flex justify-center">
                <AlertDialog.Action
                    size="lg"
                    class="w-1/2"
                    onclick={() => (errorOpen = false)}
                >
                    OK
                </AlertDialog.Action>
            </div>
        </AlertDialog.Footer>
    </AlertDialog.Content>
</AlertDialog.Root>

<AlertDialog.Root bind:open={progressOpen}>
    <AlertDialog.Content size="sm" escapeKeydownBehavior="ignore">
        <AlertDialog.Header>
            <AlertDialog.Title class="flex items-center gap-2">
                <LoaderCircle class="size-5 animate-spin" />
                Analysis in Progress
            </AlertDialog.Title>
            <AlertDialog.Description>
                Your X-Ray images are being analyzed. This may take a moment. The
                application is blocked until the analysis finishes.
            </AlertDialog.Description>
        </AlertDialog.Header>
        <AlertDialog.Footer>
            <Button
                variant="destructive"
                class="col-span-full w-full justify-center"
                onclick={onabort}
            >
                <X /> Abort Analysis
            </Button>
        </AlertDialog.Footer>
    </AlertDialog.Content>
</AlertDialog.Root>
