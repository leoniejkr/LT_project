<script lang="ts">
    import  * as Empty from "$lib/components/ui/empty/index.js"
    import * as Item  from "$lib/components/ui/item/index.js";
    import * as Field from "$lib/components/ui/field/index.js";
	import * as Select  from "$lib/components/ui/select/index.js"
	import { Button } from "$lib/components/ui/button/index.js";
	import { Badge } from "$lib/components/ui/badge/index.js";
	import { Input } from "$lib/components/ui/input/index.js"
	import { CloudUpload, Container, UserSearch } from 'lucide-svelte';
	import "../../app.css";

	let { data }: { data: any } = $props();

// TODO: Für den upload müssete man hier wahrscheinlich noch eine ShadCN Form Komponente hinzufügen.
// Spätestens für die Metadaten denke ich: Form + Checkbox + Select
// erster div Container ex., damit metadaten rechts plazierbar werden können später
// Formelle Form mit formsnap und superform ist glaube ich overkill also würde ich nativ html form nutzen mit Field ui comp

</script>

<div class="mt-6 ml-10 w-full max-w-md">
	<div class="mb-6">
		<header class="text-2xl font-bold tracking-tight">Case Input & Initialization</header>
		<h2 class="text-muted-foreground mt-1">Upload DICOM payload and contextualize patient metadata for AI analysis</h2>
	</div>
	<div class="flex flex-auto gap-4">
		<div>
			<Item.Root variant="outline" class="flex flex-col">
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
						0 files staged for upload TODO: variabel!
					</Item.Description>
				</Item.Content>
			</Item.Root>
		</div>
		<div class="flex flex-direction:row">
			<form>
				<Field.Group>
					<Field.Set>
						<Field.Legend>
							Patient Metadata
						</Field.Legend>
						<div class="grid grid-cols gap-3">
							<Field.Field>
								<Field.Label>
									Patient Age
								</Field.Label>
								<Input
									id="mysteriös"
									placeholder="Patient Age"
									required
								/>
							</Field.Field>
							<Field.Field>
								<Field.Label>
									Gender
								</Field.Label>
								<Select.Root type="single" name="Select A Gender">
									<Select.Trigger>
										ss
									</Select.Trigger>
								</Select.Root>
							</Field.Field>
						</div>
					</Field.Set>
				</Field.Group>
			</form>
		</div>
	</div>
</div>

<form method="POST">
</form>