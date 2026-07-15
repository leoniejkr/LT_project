<script lang="ts">
	import "../app.css";
	import favicon from '$lib/assets/favicon.svg';
	import Navigation from '$lib/components/navigation/navigation.svelte';
	import { ModeWatcher} from 'mode-watcher';
	import * as Tooltip from "$lib/components/ui/tooltip/index.js";

	let { children } = $props();
</script>

<svelte:head>
	<link rel="icon" href={favicon} />
</svelte:head>

<Tooltip.Provider>
	<div>
		<ModeWatcher />
		<Navigation />
	</div>

	{#if children}
		{@render children()}
	{/if}
</Tooltip.Provider>
