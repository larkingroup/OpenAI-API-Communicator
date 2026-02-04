using System.Text.Json;
using System.Text.Json.Serialization;
using OpenAICommunicator.Models;

namespace OpenAICommunicator.Services;

public class ChatHistoryService
{
    private static readonly string AppFolder = Path.Combine(
        Environment.GetFolderPath(Environment.SpecialFolder.ApplicationData),
        "OpenAICommunicator");
    
    private static readonly string HistoryFile = Path.Combine(AppFolder, "history.json");

    private static readonly JsonSerializerOptions JsonOptions = new()
    {
        WriteIndented = true,
        PropertyNameCaseInsensitive = true
    };

    public List<Conversation> LoadAll()
    {
        try
        {
            if (File.Exists(HistoryFile))
            {
                var json = File.ReadAllText(HistoryFile);
                var conversations = JsonSerializer.Deserialize<List<Conversation>>(json, JsonOptions) ?? new();
                
                // Fix any conversations with missing titles
                foreach (var convo in conversations)
                {
                    if (string.IsNullOrWhiteSpace(convo.Title))
                    {
                        // Try to derive title from first user message
                        var firstUserMsg = convo.Messages?.FirstOrDefault(m => m.Role == "user");
                        if (firstUserMsg != null && !string.IsNullOrWhiteSpace(firstUserMsg.Content))
                        {
                            var content = firstUserMsg.Content.Trim();
                            convo.Title = content.Length > 30 ? content[..30] + "..." : content;
                        }
                        else
                        {
                            convo.Title = "New Chat";
                        }
                    }
                    
                    // Ensure messages list exists
                    convo.Messages ??= new();
                }
                
                return conversations;
            }
        }
        catch { }
        return new();
    }

    public void SaveAll(List<Conversation> conversations)
    {
        try
        {
            Directory.CreateDirectory(AppFolder);
            var json = JsonSerializer.Serialize(conversations, JsonOptions);
            File.WriteAllText(HistoryFile, json);
        }
        catch { }
    }
}
