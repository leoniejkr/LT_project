<script lang="ts">
    import { Badge } from "$lib/components/ui/badge/index.js";
    import { Button } from "$lib/components/ui/button/index.js";
    import * as Card from "$lib/components/ui/card/index.js";
    import type { SymptomTopic } from "$lib/symptoms";
    import { ChevronDown, ClipboardCheck, ClipboardList } from "lucide-svelte";
    import TopicChecklist from "./topic-checklist.svelte";
    import { selectedCountOf } from "./upload-utils";

    interface Props {
        kind: "symptoms" | "history";
        title: string;
        description: string;
        contentId: string;
        topics: SymptomTopic[];
        selected: Record<string, boolean>;
    }

    let {
        kind,
        title,
        description,
        contentId,
        topics,
        selected = $bindable(),
    }: Props = $props();
    let open = $state(false);
    let tags = $derived(
        topics.flatMap((topic) =>
            topic.groups.flatMap((group) => group.symptoms),
        ),
    );
</script>

<Card.Root class="w-full">
    <Card.Header>
        <Button
            type="button"
            variant="ghost"
            class="h-auto w-full justify-between gap-2 whitespace-normal p-0 text-left hover:bg-transparent"
            onclick={() => (open = !open)}
            aria-expanded={open}
            aria-controls={contentId}
        >
            <span class="flex items-center gap-2 text-base font-medium">
                {#if kind === "symptoms"}
                    <ClipboardCheck size={18} />
                {:else}
                    <ClipboardList size={18} />
                {/if}
                {title}
            </span>
            <Badge variant="secondary" class="ml-auto hidden sm:inline-flex">
                {selectedCountOf(tags, selected)} selected
            </Badge>
            <ChevronDown
                size={18}
                class="text-muted-foreground shrink-0 transition-transform {open
                    ? ''
                    : '-rotate-90'}"
            />
        </Button>
        <Card.Description>{description}</Card.Description>
    </Card.Header>
    {#if open}
        <Card.Content id={contentId} class="flex flex-col gap-3">
            <TopicChecklist
                {topics}
                idPrefix={kind === "symptoms" ? "symptom" : "history"}
                bind:selected
            />
        </Card.Content>
    {/if}
</Card.Root>
