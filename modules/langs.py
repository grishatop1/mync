import json

class LanguageSupport:
    def __init__(self, controller, pathToJson) -> None:
        self.controller = controller
        self.lng_code = self.controller.getFromCache("language")
        self.data = self.loadLanguage(pathToJson)

    def changeLanguage(self, lang_code):
        #self.lng_code = lang_code
        self.controller.writeToCache("language", lang_code)

    def loadLanguage(self, path):
        with open(path, "r", encoding="utf8") as f:
            data = json.load(f)
        return data

    def __call__(self, _id, *args):
        if not _id in self.data:
            return f"{_id} (NT)" #NT - not translated

        if not self.lng_code in self.data[_id]:
            return self.data[_id]["en"] #return en translation if there is no required
        output = self.data[_id][self.lng_code]
        for i, arg in enumerate(args):
            toFind = "{" + str(i) + "}"
            output = output.replace(toFind, str(arg))

        return output