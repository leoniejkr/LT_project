<script lang="ts">
  import { Button } from "$lib/components/ui/button/index.js";
  import { Badge } from "$lib/components/ui/badge/index.js";
  import * as Card from "$lib/components/ui/card/index.js";
  import * as Alert from "$lib/components/ui/alert/index.js";
  import { Separator } from "$lib/components/ui/separator/index.js";
  import * as Item from "$lib/components/ui/item/index.js";
  import * as Table from "$lib/components/ui/table/index.js";
  import * as Tooltip from "$lib/components/ui/tooltip/index.js";
  import { Progress } from "$lib/components/ui/progress/index.js";
  import {
    ArrowRight,
    Upload,
    Stethoscope,
    FileText,
    Info,
    Brain,
    Cpu,
    Sparkles,
    ShieldCheck,
    CircleHelp,
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

  /** Mean ROC-AUC per model on the held-out test split (10,151 images / 3,570 patients). */
  const classifierScores = [
    { name: "ConvNeXt", architecture: "CNN", score: 0.855 },
    { name: "Swin-B", architecture: "Transformer", score: 0.849 },
    { name: "DenseNet-121", architecture: "CNN", score: 0.842 },
    { name: "Ensemble", architecture: "Soft voting", score: 0.858 },
  ];
</script>

<div class="mt-6 mx-auto w-full max-w-6xl flex flex-col gap-6 px-4 pb-12 sm:px-6">
  <Card.Root class="overflow-hidden p-0">
    <div class="grid gap-0 md:grid-cols-2">
      <Card.Content class="flex flex-col justify-center p-6 md:p-8 lg:p-10">
        <div class="mb-4 flex flex-wrap items-center gap-2">
          <Badge variant="secondary">TrustAI</Badge>
          <Tooltip.Root>
            <Tooltip.Trigger>
              {#snippet child({ props })}
                <Badge {...props} variant="outline" class="cursor-help gap-1">
                  <ShieldCheck /> Research prototype
                </Badge>
              {/snippet}
            </Tooltip.Trigger>
            <Tooltip.Content>
              Decision support for research use; not a medical device.
            </Tooltip.Content>
          </Tooltip.Root>
        </div>
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
      <Card.Root class="p-2">
        <Item.Root class="h-full items-start border-0 p-3">
          <Item.Media
            variant="icon"
            class="flex size-10 rounded-xl bg-primary/10 text-primary"
          >
            <Icon />
          </Item.Media>
          <Item.Content>
            <Item.Title class="text-base">
              <Badge variant="outline" class="mr-1">Step {i + 1}</Badge>
              {step.title}
            </Item.Title>
            <Item.Description class="mt-1 leading-relaxed">
              {step.description}
            </Item.Description>
          </Item.Content>
        </Item.Root>
      </Card.Root>
    {/each}
  </div>

  <Separator />

  <Card.Root>
    <Card.Header class="flex-row items-start gap-3">
      <div
        class="flex size-10 shrink-0 items-center justify-center rounded-xl bg-primary/10 text-primary"
      >
        <Info size={18} />
      </div>
      <div class="space-y-1">
        <Card.Title>
          <h2>Supported formats &amp; pathologies</h2>
        </Card.Title>
        <Card.Description>
          PNG upload · upright, front-facing chest X-rays
        </Card.Description>
      </div>
    </Card.Header>

    <Card.Content class="space-y-3 text-sm text-muted-foreground">
      <Separator class="mb-4" />
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
    </Card.Content>
  </Card.Root>

  <Card.Root>
    <Card.Header class="flex-row items-start gap-3">
      <div
        class="flex size-10 shrink-0 items-center justify-center rounded-xl bg-primary/10 text-primary"
      >
        <Sparkles size={18} />
      </div>
      <div class="space-y-1">
        <Card.Title>
          <h2>Fine-tuned models</h2>
        </Card.Title>
        <Card.Description>
          Clinical LLM &amp; X-ray classifiers, trained by us
        </Card.Description>
      </div>
    </Card.Header>

    <Card.Content>
      <Separator class="mb-5" />

      <div class="grid gap-5 md:grid-cols-2">
        <Item.Root variant="muted" class="items-start">
          <Item.Media
            variant="icon"
            class="flex size-9 rounded-lg bg-background text-primary"
          >
            <Brain />
          </Item.Media>
          <Item.Content>
            <Item.Title>Clinical LLM</Item.Title>
            <Item.Description class="mt-1 leading-relaxed">
              Fine-tuned for exactly these 15 pathologies. Explains every finding
              in clinical terms and reasons over the patient's own data. Runs
              locally.
            </Item.Description>
          </Item.Content>
        </Item.Root>

        <Item.Root variant="muted" class="items-start">
          <Item.Media
            variant="icon"
            class="flex size-9 rounded-lg bg-background text-primary"
          >
            <Cpu />
          </Item.Media>
          <Item.Content>
            <Item.Title>X-ray classifiers</Item.Title>
            <Item.Description class="mt-1 leading-relaxed">
              ConvNeXt, Swin-B and DenseNet-121, fine-tuned on the NIH and MIDRC
              chest X-ray datasets, plus a soft-voting ensemble.
            </Item.Description>
          </Item.Content>
        </Item.Root>
      </div>

      <Card.Root class="mt-5 overflow-hidden py-0">
        <Table.Root>
          <Table.Caption class="pb-4 text-xs">
            Mean ROC-AUC on 10,151 held-out images from 3,570 unseen patients.
          </Table.Caption>
          <Table.Header class="bg-muted/50">
            <Table.Row>
              <Table.Head class="pl-4">Model</Table.Head>
              <Table.Head>Architecture</Table.Head>
              <Table.Head class="w-[42%]">Mean ROC-AUC</Table.Head>
            </Table.Row>
          </Table.Header>
          <Table.Body>
            {#each classifierScores as classifier}
              <Table.Row>
                <Table.Cell class="pl-4 font-medium">
                  {classifier.name}
                  {#if classifier.name === "Ensemble"}
                    <Badge variant="secondary" class="ml-2">Best</Badge>
                  {/if}
                </Table.Cell>
                <Table.Cell class="text-muted-foreground">
                  {classifier.architecture}
                </Table.Cell>
                <Table.Cell>
                  <div class="flex min-w-36 items-center gap-3">
                    <Progress
                      value={classifier.score * 100}
                      max={100}
                      class="h-2"
                      aria-label={classifier.name + " mean ROC-AUC"}
                    />
                    <span class="w-10 font-mono text-xs font-medium tabular-nums">
                      {classifier.score.toFixed(3)}
                    </span>
                  </div>
                </Table.Cell>
              </Table.Row>
            {/each}
          </Table.Body>
        </Table.Root>
      </Card.Root>
    </Card.Content>
  </Card.Root>

  <Alert.Root>
    <CircleHelp />
    <Alert.Title>Clinical decision support only</Alert.Title>
    <Alert.Description>
      TrustAI is a research prototype. Its output must be reviewed by a qualified
      clinician and must not replace professional diagnosis.
    </Alert.Description>
    <Alert.Action>
      <Button href="/upload" variant="outline" size="sm">
        Try it <ArrowRight />
      </Button>
    </Alert.Action>
  </Alert.Root>
</div>

<style lang="postcss">
  @reference "tailwindcss";
</style>
