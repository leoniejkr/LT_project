<script lang="ts">
    import { Badge } from "$lib/components/ui/badge/index.js";
    import { Button } from "$lib/components/ui/button/index.js";
    import { Checkbox } from "$lib/components/ui/checkbox/index.js";
    import * as Accordion from "$lib/components/ui/accordion/index.js";
    import * as Field from "$lib/components/ui/field/index.js";
    import type { SymptomTopic } from "$lib/symptoms";
    import { ChevronDown } from "lucide-svelte";
    import { untrack } from "svelte";
    import { selectedCountOf } from "./upload-utils";

    interface Props {
        topics: SymptomTopic[];
        selected: Record<string, boolean>;
        idPrefix: string;
    }

    let { topics, selected = $bindable(), idPrefix }: Props = $props();
    let openTopics = $state<Record<string, boolean>>(
        Object.fromEntries(
            untrack(() => topics.map((topic) => [topic.topic, true])),
        ),
    );
    let openGroupsByTopic = $state<Record<string, string[]>>(
        Object.fromEntries(
            untrack(() =>
                topics.map((topic) => [
                    topic.topic,
                    topic.groups.map((group) =>
                        groupKey(topic.topic, group.name),
                    ),
                ]),
            ),
        ),
    );

    function groupKey(topic: string, groupName?: string): string {
        return `${topic}::${groupName ?? ""}`;
    }
</script>

{#each topics as topic (topic.topic)}
    {@const topicCount = selectedCountOf(
        topic.groups.flatMap((group) => group.symptoms),
        selected,
    )}
    <div class="rounded-xl border p-4 w-full min-w-0 overflow-hidden break-words">
        <Button
            type="button"
            variant="ghost"
            class="h-auto w-full justify-between gap-4 whitespace-normal px-0 py-0 text-left hover:bg-transparent"
            onclick={() => (openTopics[topic.topic] = !openTopics[topic.topic])}
            aria-expanded={openTopics[topic.topic]}
        >
            <span class="flex items-center gap-2 font-medium">{topic.topic}</span>
            <span class="flex items-center gap-3">
                {#if topicCount > 0}
                    <Badge variant="secondary" class="text-xs">
                        {topicCount} selected
                    </Badge>
                {/if}
                <ChevronDown
                    size={16}
                    class="text-muted-foreground transition-transform {openTopics[
                        topic.topic
                    ]
                        ? ''
                        : '-rotate-90'}"
                />
            </span>
        </Button>

        {#if openTopics[topic.topic]}
            <Accordion.Root
                type="multiple"
                bind:value={openGroupsByTopic[topic.topic]}
                class="mt-3"
            >
                {#each topic.groups as group, groupIndex (group.name)}
                    {@const key = groupKey(topic.topic, group.name)}
                    {@const groupCount = selectedCountOf(group.symptoms, selected)}
                    <Accordion.Item
                        value={key}
                        class={groupIndex > 0 ? "border-t" : ""}
                    >
                        <Accordion.Trigger
                            class="py-2.5 hover:no-underline text-xs font-semibold uppercase tracking-wide text-muted-foreground"
                        >
                            <span class="flex items-center gap-2">
                                {group.name}
                                {#if groupCount > 0}
                                    <Badge
                                        variant="secondary"
                                        class="h-4 px-1.5 text-[10px] normal-case"
                                    >
                                        {groupCount}
                                    </Badge>
                                {/if}
                            </span>
                        </Accordion.Trigger>
                        <Accordion.Content>
                            <div
                                class="grid grid-cols-1 md:grid-cols-2 gap-x-8 gap-y-2.5 pb-1"
                            >
                                {#each group.symptoms as tag (tag.id)}
                                    <Field.Field
                                        orientation="horizontal"
                                        class="w-auto items-start"
                                    >
                                        <Checkbox
                                            id={`${idPrefix}-${tag.id}`}
                                            bind:checked={selected[tag.id]}
                                        />
                                        <Field.Label
                                            for={`${idPrefix}-${tag.id}`}
                                            class="font-normal leading-tight"
                                        >
                                            {tag.label}
                                        </Field.Label>
                                    </Field.Field>
                                {/each}
                            </div>
                        </Accordion.Content>
                    </Accordion.Item>
                {/each}
            </Accordion.Root>
        {/if}
    </div>
{/each}
