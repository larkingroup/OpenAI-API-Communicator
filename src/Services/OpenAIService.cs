using System.Net.Http.Headers;
using System.Text;
using System.Text.Json;
using System.Text.Json.Serialization;
using OpenAICommunicator.Models;

namespace OpenAICommunicator.Services;

public class OpenAIService
{
    private readonly HttpClient _http;

    public OpenAIService()
    {
        _http = new HttpClient
        {
            BaseAddress = new Uri("https://api.openai.com/"),
            Timeout = TimeSpan.FromMinutes(3)
        };
    }

    public async Task<string> SendMessageAsync(string apiKey, string model, List<ChatMessage> messages)
    {
        if (string.IsNullOrWhiteSpace(apiKey))
            throw new Exception("API key is required");

        var request = new
        {
            model = model,
            messages = messages.Select(m => new { role = m.Role, content = m.Content }).ToList()
        };

        var json = JsonSerializer.Serialize(request);
        using var httpRequest = new HttpRequestMessage(HttpMethod.Post, "v1/chat/completions");
        httpRequest.Headers.Authorization = new AuthenticationHeaderValue("Bearer", apiKey);
        httpRequest.Content = new StringContent(json, Encoding.UTF8, "application/json");

        var response = await _http.SendAsync(httpRequest);
        var responseBody = await response.Content.ReadAsStringAsync();

        if (!response.IsSuccessStatusCode)
        {
            var error = TryGetErrorMessage(responseBody);
            throw new Exception($"API Error: {error}");
        }

        var result = JsonSerializer.Deserialize<ChatResponse>(responseBody);
        return result?.Choices?.FirstOrDefault()?.Message?.Content ?? "";
    }

    private static string TryGetErrorMessage(string json)
    {
        try
        {
            using var doc = JsonDocument.Parse(json);
            if (doc.RootElement.TryGetProperty("error", out var error) &&
                error.TryGetProperty("message", out var msg))
            {
                return msg.GetString() ?? json;
            }
        }
        catch { }
        return json;
    }

    private class ChatResponse
    {
        [JsonPropertyName("choices")]
        public List<Choice>? Choices { get; set; }
    }

    private class Choice
    {
        [JsonPropertyName("message")]
        public MessageContent? Message { get; set; }
    }

    private class MessageContent
    {
        [JsonPropertyName("content")]
        public string? Content { get; set; }
    }
}
