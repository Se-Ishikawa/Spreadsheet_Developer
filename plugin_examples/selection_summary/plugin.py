PLUGIN_META = {
    "name": "Selection Summary Example",
    "version": "1.0.0",
    "api_version": "1.0",
    "description": "SDK example: reads the selected cells without touching MainWindow internals.",
}

class SelectionSummaryPlugin:
    def activate(self, context):
        self.context = context
        context.add_action("Selection Summary Example", self.run, tooltip="Show the selected range through PluginContext")

    def run(self):
        data = self.context.selected_data(raw=True)
        rows = len(data)
        cols = max((len(r) for r in data), default=0)
        self.context.show_info("Selection Summary", f"Selected data: {rows} row(s) x {cols} column(s)")

def create_plugin():
    return SelectionSummaryPlugin()
