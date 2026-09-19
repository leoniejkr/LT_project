<script lang="ts">
    import { Badge } from "$lib/components/ui/badge/index.js";
    import { Input } from "$lib/components/ui/input/index.js";
    import * as Card from "$lib/components/ui/card/index.js";
    import * as Field from "$lib/components/ui/field/index.js";
    import * as Select from "$lib/components/ui/select/index.js";
    import { UserSearch } from "lucide-svelte";

    interface Props {
        age: string;
        gender: string;
    }

    const genders = [
        { value: "woman", label: "Woman" },
        { value: "man", label: "Man" },
        { value: "diverse", label: "Diverse" },
    ];

    let { age = $bindable(), gender = $bindable() }: Props = $props();
    let genderLabel = $derived(
        genders.find((option) => option.value === gender)?.label ??
            "Select a Gender",
    );
</script>

<Card.Root class="h-full lg:col-span-3">
    <Card.Header>
        <Card.Title>
            <h2 class="flex items-center gap-2">
                <UserSearch size={18} /> Patient Metadata
            </h2>
        </Card.Title>
        <Card.Description>
            Add the patient context required for the diagnostic report.
        </Card.Description>
        <Card.Action>
            <Badge variant="destructive">Required</Badge>
        </Card.Action>
    </Card.Header>
    <Card.Content>
        <Field.Set>
            <Field.Legend class="sr-only">Patient Metadata</Field.Legend>
            <Field.Group>
                <div class="grid grid-cols-1 gap-3 sm:grid-cols-2">
                    <Field.Field>
                        <Field.Label for="age">Patient Age</Field.Label>
                        <Input
                            id="age"
                            type="number"
                            min="0"
                            max="130"
                            placeholder="Patient Age"
                            bind:value={age}
                            required
                        />
                    </Field.Field>
                    <Field.Field>
                        <Field.Label for="gender">Gender</Field.Label>
                        <Select.Root
                            type="single"
                            name="Select A Gender"
                            bind:value={gender}
                        >
                            <Select.Trigger id="gender" class="w-full">
                                {genderLabel}
                            </Select.Trigger>
                            <Select.Content>
                                <Select.Label>Gender</Select.Label>
                                {#each genders as option (option.value)}
                                    <Select.Item
                                        value={option.value}
                                        label={option.label}
                                    >
                                        {option.label}
                                    </Select.Item>
                                {/each}
                            </Select.Content>
                        </Select.Root>
                    </Field.Field>
                </div>
            </Field.Group>
        </Field.Set>
    </Card.Content>
</Card.Root>
