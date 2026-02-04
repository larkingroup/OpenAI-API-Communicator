using System.ComponentModel;
using System.Runtime.CompilerServices;
using System.Text.Json.Serialization;

namespace OpenAICommunicator.Models;

public class Conversation : INotifyPropertyChanged
{
    private string _title = "New Chat";
    
    [JsonPropertyName("Id")]
    public string Id { get; set; } = Guid.NewGuid().ToString();
    
    [JsonPropertyName("Title")]
    public string Title
    {
        get => string.IsNullOrWhiteSpace(_title) ? "New Chat" : _title;
        set
        {
            var newValue = string.IsNullOrWhiteSpace(value) ? "New Chat" : value;
            if (_title != newValue)
            {
                _title = newValue;
                OnPropertyChanged();
            }
        }
    }
    
    [JsonPropertyName("Messages")]
    public List<ChatMessage> Messages { get; set; } = new();

    public event PropertyChangedEventHandler? PropertyChanged;

    protected void OnPropertyChanged([CallerMemberName] string? propertyName = null)
    {
        PropertyChanged?.Invoke(this, new PropertyChangedEventArgs(propertyName));
    }
}
