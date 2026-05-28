<script lang="ts">
import { Settings } from 'lucide-svelte';
import { Button } from "$lib/components/ui/button/index.js";
import { goto } from '$app/navigation';
</script>

<Button onclick={() => goto('/settings')} variant="outline" size="icon">
    <Settings class="h-5 w-5" />
    <span class="sr-only">Settings</span>
</Button>