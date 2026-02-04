namespace OpenAICommunicator.Models;

public class Conversation
{
    public string Id { get; set; } = Guid.NewGuid().ToString();
    public string Title { get; set; } = "New Chat";
    public List<ChatMessage> Messages { get; set; } = new();
}
