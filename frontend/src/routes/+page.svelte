<script lang="ts">
  import { Button } from "$lib/components/ui/button/index.js";
  import { Badge } from "$lib/components/ui/badge/index.js";
  import * as Card from "$lib/components/ui/card/index.js";
  import { Separator } from "$lib/components/ui/separator/index.js";
  import { ArrowRight, Upload, Stethoscope, FileText, Info } from "lucide-svelte";
  import "../app.css";

  const steps = [
    {
      icon: Upload,
      title: "Upload",
      description:
        "Upload one or more X-ray images.",
    },
    {
      icon: FileText,
      title: "Add context",
      description:
        "Provide patient metadata such as age, gender, symptoms and known conditions and start the analysis.",
    },
    {
      icon: Stethoscope,
      title: "Review results",
      description:
        "Inspect the model predictions and supporting image insights. Chat with the AI to understand the findings and get additional information.",
    },
  ];
</script>

<div class="mt-6 mx-auto w-full max-w-6xl flex flex-col gap-6 px-4 pb-12 sm:px-6">
  <Card.Root class="overflow-hidden p-0">
    <div class="grid gap-0 md:grid-cols-2">
      <Card.Content class="flex flex-col justify-center p-6 md:p-8 lg:p-10">
        <Badge variant="secondary" class="mb-4 w-fit">TrustAI</Badge>
        <Card.Header class="p-0">
          <Card.Title>
            <h1 class="text-3xl font-bold tracking-tight md:text-5xl">
              Medical image analysis and Risk Assessment AI
            </h1>
          </Card.Title>
          <Card.Description class="mt-4 max-w-xl text-base md:text-lg">
            This project was made to help clinicians with reviewing chest X-rays
            for disease detection and compare model-based findings with patient
            context. TrustAI is specialized in the analysis of chest X-rays. The
            interactive Chatbot assists in understanding the model's reasoning
            and provides additional information about the findings.
          </Card.Description>
        </Card.Header>
        <div class="mt-6 flex flex-wrap gap-3">
          <Button href="/upload" size="lg" class="gap-2">
            Start analysis <ArrowRight size={16} />
          </Button>
        </div>
      </Card.Content>

      <div class="relative min-h-[280px] bg-muted/40 md:min-h-[420px]">
        <img
          src="/example1.png"
          alt="Medical X-ray preview"
          class="h-full w-full object-cover"
        />
      </div>
    </div>
  </Card.Root>

  <div class="grid gap-4 md:grid-cols-3">
    {#each steps as step, i}
      {@const Icon = step.icon}
      <Card.Root class="p-5">
        <Card.Header class="p-0">
          <div
            class="mb-4 flex size-10 items-center justify-center rounded-md bg-primary/10 text-primary"
          >
            <Icon size={18} />
          </div>
          <Card.Title class="text-lg font-semibold">
            <h2>{i + 1}. {step.title}</h2>
          </Card.Title>
          <Card.Description class="mt-2">
            {step.description}
          </Card.Description>
        </Card.Header>
      </Card.Root>
    {/each}
  </div>

  <Separator />

  <Card.Root class="p-5">
    <Card.Header class="p-0">
      <div class="flex items-center gap-3">
        <div
          class="flex size-10 shrink-0 items-center justify-center rounded-md bg-primary/10 text-primary"
        >
          <Info size={18} />
        </div>
        <Card.Title class="text-lg font-semibold">
          <h2>Supported formats &amp; Pathologies &amp; Imaging Findings</h2>
        </Card.Title>
      </div>
      <Card.Description class="mt-3 space-y-3">
        <p>
          Supported image format for upload: PNG. Analysis of chest X-ray
          images to detect abnormalities and provide risk assessment based on AI
          models.
        </p>
        <p>
          Pathologies &amp; Imaging Findings: Atelectasis, Cardiomegaly,
          Consolidation, Edema, Effusion, Emphysema, Fibrosis, Hernia,
          Infiltration, Mass, Nodule, Pleural Thickening, Pneumonia,
          Pneumothorax, Covid
        </p>
      </Card.Description>
    </Card.Header>
  </Card.Root>
</div>

<style lang="postcss">
  @reference "tailwindcss";
</style>
