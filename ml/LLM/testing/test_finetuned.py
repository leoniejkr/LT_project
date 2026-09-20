from llama_cpp import Llama

# Load the model
llm = Llama(
    model_path="ml/LLM/files/clinical_model_dir/llama-3-8b-Instruct.Q4_K_M.gguf",
    n_ctx=2048,      # Context size
    n_gpu_layers=-1  # Offload all layers to Apple Metal GPU
)

# Run a chat completion
output = llm.create_chat_completion(
    messages=[
        {"role": "system", "content": "You are a helpful clinical assistant."},
        {"role": "user", "content": "What are the primary symptoms of pneumonia?"}
    ]
)

print(output['choices'][0]['message']['content'])
