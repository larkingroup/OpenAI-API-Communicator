using System.Runtime.InteropServices;
using System.Text;

namespace OpenAICommunicator.Services;

public class SettingsService
{
    private const string CredentialTarget = "OpenAICommunicator_APIKey";
    
    private static readonly string ConfigFolder = Path.Combine(
        Environment.GetFolderPath(Environment.SpecialFolder.ApplicationData),
        "OpenAICommunicator");
    
    private static readonly string KeyFile = Path.Combine(ConfigFolder, "key");

    public string LoadApiKey()
    {
        // Try platform-specific secure storage first
        if (RuntimeInformation.IsOSPlatform(OSPlatform.Windows))
        {
            var key = WindowsCredentialManager.Read(CredentialTarget);
            if (!string.IsNullOrEmpty(key))
                return key;
        }
        else
        {
            // Linux/macOS: read from config file
            var key = ReadKeyFile();
            if (!string.IsNullOrEmpty(key))
                return key;
        }

        // Fallback: check environment variable
        var envKey = Environment.GetEnvironmentVariable("OPENAI_API_KEY");
        if (!string.IsNullOrEmpty(envKey))
            return envKey;

        return "";
    }

    public void SaveApiKey(string apiKey)
    {
        if (RuntimeInformation.IsOSPlatform(OSPlatform.Windows))
        {
            // Windows: use Credential Manager
            if (string.IsNullOrEmpty(apiKey))
                WindowsCredentialManager.Delete(CredentialTarget);
            else
                WindowsCredentialManager.Write(CredentialTarget, apiKey);
        }
        else
        {
            // Linux/macOS: use config file with restricted permissions
            WriteKeyFile(apiKey);
        }
    }

    private string? ReadKeyFile()
    {
        try
        {
            if (File.Exists(KeyFile))
                return File.ReadAllText(KeyFile).Trim();
        }
        catch { }
        return null;
    }

    private void WriteKeyFile(string apiKey)
    {
        try
        {
            Directory.CreateDirectory(ConfigFolder);
            File.WriteAllText(KeyFile, apiKey);
            
            // Set file permissions to 600 (owner read/write only) on Unix
            if (!RuntimeInformation.IsOSPlatform(OSPlatform.Windows))
            {
                File.SetUnixFileMode(KeyFile, UnixFileMode.UserRead | UnixFileMode.UserWrite);
            }
        }
        catch { }
    }
}

// Windows Credential Manager wrapper
internal static class WindowsCredentialManager
{
    public static string? Read(string target)
    {
        if (!RuntimeInformation.IsOSPlatform(OSPlatform.Windows))
            return null;
            
        if (!CredRead(target, 1, 0, out var credPtr))
            return null;

        try
        {
            var cred = Marshal.PtrToStructure<CREDENTIAL>(credPtr);
            if (cred.CredentialBlob != IntPtr.Zero && cred.CredentialBlobSize > 0)
            {
                var bytes = new byte[cred.CredentialBlobSize];
                Marshal.Copy(cred.CredentialBlob, bytes, 0, (int)cred.CredentialBlobSize);
                return Encoding.UTF8.GetString(bytes);
            }
            return null;
        }
        finally
        {
            CredFree(credPtr);
        }
    }

    public static void Write(string target, string secret)
    {
        if (!RuntimeInformation.IsOSPlatform(OSPlatform.Windows))
            return;
            
        var bytes = Encoding.UTF8.GetBytes(secret);
        var cred = new CREDENTIAL
        {
            Type = 1, // CRED_TYPE_GENERIC
            TargetName = target,
            CredentialBlob = Marshal.AllocHGlobal(bytes.Length),
            CredentialBlobSize = (uint)bytes.Length,
            Persist = 2, // CRED_PERSIST_LOCAL_MACHINE
            UserName = "OpenAICommunicator"
        };

        try
        {
            Marshal.Copy(bytes, 0, cred.CredentialBlob, bytes.Length);
            CredWrite(ref cred, 0);
        }
        finally
        {
            Marshal.FreeHGlobal(cred.CredentialBlob);
        }
    }

    public static void Delete(string target)
    {
        if (!RuntimeInformation.IsOSPlatform(OSPlatform.Windows))
            return;
        CredDelete(target, 1, 0);
    }

    [DllImport("advapi32.dll", SetLastError = true, CharSet = CharSet.Unicode)]
    private static extern bool CredRead(string target, int type, int flags, out IntPtr credential);

    [DllImport("advapi32.dll", SetLastError = true, CharSet = CharSet.Unicode)]
    private static extern bool CredWrite(ref CREDENTIAL credential, int flags);

    [DllImport("advapi32.dll", SetLastError = true, CharSet = CharSet.Unicode)]
    private static extern bool CredDelete(string target, int type, int flags);

    [DllImport("advapi32.dll")]
    private static extern void CredFree(IntPtr credential);

    [StructLayout(LayoutKind.Sequential, CharSet = CharSet.Unicode)]
    private struct CREDENTIAL
    {
        public int Flags;
        public int Type;
        public string TargetName;
        public string Comment;
        public long LastWritten;
        public uint CredentialBlobSize;
        public IntPtr CredentialBlob;
        public int Persist;
        public int AttributeCount;
        public IntPtr Attributes;
        public string TargetAlias;
        public string UserName;
    }
}
