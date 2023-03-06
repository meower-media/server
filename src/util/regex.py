USERNAME_VALIDATION = "[a-zA-Z0-9-_.]{1,20}"
EMAIL_VALIDATION = "^[\w-\.]+@([\w-]+\.)+[\w-]{2,4}$"
USER_MENTION = "<@!?[0-9]{1,25}>"
CHAT_MENTION = "<#!?[0-9]{1,25}>"


def extract_mention(text: str) -> str:
    notify = ("!" not in text)
    for char in [
        "<",
        ">",
        "@",
        "#",
        "!"
    ]:
        text = text.replace(char, "")
    return text, notify
