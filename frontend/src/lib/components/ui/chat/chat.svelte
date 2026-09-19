<script lang="ts">
	import { tick } from "svelte";
	import { Bot, Send, User, X } from "lucide-svelte";
	import { Button } from "$lib/components/ui/button/index.js";
	import { Input } from "$lib/components/ui/input/index.js";
	import { Label } from "$lib/components/ui/label/index.js";
	import { Skeleton } from "$lib/components/ui/skeleton/index.js";
	import * as Empty from "$lib/components/ui/empty/index.js";
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
	let inputRef = $state<HTMLInputElement | null>(null);

	function scrollToBottom() {
		if (chatWindowRef) {
			chatWindowRef.scrollTop = chatWindowRef.scrollHeight;
		}
	}

	$effect(() => {
		messages;
		void tick().then(scrollToBottom);
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
			void tick().then(() => inputRef?.focus());
		}
	}
</script>

<div class={cn("fixed bottom-4 right-4 z-50 grid sm:bottom-6 sm:right-6", className)}>
	<Button
		size="icon-lg"
		variant="default"
		onclick={toggle}
		aria-label={open ? "Close AI assistant" : "Open AI assistant"}
		aria-expanded={open}
		aria-controls="analysis-chat"
		class="col-start-1 row-start-1 size-16 rounded-full shadow-lg shadow-primary/30 transition-transform hover:scale-110 active:scale-95"
	>
		{#if open}
			<X class="size-6" />
		{:else}
			<Bot class="size-8" />
		{/if}
	</Button>

	{#if open}
		<div
			id="analysis-chat"
			role="region"
			aria-label="AI assistant"
			class="bg-card border-border col-start-1 row-start-1 z-10 flex h-[min(42rem,calc(100vh-2rem))] w-[calc(100vw-2rem)] max-w-lg flex-col overflow-hidden rounded-2xl border shadow-xl sm:h-[min(42rem,calc(100vh-3rem))]"
		>
			<Item.Root
				variant="muted"
				class="bg-primary text-primary-foreground rounded-none px-5 py-4"
			>
				<Item.Media
					variant="icon"
					class="size-11 rounded-xl bg-primary-foreground/15"
				>
					<Bot class="size-7 text-primary-foreground" />
				</Item.Media>
				<Item.Content>
					<Item.Title class="text-base text-primary-foreground"
						>AI-Assistant</Item.Title
					>
				</Item.Content>
				<Item.Actions>
					<Button
						variant="ghost"
						size="icon-sm"
						onclick={toggle}
						aria-label="Close AI assistant"
						class="text-primary-foreground hover:bg-primary-foreground/20 hover:text-primary-foreground"
					>
						<X class="size-4" />
					</Button>
				</Item.Actions>
			</Item.Root>

			<div
				bind:this={chatWindowRef}
				role="log"
				aria-live="polite"
				aria-label="Conversation"
				class="bg-background/50 flex min-h-0 flex-1 flex-col overflow-y-auto p-4"
			>
				{#if messages.length === 0}
					<Empty.Root class="border-0 p-4">
						<Empty.Header>
							<Empty.Media variant="icon" class="size-14">
								<Bot class="size-7" />
							</Empty.Media>
							<Empty.Title class="text-base">AI Assistant</Empty.Title>
							<Empty.Description>
								Ask a question about the analysis results.
							</Empty.Description>
						</Empty.Header>
					</Empty.Root>
				{:else}
					<Item.Group class="gap-2">
						{#each messages as msg, i}
							{#if i > 0}
								<Item.Separator />
							{/if}
							<Item.Root
								size="sm"
								class={cn(
									"rounded-xl",
									msg.role === "user"
										? "bg-primary/10 justify-end"
										: "bg-muted/50",
								)}
							>
								{#if msg.role === "assistant"}
									<Item.Media variant="icon">
										<Bot
											class="size-5 text-muted-foreground"
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
										<User class="size-5 text-primary" />
									</Item.Media>
								{/if}
							</Item.Root>
						{/each}
						{#if loading}
							<Item.Separator />
							<Item.Root
								size="sm"
								class="rounded-xl bg-muted/50"
								aria-label="Assistant is writing"
								aria-busy="true"
							>
								<Item.Media variant="icon">
									<Bot class="size-5 text-muted-foreground" />
								</Item.Media>
								<Item.Content>
									<Skeleton class="h-4 w-28" />
								</Item.Content>
							</Item.Root>
						{/if}
					</Item.Group>
				{/if}
			</div>

			<Item.Root
				class="border-border bg-background rounded-none border-t px-4 py-4"
			>
				<Item.Content>
					<Label for="chat-message" class="sr-only">Message</Label>
					<Input
						id="chat-message"
						bind:ref={inputRef}
						bind:value={input}
						onkeydown={handleKeydown}
						placeholder="Type a message..."
						disabled={loading}
						class="h-11 flex-1"
					/>
				</Item.Content>
				<Item.Actions>
					<Button
						size="icon-lg"
						onclick={sendMessage}
						disabled={loading || !input.trim()}
						aria-label="Send message"
					>
						<Send class="size-5" />
					</Button>
				</Item.Actions>
			</Item.Root>
		</div>
	{/if}
</div>
