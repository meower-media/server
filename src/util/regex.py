USERNAME_VALIDATION = "[a-zA-Z0-9-_.]{1,20}"
EMAIL_VALIDATION = "^[\w-\.]+@([\w-]+\.)+[\w-]{2,4}$"
USER_MENTION = f"@!?{USERNAME_VALIDATION}"


def extract_mention(text: str) -> str:
    notify = ("!" not in text)
    for char in [
        "@",
        "!"
    ]:
        text = text.replace(char, "")
    return text, notify
