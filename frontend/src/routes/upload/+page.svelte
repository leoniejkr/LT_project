<script lang="ts">
    import  * as Empty from "$lib/components/ui/empty/index.js"
    import * as Item  from "$lib/components/ui/item/index.js";
	import { Button } from "$lib/components/ui/button/index.js";
	import { Badge } from "$lib/components/ui/badge/index.js";
	import { CloudUpload, Container } from 'lucide-svelte';
	import "../../app.css";

	let { data }: { data: any } = $props();
// TODO: Für den upload müssete man hier wahrscheinlich noch eine ShadCN Form Komponente hinzufügen.
// Spätestens für die Metadaten denke ich: Form + Checkbox + Select
// erster div Container ex., damit metadaten rechts plazierbar werden können später
</script>

<div class="mt-6 ml-10">
	<div class="mb-6">
		<header class="text-2xl font-bold tracking-tight">Case Input & Initialization</header>
		<h2 class="text-muted-foreground mt-1">Upload DICOM payload and contextualize patient metadata for AI analysis</h2>
	</div>
	<div class="flex gap-4">
		<div>
			<Item.Root variant="outline" class="flex w-md flex-col">
				<Item.Content>
					<Item.Title>
						Radiological Scans (.dcm)
						<Badge variant="secondary" class="ml-40">Required</Badge>
					</Item.Title>
					<Item.Media>
					</Item.Media>
					<Empty.Root>
						<Empty.Header>
							<Empty.Media variant="icon">
								<CloudUpload/>
							</Empty.Media>
							<Empty.Title>Upload DICOM Files</Empty.Title>
							<Empty.Description>
								Support for standart DICOM formats. Ensure everything is included in the upload.
							</Empty.Description>
						</Empty.Header>
						<Empty.Content>
							<Button variant="outline">
								Browse Local Storage
							</Button>
						</Empty.Content>
					</Empty.Root>
					<Item.Separator/>
					<Item.Description>
						0 files staged for upload
					</Item.Description>
				</Item.Content>
			</Item.Root>
		</div>
		<div>

		</div>
	</div>
</div>

<form method="POST">
</form>