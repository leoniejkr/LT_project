<script lang="ts">
    import * as Empty from "$lib/components/ui/empty/index.js"
    import * as Item  from "$lib/components/ui/item/index.js";
    import * as Field from "$lib/components/ui/field/index.js";
	import * as Select  from "$lib/components/ui/select/index.js"
	import { Button } from "$lib/components/ui/button/index.js";
	import { Badge } from "$lib/components/ui/badge/index.js";
	import { Input } from "$lib/components/ui/input/index.js"
	import { Checkbox } from "$lib/components/ui/checkbox/index.js";
	import { Separator } from "$lib/components/ui/separator/index.js";
	import { UserSearch, CloudUpload, ClipboardCheck, Cpu } from 'lucide-svelte';
	import "../../app.css";

	let { data }: { data: any } = $props();

	const genders = [
		{ value: "woman", label: "Woman"},
		{ value: "man", label: "Man"},
		{ value: "diverse", label: "Diverse"},
	]
	let value = $state("");
	const fieldLabel = $derived(
		genders.find(gender => gender.value === value)?.label ?? "Select a Gender"
	);
// TODO: Für den upload müssete man hier wahrscheinlich noch eine ShadCN Form Komponente hinzufügen.
// Spätestens für die Metadaten denke ich: Form + Checkbox + Select
// erster div Container ex., damit metadaten rechts plazierbar werden können später
// Formelle Form mit formsnap und superform ist glaube ich overkill also würde ich nativ html form nutzen mit Field ui comp

// TODO: reusable components besonders bei der checklist der known illnesses
// das kann man gut mit shadcn machen, aber das würde ich jetzt noch nciht machen, 
// sondern erst, wenn die funktionalität an sich steht und wir das später nocvh schöner machen wollen

// TODO: das styling mit funktionalität versehen
</script>

<div class="mt-6 ml-10 w-full max-w-5xl flex flex-col gap-6">
	<div>
		<header class="text-2xl font-bold tracking-tight">Case Input & Initialization</header>
		<h2 class="text-muted-foreground mt-1">Upload DICOM payload and contextualize patient metadata for AI analysis</h2>
	</div>

	<div class="flex items-start gap-6">
		<div class="w-4/7">
			<Item.Root variant="outline" class="flex flex-col h-full">
				<Item.Content>
					<Item.Title class="w-full justify-between">
						Radiological Scans (.dcm)
						<Badge variant="secondary">Required</Badge>
					</Item.Title>
					<Item.Media>
					</Item.Media>
					<Empty.Root>
						<Empty.Header>
							<Empty.Media variant="icon">
								<CloudUpload/>
							</Empty.Media>
							<Empty.Title>Upload DICOM Files</Empty.Title>
							<Empty.Description>
								Support for standart DICOM formats. Ensure everything is included in the upload.
							</Empty.Description>
						</Empty.Header>
						<Empty.Content>
							<Button variant="outline">
								Browse Local Storage
							</Button>
						</Empty.Content>
					</Empty.Root>
					<Item.Separator/>
					<Item.Description>
						0 files staged for upload TODO: variabel!
					</Item.Description>
				</Item.Content>
			</Item.Root>
		</div>

		<div class="flex-1">
			<Item.Root variant="outline" class="flex flex-col items-start">
				<Item.Content class="w-full">
					<form class="w-full">
						<Field.Set>
							<Field.Legend class="flex items-center gap-2">
								<UserSearch size={18} /> Patient Metadata
							</Field.Legend>
							<Field.Group>
								<div class="grid grid-cols-2 gap-3">
									<Field.Field>
										<Field.Label>
											Patient Age
										</Field.Label>
										<Input
											id="mysteriös"
											placeholder="Patient Age"
											required
										/>
									</Field.Field>
									<Field.Field>
										<Field.Label>
											Gender
										</Field.Label>
										<Select.Root type="single" name="Select A Gender" bind:value>
											<Select.Trigger>
												{fieldLabel}
											</Select.Trigger>
											<Select.Content>
												<Select.Label>Gender</Select.Label>
												{#each genders as gender (gender.value)}
													<Select.Item 
														value={gender.value}
														label={gender.label}
														>
														{gender.label}
													</Select.Item>
												{/each}
											</Select.Content>
										</Select.Root>
									</Field.Field>
								</div>
								<Field.Group class="flex-wrap flex-row mt-4">
									<Field.Field orientation="horizontal" class="w-auto">
										<Checkbox id="icu"/>
										<Field.Label for="icu">
											Admitted to ICU
										</Field.Label>
									</Field.Field>
									<Field.Field orientation="horizontal" class="w-auto">
										<Checkbox id="ventilator"/>
										<Field.Label for="ventilator">
											Requires Ventilator
										</Field.Label>
									</Field.Field>
								</Field.Group>
							</Field.Group>
							<Field.Group class="flex-row flex-wrap gap-y-1 mt-4">
								<Field.Legend class="w-full text-sm font-semibold">
									Known Illnesses
								</Field.Legend>
								<Field.Field orientation="horizontal" class="w-auto">
									<Checkbox id="covid" />
									<Field.Label for="covid">Covid</Field.Label>
								</Field.Field>
								<Field.Field orientation="horizontal" class="w-auto">
									<Checkbox id="pneumonia" />
									<Field.Label for="pneumonia">Pneumonia</Field.Label>
								</Field.Field>
								<Field.Field orientation="horizontal" class="w-auto">
									<Checkbox id="emphysema" />
									<Field.Label for="emphysema">Emphysema</Field.Label>
								</Field.Field>
								<Field.Field orientation="horizontal" class="w-auto">
									<Checkbox id="effusion" />
									<Field.Label for="effusion">Effusion</Field.Label>
								</Field.Field>
								<Field.Field orientation="horizontal" class="w-auto">
									<Checkbox id="fibrosis" />
									<Field.Label for="fibrosis">Fibrosis</Field.Label>
								</Field.Field>
							</Field.Group>
						</Field.Set>
					</form>
				</Item.Content>
			</Item.Root>
		</div>
	</div>

	<div class="w-full">
		<Item.Root variant="outline">
			<Item.Content>
				<Item.Title class="flex items-center gap-2 mb-4">
					<ClipboardCheck size={18} /> Symptom Checklist
				</Item.Title>
				<div class="flex flex-wrap gap-x-8 gap-y-3">
					<Field.Field orientation="horizontal" class="w-auto">
						<Checkbox id="cough" />
						<Field.Label for="cough">Cough</Field.Label>
					</Field.Field>
					<Field.Field orientation="horizontal" class="w-auto">
						<Checkbox id="fever" />
						<Field.Label for="fever">Fever</Field.Label>
					</Field.Field>
					<Field.Field orientation="horizontal" class="w-auto">
						<Checkbox id="dyspnea" />
						<Field.Label for="dyspnea">Shortness of breath</Field.Label>
					</Field.Field>
					<Field.Field orientation="horizontal" class="w-auto">
						<Checkbox id="fatigue" />
						<Field.Label for="fatigue">Fatigue</Field.Label>
					</Field.Field>
				</div>
			</Item.Content>
		</Item.Root>
	</div>
	<Separator orientation="horizontal" class="self-stretch mt-1" />
	<div class="flex justify-end w-full pb-5">
		<Button>
			<Cpu /> Start Analysis
		</Button>
	</div>
</div>

<form method="POST">
</form>