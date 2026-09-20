package chat

type Role string

const (
	UserRole      Role = "user"
	AssistantRole Role = "assistant"
	SystemRole    Role = "system"
)

type Message struct {
	Role    Role   `json:"role"`
	Content string `json:"content"`
}

// Options are Ollama sampling parameters. num_predict / num_ctx are raised
// from the Modelfile defaults (200 / 2048) so long clinical answers are not
// cut off mid-sentence and the system prompt + history fit into the context.
type Options struct {
	Temperature float64 `json:"temperature,omitempty"`
	NumPredict  int     `json:"num_predict,omitempty"`
	NumCtx      int     `json:"num_ctx,omitempty"`
}

type ChatRequest struct {
	Model    string    `json:"model"`
	Messages []Message `json:"messages"`
	Stream   bool      `json:"stream"`
	Options  Options   `json:"options,omitempty"`
}

type ChatResponse struct {
	Message Message `json:"message"`
}
