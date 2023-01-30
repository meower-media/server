from better_profanity import profanity

# Load profanity list
profanity.load_censor_words()

def censor(text: str):
    return profanity.censor(text)
