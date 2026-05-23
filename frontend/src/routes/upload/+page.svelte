<script lang="ts">
    import  * as Empty from "$lib/components/ui/empty/index.js"
    import * as Item  from "$lib/components/ui/item/index.js";
    import * as Field from "$lib/components/ui/field/index.js";
	import * as Select  from "$lib/components/ui/select/index.js"
	import { Button } from "$lib/components/ui/button/index.js";
	import { Badge } from "$lib/components/ui/badge/index.js";
	import { Input } from "$lib/components/ui/input/index.js"
	import { Checkbox } from "$lib/components/ui/checkbox/index.js";
	import { CloudUpload } from 'lucide-svelte';
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

</script>

<div class="mt-6 ml-10 w-full max-w-5xl">
	<div class="mb-6">
		<header class="text-2xl font-bold tracking-tight">Case Input & Initialization</header>
		<h2 class="text-muted-foreground mt-1">Upload DICOM payload and contextualize patient metadata for AI analysis</h2>
	</div>
	<div class="flex flex-auto gap-6">
		<div class="w-3/5">
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
			<Item.Root variant="outline" class="flex flex-col h-3/4 items-start">
				<Item.Content class="w-full">
					<form class="w-full">
						<Field.Group>
							<Field.Set>
								<Field.Legend>
									Patient Metadata
								</Field.Legend>
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
								<div class="flex grid-cols-1 gap-5 mt-1">
									<div class="flex items-center space-x-2">
										<Checkbox id="icu"/>
										<Field.Label for="icu">
											Admitted to ICU
										</Field.Label>
									</div>
									<div class="flex items-center space-x-2">
										<Checkbox id="ventilator"/>
										<Field.Label for="ventilator">
											Requires Ventilator
										</Field.Label>
									</div>
								</div>
							</Field.Set>
								<Field.Separator/>
								<div>
									<Field.Field>
										<Field.Legend>
											Additional Metadata
										</Field.Legend>
									</Field.Field>
								</div>
						</Field.Group>
					</form>
				</Item.Content>
			</Item.Root>
		</div>
	</div>
</div>

<form method="POST">
</form>