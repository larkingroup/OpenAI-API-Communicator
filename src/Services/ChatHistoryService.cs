using System.Text.Json;
using OpenAICommunicator.Models;

namespace OpenAICommunicator.Services;

public class ChatHistoryService
{
    private static readonly string AppFolder = Path.Combine(
        Environment.GetFolderPath(Environment.SpecialFolder.ApplicationData),
        "OpenAICommunicator");
    
    private static readonly string HistoryFile = Path.Combine(AppFolder, "history.json");

    public List<Conversation> LoadAll()
    {
        try
        {
            if (File.Exists(HistoryFile))
            {
                var json = File.ReadAllText(HistoryFile);
                return JsonSerializer.Deserialize<List<Conversation>>(json) ?? new();
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
            var json = JsonSerializer.Serialize(conversations, new JsonSerializerOptions { WriteIndented = true });
            File.WriteAllText(HistoryFile, json);
        }
        catch { }
    }
}
