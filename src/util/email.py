from smtplib import SMTP
from jinja2 import Template
from threading import Thread
import requests
import os

from src.util import uid, logging
from src.database import db

EMAIL_PROVIDER = os.getenv("EMAIL_PROVIDER")
EMAIL_SUBJECTS = {
    "email_verification": "Verify your email address",
    "email_changed": "Email address changed",
    "password_reset": "Reset your account password",
    "password_changed": "Password changed",
    "new_login_location": "Logged in from a new location",
    "compromised_account": "Account disabled for suspicious activity",
    "tos_violation": "Notice of Terms of Service violation"
}

def send_email(email: str, name: str, template: str, kwargs: dict):
    def run():
        # Check whether email provider and template are valid
        if EMAIL_PROVIDER not in ["smtp", "worker"]:
            logging.error("No email provider set! Email was not sent.")
        elif template not in EMAIL_SUBJECTS:
            logging.error(f"No email template named {template}! Email was not sent.")

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

        # Log sent email
        db.sent_emails.insert_one({
            "_id": uid.snowflake(),
            "email": email,
            "name": name,
            "template": template,
            "kwargs": kwargs,
            "subject": EMAIL_SUBJECTS[template],
            "body": email_body,
            "time": uid.timestamp()
        })
    Thread(target=run).start()
