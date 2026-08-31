import logging
from django.conf import settings
from django.core.mail import send_mail

logger = logging.getLogger("video_generator")


def send_account_verification_email(user, token_str: str) -> bool:
    """Dispatches an account verification email containing an activation link."""
    frontend_url = getattr(settings, "FRONTEND_URL", "http://localhost:3000").rstrip("/")
    verification_url = f"{frontend_url}/verify-email?token={token_str}"

    subject = "Verify your AI Video Studio account"
    from_email = getattr(settings, "DEFAULT_FROM_EMAIL", "AI Video Studio <no-reply@aivideostudio.com>")
    recipient_list = [user.email]

    text_body = (
        f"Hello {user.username},\n\n"
        "Thank you for creating an account with AI Video Studio!\n\n"
        "Please verify your email address to activate your account and claim your 10 Free credits:\n"
        f"{verification_url}\n\n"
        "If you did not create this account, please ignore this email.\n"
    )

    html_body = f"""<!DOCTYPE html>
<html>
<head>
  <meta charset="utf-8">
  <title>Verify your AI Video Studio account</title>
</head>
<body style="margin: 0; padding: 0; background-color: #08090d; font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, Helvetica, Arial, sans-serif; color: #ffffff;">
  <table role="presentation" border="0" cellpadding="0" cellspacing="0" width="100%" style="background-color: #08090d; padding: 40px 20px;">
    <tr>
      <td align="center">
        <table role="presentation" border="0" cellpadding="0" cellspacing="0" width="100%" style="max-width: 540px; background-color: #0d0e14; border: 1px solid rgba(255, 255, 255, 0.1); border-radius: 24px; padding: 40px; box-shadow: 0 20px 40px rgba(0, 0, 0, 0.5);">
          <tr>
            <td align="center" style="padding-bottom: 24px;">
              <span style="display: inline-block; background-color: rgba(124, 58, 237, 0.15); color: #a78bfa; border: 1px solid rgba(124, 58, 237, 0.3); border-radius: 9999px; padding: 6px 16px; font-size: 11px; font-weight: 700; text-transform: uppercase; letter-spacing: 0.15em;">
                AI Video Studio
              </span>
            </td>
          </tr>
          <tr>
            <td align="center" style="padding-bottom: 12px;">
              <h1 style="margin: 0; font-size: 24px; font-weight: 700; color: #ffffff; letter-spacing: -0.02em;">
                Verify your email address
              </h1>
            </td>
          </tr>
          <tr>
            <td align="center" style="padding-bottom: 28px;">
              <p style="margin: 0; font-size: 14px; line-height: 1.6; color: rgba(255, 255, 255, 0.6);">
                Hello <strong style="color: #ffffff;">{user.username}</strong>, thanks for signing up! Activate your account now to claim your <strong style="color: #34d399;">10 Free Credits</strong> and start generating AI videos.
              </p>
            </td>
          </tr>
          <tr>
            <td align="center" style="padding-bottom: 32px;">
              <table role="presentation" border="0" cellpadding="0" cellspacing="0">
                <tr>
                  <td align="center" style="border-radius: 14px; background-color: #ffffff;">
                    <a href="{verification_url}" target="_blank" style="display: inline-block; padding: 14px 32px; font-size: 14px; font-weight: 600; color: #000000; text-decoration: none; border-radius: 14px;">
                      Activate Account &rarr;
                    </a>
                  </td>
                </tr>
              </table>
            </td>
          </tr>
          <tr>
            <td style="border-top: 1px solid rgba(255, 255, 255, 0.08); padding-top: 20px;">
              <p style="margin: 0 0 8px 0; font-size: 11px; color: rgba(255, 255, 255, 0.4);">
                If the button above does not work, copy and paste this link into your browser:
              </p>
              <p style="margin: 0; font-size: 11px; color: #a78bfa; word-break: break-all;">
                <a href="{verification_url}" style="color: #a78bfa; text-decoration: underline;">{verification_url}</a>
              </p>
            </td>
          </tr>
        </table>
      </td>
    </tr>
  </table>
</body>
</html>"""

    if settings.DEBUG:
        logger.info(f"[DEV] Verification email for {user.email}: {verification_url}")

    try:
        send_mail(
            subject=subject,
            message=text_body,
            from_email=from_email,
            recipient_list=recipient_list,
            html_message=html_body,
            fail_silently=False,
        )
        return True
    except Exception as e:
        logger.error(f"Failed to dispatch verification email to {user.email}: {e}")
        return False
