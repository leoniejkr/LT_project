<script lang="ts">
	import { NavigationMenu as NavigationMenuPrimitive } from "bits-ui";
	import { cn } from "$lib/utils.js";

	let {
		ref = $bindable(null),
		class: className,
		...restProps
	}: NavigationMenuPrimitive.ListProps = $props();
</script>

<NavigationMenuPrimitive.List
	bind:ref
	data-slot="navigation-menu-list"
	class={cn(
		"gap-1 flex flex-auto flex-wrap list-none items-center",
		className
	)}
	{...restProps}
/>
