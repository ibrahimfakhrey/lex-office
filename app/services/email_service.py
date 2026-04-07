"""Email service for OTP, invitations, and notifications."""
from flask import current_app, render_template_string
from flask_mail import Message
from app.extensions import mail


def send_email(to, subject, html_body, text_body=None):
    """Send an email. Silently fails in development if mail not configured."""
    try:
        msg = Message(
            subject=subject,
            recipients=[to] if isinstance(to, str) else to,
            html=html_body,
            body=text_body or '',
        )
        mail.send(msg)
        return True
    except Exception as e:
        current_app.logger.error(f'Email send failed to {to}: {e}')
        return False


def send_otp_email(email, otp_code, name=''):
    """Send OTP verification email."""
    subject = 'رمز التحقق - LexOffice'
    html = f"""
    <div dir="rtl" style="font-family: Tajawal, Arial, sans-serif; max-width: 500px; margin: 0 auto; padding: 20px;">
        <h2 style="color: #2563eb;">LexOffice</h2>
        <p>مرحباً {name}،</p>
        <p>رمز التحقق الخاص بك هو:</p>
        <div style="background: #f1f5f9; padding: 20px; text-align: center; border-radius: 8px; margin: 20px 0;">
            <span style="font-size: 32px; font-weight: bold; letter-spacing: 8px; color: #1e293b;">{otp_code}</span>
        </div>
        <p>هذا الرمز صالح لمدة 10 دقائق.</p>
        <p style="color: #64748b; font-size: 14px;">إذا لم تطلب هذا الرمز، يرجى تجاهل هذا البريد.</p>
    </div>
    """
    return send_email(email, subject, html)


def send_invitation_email(email, invite_token, office_name, role_name):
    """Send team invitation email."""
    from flask import url_for
    invite_url = url_for('auth.accept_invite', token=invite_token, _external=True)
    subject = f'دعوة للانضمام إلى {office_name} - LexOffice'
    html = f"""
    <div dir="rtl" style="font-family: Tajawal, Arial, sans-serif; max-width: 500px; margin: 0 auto; padding: 20px;">
        <h2 style="color: #2563eb;">LexOffice</h2>
        <p>مرحباً،</p>
        <p>تمت دعوتك للانضمام إلى <strong>{office_name}</strong> بصفة <strong>{role_name}</strong>.</p>
        <div style="text-align: center; margin: 30px 0;">
            <a href="{invite_url}" style="background: #2563eb; color: white; padding: 12px 32px; text-decoration: none; border-radius: 8px; font-weight: bold;">قبول الدعوة</a>
        </div>
        <p style="color: #64748b; font-size: 14px;">هذه الدعوة صالحة لمدة 7 أيام.</p>
    </div>
    """
    return send_email(email, subject, html)


def send_password_reset_email(email, reset_token, name=''):
    """Send password reset email."""
    from flask import url_for
    reset_url = url_for('auth.reset_password', token=reset_token, _external=True)
    subject = 'إعادة تعيين كلمة المرور - LexOffice'
    html = f"""
    <div dir="rtl" style="font-family: Tajawal, Arial, sans-serif; max-width: 500px; margin: 0 auto; padding: 20px;">
        <h2 style="color: #2563eb;">LexOffice</h2>
        <p>مرحباً {name}،</p>
        <p>تلقينا طلباً لإعادة تعيين كلمة المرور الخاصة بك.</p>
        <div style="text-align: center; margin: 30px 0;">
            <a href="{reset_url}" style="background: #2563eb; color: white; padding: 12px 32px; text-decoration: none; border-radius: 8px; font-weight: bold;">إعادة تعيين كلمة المرور</a>
        </div>
        <p style="color: #64748b; font-size: 14px;">هذا الرابط صالح لمدة ساعة واحدة. إذا لم تطلب هذا، يرجى تجاهل هذا البريد.</p>
    </div>
    """
    return send_email(email, subject, html)
