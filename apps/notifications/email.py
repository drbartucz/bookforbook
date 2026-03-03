"""
Email helper functions for BookForBook notifications.
Uses Django's email backend (SendGrid SMTP in production, console in development).
"""
import logging

from django.conf import settings
from django.core.mail import send_mail, EmailMultiAlternatives
from django.template.loader import render_to_string
from django.utils.html import strip_tags

logger = logging.getLogger(__name__)


def send_email(
    to_email: str,
    subject: str,
    text_body: str,
    html_body: str | None = None,
    from_email: str | None = None,
) -> bool:
    """
    Send an email. Returns True on success, False on failure.
    """
    from_email = from_email or settings.DEFAULT_FROM_EMAIL
    try:
        if html_body:
            msg = EmailMultiAlternatives(subject, text_body, from_email, [to_email])
            msg.attach_alternative(html_body, 'text/html')
            msg.send()
        else:
            send_mail(subject, text_body, from_email, [to_email], fail_silently=False)
        logger.info('Email sent to %s: %s', to_email, subject)
        return True
    except Exception:
        logger.exception('Failed to send email to %s: %s', to_email, subject)
        return False


def send_verification_email(user, uid: str, token: str) -> bool:
    verify_url = f'{settings.FRONTEND_URL}/verify-email?uid={uid}&token={token}'
    subject = 'Verify your BookForBook email address'
    text_body = (
        f'Hi {user.username},\n\n'
        f'Please verify your email address by clicking the link below:\n\n'
        f'{verify_url}\n\n'
        f'This link expires in 24 hours.\n\n'
        f'If you did not create a BookForBook account, you can safely ignore this email.\n\n'
        f'— The BookForBook Team'
    )
    html_body = (
        f'<p>Hi <strong>{user.username}</strong>,</p>'
        f'<p>Please verify your email address by clicking the link below:</p>'
        f'<p><a href="{verify_url}" style="background:#2563eb;color:#fff;padding:12px 24px;'
        f'text-decoration:none;border-radius:4px;display:inline-block;">Verify Email</a></p>'
        f'<p>This link expires in 24 hours.</p>'
        f'<p>If you did not create a BookForBook account, you can safely ignore this email.</p>'
        f'<p>— The BookForBook Team</p>'
    )
    return send_email(user.email, subject, text_body, html_body)


def send_password_reset_email(user, uid: str, token: str) -> bool:
    reset_url = f'{settings.FRONTEND_URL}/reset-password?uid={uid}&token={token}'
    subject = 'Reset your BookForBook password'
    text_body = (
        f'Hi {user.username},\n\n'
        f'Click the link below to reset your password:\n\n'
        f'{reset_url}\n\n'
        f'This link expires in 1 hour.\n\n'
        f'If you did not request a password reset, you can safely ignore this email.\n\n'
        f'— The BookForBook Team'
    )
    return send_email(user.email, subject, text_body)


def send_match_notification_email(user, match) -> bool:
    match_url = f'{settings.FRONTEND_URL}/matches/{match.pk}'
    subject = 'You have a new book match!'
    if match.match_type == 'direct':
        body_detail = 'Someone wants to trade books with you!'
    else:
        body_detail = f'You are part of a {len(list(match.legs.all()))}-way book exchange ring!'
    text_body = (
        f'Hi {user.username},\n\n'
        f'{body_detail}\n\n'
        f'View your match here:\n{match_url}\n\n'
        f'This match expires in 48 hours — act soon!\n\n'
        f'— The BookForBook Team'
    )
    return send_email(user.email, subject, text_body)


def send_trade_confirmed_email(user, trade) -> bool:
    trade_url = f'{settings.FRONTEND_URL}/trades/{trade.pk}'
    subject = 'Your trade has been confirmed!'
    text_body = (
        f'Hi {user.username},\n\n'
        f'Your trade has been confirmed. Shipping addresses are now revealed.\n\n'
        f'View your trade here:\n{trade_url}\n\n'
        f'Please ship your book within a reasonable time.\n\n'
        f'— The BookForBook Team'
    )
    return send_email(user.email, subject, text_body)


def send_rating_reminder_email(user, trade) -> bool:
    trade_url = f'{settings.FRONTEND_URL}/trades/{trade.pk}'
    subject = 'Please rate your BookForBook trade'
    text_body = (
        f'Hi {user.username},\n\n'
        f'Don\'t forget to rate your recent trade!\n\n'
        f'Your rating helps build trust in the BookForBook community.\n\n'
        f'Rate your trade here:\n{trade_url}\n\n'
        f'— The BookForBook Team'
    )
    return send_email(user.email, subject, text_body)


def send_inactivity_warning_1m_email(user) -> bool:
    subject = 'We miss you on BookForBook!'
    text_body = (
        f'Hi {user.username},\n\n'
        f'We noticed you haven\'t logged in for a while. '
        f'Your books are still available for matching!\n\n'
        f'Log back in to see your matches and keep your trades active.\n\n'
        f'{settings.FRONTEND_URL}\n\n'
        f'— The BookForBook Team'
    )
    return send_email(user.email, subject, text_body)


def send_inactivity_warning_2m_email(user) -> bool:
    subject = 'Your books will be delisted soon — BookForBook'
    text_body = (
        f'Hi {user.username},\n\n'
        f'You haven\'t logged in for 2 months. '
        f'If you don\'t log in within the next month, '
        f'your books will be temporarily removed from the matching pool.\n\n'
        f'Don\'t worry — your books stay in your account. '
        f'They\'ll be re-listed automatically when you log back in.\n\n'
        f'{settings.FRONTEND_URL}\n\n'
        f'— The BookForBook Team'
    )
    return send_email(user.email, subject, text_body)


def send_books_delisted_email(user) -> bool:
    subject = 'Your books have been delisted — BookForBook'
    text_body = (
        f'Hi {user.username},\n\n'
        f'Because you haven\'t logged in for 3 months, '
        f'your books have been temporarily removed from the matching pool.\n\n'
        f'Your books are still safely stored in your account. '
        f'Log back in to re-list them and start getting matches again!\n\n'
        f'{settings.FRONTEND_URL}\n\n'
        f'— The BookForBook Team'
    )
    return send_email(user.email, subject, text_body)


def send_account_deletion_email(user) -> bool:
    subject = 'BookForBook account deletion initiated'
    text_body = (
        f'Hi {user.username},\n\n'
        f'We have received your account deletion request. '
        f'Your account will be permanently deleted after a 30-day grace period.\n\n'
        f'A full export of your data has been queued and will be sent to this email.\n\n'
        f'If you change your mind, please contact support before the 30-day period ends.\n\n'
        f'— The BookForBook Team'
    )
    return send_email(user.email, subject, text_body)
