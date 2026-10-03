# Research Spreadsheet Plugins

Drop each plugin into its own folder:

```
plugins/
  my_plugin/
    plugin.py
```

`plugin.py` must expose `PLUGIN_META`, `create_plugin()`, and an object with `activate(context)`.
Use only the public `PluginContext` API. See `plugin_examples/selection_summary/plugin.py`.
