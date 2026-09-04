from datasets import load_dataset
from unsloth import FastLanguageModel
from trl import SFTTrainer
from transformers import TrainingArguments

# note: run this script in google colab!!


# 1. Load Model
model, tokenizer = FastLanguageModel.from_pretrained(
    model_name="unsloth/llama-3-8b-Instruct-bnb-4bit",
    max_seq_length=2048,
    load_in_4bit=True,
)

# 2. Add LoRA Adapters
model = FastLanguageModel.get_peft_model(
    model,
    r=16,
    lora_alpha=16,
    lora_dropout=0,
    target_modules=["q_proj", "k_proj", "v_proj", "o_proj"],
)

# 3. Load JSONL Data
dataset = load_dataset("json", data_files={"train": "fine_tuning_ready.jsonl"})

# 4. Train
trainer = SFTTrainer(
    model=model,
    tokenizer=tokenizer,
    train_dataset=dataset["train"],
    dataset_text_field="messages",
    max_seq_length=2048,
    args=TrainingArguments(
        per_device_train_batch_size=2,
        gradient_accumulation_steps=4,
        warmup_steps=5,
        max_steps=60, # Adjust higher if you have thousands of samples
        learning_rate=2e-4,
        fp16=True,
        logging_steps=1,
        output_dir="outputs",
    ),
)
trainer.train()

# 5. Export to GGUF format for Ollama
model.save_pretrained_gguf("clinical_model_dir", tokenizer, quantization_method="q4_k_m")