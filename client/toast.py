from win10toast import ToastNotifier

class MyncNotifier:
    def __init__(self, controller) -> None:
        self.controller = controller
        self.toast = ToastNotifier()

    def notify(self, content, title="Mync"):
        self.toast.show_toast(
            title,
            content,
            icon_path="media/iconica.ico",
            duration=4,
            threaded=True
        )