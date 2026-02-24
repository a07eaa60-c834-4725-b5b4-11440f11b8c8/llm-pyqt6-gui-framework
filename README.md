# PyQt6 Chat Framework

A modern desktop chat application with support for multiple AI services including Google Gemini and NVIDIA NIM.

## Features

- **Multi-Service Support**: Switch between Gemini and NVIDIA NIM AI services
- **Multiple Models**: Access to Gemini Flash/Pro, DeepSeek V3.2, and Kimi K2
- **File Attachments**: Upload and process files with AI (Gemini only)
- **Streaming Responses**: Real-time response streaming with thinking/reasoning display
- **Chat History**: Persistent chat storage with navigation
- **Dark Theme**: Modern dark UI with syntax highlighting
- **Keyboard Shortcuts**: Efficient navigation and controls

## Requirements

- Python 3.8+
- Windows/Linux/macOS

## Installation

1. Clone the repository:
   ```bash
   git clone https://github.com/yourusername/pyqt6-chat-framework.git
   cd pyqt6-chat-framework
   ```

2. Create a virtual environment (recommended):
   ```bash
   python -m venv venv
   
   # Windows
   venv\Scripts\activate
   
   # Linux/macOS
   source venv/bin/activate
   ```

3. Install dependencies:
   ```bash
   pip install -r requirements.txt
   ```

## Configuration

### API Keys

Set environment variables for your chosen AI service(s):

**Windows (Command Prompt):**
```cmd
set GEMINI_API_KEY=your_gemini_api_key_here
set NVIDIA_NIM_API_KEY=your_nvidia_nim_api_key_here
```

**Windows (PowerShell):**
```powershell
$env:GEMINI_API_KEY="your_gemini_api_key_here"
$env:NVIDIA_NIM_API_KEY="your_nvidia_nim_api_key_here"
```

**Linux/macOS:**
```bash
export GEMINI_API_KEY="your_gemini_api_key_here"
export NVIDIA_NIM_API_KEY="your_nvidia_nim_api_key_here"
```

### API Key Rotation (Gemini)

For rate limit handling, you can configure multiple Gemini API keys:

```bash
export GEMINI_ROTATE_API_KEY="key1,key2,key3"
```

### Getting API Keys

- **Google Gemini**: [Google AI Studio](https://aistudio.google.com/app/apikey)
- **NVIDIA NIM**: [NVIDIA Build](https://build.nvidia.com/)

## Usage

### Running the Application

**Windows:**
```cmd
start.bat
```

Or directly:
```bash
python -m app.main
```

### Keyboard Shortcuts

| Shortcut | Action |
|----------|--------|
| `Ctrl+Enter` | Send message |
| `Ctrl+F` | Open search in response panel |
| `Ctrl+Left` | Navigate to previous chat |
| `Ctrl+Right` | Navigate to next chat (or create new) |
| `Ctrl+D` | Delete all chats |
| `Ctrl+V` | Paste image from clipboard |

### Supported Models

| Service | Model | File Support |
|---------|-------|--------------|
| Gemini | Flash (gemini-2.5-flash) | ✅ Yes |
| Gemini | Pro (gemini-2.5-pro) | ✅ Yes |
| NVIDIA NIM | DeepSeek V3.2 | ❌ No |
| NVIDIA NIM | Kimi K2 | ❌ No |

### File Attachments

- Click **Attach** button or drag-and-drop files
- Supports images, PDFs, and other file types
- Maximum file size: 15MB
- File attachments only available with Gemini service

## Project Structure

```
pyqt6-chat-framework/
├── app/
│   ├── main.py          # Application entry point
│   └── controller.py    # Application orchestration
├── core/
│   ├── config.py        # Configuration management
│   └── services/        # AI service integrations
├── gui/
│   ├── main_window.py   # Main application window
│   └── widgets/         # UI components
├── assets/
│   └── icons/           # Application icons
├── requirements.txt     # Python dependencies
└── start.bat           # Windows launcher
```

## Dependencies

- **PyQt6** - GUI framework
- **google-genai** - Gemini API integration
- **openai** - NVIDIA NIM API integration (OpenAI-compatible)
- **Pillow** - Image processing
- **markdown** - Markdown rendering
- **Pygments** - Syntax highlighting
- **PyPDF2** - PDF file processing

## Troubleshooting

### "No API keys configured" Error

Ensure environment variables are set before running the application. On Windows, you may need to restart your terminal after setting environment variables.

### File Upload Not Working

- Verify you're using Gemini service (NVIDIA NIM doesn't support file attachments)
- Check file size is under 15MB
- Ensure file format is supported

### Rate Limit Errors

For Gemini, configure multiple API keys using `GEMINI_ROTATE_API_KEY` for automatic key rotation on rate limits.

## License

[Add your license here]

## Contributing

[Add contribution guidelines here]
