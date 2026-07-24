"""
Telegram bot notifier for Open Brain.
"""
import os
from typing import List

import requests


class TelegramNotifier:
    """Send notifications via Telegram bot."""
    
    def __init__(self, bot_token: str = None, chat_id: str = None):
        """
        Initialize Telegram notifier.
        
        Args:
            bot_token: Telegram bot token (env: TELEGRAM_BOT_TOKEN)
            chat_id: Chat ID to send to (env: TELEGRAM_CHAT_ID)
        """
        self.bot_token = bot_token or os.environ.get('TELEGRAM_BOT_TOKEN')
        self.chat_id = chat_id or os.environ.get('TELEGRAM_CHAT_ID')
        self.api_url = f"https://api.telegram.org/bot{self.bot_token}" if self.bot_token else None
    
    def is_configured(self) -> bool:
        """Check if notifier is configured."""
        return bool(self.bot_token and self.chat_id)
    
    def send_message(self, message: str, parse_mode: str = "Markdown") -> bool:
        """
        Send a message via Telegram.
        
        Args:
            message: Message to send
            parse_mode: Parse mode (Markdown, HTML)
            
        Returns:
            True if successful
        """
        if not self.is_configured():
            print("Telegram notifier not configured. Set TELEGRAM_BOT_TOKEN and TELEGRAM_CHAT_ID")
            return False
        
        url = f"{self.api_url}/sendMessage"
        data = {
            "chat_id": self.chat_id,
            "text": message,
            "parse_mode": parse_mode
        }
        
        try:
            response = requests.post(url, json=data, timeout=10)
            return response.status_code == 200
        except Exception as e:
            print(f"Error sending Telegram message: {e}")
            return False
    
    def send_memory_alert(self, memory_content: str, tags: List[str]) -> bool:
        """Send an alert when important memory is stored."""
        message = "🧠 *New Memory Stored*\n\n"
        message += f"{memory_content[:200]}...\n\n"
        if tags:
            message += f"Tags: {', '.join(['#' + t for t in tags])}"
        
        return self.send_message(message)
    
    def send_stats_digest(self, stats: dict) -> bool:
        """Send daily stats digest."""
        message = "📊 *Open Brain Daily Digest*\n\n"
        message += f"Total Memories: {stats.get('total', 0)}\n"
        
        by_source = stats.get('by_source', {})
        if by_source:
            message += "\n*By Source:*\n"
            for source, count in by_source.items():
                message += f"• {source}: {count}\n"
        
        return self.send_message(message)
    
    def send_error_alert(self, error: str) -> bool:
        """Send an error alert."""
        message = f"⚠️ *Open Brain Error*\n\n{error}"
        return self.send_message(message)


def send_notification(message: str) -> bool:
    """Convenience function to send notification."""
    notifier = TelegramNotifier()
    return notifier.send_message(message)
