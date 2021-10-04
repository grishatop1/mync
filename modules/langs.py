import json

class LanguageSupport:
    def __init__(self, controller, pathToJson) -> None:
        self.controller = controller
        self.lng_code = self.controller.getFromCache("language")
        self.data = self.loadLanguage(pathToJson)

    def loadLanguage(self, path):
        with open(path, "r", encoding="utf8") as f:
            data = json.load(f)
        return data[self.lng_code]

    def str(self, _id, *args):
        if not _id in self.data:
            return "Not translated!"

        output = self.data[_id]
        for i, arg in enumerate(args):
            toFind = "{" + str(i) + "}"
            output = output.replace(toFind, arg)

        return output