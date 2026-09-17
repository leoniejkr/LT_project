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

type ChatRequest struct {
	Model    string    `json:"model"`
	Messages []Message `json:"messages"`
	Stream   bool      `json:"stream"`
}

type ChatResponse struct {
	Message Message `json:"message"`
}
