using System.Text.Json;

namespace OpenAICommunicator.Services;

public class SettingsService
{
    private static readonly string AppFolder = Path.Combine(
        Environment.GetFolderPath(Environment.SpecialFolder.ApplicationData),
        "OpenAICommunicator");
    
    private static readonly string SettingsFile = Path.Combine(AppFolder, "settings.json");

    public string LoadApiKey()
    {
        try
        {
            if (File.Exists(SettingsFile))
            {
                var json = File.ReadAllText(SettingsFile);
                var settings = JsonSerializer.Deserialize<Settings>(json);
                return settings?.ApiKey ?? "";
            }
        }
        catch { }
        return "";
    }

    public void SaveApiKey(string apiKey)
    {
        try
        {
            Directory.CreateDirectory(AppFolder);
            var settings = new Settings { ApiKey = apiKey };
            var json = JsonSerializer.Serialize(settings);
            File.WriteAllText(SettingsFile, json);
        }
        catch { }
    }

    private class Settings
    {
        public string ApiKey { get; set; } = "";
    }
}
