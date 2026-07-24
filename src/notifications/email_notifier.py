"""
Email notifier for Open Brain.
"""
import os
import smtplib
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
from typing import List


class EmailNotifier:
    """Send notifications via email."""
    
    def __init__(
        self,
        smtp_host: str = None,
        smtp_port: int = None,
        username: str = None,
        password: str = None,
        from_addr: str = None,
        to_addrs: List[str] = None
    ):
        """
        Initialize email notifier.
        
        Args:
            smtp_host: SMTP server host (env: SMTP_HOST)
            smtp_port: SMTP server port (env: SMTP_PORT)
            username: SMTP username (env: SMTP_USERNAME)
            password: SMTP password (env: SMTP_PASSWORD)
            from_addr: From email address (env: SMTP_FROM)
            to_addrs: List of recipient addresses (env: SMTP_TO)
        """
        self.smtp_host = smtp_host or os.environ.get('SMTP_HOST', 'smtp.gmail.com')
        self.smtp_port = smtp_port or int(os.environ.get('SMTP_PORT', '587'))
        self.username = username or os.environ.get('SMTP_USERNAME')
        self.password = password or os.environ.get('SMTP_PASSWORD')
        self.from_addr = from_addr or os.environ.get('SMTP_FROM', self.username)
        self.to_addrs = to_addrs or os.environ.get('SMTP_TO', '').split(',')
    
    def is_configured(self) -> bool:
        """Check if notifier is configured."""
        return bool(self.username and self.password and self.to_addrs)
    
    def send_email(
        self,
        subject: str,
        body: str,
        html: bool = False
    ) -> bool:
        """
        Send an email.
        
        Args:
            subject: Email subject
            body: Email body
            html: Whether body is HTML
            
        Returns:
            True if successful
        """
        if not self.is_configured():
            print("Email notifier not configured. Set SMTP_* environment variables")
            return False
        
        msg = MIMEMultipart('alternative')
        msg['Subject'] = subject
        msg['From'] = self.from_addr
        msg['To'] = ', '.join(self.to_addrs)
        
        mime_type = 'html' if html else 'plain'
        msg.attach(MIMEText(body, mime_type))
        
        try:
            with smtplib.SMTP(self.smtp_host, self.smtp_port) as server:
                server.starttls()
                server.login(self.username, self.password)
                server.send_message(msg)
            return True
        except Exception as e:
            print(f"Error sending email: {e}")
            return False
    
    def send_memory_alert(self, memory_content: str, tags: List[str]) -> bool:
        """Send an alert when important memory is stored."""
        subject = "🧠 New Memory Stored - Open Brain"
        
        body = f"""A new memory has been stored in Open Brain.

Content:
{memory_content}

Tags: {', '.join(tags)}
"""
        
        return self.send_email(subject, body)
    
    def send_stats_digest(self, stats: dict) -> bool:
        """Send daily stats digest."""
        subject = "📊 Daily Digest - Open Brain"
        
        body = f"""Open Brain Daily Digest

Total Memories: {stats.get('total', 0)}

By Source:
"""
        
        by_source = stats.get('by_source', {})
        for source, count in by_source.items():
            body += f"  • {source}: {count}\n"
        
        top_tags = stats.get('top_tags', [])
        if top_tags:
            body += "\nTop Tags:\n"
            for tag, count in top_tags[:10]:
                body += f"  • #{tag}: {count}\n"
        
        return self.send_email(subject, body)
    
    def send_weekly_report(self, report: str) -> bool:
        """Send weekly report."""
        subject = "📝 Weekly Report - Open Brain"
        return self.send_email(subject, report)


def send_email_notification(subject: str, body: str) -> bool:
    """Convenience function to send email notification."""
    notifier = EmailNotifier()
    return notifier.send_email(subject, body)
