class MyncNotifier:
    def __init__(self, controller) -> None:
        try:
            from win10toast import ToastNotifier
            self.initialized = True
        except:
            self.initialized = False
            return

        self.controller = controller
        self.toast = ToastNotifier()
        

    def notify(self, content, title="Mync"):
        if not self.initialized: return
        self.toast.show_toast(
            title,
            content,
            icon_path="media/iconica.ico",
            duration=4,
            threaded=True
        )