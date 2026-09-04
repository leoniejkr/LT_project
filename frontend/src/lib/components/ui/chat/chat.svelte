<script lang="ts">
	import { Bot, Send, User, X } from "lucide-svelte";
	import { Button } from "$lib/components/ui/button/index.js";
	import { Input } from "$lib/components/ui/input/index.js";
	import * as Item from "$lib/components/ui/item/index.js";
	import { cn } from "$lib/utils.js";
	import { llmModel } from "$lib/models";

	let {
		class: className,
		apiEndpoint = "/api/chat",
		context = undefined,
	}: {
		class?: string;
		apiEndpoint?: string;
		context?: Record<string, unknown>;
	} = $props();

	let open = $state(false);
	let input = $state("");
	let messages = $state<{ role: "user" | "assistant"; content: string }[]>(
		[],
	);
	let loading = $state(false);
	let chatWindowRef = $state<HTMLDivElement | null>(null);

	function scrollToBottom() {
		if (chatWindowRef) {
			chatWindowRef.scrollTop = chatWindowRef.scrollHeight;
		}
	}

	$effect(() => {
		messages;
		setTimeout(scrollToBottom, 0);
	});

	async function sendMessage() {
		const text = input.trim();
		if (!text || loading) return;

		messages = [...messages, { role: "user", content: text }];
		input = "";
		loading = true;

		try {
			const res = await fetch(apiEndpoint, {
				method: "POST",
				headers: { "Content-Type": "application/json" },
				body: JSON.stringify({
					message: text,
					history: messages,
					model: $llmModel,
					...(context ? { context } : {}),
				}),
			});

			if (!res.ok) throw new Error(`HTTP ${res.status}`);

			const data = await res.json();
			const reply =
				data.reply ??
				data.message ??
				data.content ??
				"Keine Antwort erhalten.";
			messages = [...messages, { role: "assistant", content: reply }];
		} catch {
			messages = [
				...messages,
				{
					role: "assistant",
					content: "Error: Inquiry could not be processed.",
				},
			];
		} finally {
			loading = false;
		}
	}

	function handleKeydown(e: KeyboardEvent) {
		if (e.key === "Enter" && !e.shiftKey) {
			e.preventDefault();
			sendMessage();
		}
	}

	function toggle() {
		open = !open;
		if (open) {
			setTimeout(() => {
				const inputEl =
					document.querySelector<HTMLElement>("[data-chat-input]");
				inputEl?.focus();
			}, 100);
		}
	}
</script>

<div class={cn("fixed bottom-6 right-6 z-50 grid", className)}>
	<Button
		size="icon-lg"
		variant="default"
		onclick={toggle}
		class="col-start-1 row-start-1 size-14 shadow-primary/30 rounded-full shadow-lg transition-transform hover:scale-110 active:scale-95"
	>
		{#if open}
			<X class="size-5" />
		{:else}
			<Bot class="size-7" />
		{/if}
	</Button>

	{#if open}
		<div
			class="bg-card border-border col-start-1 row-start-1 z-10 flex w-80 flex-col overflow-hidden rounded-xl border shadow-lg sm:w-96"
		>
			<Item.Root
				variant="muted"
				class="bg-primary text-primary-foreground rounded-none px-4 py-3"
			>
				<Item.Media variant="icon">
					<Bot class="text-primary-foreground size-lg" />
				</Item.Media>
				<Item.Content>
					<Item.Title class="text-primary-foreground"
						>AI-Assistant</Item.Title
					>
				</Item.Content>
				<Item.Actions>
					<Button
						variant="ghost"
						size="icon-xs"
						onclick={toggle}
						class="text-primary-foreground hover:bg-primary-foreground/20 hover:text-primary-foreground"
					>
						<X class="size-4" />
					</Button>
				</Item.Actions>
			</Item.Root>

			<div
				bind:this={chatWindowRef}
				class="bg-background/50 flex h-80 flex-col overflow-y-auto p-2"
			>
				{#if messages.length === 0}
					<div
						class="text-muted-foreground flex flex-1 items-center justify-center text-sm"
					>
						Ask me anything about the analysis results...
					</div>
				{:else}
					<Item.Group class="gap-1">
						{#each messages as msg, i}
							{#if i > 0}
								<Item.Separator />
							{/if}
							<Item.Root
								size="sm"
								class={cn(
									"rounded-lg",
									msg.role === "user"
										? "bg-primary/10 justify-end"
										: "bg-muted/50",
								)}
							>
								{#if msg.role === "assistant"}
									<Item.Media variant="icon">
										<Bot
											class="text-muted-foreground size-4"
										/>
									</Item.Media>
								{/if}
								<Item.Content>
									<Item.Description
										class={cn(
											"line-clamp-none",
											msg.role === "user"
												? "text-right"
												: "",
										)}
									>
										{msg.content}
									</Item.Description>
								</Item.Content>
								{#if msg.role === "user"}
									<Item.Media variant="icon">
										<User class="text-primary size-4" />
									</Item.Media>
								{/if}
							</Item.Root>
						{/each}
						{#if loading}
							<Item.Separator />
							<Item.Root size="sm" class="rounded-lg bg-muted/50">
								<Item.Media variant="icon">
									<Bot class="text-muted-foreground size-4" />
								</Item.Media>
								<Item.Content>
									<Item.Description>
										<span class="animate-pulse"
											>Writing...</span
										>
									</Item.Description>
								</Item.Content>
							</Item.Root>
						{/if}
					</Item.Group>
				{/if}
			</div>

			<Item.Root
				class="border-border bg-background rounded-none border-t px-3 py-3"
			>
				<Item.Content>
					<Input
						data-chat-input
						bind:value={input}
						onkeydown={handleKeydown}
						placeholder="Type a message..."
						disabled={loading}
						class="flex-1"
					/>
				</Item.Content>
				<Item.Actions>
					<Button
						size="icon"
						onclick={sendMessage}
						disabled={loading || !input.trim()}
					>
						<Send class="size-4" />
					</Button>
				</Item.Actions>
			</Item.Root>
		</div>
	{/if}
</div>
