<script lang="ts">
    import { scrollY, innerWidth } from 'svelte/reactivity/window';
    import * as NavigationMenu from '../ui/navigation-menu/index.js';
    import ToggleMode from './toggle-mode.svelte';
    import { Button } from '../ui/button/index.js';
    import { Settings } from 'lucide-svelte';
    import { goto } from '$app/navigation';

	const desktop = $derived(innerWidth.current ? innerWidth.current > 1024 : false);
	const scrolled = $derived(scrollY.current ? scrollY.current > 0 : false);
    
    const LINKS = [
        { name: 'Home', href: '/' },
        { name: 'Upload', href: '/upload' },
        { name: 'Diagnostics', href: '/diagnostics' },
        { name: 'Help', href: '/help' },
    ];
</script>

<NavigationMenu.Root>
    <NavigationMenu.List class="flex-wrap">

        {#each LINKS as link}
            <NavigationMenu.Item>
                <NavigationMenu.Link href={link.href}>
                    {link.name}
                </NavigationMenu.Link>
            </NavigationMenu.Item>
        {/each}

        <NavigationMenu.Item>
            <Button onclick={() => goto('/settings')} variant="outline" size="icon">
                <Settings class="h-4 w-4" />
                <span class="sr-only">Change Settings</span>
            </Button>
        </NavigationMenu.Item>

        <NavigationMenu.Item>
            <ToggleMode />
        </NavigationMenu.Item>

    </NavigationMenu.List>
</NavigationMenu.Root>

