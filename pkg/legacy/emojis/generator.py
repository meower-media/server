"""
The purpose of this generator is to remove data that is unnecessary for Meower clients to use in their emoji pickers.

This generator uses https://unpkg.com/unicode-emoji-json@0.6.0/data-by-group.json for emoji groups.
"""

import requests, json, copy
from emoji import emojize
from emoji.unicode_codes.data_dict import EMOJI_DATA, LANGUAGES, fully_qualified

DATA_BY_GROUP_URL = "https://unpkg.com/unicode-emoji-json@0.6.0/data-by-group.json"

def apply_skin_tone(seq: str, tone: str) -> str:
    new_seq = ""
    for comp in seq:
        comp_data = EMOJI_DATA.get(comp)
        new_seq += comp + (tone if comp_data and comp_data["status"] == fully_qualified else "")
    return new_seq

def generate(dir: str = "emojis"):
    # Get emoji groups
    resp = requests.get(DATA_BY_GROUP_URL)
    if not resp.ok:
        print(f"Response code for data-by-group request ({resp.status_code}) was not OK: {resp.text}")
        exit(1)
    resp_json = resp.json()

    # Combine smileys_emotion & people_body
    resp_json[0]["emojis"] += resp_json[1]["emojis"]
    del resp_json[1]

    # Construct groups
    groups = []
    for group in resp_json:
        match group["slug"]:
            case "smileys_emotion":
                groups.append({"slug": "people", "name": "People", "icon_emoji": "😀", "emojis": group["emojis"]})
            case "animals_nature":
                groups.append({"slug": "animals_nature", "name": "Animals & Nature", "icon_emoji": "😺", "emojis": group["emojis"]})
            case "food_drink":
                groups.append({"slug": "food_drink", "name": "Food & Drink", "icon_emoji": "🍎", "emojis": group["emojis"]})
            case "travel":
                groups.append({"slug": "travel", "name": "Travel", "icon_emoji": "🏠", "emojis": group["emojis"]})
            case "activities":
                groups.append({"slug": "activities", "name": "Activities", "icon_emoji": "⚽", "emojis": group["emojis"]})
            case "objects":
                groups.append({"slug": "objects", "name": "Objects", "icon_emoji": "📃", "emojis": group["emojis"]})
            case "symbols":
                groups.append({"slug": "symbols", "name": "Symbols", "icon_emoji": "❤️", "emojis": group["emojis"]})
            case "flags":
                groups.append({"slug": "flags", "name": "Flags", "icon_emoji": "🏳️‍🌈", "emojis": group["emojis"]})

    # Format `emojis` arrays like this: [["<base emoji>", "<light tone>", "<medium light tone>", "<medium tone>", "<medium dark tone>", "<dark tone>"], [<emoji name and aliases (strings)>]]
    # NOTE: Alternate tones will not be present for emojis that don't support skin tones. Emojis will always have a base emoji at index 0.
    for group in groups:
        for i, emoji in enumerate(group["emojis"]):
            emoji_data = EMOJI_DATA[emoji["emoji"]]
            group["emojis"][i] = [
                [emoji["emoji"]] + ([
                    apply_skin_tone(emojize(emoji_data["en"]), "\U0001F3FB"), # light
                    apply_skin_tone(emojize(emoji_data["en"]), "\U0001F3FC"), # medium light
                    apply_skin_tone(emojize(emoji_data["en"]), "\U0001F3FD"), # medium
                    apply_skin_tone(emojize(emoji_data["en"]), "\U0001F3FE"), # medium dark
                    apply_skin_tone(emojize(emoji_data["en"]), "\U0001F3FF")  # dark
                ] if emoji["skin_tone_support"] else []),
                None  # names (done per language)
            ]

    for lang in LANGUAGES:
        # Update emoji names (sadly, no aliases for other langs)
        for group in copy.copy(groups):
            for emoji in group["emojis"]:
                emoji_data = EMOJI_DATA[emoji[0][0]]
                emoji[1] = [emoji_data[lang]] + (emoji_data["alias"] if lang == "en" and "alias" in emoji_data else [])

        # Dump language
        f = open(f"{dir}/{lang}.json", "w")
        f.write(json.dumps(groups, separators=(",", ":")))
        f.close()

if __name__ == "__main__":
    generate()
