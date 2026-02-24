# app/main.py
"""
Application Entry Point
"""
import sys
from PyQt6.QtWidgets import QApplication
from PyQt6.QtGui import QGuiApplication
from PyQt6.QtCore import Qt, qInstallMessageHandler, QtMsgType
from app.controller import ApplicationController


def qt_message_handler(mode, context, message):
    """
    Custom Qt message handler to suppress QPainter warnings.

    Args:
        mode: QtMsgType - The type of message
        context: QMessageLogContext - Context information
        message: str - The message content
    """
    # Suppress QPainter warnings as they are not from our code and can be safely ignored
    if "QPainter" in message:
        return

    # For all other messages, use default handling
    # We can't call the original handler directly, so we'll print to stderr for warnings/errors
    if mode in (QtMsgType.QtWarningMsg, QtMsgType.QtCriticalMsg, QtMsgType.QtFatalMsg):
        print(f"Qt {mode.name}: {message}", file=sys.stderr)
    elif mode == QtMsgType.QtInfoMsg:
        print(f"Qt Info: {message}", file=sys.stderr)
    # QtDebugMsg is typically not printed in release builds

if __name__ == "__main__":
    # Set high DPI policy for better scaling on modern displays (must be before QApplication)
    QGuiApplication.setHighDpiScaleFactorRoundingPolicy(Qt.HighDpiScaleFactorRoundingPolicy.PassThrough)
    QApplication.setAttribute(Qt.ApplicationAttribute.AA_ShareOpenGLContexts)

    try:
        # Install custom message handler to suppress QPainter warnings
        qInstallMessageHandler(qt_message_handler)

        # QApplication instance must be created first
        q_app = QApplication(sys.argv)
        
        # Initialize and run the main application controller
        controller = ApplicationController(q_app)
        controller.run()
        
    except Exception as e:
        print(f"FATAL APPLICATION ERROR: {e}", file=sys.stderr)
        sys.exit(1)
