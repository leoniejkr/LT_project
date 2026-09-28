<script lang="ts">
  import { Button } from "$lib/components/ui/button/index.js";
  import { Badge } from "$lib/components/ui/badge/index.js";
  import * as Card from "$lib/components/ui/card/index.js";
  import { Separator } from "$lib/components/ui/separator/index.js";
  import * as Accordion from "$lib/components/ui/accordion/index.js";
  import {
    ArrowRight,
    Upload,
    Stethoscope,
    FileText,
    Info,
    Brain,
    Cpu,
    Sparkles,
  } from "lucide-svelte";
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

  let formatsOpen = $state<string | undefined>("formats");
  let modelsOpen = $state<string | undefined>("models");

  /** Mean ROC-AUC per model on the held-out test split (10,151 images / 3,570 patients). */
  const classifierScores = [
    { name: "ConvNeXt", score: "0.855" },
    { name: "Swin-B", score: "0.849" },
    { name: "DenseNet-121", score: "0.842" },
    { name: "Ensemble", score: "0.858" },
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

  <Accordion.Root type="single" bind:value={formatsOpen} class="bg-card">
    <Accordion.Item value="formats">
      <Accordion.Trigger class="items-center gap-3 hover:no-underline">
        <span class="flex items-center gap-3">
          <span
            class="flex size-8 shrink-0 items-center justify-center rounded-md bg-primary/10 text-primary"
          >
            <Info size={16} />
          </span>
          <span>
            <span class="block text-sm font-semibold">
              Supported formats &amp; pathologies
            </span>
            <span class="mt-0.5 block text-xs font-normal text-muted-foreground">
              PNG upload · upright, front-facing chest X-rays
            </span>
          </span>
        </span>
      </Accordion.Trigger>

      <Accordion.Content>
        <div class="space-y-3 border-t pt-4 text-sm text-muted-foreground">
          <p>
            Supported image format for upload: PNG. Analysis of chest X-ray
            images to detect abnormalities and provide risk assessment based on
            AI models.
          </p>
          <p>
            DICOM files are not accepted directly and must be
            <strong class="text-foreground">converted to PNG first</strong>.
            Images should be
            <strong class="text-foreground">
              front-facing (PA/AP view) and upright
            </strong>
            chest X-rays, as the models were trained on upright frontal
            projections.
          </p>
          <p>
            <strong class="text-foreground">Pathologies &amp; Imaging Findings:</strong>
            Atelectasis, Cardiomegaly, Consolidation, Edema, Effusion,
            Emphysema, Fibrosis, Hernia, Infiltration, Mass, Nodule, Pleural
            Thickening, Pneumonia, Pneumothorax, Covid
          </p>
        </div>
      </Accordion.Content>
    </Accordion.Item>
  </Accordion.Root>

  <Accordion.Root type="single" bind:value={modelsOpen} class="bg-card">
    <Accordion.Item value="models">
      <Accordion.Trigger class="items-center gap-3 hover:no-underline">
        <span class="flex items-center gap-3">
          <span
            class="flex size-8 shrink-0 items-center justify-center rounded-md bg-primary/10 text-primary"
          >
            <Sparkles size={16} />
          </span>
          <span>
            <span class="block text-sm font-semibold">Fine-tuned models</span>
            <span class="mt-0.5 block text-xs font-normal text-muted-foreground">
              Clinical LLM &amp; X-ray classifiers, trained by us
            </span>
          </span>
        </span>
      </Accordion.Trigger>

      <Accordion.Content>
        <div class="grid gap-5 border-t pt-4 md:grid-cols-2">
          <div>
            <h3 class="flex items-center gap-2 text-sm font-semibold">
              <Brain size={14} class="text-primary" />
              Clinical LLM
            </h3>
            <p class="mt-1.5 text-sm text-muted-foreground">
              Fine-tuned for exactly these 15 pathologies. Explains every finding
              in clinical terms and reasons over the patient's own data. Runs
              locally.
            </p>
          </div>

          <div>
            <h3 class="flex items-center gap-2 text-sm font-semibold">
              <Cpu size={14} class="text-primary" />
              X-ray classifiers
            </h3>
            <p class="mt-1.5 text-sm text-muted-foreground">
              ConvNeXt, Swin-B and DenseNet-121, fine-tuned on the NIH and MIDRC
              chest X-ray datasets, plus a soft-voting ensemble.
            </p>
          </div>
        </div>

        <dl class="mt-4 flex flex-wrap gap-x-5 gap-y-1 border-t pt-4 text-xs">
          {#each classifierScores as c}
            <div class="flex items-baseline gap-1.5">
              <dt class="text-muted-foreground">{c.name}</dt>
              <dd class="font-mono font-medium tabular-nums">{c.score}</dd>
            </div>
          {/each}
        </dl>
        <p class="mt-2 text-xs text-muted-foreground">
          Mean ROC-AUC on 10,151 held-out images from 3,570 unseen patients.
          Research prototype — not a medical device.
        </p>
      </Accordion.Content>
    </Accordion.Item>
  </Accordion.Root>
</div>

<style lang="postcss">
  @reference "tailwindcss";
</style>
