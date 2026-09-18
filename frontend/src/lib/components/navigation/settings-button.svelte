<script lang="ts">
	import { Settings } from "lucide-svelte";
	import { Button } from "$lib/components/ui/button/index.js";
</script>

<Button href="/settings" variant="outline" size="icon" aria-label="Settings">
	<Settings class="h-5 w-5" />
	<span class="sr-only">Settings</span>
</Button>
