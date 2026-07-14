<script lang="ts">
    // Wegen dem Verhalten der Navigationsmenuleiste musste die Komponente selbst implementiert werden
    // Die Implementation der UI Komponente hier wurde von der KI geschrieben und von mir angepasst

    import ToggleModeButton from "./toggle-mode-button.svelte";
    import { Button } from "../ui/button/index.js";
    import { goto } from "$app/navigation";
    import { page } from "$app/state";
    import SettingsButton from "./settings-button.svelte";
    import Logo from "$lib/assets/Logo.svg";

    const LINKS = [
        { name: "Home", href: "/" },
        { name: "Upload", href: "/upload" },
        { name: "Result", href: "/result" },
    ];

    // Hilfsfunktion für aktive Links (ähnlich wie NavigationMenu.Link)
    function isActive(href: string) {
        if (href === "/") return page.url.pathname === "/";
        return page.url.pathname.startsWith(href);
    }
</script>

<nav
    class="border-b px-6 h-14 flex items-center w-full bg-popover sticky top-0 z-50"
>
    <div class="flex items-center gap-4">
        <img src={Logo} alt="Logo" class="h-10 w-10" />
        {#each LINKS as link}
            <Button
                variant="link"
                size="lg"
                onclick={() => goto(link.href)}
                class={isActive(link.href)
                    ? "bg-muted text-primary"
                    : "text-muted-foreground"}
            >
                {link.name}
            </Button>
        {/each}
    </div>

    <!-- Spacer: Schiebt den Rest nach rechts -->
    <div class="flex-grow"></div>

    <div class="flex items-center gap-2">
        <SettingsButton />
        <ToggleModeButton />
    </div>
</nav>
