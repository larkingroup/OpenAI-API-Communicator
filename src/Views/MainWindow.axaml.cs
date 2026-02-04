using Avalonia.Controls;
using Avalonia.Input;
using OpenAICommunicator.ViewModels;

namespace OpenAICommunicator.Views;

public partial class MainWindow : Window
{
    public MainWindow()
    {
        InitializeComponent();
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
}
