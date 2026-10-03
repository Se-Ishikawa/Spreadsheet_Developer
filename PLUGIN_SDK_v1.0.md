# Research Spreadsheet Plugin SDK v1.0

v0.5.0 introduces the first stable plugin boundary. Analysis plugins should use `PluginContext` instead of accessing `MainWindow` internals.

## Entry point
Each plugin lives in `plugins/<plugin_id>/plugin.py` and exports:

```python
PLUGIN_META = {"name":"My Plugin", "version":"1.0.0", "api_version":"1.0", "description":"..."}

def create_plugin():
    return MyPlugin()

class MyPlugin:
    def activate(self, context):
        context.add_action("Run My Plugin", self.run)
```

## PluginContext v1.0
- `current_sheet_name()`
- `sheet_names()`
- `selected_range()`
- `selected_data(raw=True)`
- `current_sheet_data(raw=True)`
- `create_sheet(name)`
- `write_cells(sheet_name, start_row, start_col, matrix)`
- `activate_sheet(sheet_name)`
- `add_action(text, callback, tooltip="")`
- `show_info(title, message)`
- `show_warning(title, message)`

## Safety / lifecycle
Plugins are normal Python code and should only be installed from trusted sources. Enable/disable changes are persisted in `plugins/plugin_state.json` and take effect after restart. A broken plugin is isolated during loading and recorded in `research_spreadsheet.log`; the spreadsheet continues starting.

## Example
Copy `plugin_examples/selection_summary` into `plugins/` to test discovery and action registration.
