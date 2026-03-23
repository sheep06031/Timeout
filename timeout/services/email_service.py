import logging
from django.conf import settings
logger = logging.getLogger(__name__)
class EmailService:
    """Send transactional emails via Twilio SendGrid."""
    @staticmethod
    def send_reset_code(to_email, code):
        """Send a 6-digit password reset code to the user's email."""
        from sendgrid import SendGridAPIClient
        from sendgrid.helpers.mail import Mail

        message = Mail(
            from_email=settings.SENDGRID_FROM_EMAIL,
            to_emails=to_email,
            subject='Timeout — Your Password Reset Code',
            html_content=(
                f'<div style="font-family:Arial,sans-serif;max-width:480px;margin:auto;'
                f'padding:32px;background:#f9fafb;border-radius:12px;">'
                f'<h2 style="color:#525AFF;margin-bottom:8px;">Password Reset</h2>'
                f'<p style="color:#4a5568;">Use the code below to reset your Timeout password. '
                f'This code expires in 10 minutes.</p>'
                f'<div style="font-size:36px;font-weight:700;letter-spacing:8px;text-align:center;'
                f'padding:24px;background:#fff;border-radius:8px;margin:24px 0;'
                f'border:2px solid #e2e8f0;color:#2d3748;">{code}</div>'
                f'<p style="color:#718096;font-size:14px;">If you didn\'t request this, '
                f'you can safely ignore this email.</p>'
                f'</div>'
            ),
        )

        try:
            sg = SendGridAPIClient(settings.SENDGRID_API_KEY)
            sg.send(message)
            return True
        except Exception as e:
            logger.error('SendGrid email failed: %s', e)
            return False
