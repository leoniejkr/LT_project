<script lang="ts">
  import { Button } from "$lib/components/ui/button/index.js";
  import { Badge } from "$lib/components/ui/badge/index.js";
  import * as Item from "$lib/components/ui/item/index.js";
  import { ArrowRight, Upload, Stethoscope, FileText } from "lucide-svelte";
  import "../app.css";

  const steps = [
    {
      icon: Upload,
      title: "1. Upload",
      description:
        "Upload one or more X-ray images to start a new medical analysis.",
    },
    {
      icon: FileText,
      title: "2. Add context",
      description:
        "Provide patient metadata such as age, gender, symptoms and known conditions.",
    },
    {
      icon: Stethoscope,
      title: "3. Review results",
      description:
        "Inspect the model prediction, explanation and supporting image insights. (Chat with LLM)",
    },
  ];
</script>

<div class="mt-6 mx-auto w-full max-w-6xl flex flex-col gap-6 px-6 pb-12">
  <Item.Root variant="outline" class="overflow-hidden p-0">
    <div class="grid gap-0 md:grid-cols-2">
      <div class="flex flex-col justify-center p-6 md:p-8 lg:p-10">
        <Badge variant="secondary" class="mb-4 w-fit">TrustAI</Badge>
        <h1 class="text-3xl font-bold tracking-tight md:text-5xl">
          Medical image analysis and Risk Assessment AI
        </h1>
        <p class="mt-4 max-w-xl text-base text-muted-foreground md:text-lg">
          This app helps clinicians review chest X-rays and compare model-based
          findings with patient context. - Transparency, reasoning, explanations
          - Risk Assessment
        </p>
        <div class="mt-6 flex flex-wrap gap-3">
          <Button href="/upload" size="lg" class="gap-2">
            Start analysis <ArrowRight size={16} />
          </Button>
          <Button href="/result" variant="outline" size="lg">
            View example results
          </Button>
        </div>
      </div>

      <!-- change src to maybe heatmap image? -->
      <div class="relative min-h-[280px] bg-muted/40 md:min-h-[420px]">
        <img
          src="/example1.png"
          alt="Medical X-ray preview"
          class="h-full w-full object-cover"
        />
      </div>
    </div>
  </Item.Root>

  <div class="grid gap-4 md:grid-cols-3">
    {#each steps as step}
      {@const Icon = step.icon}
      <Item.Root variant="outline" class="p-5">
        <div
          class="mb-4 flex size-10 items-center justify-center rounded-md bg-primary/10 text-primary"
        >
          <Icon size={18} />
        </div>
        <h2 class="text-lg font-semibold">{step.title}</h2>
        <p class="mt-2 text-sm text-muted-foreground">
          {step.description}
        </p>
      </Item.Root>
    {/each}
  </div>

  <Item.Root variant="outline" class="p-6 md:p-8">
    <div class="grid gap-6 md:grid-cols-2">
      <div>
        <h2 class="text-2xl font-semibold tracking-tight">Info</h2>
        <p class="mt-3 text-muted-foreground">
          Supported image format for upload: PNG (& DICOM) Analysis of X-ray
          images to detect abnormalities and provide risk assessment based on AI
          models.
        </p>
        <p class="mt-3 text-muted-foreground">
          Sicknesses: Atelectasis, Cardiomegaly, Consolidation, Edema, Effusion,
          Emphysema, Fibrosis, Hernia, Infiltration, Mass, Nodule, Pleural
          Thickening, Pneumonia, Pneumothorax, Covid
        </p>
      </div>

      <div>
        <h2 class="text-2xl font-semibold tracking-tight">How to use it</h2>
        <ol class="mt-3 space-y-3 text-muted-foreground">
          <li>
            1. Open the upload page and select the X-ray files you want to
            analyze.
          </li>
          <li>
            2. Enter patient details such as age, gender and relevant symptoms
            or medical history.
          </li>
          <li>3. Start analysis and review prediction and image insights.</li>
          <li>
            4. Use the result view to understand the diagnosis, examine the
            images manually and use the chat for further information/help.
          </li>
        </ol>
        <div class="mt-5">
          <Button href="/upload" class="gap-2">
            Go to Upload <ArrowRight size={16} />
          </Button>
        </div>
      </div>
    </div>
  </Item.Root>
</div>

<style lang="postcss">
  @reference "tailwindcss";
  :global(html) {
    background-color: theme(--color-gray-100);
  }
</style>
