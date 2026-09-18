<script lang="ts">
    import { Badge } from "$lib/components/ui/badge/index.js";
    import { Input } from "$lib/components/ui/input/index.js";
    import * as Card from "$lib/components/ui/card/index.js";
    import * as Empty from "$lib/components/ui/empty/index.js";
    import * as Field from "$lib/components/ui/field/index.js";
    import { CloudUpload, ImageUp } from "lucide-svelte";

    let { files = $bindable() }: { files?: FileList } = $props();
    let imageCount = $derived(files?.length ?? 0);
</script>

<Card.Root class="h-full lg:col-span-4">
    <Card.Header>
        <Card.Title><h2>Radiological Scans (.png)</h2></Card.Title>
        <Card.Description>
            Upload the X-Ray images that should be included in this analysis.
        </Card.Description>
        <Card.Action>
            <Badge variant="destructive">Required</Badge>
        </Card.Action>
    </Card.Header>
    <Card.Content>
        <Empty.Root class="border">
            <Empty.Header>
                <Empty.Media variant="icon"><CloudUpload /></Empty.Media>
                <Empty.Title>Upload X-Ray Files</Empty.Title>
                <Empty.Description>
                    Support for standard X-Ray formats. Ensure everything is included
                    in the upload.
                </Empty.Description>
            </Empty.Header>
            <Empty.Content>
                <ImageUp />
                <Field.Label for="png_images" class="sr-only">
                    Select X-Ray files
                </Field.Label>
                <Input id="png_images" type="file" multiple bind:files />
            </Empty.Content>
        </Empty.Root>
    </Card.Content>
    <Card.Footer class="border-t justify-between text-muted-foreground">
        <span>Selected files</span>
        <Badge variant="secondary">{imageCount}</Badge>
    </Card.Footer>
</Card.Root>
