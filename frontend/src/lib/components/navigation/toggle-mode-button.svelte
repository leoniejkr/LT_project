<script lang="ts">
 import { SunIcon, MoonIcon } from "lucide-svelte";
 import { toggleMode } from "mode-watcher";
 import { Button } from "$lib/components/ui/button/index.js";
</script>
 
<Button onclick={toggleMode} variant="outline" size="icon">
    <SunIcon class="h-4 w-4 scale-100 rotate-0 !transition-all dark:scale-0 dark:-rotate-90"/>
    <MoonIcon class="absolute h-4 w-4 scale-0 rotate-90 !transition-all dark:scale-100 dark:rotate-0"/>
 <span class="sr-only">Toggle theme</span>
</Button>