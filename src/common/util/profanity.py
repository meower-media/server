from better_profanity import profanity

from src.common.database import db


# Load custom filter settings
custom_settings = db.config.find_one({"_id": "filter"})


def censor(text: str):
    profanity.load_censor_words(whitelist_words=custom_settings["whitelist"])
    text = profanity.censor(text)
    profanity.load_censor_words(whitelist_words=custom_settings["whitelist"], custom_words=custom_settings["blacklist"])
    text = profanity.censor(text)
    return text
