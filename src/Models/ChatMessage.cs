namespace OpenAICommunicator.Models;

public class ChatMessage
{
    public string Role { get; set; } = "user";
    public string Content { get; set; } = "";
    public bool IsUser => Role == "user";
    public bool IsAssistant => Role == "assistant";
}
