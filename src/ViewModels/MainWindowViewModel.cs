using System.Collections.ObjectModel;
using CommunityToolkit.Mvvm.ComponentModel;
using CommunityToolkit.Mvvm.Input;
using OpenAICommunicator.Models;
using OpenAICommunicator.Services;

namespace OpenAICommunicator.ViewModels;

public partial class MainWindowViewModel : ViewModelBase
{
    private readonly OpenAIService _openAI = new();
    private readonly SettingsService _settings = new();
    private readonly ChatHistoryService _history = new();

    [ObservableProperty]
    private string _apiKey = "";

    [ObservableProperty]
    private string _selectedModel = "gpt-4o-mini";

    [ObservableProperty]
    private string _messageInput = "";

    [ObservableProperty]
    private bool _isSending;

    [ObservableProperty]
    private string _errorMessage = "";

    [ObservableProperty]
    private bool _showSettings = true;

    [ObservableProperty]
    private bool _showSidebar = true;

    [ObservableProperty]
    private Conversation? _currentConversation;

    public ObservableCollection<ChatMessage> Messages { get; } = new();
    public ObservableCollection<Conversation> Conversations { get; } = new();

    public List<string> AvailableModels { get; } =
    [
        "gpt-4o",
        "gpt-4o-mini", 
        "gpt-4-turbo",
        "gpt-4",
        "gpt-3.5-turbo",
        "o1",
        "o1-mini",
        "o3-mini"
    ];

    public bool HasApiKey => !string.IsNullOrWhiteSpace(ApiKey);
    public bool CanSend => HasApiKey && !string.IsNullOrWhiteSpace(MessageInput) && !IsSending;

    public MainWindowViewModel()
    {
        // Load saved API key
        ApiKey = _settings.LoadApiKey();
        if (HasApiKey) ShowSettings = false;

        // Load chat history
        var saved = _history.LoadAll();
        foreach (var c in saved)
            Conversations.Add(c);

        // Start with first conversation or create new
        if (Conversations.Count > 0)
            SelectConversation(Conversations[0]);
        else
            NewChat();
    }

    partial void OnApiKeyChanged(string value)
    {
        OnPropertyChanged(nameof(HasApiKey));
        OnPropertyChanged(nameof(CanSend));
        
        // Save API key when changed
        _settings.SaveApiKey(value);
        
        if (HasApiKey) ShowSettings = false;
    }

    partial void OnMessageInputChanged(string value) => OnPropertyChanged(nameof(CanSend));
    partial void OnIsSendingChanged(bool value) => OnPropertyChanged(nameof(CanSend));

    [RelayCommand]
    private void NewChat()
    {
        var convo = new Conversation();
        Conversations.Insert(0, convo);
        SelectConversation(convo);
        SaveHistory();
    }

    [RelayCommand]
    private void SelectConversation(Conversation? convo)
    {
        if (convo == null) return;
        
        CurrentConversation = convo;
        Messages.Clear();
        foreach (var msg in convo.Messages)
            Messages.Add(msg);
    }

    [RelayCommand]
    private void DeleteConversation(Conversation? convo)
    {
        if (convo == null) return;
        
        Conversations.Remove(convo);
        
        if (CurrentConversation == convo)
        {
            if (Conversations.Count > 0)
                SelectConversation(Conversations[0]);
            else
                NewChat();
        }
        
        SaveHistory();
    }

    [RelayCommand]
    private async Task SendMessage()
    {
        if (!CanSend || CurrentConversation == null) return;

        var userMessage = MessageInput.Trim();
        MessageInput = "";
        ErrorMessage = "";

        var msg = new ChatMessage { Role = "user", Content = userMessage };
        Messages.Add(msg);
        CurrentConversation.Messages.Add(msg);

        // Update title from first message
        if (CurrentConversation.Messages.Count == 1)
        {
            CurrentConversation.Title = userMessage.Length > 30 
                ? userMessage[..30] + "..." 
                : userMessage;
            // Refresh the list
            var idx = Conversations.IndexOf(CurrentConversation);
            if (idx >= 0)
            {
                Conversations.RemoveAt(idx);
                Conversations.Insert(idx, CurrentConversation);
                SelectConversation(CurrentConversation);
            }
        }

        SaveHistory();

        IsSending = true;
        try
        {
            var response = await _openAI.SendMessageAsync(ApiKey, SelectedModel, Messages.ToList());
            var assistantMsg = new ChatMessage { Role = "assistant", Content = response };
            Messages.Add(assistantMsg);
            CurrentConversation.Messages.Add(assistantMsg);
            SaveHistory();
        }
        catch (Exception ex)
        {
            ErrorMessage = ex.Message;
            // Remove the user message if we failed
            if (Messages.Count > 0 && Messages[^1].IsUser)
            {
                Messages.RemoveAt(Messages.Count - 1);
                CurrentConversation.Messages.RemoveAt(CurrentConversation.Messages.Count - 1);
                SaveHistory();
            }
        }
        finally
        {
            IsSending = false;
        }
    }

    [RelayCommand]
    private void ToggleSettings()
    {
        ShowSettings = !ShowSettings;
    }

    [RelayCommand]
    private void ToggleSidebar()
    {
        ShowSidebar = !ShowSidebar;
    }

    private void SaveHistory()
    {
        _history.SaveAll(Conversations.ToList());
    }
}
