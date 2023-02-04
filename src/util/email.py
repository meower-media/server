from smtplib import SMTP
from jinja2 import Template
from threading import Thread
import requests
import os

from src.util import logging

EMAIL_PROVIDER = os.getenv("EMAIL_PROVIDER")
EMAIL_SUBJECTS = {
    "email_verification": "Verify your email address",
    "email_changed": "Security Alert: Email changed",
    "password_reset": "Reset your account password",
    "password_changed": "Security Alert: Password changed",
    "mfa_enabled": "Security Alert: Multi-factor authentication enabled",
    "mfa_disabled": "Security Alert: Multi-factor authentication disabled",
    "new_login_location": "Security Alert: Account logged in from a new location",
    "token_reuse": "Security Alert: Suspicious activity",
    "parent_link": "Verify your child's Meower account",
    "parent_unlink": "Important changes regarding your child's Meower account",
    "moderation_warning": "Notice of Terms of Service violation",
    "moderation_suspended": "Account suspended - Notice of Terms of Service violation",
    "moderation_banned": "Account banned - Notice of Terms of Service violation"
}

def send_email(email: str, name: str, template: str, kwargs: dict):
    def run():
        # Get and render email template
        with open(f"src/util/email_templates/{template}.html", "r") as f:
            email_body = Template(f.read()).render(**kwargs)
        
        # Send email
        if EMAIL_PROVIDER == "smtp":
            pass
        elif EMAIL_PROVIDER == "worker":
            requests.post(
                os.environ["EMAIL_WORKER_URI"],
                headers={
                    "X-Auth-Token": os.environ["EMAIL_WORKER_TOKEN"]
                },
                json={
                    "email": email,
                    "name": name,
                    "subject": EMAIL_SUBJECTS[template],
                    "body": email_body
                }
            )
        else:
            logging.error("No email provider set! Email was not sent.")
    Thread(target=run).start()
