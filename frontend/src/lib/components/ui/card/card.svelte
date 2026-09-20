<script lang="ts">
	import { cn, type WithElementRef } from "$lib/utils.js";
	import type { HTMLAttributes } from "svelte/elements";

	let {
		ref = $bindable(null),
		class: className,
		children,
		size = "default",
		...restProps
	}: WithElementRef<HTMLAttributes<HTMLDivElement>> & { size?: "default" | "sm" } = $props();
</script>

<div
	bind:this={ref}
	data-slot="card"
	data-size={size}
	class={cn("gap-(--card-spacing) overflow-hidden rounded-4xl bg-card py-(--card-spacing) text-sm text-card-foreground shadow-md ring-1 ring-foreground/5 [--card-spacing:--spacing(6)] has-[>img:first-child]:pt-0 data-[size=sm]:[--card-spacing:--spacing(4)] dark:shadow-[0_12px_32px_rgba(0,0,0,0.45),inset_0_1px_0_rgba(255,255,255,0.05)] dark:ring-white/10 *:[img:first-child]:rounded-t-4xl *:[img:last-child]:rounded-b-4xl group/card flex flex-col", className)}
	{...restProps}
>
	{@render children?.()}
</div>
