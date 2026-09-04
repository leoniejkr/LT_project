<script lang="ts">
	import "../../app.css";
	import * as Item from "$lib/components/ui/item/index.js";
	import { Badge } from "$lib/components/ui/badge/index.js";
	import { Button } from "$lib/components/ui/button/index.js";
	import * as Slider from "$lib/components/ui/slider/index.js";
	import { Label } from "$lib/components/ui/label/index.js";
	import { Separator } from "$lib/components/ui/separator/index.js";
	import { SlidersHorizontal, ChevronDown } from "lucide-svelte";
	import {
		DECISION_MODES,
		decisionMode,
		customThreshold,
		effectiveThreshold,
		isCustom,
		type DecisionMode,
	} from "$lib/settings";

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
	function toggle() {
		expanded = !expanded;
	}
</script>

<div class="mt-6 mx-auto w-full max-w-3xl flex flex-col gap-6 px-6 pb-12">
	<div class="flex items-center justify-between border-b pb-4">
		<div>
			<header
				class="text-2xl font-bold tracking-tight flex items-center gap-2"
			>
				<SlidersHorizontal size={22} />
				Settings
			</header>
			<h2 class="text-muted-foreground mt-1">
				Controls which classifier findings are accepted.
			</h2>
		</div>
	</div>

	<Item.Root variant="outline" class="flex-col items-stretch p-4">
		<div class="flex items-start gap-2">
			<Item.Header class="mb-2 flex-1 min-w-0">
				<Item.Title class="text-lg flex items-center gap-2">
					Decision Mode
					<Badge variant="secondary" class="text-xs">
						{$effectiveThreshold}% threshold
					</Badge>
				</Item.Title>
				<Item.Description class="text-sm">
					Sets the confidence threshold for findings on the dashboard.
				</Item.Description>
			</Item.Header>
			<Button
				variant="ghost"
				size="icon"
				class="mt-0.5 shrink-0"
				aria-label={expanded ? "Collapse Decision Mode" : "Expand Decision Mode"}
				aria-expanded={expanded}
				onclick={toggle}
			>
				<ChevronDown
					class="transition-transform duration-200 {expanded ? '' : 'rotate-180'}"
				/>
			</Button>
		</div>

		{#if expanded}
		<!-- segmented decision-mode control -->
		<div class="grid grid-cols-1 sm:grid-cols-2 gap-2">
			{#each DECISION_MODES as mode}
				<Button
					variant={$decisionMode === mode.value ? "default" : "outline"}
					class="flex items-center gap-3 h-auto py-3 px-4 justify-start text-left"
					aria-pressed={$decisionMode === mode.value}
					onclick={() => decisionMode.set(mode.value as DecisionMode)}
				>
					<span
						class="shrink-0 w-4 h-4 rounded-full border-2 grid place-items-center
							{$decisionMode === mode.value
							? 'border-white'
							: 'border-muted-foreground/50'}"
					>
						{#if $decisionMode === mode.value}
							<span class="w-2 h-2 rounded-full bg-white"></span>
						{/if}
					</span>
					<span class="min-w-0">
						<span class="block font-medium">{mode.label}</span>
						<span class="block text-xs opacity-80 normal-case">
							{mode.description}
						</span>
					</span>
				</Button>
			{/each}
		</div>

		<Separator class="my-5" />

		<!-- custom threshold, only enabled in custom mode -->
		<div class={$isCustom ? "" : "opacity-50"}>
			<div class="flex items-center gap-3 mb-2">
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
					class="flex-1 slider-thick"
				/>
				<Label class="min-w-8 text-right">{custom}%</Label>
			</div>
			<p class="text-xs text-muted-foreground mt-2">
				Slider is only draggable in Custom mode.
			</p>
		</div>
		{/if}
	</Item.Root>
</div>
