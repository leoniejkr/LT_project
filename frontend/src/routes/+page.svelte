<script lang="ts">
  import { Button } from "$lib/components/ui/button/index.js";
  import { Badge } from "$lib/components/ui/badge/index.js";
  import * as Card from "$lib/components/ui/card/index.js";
  import * as Tabs from "$lib/components/ui/tabs/index.js";
  import * as Accordion from "$lib/components/ui/accordion/index.js";
  import { Separator } from "$lib/components/ui/separator/index.js";
  import * as Alert from "$lib/components/ui/alert/index.js";
  import { ArrowRight, Upload, Stethoscope, FileText, Info } from "lucide-svelte";
  import "../app.css";

  const steps = [
    {
      icon: Upload,
      title: "Upload",
      description:
        "Upload one or more X-ray images to start a new medical analysis.",
    },
    {
      icon: FileText,
      title: "Add context",
      description:
        "Provide patient metadata such as age, gender, symptoms and known conditions.",
    },
    {
      icon: Stethoscope,
      title: "Review results",
      description:
        "Inspect the model prediction, explanation and supporting image insights. Chat with the AI to understand the findings and get additional information.",
    },
  ];
</script>

<div class="mt-6 mx-auto w-full max-w-6xl flex flex-col gap-6 px-6 pb-12">
  <Card.Root class="overflow-hidden p-0">
    <div class="grid gap-0 md:grid-cols-2">
      <Card.Content class="flex flex-col justify-center p-6 md:p-8 lg:p-10">
        <Badge variant="secondary" class="mb-4 w-fit">TrustAI</Badge>
        <Card.Header class="p-0">
          <Card.Title class="text-3xl font-bold tracking-tight md:text-5xl">
            Medical image analysis and Risk Assessment AI
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
          <Button href="/result" variant="outline" size="lg">
            View example results
          </Button>
        </div>
      </Card.Content>

      <!-- change src to maybe heatmap image? -->
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
          <Card.Title class="text-lg font-semibold">{i + 1}. {step.title}</Card.Title>
          <Card.Description class="mt-2">
            {step.description}
          </Card.Description>
        </Card.Header>
      </Card.Root>
    {/each}
  </div>

  <Separator />

  <Tabs.Root value="info" class="w-full">
    <Tabs.List class="w-full justify-start">
      <Tabs.Trigger value="info">Info</Tabs.Trigger>
      <Tabs.Trigger value="howto">How to use it</Tabs.Trigger>
    </Tabs.List>

    <Tabs.Content value="info">
      <Alert.Root>
        <Info class="size-4" />
        <Alert.Title>Supported formats &amp; Pathologies &amp; Imaging Findings</Alert.Title>
        <Alert.Description class="mt-2 space-y-3">
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
        </Alert.Description>
      </Alert.Root>
    </Tabs.Content>

    <Tabs.Content value="howto">
      <Card.Root>
        <Card.Content>
          <Accordion.Root type="single">
            <Accordion.Item value="step-1">
              <Accordion.Trigger>1. Open the upload page</Accordion.Trigger>
              <Accordion.Content>
                Select the X-ray files you want to analyze.
              </Accordion.Content>
            </Accordion.Item>
            <Accordion.Item value="step-2">
              <Accordion.Trigger>2. Enter patient details</Accordion.Trigger>
              <Accordion.Content>
                Provide age, gender and relevant symptoms or medical history.
              </Accordion.Content>
            </Accordion.Item>
            <Accordion.Item value="step-3">
              <Accordion.Trigger>3. Start analysis</Accordion.Trigger>
              <Accordion.Content>
                Review prediction and image insights.
              </Accordion.Content>
            </Accordion.Item>
            <Accordion.Item value="step-4">
              <Accordion.Trigger>4. Use the result view</Accordion.Trigger>
              <Accordion.Content>
                Understand the diagnosis, examine the images manually and use the
                chat for further information and help.
              </Accordion.Content>
            </Accordion.Item>
          </Accordion.Root>
        </Card.Content>
        <Card.Footer>
          <Button href="/upload" class="gap-2">
            Go to Upload <ArrowRight size={16} />
          </Button>
        </Card.Footer>
      </Card.Root>
    </Tabs.Content>
  </Tabs.Root>
</div>

<style lang="postcss">
  @reference "tailwindcss";
</style>
