<script lang="ts">
	import * as Empty from "$lib/components/ui/empty/index.js";
	import * as Item from "$lib/components/ui/item/index.js";
	import * as Field from "$lib/components/ui/field/index.js";
	import * as Select from "$lib/components/ui/select/index.js";
	import { Button } from "$lib/components/ui/button/index.js";
	import { Badge } from "$lib/components/ui/badge/index.js";
	import { Input } from "$lib/components/ui/input/index.js";
	import { Checkbox } from "$lib/components/ui/checkbox/index.js";
	import { Separator } from "$lib/components/ui/separator/index.js";
	import * as AlertDialog from "$lib/components/ui/alert-dialog/index.js";
	import {
		UserSearch,
		CloudUpload,
		ClipboardCheck,
		Cpu,
		ImageUp,
		LoaderCircle,
		X,
	} from "lucide-svelte";
	import { goto } from "$app/navigation";
	import {
		analysisResult,
		patientMetadata,
		uploadedFileUrls,
	} from "$lib/stores.js";
	import "../../app.css";
	import {
		SYMPTOM_TOPICS,
		ALL_SYMPTOM_TAGS,
		type SymptomTag,
	} from "$lib/symptoms";

	let { data }: { data: any } = $props();
	let files = $state<FileList | undefined>();
	const imageNumber = $derived(files?.length ?? 0);
	const genders = [
		{ value: "woman", label: "Woman" },
		{ value: "man", label: "Man" },
		{ value: "diverse", label: "Diverse" },
	];
	let value = $state("");
	const fieldLabel = $derived(
		genders.find((gender) => gender.value === value)?.label ??
			"Select a Gender",
	);

	// Patient Metadata
	let patientAge = $state("");

	// Known Illnesses
	let illnesses = $state({
		covid: false,
		pneumonia: false,
		emphysema: false,
		effusion: false,
		fibrosis: false,
	});

	// Symptoms (tag id -> checked)
	const allSymptomTags: SymptomTag[] = ALL_SYMPTOM_TAGS;
	const selectedSymptoms = $state<Record<string, boolean>>(
		Object.fromEntries(allSymptomTags.map((tag) => [tag.id, false])),
	);

	function selectedSymptomLabels(): string[] {
		return allSymptomTags
			.filter((tag) => selectedSymptoms[tag.id])
			.map((tag) => tag.label);
	}

	let showDialog = $state(false);
	let dialogMessage = $state("");

	let showAnalysisPanel = $state(false);
	let analysisController: AbortController | null = null;

	function abortAnalysis() {
		analysisController?.abort();
		analysisController = null;
		showAnalysisPanel = false;
		fetch("/api/analysis", { method: "DELETE" }).catch((e) =>
			console.error("Failed to clean up data after abort:", e),
		);
	}

	async function startAnalysis() {
		if (!files || files.length === 0) {
			dialogMessage = "Please upload at least one X-Ray file.";
			showDialog = true;
			return;
		}
		if (!patientAge || !value) {
			dialogMessage = "Please fill in age and gender.";
			showDialog = true;
			return;
		}

		try {
			await fetch("/api/analysis", { method: "DELETE" });
		} catch (e) {
			console.error("Failed to delete previous data:", e);
		}

		const formData = new FormData();

		for (const file of files) {
			formData.append("image_files", file);
		}

		const metadata = {
			age: parseInt(patientAge),
			gender: value,
			knownIllnesses: Object.keys(illnesses).filter(
				(k) => illnesses[k as keyof typeof illnesses],
			),
			symptoms: selectedSymptomLabels(),
		};

		formData.append("formData", JSON.stringify(metadata));

		console.log("Submitting Case:", metadata);

		try {
			analysisController = new AbortController();
			showAnalysisPanel = true;
			const response = await fetch("/api/analysis", {
				method: "POST",
				body: formData,
				signal: analysisController.signal,
			});
			const result = await response.json();
			console.log("Analysis Result:", result);

			if (!response.ok || result.status === "error") {
				dialogMessage = result.analysis?.error || `Analysis failed with status ${response.status}.`;
				showDialog = true;
				return;
			}

			analysisResult.set(result);
			patientMetadata.set(result.patient ?? metadata);
			uploadedFileUrls.set(
				Array.from(files ?? []).map((f) => URL.createObjectURL(f)),
			);
			goto("/result");
		} catch (error) {
			if (error instanceof DOMException && error.name === "AbortError") {
				return;
			}
			console.error("Analysis failed:", error);
			dialogMessage = `Analysis failed: ${error instanceof Error ? error.message : "Unknown error"}. Check if all services are running.`;
			showDialog = true;
		} finally {
			showAnalysisPanel = false;
			analysisController = null;
		}
	}

	// TODO: reusable components besonders bei der checklist der known illnesses
	// das kann man gut mit shadcn machen, aber das würde ich jetzt noch nciht machen,
	// sondern erst, wenn die funktionalität an sich steht und wir das später nocvh schöner machen wollen

	// TODO: required auch required machen
</script>

<div class="mt-6 mx-auto w-full max-w-5xl flex flex-col gap-6 px-6">
	<div>
		<header class="text-2xl font-bold tracking-tight">
			Case Input & Initialization
		</header>
		<h2 class="text-muted-foreground mt-1">
			Upload X-Ray images and contextualize patient metadata for AI
			analysis
		</h2>
	</div>

	<div class="flex items-start gap-6">
		<div class="w-4/7">
			<Item.Root variant="outline" class="flex flex-col h-full">
				<Item.Content>
					<Item.Title class="w-full justify-between">
						Radiological Scans (.png)
						<Badge variant="destructive">Required</Badge>
					</Item.Title>
					<Item.Media></Item.Media>
					<Empty.Root>
						<Empty.Header>
							<Empty.Media variant="icon">
								<CloudUpload />
							</Empty.Media>
							<Empty.Title>Upload X-Ray Files</Empty.Title>
							<Empty.Description>
								Support for standard X-Ray formats. Ensure
								everything is included in the upload.
							</Empty.Description>
						</Empty.Header>
						<Empty.Content>
							<ImageUp />
							<Input
								id="png_images"
								type="file"
								multiple
								bind:files
							/>
						</Empty.Content>
					</Empty.Root>
					<Item.Separator />
					<Item.Description>
						{imageNumber}
					</Item.Description>
				</Item.Content>
			</Item.Root>
		</div>

		<div class="flex-1">
			<Item.Root variant="outline" class="flex flex-col items-start">
				<Item.Content class="w-full">
					<Badge variant="destructive" class="ml-auto">Required</Badge
					>
					<form class="w-full">
						<Field.Set>
							<Field.Legend class="flex items-center gap-2">
								<UserSearch size={18} /> Patient Metadata
							</Field.Legend>
							<Field.Group>
								<div class="grid grid-cols-2 gap-3">
									<Field.Field>
										<Field.Label>Patient Age</Field.Label>
										<Input
											id="age"
											placeholder="Patient Age"
											bind:value={patientAge}
											required
										/>
									</Field.Field>
									<Field.Field>
										<Field.Label>Gender</Field.Label>
										<Select.Root
											type="single"
											name="Select A Gender"
											bind:value
										>
											<Select.Trigger>
												{fieldLabel}
											</Select.Trigger>
											<Select.Content>
												<Select.Label
													>Gender</Select.Label
												>
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
									<Field.Field
										orientation="horizontal"
										class="w-auto"
									></Field.Field>
									<Field.Field
										orientation="horizontal"
										class="w-auto"
									></Field.Field>
								</Field.Group>
							</Field.Group>
							<Field.Group
								class="flex-row flex-wrap gap-y-1 mt-4"
							>
								<Field.Legend
									class="w-full text-sm font-semibold"
								>
									Known Illnesses
								</Field.Legend>
								<Field.Field
									orientation="horizontal"
									class="w-auto"
								>
									<Checkbox
										id="covid"
										bind:checked={illnesses.covid}
									/>
									<Field.Label for="covid"
										>Covid19</Field.Label
									>
								</Field.Field>
								<Field.Field
									orientation="horizontal"
									class="w-auto"
								>
									<Checkbox
										id="pneumonia"
										bind:checked={illnesses.pneumonia}
									/>
									<Field.Label for="pneumonia"
										>Pneumonia</Field.Label
									>
								</Field.Field>
								<Field.Field
									orientation="horizontal"
									class="w-auto"
								>
									<Checkbox
										id="emphysema"
										bind:checked={illnesses.emphysema}
									/>
									<Field.Label for="emphysema"
										>Emphysema</Field.Label
									>
								</Field.Field>
								<Field.Field
									orientation="horizontal"
									class="w-auto"
								>
									<Checkbox
										id="effusion"
										bind:checked={illnesses.effusion}
									/>
									<Field.Label for="effusion"
										>Effusion</Field.Label
									>
								</Field.Field>
								<Field.Field
									orientation="horizontal"
									class="w-auto"
								>
									<Checkbox
										id="fibrosis"
										bind:checked={illnesses.fibrosis}
									/>
									<Field.Label for="fibrosis"
										>Fibrosis</Field.Label
									>
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
				<div
					class="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-x-8 gap-y-6"
				>
					{#each SYMPTOM_TOPICS as topic (topic.topic)}
						<div class="flex flex-col gap-3">
							<Field.Legend class="text-sm font-semibold">
								{topic.topic}
							</Field.Legend>
							{#each topic.groups as group (group.name ?? "")}
								{#if group.name}
									<p class="text-xs font-medium text-muted-foreground -mb-2">
										{group.name}
									</p>
								{/if}
								<div class="flex flex-col gap-2.5">
									{#each group.symptoms as tag (tag.id)}
										<Field.Field
											orientation="horizontal"
											class="w-auto items-start"
										>
											<Checkbox
												id={`symptom-${tag.id}`}
												bind:checked={selectedSymptoms[tag.id]}
											/>
											<Field.Label
												for={`symptom-${tag.id}`}
												class="flex flex-col gap-0.5 font-normal leading-tight"
											>
												<span>{tag.label}</span>
												{#if tag.description}
													<span
														class="text-xs text-muted-foreground"
													>
														{tag.description}
													</span>
												{/if}
											</Field.Label>
										</Field.Field>
									{/each}
								</div>
							{/each}
						</div>
					{/each}
				</div>
			</Item.Content>
		</Item.Root>
	</div>
	<Separator orientation="horizontal" class="self-stretch mt-1" />
	<div class="flex justify-end w-full pb-5">
		<Button type="button" onclick={startAnalysis}>
			<Cpu /> Start Analysis
		</Button>
	</div>
</div>

<AlertDialog.Root bind:open={showDialog}>
	<AlertDialog.Content size="sm">
		<AlertDialog.Header>
			<AlertDialog.Title>Analysis not Started</AlertDialog.Title>
			<AlertDialog.Description>{dialogMessage}</AlertDialog.Description>
		</AlertDialog.Header>
		<AlertDialog.Footer>
			<div class="col-span-2 flex justify-center">
				<AlertDialog.Action
					size="lg"
					class="w-1/2"
					onclick={() => (showDialog = false)}
				>
					OK
				</AlertDialog.Action>
			</div>
		</AlertDialog.Footer>
	</AlertDialog.Content>
</AlertDialog.Root>

<AlertDialog.Root bind:open={showAnalysisPanel}>
	<AlertDialog.Content size="sm" escapeKeydownBehavior="ignore">
		<AlertDialog.Header>
			<AlertDialog.Title class="flex items-center gap-2">
				<LoaderCircle class="size-5 animate-spin" />
				Analysis in Progress
			</AlertDialog.Title>
			<AlertDialog.Description>
				Your X-Ray images are being analyzed. This may take a moment.
				The application is blocked until the analysis finishes.
			</AlertDialog.Description>
		</AlertDialog.Header>
		<AlertDialog.Footer>
			<Button
				variant="destructive"
				class="w-full"
				onclick={abortAnalysis}
			>
				<X /> Abort Analysis
			</Button>
		</AlertDialog.Footer>
	</AlertDialog.Content>
</AlertDialog.Root>

<form method="POST"></form>
