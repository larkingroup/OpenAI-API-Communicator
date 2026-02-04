using Avalonia;
using Avalonia.Controls;
using Avalonia.Input;
using Avalonia.Styling;
using Avalonia.Threading;
using OpenAICommunicator.ViewModels;

namespace OpenAICommunicator.Views;

public partial class MainWindow : Window
{
    private ScrollViewer? _messagesScroller;

    public MainWindow()
    {
        InitializeComponent();
        
        // Set dark mode by default
        Application.Current!.RequestedThemeVariant = ThemeVariant.Dark;
        
        // Get scroller reference
        _messagesScroller = this.FindControl<ScrollViewer>("MessagesScroller");
        
        // Listen for escape key
        KeyDown += OnWindowKeyDown;
        
        // Setup ViewModel events after DataContext is set
        Loaded += (s, e) =>
        {
            if (DataContext is MainWindowViewModel vm)
            {
                vm.ThemeChanged += OnThemeChanged;
                vm.ScrollRequested += ScrollToBottom;
            }
        };
    }

    private void OnThemeChanged(bool isDark)
    {
        Application.Current!.RequestedThemeVariant = isDark ? ThemeVariant.Dark : ThemeVariant.Light;
    }

    private void OnWindowKeyDown(object? sender, KeyEventArgs e)
    {
        if (e.Key == Key.Escape && DataContext is MainWindowViewModel vm && vm.ShowSettings)
        {
            vm.ShowSettings = false;
            e.Handled = true;
        }
    }

    private void ScrollToBottom()
    {
        Dispatcher.UIThread.Post(() =>
        {
            _messagesScroller?.ScrollToEnd();
        }, DispatcherPriority.Background);
    }

    private void InputBox_KeyDown(object? sender, KeyEventArgs e)
    {
        if (e.Key == Key.Enter && e.KeyModifiers != KeyModifiers.Shift)
        {
            e.Handled = true;
            if (DataContext is MainWindowViewModel vm && vm.CanSend)
            {
                vm.SendMessageCommand.Execute(null);
            }
        }
    }

    private void DarkTheme_Click(object? sender, Avalonia.Interactivity.RoutedEventArgs e)
    {
        if (DataContext is MainWindowViewModel vm)
        {
            vm.IsDarkMode = true;
            Application.Current!.RequestedThemeVariant = ThemeVariant.Dark;
        }
    }

    private void LightTheme_Click(object? sender, Avalonia.Interactivity.RoutedEventArgs e)
    {
        if (DataContext is MainWindowViewModel vm)
        {
            vm.IsDarkMode = false;
            Application.Current!.RequestedThemeVariant = ThemeVariant.Light;
        }
    }
}
