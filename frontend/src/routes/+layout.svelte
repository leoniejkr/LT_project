<script lang="ts">
	import "../app.css";
	import favicon from '$lib/assets/favicon.svg';
	import Navigation from '$lib/components/navigation/navigation.svelte';
	import { ModeWatcher} from 'mode-watcher';

	let { children } = $props();
</script>

<svelte:head>
	<link rel="icon" href={favicon} />
</svelte:head>

<div>
	<ModeWatcher />
	<Navigation />
</div>

{#if children}
	{@render children()}
{/if}
