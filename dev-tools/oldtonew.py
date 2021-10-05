import json

INPUT_FILE = "languages.json"
OUTPUT_FILE = "languages-new.json"

new_data = {}
with open(INPUT_FILE, "r", encoding="utf8") as f:
    data = json.load(f)

for lang_code, lang_data in data.items():
    for _id, value in lang_data.items():
        if not _id in new_data:
            new_data[_id] = {}
        new_data[_id].update(
            {lang_code:value}
        )

with open(OUTPUT_FILE, "w", encoding="utf8") as f:
    json.dump(new_data, f, indent=4, ensure_ascii=False)