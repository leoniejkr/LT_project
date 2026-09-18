<script lang="ts">
    // Wegen dem Verhalten der Navigationsmenuleiste musste die Komponente selbst implementiert werden
    // Die Implementation der UI Komponente hier wurde von der KI geschrieben und von mir angepasst

    import ToggleModeButton from "./toggle-mode-button.svelte";
    import { Button } from "../ui/button/index.js";
    import { page } from "$app/state";
    import SettingsButton from "./settings-button.svelte";
    import Logo from "$lib/assets/Logo.svg";

    const LINKS = [
        { name: "Home", href: "/" },
        { name: "Upload", href: "/upload" },
        { name: "Result", href: "/result" },
        { name: "History", href: "/history" },
    ];

    // Hilfsfunktion für aktive Links (ähnlich wie NavigationMenu.Link)
    function isActive(href: string) {
        if (href === "/") return page.url.pathname === "/";
        return page.url.pathname.startsWith(href);
    }
</script>

<nav
    aria-label="Main navigation"
    class="border-b h-14 flex items-center gap-2 w-full bg-popover sticky top-0 z-50 overflow-x-auto px-2 sm:px-6"
>
    <div class="flex items-center gap-1 sm:gap-2">
        <img src={Logo} alt="TrustAI" class="hidden h-12 w-12 md:block" />
        {#each LINKS as link}
            <Button
                variant="link"
                size="sm"
                href={link.href}
                aria-current={isActive(link.href) ? "page" : undefined}
                class="px-2 sm:px-3 {isActive(link.href)
                    ? 'bg-muted text-primary'
                    : 'text-muted-foreground'}"
            >
                {link.name}
            </Button>
        {/each}
    </div>

    <!-- Spacer: Schiebt den Rest nach rechts -->
    <div class="min-w-2 flex-grow"></div>

    <div class="flex items-center gap-2">
        <SettingsButton />
        <ToggleModeButton />
    </div>
</nav>
