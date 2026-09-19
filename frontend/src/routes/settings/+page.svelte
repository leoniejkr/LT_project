<script lang="ts">
	import "../../app.css";
	import * as Card from "$lib/components/ui/card/index.js";
	import { Badge } from "$lib/components/ui/badge/index.js";
	import { Button } from "$lib/components/ui/button/index.js";
	import * as Slider from "$lib/components/ui/slider/index.js";
	import { Label } from "$lib/components/ui/label/index.js";
	import { Separator } from "$lib/components/ui/separator/index.js";
	import * as Select from "$lib/components/ui/select/index.js";
	import { SlidersHorizontal, ChevronDown, Cpu, BrainCircuit } from "lucide-svelte";
	import {
		DECISION_MODES,
		decisionMode,
		customThreshold,
		effectiveThreshold,
		isCustom,
		type DecisionMode,
	} from "$lib/settings";
	import {
		CLASSIFIER_MODELS,
		LLM_MODELS,
		classifierModel,
		llmModel,
		classifierLabel,
		llmLabel,
		selectedClassifier,
		selectedLLM,
	} from "$lib/models";

	// Local editable copy of the threshold so the slider can be bound.
	// In custom mode, dragging writes back into the store; otherwise the
	// slider is disabled and simply mirrors the active preset threshold.
	let custom = $state($effectiveThreshold);
	$effect(() => {
		if ($isCustom) {
			customThreshold.set(custom);
		} else {
			custom = $effectiveThreshold;
		}
	});

	let expanded = $state(true);
	let modelExpanded = $state(true);
	function toggle() {
		expanded = !expanded;
	}
	function toggleModel() {
		modelExpanded = !modelExpanded;
	}

	// Model selection (bound locally, pushed into the stores so the rest of
	// the app + the analysis request use the active selection).
	let cls = $state($classifierModel);
	let llm = $state($llmModel);
	$effect(() => {
		classifierModel.set(cls);
	});
	$effect(() => {
		llmModel.set(llm);
	});
</script>

<div class="mt-6 mx-auto w-full max-w-6xl flex flex-col gap-6 px-4 pb-12 sm:px-6">
	<div>
		<h1 class="flex items-center gap-2 text-2xl font-bold tracking-tight">
			<SlidersHorizontal size={22} />
			Settings
		</h1>
		<p class="mt-1 text-muted-foreground">
			Controls which classifier findings are accepted.
		</p>
	</div>

	<Card.Root>
		<Card.Header>
			<Card.Title class="flex flex-wrap items-center gap-2 text-lg">
				<h2>Decision Mode</h2>
				<Badge variant="secondary" class="text-xs">
					{$effectiveThreshold}% threshold
				</Badge>
			</Card.Title>
			<Card.Description>
				Confidence threshold for displayed findings.
			</Card.Description>
			<Card.Action>
				<Button
					variant="ghost"
					size="icon"
					aria-label={expanded ? "Collapse Decision Mode" : "Expand Decision Mode"}
					aria-expanded={expanded}
					onclick={toggle}
				>
					<ChevronDown
						class="transition-transform duration-200 {expanded ? '' : 'rotate-180'}"
					/>
				</Button>
			</Card.Action>
		</Card.Header>

		{#if expanded}
			<Card.Content>
				<!-- segmented decision-mode control -->
				<div class="grid grid-cols-1 gap-2 sm:grid-cols-2">
					{#each DECISION_MODES as mode}
						<Button
							variant={$decisionMode === mode.value ? "default" : "outline"}
							class="flex h-auto items-center justify-start gap-3 px-4 py-3 text-left"
							aria-pressed={$decisionMode === mode.value}
							onclick={() => decisionMode.set(mode.value as DecisionMode)}
						>
							<span
								class="grid size-4 shrink-0 place-items-center rounded-full border-2
									{$decisionMode === mode.value
									? 'border-white'
									: 'border-muted-foreground/50'}"
							>
								{#if $decisionMode === mode.value}
									<span class="size-2 rounded-full bg-white"></span>
								{/if}
							</span>
							<span class="min-w-0">
								<span class="block font-medium">{mode.label}</span>
								<span class="block text-xs normal-case opacity-80">
									{mode.description}
								</span>
							</span>
						</Button>
					{/each}
				</div>

				<Separator class="my-5" />

				<!-- custom threshold, only enabled in custom mode -->
				<div class={$isCustom ? "" : "opacity-50"}>
					<div class="mb-2 flex items-center gap-3">
						<Label class="whitespace-nowrap">
							Custom confidence threshold
						</Label>
						<Badge variant="outline" class="text-xs">
							{$isCustom ? "Active" : "Disabled"}
						</Badge>
					</div>
					<div class="flex items-center gap-3">
						<Slider.Root
							type="single"
							bind:value={custom}
							min={0}
							max={100}
							step={1}
							disabled={!$isCustom}
							class="slider-thick flex-1"
						/>
						<Label class="min-w-8 text-right">{custom}%</Label>
					</div>
					<p class="mt-2 text-xs text-muted-foreground">
						Slider is only draggable in Custom mode.
					</p>
				</div>
			</Card.Content>
		{/if}
	</Card.Root>

	<Card.Root>
		<Card.Header>
			<Card.Title class="flex items-center gap-2 text-lg">
				<h2>Model Selection / Architecture</h2>
			</Card.Title>
			<Card.Description>
				Select the image classifier and report-writing LLM.
			</Card.Description>
			<Card.Action>
				<Button
					variant="ghost"
					size="icon"
					aria-label={modelExpanded ? "Collapse Model Selection" : "Expand Model Selection"}
					aria-expanded={modelExpanded}
					onclick={toggleModel}
				>
					<ChevronDown
						class="transition-transform duration-200 {modelExpanded ? '' : 'rotate-180'}"
					/>
				</Button>
			</Card.Action>
		</Card.Header>

		{#if modelExpanded}
			<Card.Content>
				<div class="grid grid-cols-1 gap-6 md:grid-cols-2">
					<div>
						<Label class="mb-2 flex items-center gap-2">
							<Cpu size={16} /> Classifier Model
						</Label>
						<Select.Root type="single" bind:value={cls}>
							<Select.Trigger class="w-full justify-between">
								{classifierLabel(cls)}
							</Select.Trigger>
							<Select.Content>
								<Select.Label>Classifier</Select.Label>
								{#each CLASSIFIER_MODELS as m (m.id)}
									<Select.Item value={m.id} label={m.label}>
										{m.label}
									</Select.Item>
								{/each}
							</Select.Content>
						</Select.Root>
						<p class="mt-2 text-xs text-muted-foreground">
							{$selectedClassifier?.description}
						</p>
					</div>

					<div>
						<Label class="mb-2 flex items-center gap-2">
							<BrainCircuit size={16} /> LLM Model
						</Label>
						<Select.Root type="single" bind:value={llm}>
							<Select.Trigger class="w-full justify-between">
								{llmLabel(llm)}
							</Select.Trigger>
							<Select.Content>
								<Select.Label>LLM</Select.Label>
								{#each LLM_MODELS as m (m.id)}
									<Select.Item value={m.id} label={m.label}>
										{m.label}
									</Select.Item>
								{/each}
							</Select.Content>
						</Select.Root>
						<p class="mt-2 text-xs text-muted-foreground">
							{$selectedLLM?.description}
						</p>
					</div>
				</div>
			</Card.Content>
		{/if}
	</Card.Root>
</div>
