from __future__ import annotations

import json
import math
from dataclasses import dataclass
from typing import Any, Sequence

from matplotlib.backends.backend_qtagg import FigureCanvasQTAgg
from matplotlib.figure import Figure
from PySide6.QtCore import Qt, Signal
from PySide6.QtWidgets import (
    QAbstractItemView,
    QCheckBox,
    QComboBox,
    QDialog,
    QDialogButtonBox,
    QDoubleSpinBox,
    QFileDialog,
    QFormLayout,
    QGridLayout,
    QGroupBox,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QListWidget,
    QListWidgetItem,
    QMessageBox,
    QPlainTextEdit,
    QPushButton,
    QScrollArea,
    QSpinBox,
    QSplitter,
    QVBoxLayout,
    QWidget,
)


@dataclass
class SeriesSpec:
    name: str
    values: list[Any]


class ChartDialog(QDialog):
    sessionSaved = Signal(dict)

    def __init__(
        self,
        parent=None,
        headers: Sequence[str] = (),
        data: list[list[str]] | None = None,
        selected_cols: list[int] | None = None,
        selected_range: tuple[int, int, int, int] | None = None,
        initial_config: dict[str, Any] | None = None,
    ) -> None:
        super().__init__(parent)
        self.setWindowTitle("Create Chart - Phase 3")
        self.resize(1480, 940)
        self.setMinimumSize(1120, 680)
        self.setSizeGripEnabled(True)

        self.headers = list(headers)
        self.data = data or []
        self.selected_cols = selected_cols or []
        self.selected_range = selected_range
        self._last_stats = ""
        self._current_series_names: list[str] = []
        self._syncing_secondary = False

        root = QVBoxLayout(self)
        root.setContentsMargins(6, 6, 6, 6)
        root.setSpacing(6)

        splitter = QSplitter(Qt.Horizontal)
        splitter.setChildrenCollapsible(False)
        root.addWidget(splitter, 1)

        left_container = QWidget()
        left_layout = QVBoxLayout(left_container)
        left_layout.setContentsMargins(0, 0, 0, 0)
        left_layout.setSpacing(8)

        range_group = QGroupBox("Data Range")
        range_form = QFormLayout(range_group)
        self.range_label = QLabel(self._range_text())
        self.range_label.setWordWrap(True)
        self.auto_check = QCheckBox("Interpret selected range automatically")
        self.auto_check.setChecked(True)
        self.header_check = QCheckBox("Use first row as series names")
        self.header_check.setChecked(True)
        self.first_col_x_check = QCheckBox("Use first column as X axis")
        self.first_col_x_check.setChecked(True)
        self.row_series_check = QCheckBox("Series by rows instead of columns")
        self.drop_empty_check = QCheckBox("Skip empty rows / columns")
        self.drop_empty_check.setChecked(True)
        range_form.addRow("Selection", self.range_label)
        range_form.addRow("", self.auto_check)
        range_form.addRow("", self.header_check)
        range_form.addRow("", self.first_col_x_check)
        range_form.addRow("", self.row_series_check)
        range_form.addRow("", self.drop_empty_check)
        left_layout.addWidget(range_group)

        type_group = QGroupBox("Chart Type")
        type_form = QFormLayout(type_group)
        self.chart_type = QComboBox()
        self.chart_type.addItems([
            "Line",
            "Scatter",
            "Scatter + Fit",
            "Bar",
            "Horizontal Bar",
            "Area",
            "Step",
            "Histogram",
            "Boxplot",
            "Heatmap",
            "Pie",
            "Combo Line/Bar",
        ])
        self.x_combo = QComboBox()
        self.y_combo = QComboBox()
        self.x_combo.addItems(self.headers)
        self.y_combo.addItems(self.headers)
        default_x = self.selected_cols[0] if len(self.selected_cols) >= 1 else 0
        default_y = self.selected_cols[1] if len(self.selected_cols) >= 2 else (1 if len(self.headers) > 1 else 0)
        self.x_combo.setCurrentIndex(default_x)
        self.y_combo.setCurrentIndex(default_y)
        self.secondary_combo = QComboBox()
        self.secondary_combo.addItem("None")
        self.secondary_combo.addItems(self.headers)
        self.orientation_combo = QComboBox()
        self.orientation_combo.addItems(["Vertical", "Horizontal"])
        type_form.addRow("Chart Type", self.chart_type)
        type_form.addRow("Manual X", self.x_combo)
        type_form.addRow("Manual Y", self.y_combo)
        type_form.addRow("Legacy Secondary Y", self.secondary_combo)
        type_form.addRow("Bar Orientation", self.orientation_combo)
        left_layout.addWidget(type_group)

        style_group = QGroupBox("Style / Analysis")
        style_grid = QGridLayout(style_group)
        self.title_edit = QLineEdit()
        self.title_edit.setPlaceholderText("Chart title")
        self.x_label_edit = QLineEdit()
        self.x_label_edit.setPlaceholderText("X axis label")
        self.y_label_edit = QLineEdit()
        self.y_label_edit.setPlaceholderText("Y axis label")
        self.y2_label_edit = QLineEdit()
        self.y2_label_edit.setPlaceholderText("Secondary Y label")

        self.bins_spin = QSpinBox()
        self.bins_spin.setRange(3, 200)
        self.bins_spin.setValue(15)
        self.line_width_spin = QSpinBox()
        self.line_width_spin.setRange(1, 8)
        self.line_width_spin.setValue(2)
        self.marker_size_spin = QSpinBox()
        self.marker_size_spin.setRange(1, 16)
        self.marker_size_spin.setValue(6)
        self.marker_combo = QComboBox()
        self.marker_combo.addItems(["None", "o", "s", "^", "D", "x", "+", ".", "*"])
        self.cmap_combo = QComboBox()
        self.cmap_combo.addItems(["viridis", "plasma", "magma", "cividis", "coolwarm"])

        self.legend_check = QCheckBox("Show legend")
        self.legend_check.setChecked(True)
        self.grid_check = QCheckBox("Show grid")
        self.grid_check.setChecked(True)
        self.tight_check = QCheckBox("Tight layout")
        self.tight_check.setChecked(True)
        self.trend_check = QCheckBox("Show linear trendline")
        self.corr_check = QCheckBox("Annotate Pearson r")
        self.log_x_check = QCheckBox("Log X")
        self.log_y_check = QCheckBox("Log Y")
        self.annotate_points_check = QCheckBox("Annotate points")
        self.stacked_check = QCheckBox("Stack series")
        self.data_labels_check = QCheckBox("Bar / pie labels")
        self.regression_eq_check = QCheckBox("Annotate regression equation")
        self.errorbar_check = QCheckBox("Use Y error bars")
        self.error_mode_combo = QComboBox()
        self.error_mode_combo.addItems(["Constant", "From next series"])
        self.error_value_spin = QDoubleSpinBox()
        self.error_value_spin.setRange(0.0, 1_000_000.0)
        self.error_value_spin.setDecimals(6)
        self.error_value_spin.setValue(0.1)
        self.error_value_spin.setSingleStep(0.1)

        row = 0
        style_grid.addWidget(QLabel("Title"), row, 0)
        style_grid.addWidget(self.title_edit, row, 1, 1, 3)
        row += 1
        style_grid.addWidget(QLabel("X label"), row, 0)
        style_grid.addWidget(self.x_label_edit, row, 1)
        style_grid.addWidget(QLabel("Y label"), row, 2)
        style_grid.addWidget(self.y_label_edit, row, 3)
        row += 1
        style_grid.addWidget(QLabel("Y2 label"), row, 0)
        style_grid.addWidget(self.y2_label_edit, row, 1)
        style_grid.addWidget(QLabel("Bins"), row, 2)
        style_grid.addWidget(self.bins_spin, row, 3)
        row += 1
        style_grid.addWidget(QLabel("Line width"), row, 0)
        style_grid.addWidget(self.line_width_spin, row, 1)
        style_grid.addWidget(QLabel("Marker size"), row, 2)
        style_grid.addWidget(self.marker_size_spin, row, 3)
        row += 1
        style_grid.addWidget(QLabel("Marker"), row, 0)
        style_grid.addWidget(self.marker_combo, row, 1)
        style_grid.addWidget(QLabel("Colormap"), row, 2)
        style_grid.addWidget(self.cmap_combo, row, 3)
        row += 1
        style_grid.addWidget(self.legend_check, row, 0)
        style_grid.addWidget(self.grid_check, row, 1)
        style_grid.addWidget(self.tight_check, row, 2)
        style_grid.addWidget(self.trend_check, row, 3)
        row += 1
        style_grid.addWidget(self.corr_check, row, 0)
        style_grid.addWidget(self.log_x_check, row, 1)
        style_grid.addWidget(self.log_y_check, row, 2)
        style_grid.addWidget(self.annotate_points_check, row, 3)
        row += 1
        style_grid.addWidget(self.stacked_check, row, 0)
        style_grid.addWidget(self.data_labels_check, row, 1)
        style_grid.addWidget(self.regression_eq_check, row, 2)
        row += 1
        style_grid.addWidget(self.errorbar_check, row, 0)
        style_grid.addWidget(self.error_mode_combo, row, 1)
        style_grid.addWidget(QLabel("Error value"), row, 2)
        style_grid.addWidget(self.error_value_spin, row, 3)
        left_layout.addWidget(style_group)

        secondary_group = QGroupBox("Secondary Axis / Presets")
        secondary_layout = QVBoxLayout(secondary_group)
        secondary_layout.addWidget(QLabel("For Combo Line/Bar, checked series are drawn on the secondary Y axis."))
        self.secondary_series_list = QListWidget()
        self.secondary_series_list.setSelectionMode(QAbstractItemView.NoSelection)
        self.secondary_series_list.setMinimumHeight(120)
        secondary_layout.addWidget(self.secondary_series_list)

        preset_buttons = QHBoxLayout()
        self.save_preset_btn = QPushButton("Save Preset")
        self.load_preset_btn = QPushButton("Load Preset")
        preset_buttons.addWidget(self.save_preset_btn)
        preset_buttons.addWidget(self.load_preset_btn)
        secondary_layout.addLayout(preset_buttons)
        left_layout.addWidget(secondary_group)

        info_group = QGroupBox("Series Preview")
        info_layout = QVBoxLayout(info_group)
        self.series_info = QPlainTextEdit()
        self.series_info.setReadOnly(True)
        self.series_info.setMinimumHeight(180)
        info_layout.addWidget(self.series_info)
        left_layout.addWidget(info_group, 1)

        left_layout.addStretch(1)

        left_scroll = QScrollArea()
        left_scroll.setWidgetResizable(True)
        left_scroll.setHorizontalScrollBarPolicy(Qt.ScrollBarAsNeeded)
        left_scroll.setVerticalScrollBarPolicy(Qt.ScrollBarAsNeeded)
        left_scroll.setWidget(left_container)
        splitter.addWidget(left_scroll)

        right_panel = QWidget()
        right_layout = QVBoxLayout(right_panel)
        right_layout.setContentsMargins(0, 0, 0, 0)
        right_layout.setSpacing(6)
        self.figure = Figure()
        self.canvas = FigureCanvasQTAgg(self.figure)
        right_layout.addWidget(self.canvas, 1)
        splitter.addWidget(right_panel)
        splitter.setSizes([420, 980])
        splitter.setStretchFactor(0, 0)
        splitter.setStretchFactor(1, 1)

        btns = QDialogButtonBox(QDialogButtonBox.Close)
        self.plot_btn = btns.addButton("Plot", QDialogButtonBox.ActionRole)
        self.save_btn = btns.addButton("Save PNG", QDialogButtonBox.ActionRole)
        self.save_gallery_btn = btns.addButton("Save to Gallery", QDialogButtonBox.ActionRole)
        self.plot_btn.clicked.connect(self.plot)
        self.save_btn.clicked.connect(self._save_png)
        self.save_gallery_btn.clicked.connect(self._save_to_gallery)
        btns.rejected.connect(self.reject)
        root.addWidget(btns)

        signal_widgets = [
            self.chart_type,
            self.auto_check,
            self.header_check,
            self.first_col_x_check,
            self.row_series_check,
            self.drop_empty_check,
            self.x_combo,
            self.y_combo,
            self.secondary_combo,
            self.orientation_combo,
            self.legend_check,
            self.grid_check,
            self.tight_check,
            self.trend_check,
            self.corr_check,
            self.log_x_check,
            self.log_y_check,
            self.annotate_points_check,
            self.stacked_check,
            self.data_labels_check,
            self.marker_combo,
            self.cmap_combo,
            self.line_width_spin,
            self.marker_size_spin,
            self.bins_spin,
            self.regression_eq_check,
            self.errorbar_check,
            self.error_mode_combo,
            self.error_value_spin,
        ]
        for widget in signal_widgets:
            signal = getattr(widget, "currentTextChanged", None)
            if signal is not None:
                signal.connect(self.plot)
            signal = getattr(widget, "stateChanged", None)
            if signal is not None:
                signal.connect(self.plot)
            signal = getattr(widget, "valueChanged", None)
            if signal is not None:
                signal.connect(self.plot)

        for edit in [self.title_edit, self.x_label_edit, self.y_label_edit, self.y2_label_edit]:
            edit.textChanged.connect(self.plot)

        self.chart_type.currentTextChanged.connect(self._on_chart_type_changed)
        self.auto_check.stateChanged.connect(self._on_auto_changed)
        self.auto_check.stateChanged.connect(self._refresh_secondary_series)
        self.header_check.stateChanged.connect(self._refresh_secondary_series)
        self.first_col_x_check.stateChanged.connect(self._refresh_secondary_series)
        self.row_series_check.stateChanged.connect(self._refresh_secondary_series)
        self.drop_empty_check.stateChanged.connect(self._refresh_secondary_series)
        self.secondary_series_list.itemChanged.connect(lambda _item: self.plot())
        self.save_preset_btn.clicked.connect(self._save_preset)
        self.load_preset_btn.clicked.connect(self._load_preset)

        if initial_config:
            self._apply_config(initial_config)
        self._on_chart_type_changed(self.chart_type.currentText())
        self._on_auto_changed(self.auto_check.checkState())
        self._refresh_secondary_series()
        self.plot()

    def _range_text(self) -> str:
        if not self.selected_range:
            return "No rectangular selection - using full sheet / manual columns"
        r0, c0, r1, c1 = self.selected_range
        return f"Rows {r0 + 1}-{r1 + 1}, Cols {c0 + 1}-{c1 + 1}"

    def _on_auto_changed(self, _state: int) -> None:
        manual_enabled = not self.auto_check.isChecked()
        self.x_combo.setEnabled(manual_enabled)
        self.y_combo.setEnabled(manual_enabled)

    def _on_chart_type_changed(self, chart: str) -> None:
        histogram_like = chart == "Histogram"
        heatmap_like = chart == "Heatmap"
        combo_like = chart == "Combo Line/Bar"
        scatter_like = chart in {"Scatter", "Scatter + Fit"}
        box_like = chart == "Boxplot"

        self.bins_spin.setEnabled(histogram_like)
        self.secondary_combo.setEnabled(combo_like)
        self.orientation_combo.setEnabled(chart in {"Bar", "Horizontal Bar"})
        self.first_col_x_check.setEnabled(chart not in {"Histogram", "Boxplot"})
        self.row_series_check.setEnabled(chart not in {"Heatmap", "Pie", "Histogram"})
        self.stacked_check.setEnabled(chart in {"Bar", "Area", "Combo Line/Bar"})
        self.data_labels_check.setEnabled(chart in {"Bar", "Horizontal Bar", "Pie", "Combo Line/Bar"})
        self.cmap_combo.setEnabled(heatmap_like)
        self.trend_check.setEnabled(scatter_like)
        self.corr_check.setEnabled(scatter_like)
        self.regression_eq_check.setEnabled(scatter_like)
        self.annotate_points_check.setEnabled(scatter_like or chart == "Line")
        self.marker_combo.setEnabled(chart in {"Line", "Scatter", "Scatter + Fit", "Step", "Combo Line/Bar"})
        self.marker_size_spin.setEnabled(chart in {"Line", "Scatter", "Scatter + Fit", "Step", "Combo Line/Bar"})
        self.y2_label_edit.setEnabled(combo_like)
        self.secondary_series_list.setEnabled(combo_like)
        self.errorbar_check.setEnabled(chart in {"Line", "Scatter", "Scatter + Fit", "Bar", "Horizontal Bar", "Combo Line/Bar"})
        self.error_mode_combo.setEnabled(self.errorbar_check.isChecked() and not box_like)
        self.error_value_spin.setEnabled(self.errorbar_check.isChecked() and self.error_mode_combo.currentText() == "Constant")
        self._refresh_secondary_series()

    def _selected_matrix(self) -> list[list[Any]]:
        if not self.selected_range:
            return [row[:] for row in self.data]
        r0, c0, r1, c1 = self.selected_range
        matrix = []
        for r in range(r0, r1 + 1):
            row_values = []
            src = self.data[r] if r < len(self.data) else []
            for c in range(c0, c1 + 1):
                row_values.append(src[c] if c < len(src) else "")
            matrix.append(row_values)
        return matrix

    def _drop_empty_edges(self, matrix: list[list[Any]]) -> list[list[Any]]:
        if not matrix:
            return matrix
        rows = [row[:] for row in matrix]
        if self.drop_empty_check.isChecked():
            rows = [row for row in rows if any(str(v).strip() != "" for v in row)]
            if not rows:
                return []
            col_keep = []
            max_cols = max(len(r) for r in rows)
            for c in range(max_cols):
                keep = any(c < len(r) and str(r[c]).strip() != "" for r in rows)
                col_keep.append(keep)
            rows = [[r[c] if c < len(r) else "" for c, keep in enumerate(col_keep) if keep] for r in rows]
        return rows

    def _manual_dataset(self) -> tuple[list[Any], list[SeriesSpec]]:
        x_idx = self.x_combo.currentIndex()
        y_idx = self.y_combo.currentIndex()
        x_vals: list[Any] = []
        y_vals: list[Any] = []
        for row in self.data:
            x = row[x_idx] if x_idx < len(row) else ""
            y = row[y_idx] if y_idx < len(row) else ""
            if str(x).strip() == "" and str(y).strip() == "":
                continue
            x_vals.append(x)
            y_vals.append(y)
        x_name = self.headers[x_idx] if 0 <= x_idx < len(self.headers) else "X"
        y_name = self.headers[y_idx] if 0 <= y_idx < len(self.headers) else "Y"
        return x_vals, [SeriesSpec(y_name, y_vals)]

    def _auto_dataset(self) -> tuple[list[Any], list[SeriesSpec], str, str]:
        matrix = self._drop_empty_edges(self._selected_matrix())
        if not matrix:
            return [], [], "", ""

        row_series = self.row_series_check.isChecked()
        use_header = self.header_check.isChecked()
        use_first_col_x = self.first_col_x_check.isChecked()

        if row_series:
            matrix = list(map(list, zip(*matrix)))

        header_row: list[Any] | None = None
        if use_header and matrix:
            header_row = matrix[0]
            matrix = matrix[1:]

        if not matrix:
            return [], [], "", ""

        x_vals = []
        x_name = "Index"
        y_name = "Value"
        series: list[SeriesSpec] = []

        if use_first_col_x and matrix and matrix[0]:
            x_vals = [row[0] if len(row) >= 1 else "" for row in matrix]
            start_col = 1
            x_name = str(header_row[0]) if header_row and len(header_row) >= 1 and str(header_row[0]).strip() else x_name
        else:
            x_vals = list(range(1, len(matrix) + 1))
            start_col = 0

        max_cols = max(len(r) for r in matrix)
        for c in range(start_col, max_cols):
            vals = [row[c] if c < len(row) else "" for row in matrix]
            label = f"Series {c - start_col + 1}"
            if header_row and c < len(header_row) and str(header_row[c]).strip():
                label = str(header_row[c])
            series.append(SeriesSpec(label, vals))

        if series:
            y_name = "Values" if len(series) > 1 else series[0].name
        return x_vals, series, x_name, y_name

    def _get_dataset(self) -> tuple[list[Any], list[SeriesSpec], str, str]:
        if self.auto_check.isChecked() and self.selected_range:
            return self._auto_dataset()
        x_vals, series = self._manual_dataset()
        x_name = self.headers[self.x_combo.currentIndex()] if self.headers else "X"
        y_name = self.headers[self.y_combo.currentIndex()] if self.headers else "Y"
        return x_vals, series, x_name, y_name

    @staticmethod
    def _to_float(value: Any) -> float | None:
        if value is None:
            return None
        text = str(value).strip()
        if text == "":
            return None
        try:
            return float(text)
        except Exception:
            return None

    def _series_numeric_pairs(self, x_vals: list[Any], series: SeriesSpec) -> tuple[list[float], list[float], list[str], list[int]]:
        xs: list[float] = []
        ys: list[float] = []
        labels: list[str] = []
        indices: list[int] = []
        for idx, (x, y) in enumerate(zip(x_vals, series.values)):
            xf = self._to_float(x)
            yf = self._to_float(y)
            if xf is None or yf is None:
                continue
            xs.append(xf)
            ys.append(yf)
            labels.append(str(x))
            indices.append(idx)
        return xs, ys, labels, indices

    def _series_y_numeric(self, series: SeriesSpec) -> list[float]:
        vals = []
        for item in series.values:
            num = self._to_float(item)
            if num is not None:
                vals.append(num)
        return vals

    @staticmethod
    def _pearson_r(x: list[float], y: list[float]) -> float | None:
        n = min(len(x), len(y))
        if n < 2:
            return None
        x = x[:n]
        y = y[:n]
        mx = sum(x) / n
        my = sum(y) / n
        sx = math.sqrt(sum((v - mx) ** 2 for v in x))
        sy = math.sqrt(sum((v - my) ** 2 for v in y))
        if sx == 0 or sy == 0:
            return None
        return sum((a - mx) * (b - my) for a, b in zip(x, y)) / (sx * sy)

    @staticmethod
    def _linear_fit(x: list[float], y: list[float]) -> tuple[float, float] | None:
        n = min(len(x), len(y))
        if n < 2:
            return None
        x = x[:n]
        y = y[:n]
        mean_x = sum(x) / n
        mean_y = sum(y) / n
        den = sum((a - mean_x) ** 2 for a in x)
        if den == 0:
            return None
        slope = sum((a - mean_x) * (b - mean_y) for a, b in zip(x, y)) / den
        intercept = mean_y - slope * mean_x
        return slope, intercept

    def _plot_trendline(self, ax, x: list[float], y: list[float], label: str | None = None) -> tuple[float, float] | None:
        fit = self._linear_fit(x, y)
        if fit is None:
            return None
        slope, intercept = fit
        xs = [min(x), max(x)]
        ys = [slope * xi + intercept for xi in xs]
        ax.plot(xs, ys, linestyle="--", linewidth=max(1, self.line_width_spin.value() - 1), label=label)
        return slope, intercept

    def _marker(self) -> str | None:
        marker = self.marker_combo.currentText()
        return None if marker == "None" else marker

    def _annotate_points(self, ax, x: list[float], y: list[float], labels: list[str]) -> None:
        if not self.annotate_points_check.isChecked():
            return
        for xi, yi, label in zip(x, y, labels):
            ax.annotate(label, (xi, yi), xytext=(4, 4), textcoords="offset points", fontsize=8)

    def _apply_axes_style(self, ax) -> None:
        ax.grid(self.grid_check.isChecked())
        if self.log_x_check.isChecked():
            try:
                ax.set_xscale("log")
            except Exception:
                pass
        if self.log_y_check.isChecked():
            try:
                ax.set_yscale("log")
            except Exception:
                pass

    def _series_summary(self, x_vals: list[Any], series_list: list[SeriesSpec], x_name: str, y_name: str) -> str:
        lines = [
            f"X axis: {x_name}",
            f"Y axis: {y_name}",
            f"Series count: {len(series_list)}",
            f"Rows: {len(x_vals)}",
            "",
        ]
        if self.errorbar_check.isChecked():
            lines.append(f"Error bars: {self.error_mode_combo.currentText()}")
            if self.error_mode_combo.currentText() == "Constant":
                lines.append(f"Constant error: {self.error_value_spin.value():.6g}")
            lines.append("")
        for idx, s in enumerate(series_list[:12]):
            numeric = self._series_y_numeric(s)
            sec = " [Y2]" if s.name in self._checked_secondary_names() else ""
            lines.append(f"- {idx + 1}: {s.name}{sec} | pts={len(s.values)} | numeric={len(numeric)}")
        return "\n".join(lines)

    def _refresh_secondary_series(self) -> None:
        try:
            _, series_list, _, _ = self._get_dataset()
        except Exception:
            series_list = []
        previous = set(self._checked_secondary_names())
        self._syncing_secondary = True
        self.secondary_series_list.clear()
        self._current_series_names = [s.name for s in series_list]
        for name in self._current_series_names:
            item = QListWidgetItem(name)
            item.setFlags(item.flags() | Qt.ItemIsUserCheckable)
            item.setCheckState(Qt.Checked if name in previous else Qt.Unchecked)
            self.secondary_series_list.addItem(item)
        self._syncing_secondary = False

    def _checked_secondary_names(self) -> set[str]:
        names: set[str] = set()
        for i in range(self.secondary_series_list.count()):
            item = self.secondary_series_list.item(i)
            if item.checkState() == Qt.Checked:
                names.add(item.text())
        return names

    def _constant_error_values(self, n: int) -> list[float]:
        return [self.error_value_spin.value()] * n

    def _error_values_from_next_series(self, series_list: list[SeriesSpec], idx: int, indices: list[int] | None = None) -> list[float] | None:
        if idx + 1 >= len(series_list):
            return None
        candidate = series_list[idx + 1].values
        values: list[float] = []
        if indices is None:
            for val in candidate:
                num = self._to_float(val)
                values.append(0.0 if num is None else abs(num))
        else:
            for pos in indices:
                val = candidate[pos] if pos < len(candidate) else None
                num = self._to_float(val)
                values.append(0.0 if num is None else abs(num))
        return values if values else None

    def _plot_errorbars(self, ax, xs: list[float], ys: list[float], series_list: list[SeriesSpec], idx: int, indices: list[int] | None = None) -> None:
        if not self.errorbar_check.isChecked() or not xs or not ys:
            return
        if self.error_mode_combo.currentText() == "Constant":
            yerr = self._constant_error_values(len(ys))
        else:
            yerr = self._error_values_from_next_series(series_list, idx, indices)
        if not yerr:
            return
        if len(yerr) < len(ys):
            yerr = yerr + [0.0] * (len(ys) - len(yerr))
        ax.errorbar(xs, ys, yerr=yerr[:len(ys)], fmt="none", capsize=3, alpha=0.8)

    def export_config(self) -> dict[str, Any]:
        secondary_names = sorted(self._checked_secondary_names())
        return {
            "version": 1,
            "chart_type": self.chart_type.currentText(),
            "auto": self.auto_check.isChecked(),
            "use_header": self.header_check.isChecked(),
            "use_first_col_x": self.first_col_x_check.isChecked(),
            "series_by_rows": self.row_series_check.isChecked(),
            "drop_empty": self.drop_empty_check.isChecked(),
            "x_index": self.x_combo.currentIndex(),
            "y_index": self.y_combo.currentIndex(),
            "secondary_index": self.secondary_combo.currentIndex(),
            "bar_orientation": self.orientation_combo.currentText(),
            "title": self.title_edit.text(),
            "x_label": self.x_label_edit.text(),
            "y_label": self.y_label_edit.text(),
            "y2_label": self.y2_label_edit.text(),
            "bins": self.bins_spin.value(),
            "line_width": self.line_width_spin.value(),
            "marker_size": self.marker_size_spin.value(),
            "marker": self.marker_combo.currentText(),
            "show_legend": self.legend_check.isChecked(),
            "show_grid": self.grid_check.isChecked(),
            "tight_layout": self.tight_check.isChecked(),
            "show_trendline": self.trend_check.isChecked(),
            "annotate_r": self.corr_check.isChecked(),
            "log_x": self.log_x_check.isChecked(),
            "log_y": self.log_y_check.isChecked(),
            "annotate_points": self.annotate_points_check.isChecked(),
            "stack_series": self.stacked_check.isChecked(),
            "data_labels": self.data_labels_check.isChecked(),
            "colormap": self.cmap_combo.currentText(),
            "regression_equation": self.regression_eq_check.isChecked(),
            "use_errorbars": self.errorbar_check.isChecked(),
            "error_mode": self.error_mode_combo.currentText(),
            "error_value": self.error_value_spin.value(),
            "secondary_series_names": secondary_names,
            "selection_range": list(self.selected_range) if self.selected_range else None,
        }

    def _apply_config(self, config: dict[str, Any]) -> None:
        def set_text(combo: QComboBox, text: str | None) -> None:
            if not text:
                return
            idx = combo.findText(text)
            if idx >= 0:
                combo.setCurrentIndex(idx)

        self.auto_check.setChecked(bool(config.get("auto", self.auto_check.isChecked())))
        self.header_check.setChecked(bool(config.get("use_header", self.header_check.isChecked())))
        self.first_col_x_check.setChecked(bool(config.get("use_first_col_x", self.first_col_x_check.isChecked())))
        self.row_series_check.setChecked(bool(config.get("series_by_rows", self.row_series_check.isChecked())))
        self.drop_empty_check.setChecked(bool(config.get("drop_empty", self.drop_empty_check.isChecked())))
        set_text(self.chart_type, config.get("chart_type"))
        self.x_combo.setCurrentIndex(min(max(int(config.get("x_index", self.x_combo.currentIndex())), 0), max(0, self.x_combo.count() - 1)))
        self.y_combo.setCurrentIndex(min(max(int(config.get("y_index", self.y_combo.currentIndex())), 0), max(0, self.y_combo.count() - 1)))
        self.secondary_combo.setCurrentIndex(min(max(int(config.get("secondary_index", self.secondary_combo.currentIndex())), 0), max(0, self.secondary_combo.count() - 1)))
        set_text(self.orientation_combo, config.get("bar_orientation"))
        self.title_edit.setText(str(config.get("title", self.title_edit.text())))
        self.x_label_edit.setText(str(config.get("x_label", self.x_label_edit.text())))
        self.y_label_edit.setText(str(config.get("y_label", self.y_label_edit.text())))
        self.y2_label_edit.setText(str(config.get("y2_label", self.y2_label_edit.text())))
        self.bins_spin.setValue(int(config.get("bins", self.bins_spin.value())))
        self.line_width_spin.setValue(int(config.get("line_width", self.line_width_spin.value())))
        self.marker_size_spin.setValue(int(config.get("marker_size", self.marker_size_spin.value())))
        set_text(self.marker_combo, config.get("marker"))
        self.legend_check.setChecked(bool(config.get("show_legend", self.legend_check.isChecked())))
        self.grid_check.setChecked(bool(config.get("show_grid", self.grid_check.isChecked())))
        self.tight_check.setChecked(bool(config.get("tight_layout", self.tight_check.isChecked())))
        self.trend_check.setChecked(bool(config.get("show_trendline", self.trend_check.isChecked())))
        self.corr_check.setChecked(bool(config.get("annotate_r", self.corr_check.isChecked())))
        self.log_x_check.setChecked(bool(config.get("log_x", self.log_x_check.isChecked())))
        self.log_y_check.setChecked(bool(config.get("log_y", self.log_y_check.isChecked())))
        self.annotate_points_check.setChecked(bool(config.get("annotate_points", self.annotate_points_check.isChecked())))
        self.stacked_check.setChecked(bool(config.get("stack_series", self.stacked_check.isChecked())))
        self.data_labels_check.setChecked(bool(config.get("data_labels", self.data_labels_check.isChecked())))
        set_text(self.cmap_combo, config.get("colormap"))
        self.regression_eq_check.setChecked(bool(config.get("regression_equation", self.regression_eq_check.isChecked())))
        self.errorbar_check.setChecked(bool(config.get("use_errorbars", self.errorbar_check.isChecked())))
        set_text(self.error_mode_combo, config.get("error_mode"))
        self.error_value_spin.setValue(float(config.get("error_value", self.error_value_spin.value())))
        self._refresh_secondary_series()
        wanted = set(config.get("secondary_series_names", []))
        self._syncing_secondary = True
        for i in range(self.secondary_series_list.count()):
            item = self.secondary_series_list.item(i)
            item.setCheckState(Qt.Checked if item.text() in wanted else Qt.Unchecked)
        self._syncing_secondary = False

    def _save_preset(self) -> None:
        path, _ = QFileDialog.getSaveFileName(self, "Save Chart Preset", "chart_preset.json", "JSON Files (*.json)")
        if not path:
            return
        try:
            with open(path, "w", encoding="utf-8") as f:
                json.dump(self.export_config(), f, ensure_ascii=False, indent=2)
        except Exception as e:
            QMessageBox.warning(self, "Save Preset", str(e))

    def _load_preset(self) -> None:
        path, _ = QFileDialog.getOpenFileName(self, "Load Chart Preset", "", "JSON Files (*.json)")
        if not path:
            return
        try:
            with open(path, "r", encoding="utf-8") as f:
                config = json.load(f)
            self._apply_config(config)
            self.plot()
        except Exception as e:
            QMessageBox.warning(self, "Load Preset", str(e))

    def _save_to_gallery(self) -> None:
        config = self.export_config()
        title = self.title_edit.text().strip() or self.chart_type.currentText()
        config["gallery_name"] = title
        self.sessionSaved.emit(config)

    def plot(self) -> None:
        chart = self.chart_type.currentText()
        self.figure.clear()
        ax = self.figure.add_subplot(111)
        self._last_stats = ""

        try:
            x_vals, series_list, default_x_name, default_y_name = self._get_dataset()
            self._refresh_secondary_series()
            if not series_list:
                raise ValueError("No plottable series found. Select a rectangular range or choose manual columns.")

            x_name = self.x_label_edit.text().strip() or default_x_name
            y_name = self.y_label_edit.text().strip() or default_y_name
            marker = self._marker()
            lw = self.line_width_spin.value()
            ms = self.marker_size_spin.value()
            secondary_names = self._checked_secondary_names()
            skip_error_indices = set()
            if self.errorbar_check.isChecked() and self.error_mode_combo.currentText() == "From next series":
                skip_error_indices = {i + 1 for i in range(len(series_list) - 1)}
            self.series_info.setPlainText(self._series_summary(x_vals, series_list, x_name, y_name))

            if chart == "Histogram":
                data_sets = []
                labels = []
                for s in series_list:
                    vals = self._series_y_numeric(s)
                    if vals:
                        data_sets.append(vals)
                        labels.append(s.name)
                if not data_sets:
                    raise ValueError("Histogram requires numeric data.")
                if len(data_sets) == 1:
                    ax.hist(data_sets[0], bins=self.bins_spin.value())
                else:
                    ax.hist(data_sets, bins=self.bins_spin.value(), label=labels, alpha=0.75)
                ax.set_xlabel(x_name if x_name != "Index" else (labels[0] if labels else x_name))
                ax.set_ylabel("Count")

            elif chart == "Boxplot":
                datasets = []
                labels = []
                for s in series_list:
                    vals = self._series_y_numeric(s)
                    if vals:
                        datasets.append(vals)
                        labels.append(s.name)
                if not datasets:
                    raise ValueError("Boxplot requires numeric data.")
                ax.boxplot(datasets, tick_labels=labels)
                ax.set_ylabel(y_name)

            elif chart == "Heatmap":
                matrix = []
                labels = []
                for s in series_list:
                    vals = self._series_y_numeric(s)
                    if vals:
                        matrix.append(vals)
                        labels.append(s.name)
                if not matrix:
                    raise ValueError("Heatmap requires numeric data.")
                max_len = max(len(row) for row in matrix)
                padded = [row + [math.nan] * (max_len - len(row)) for row in matrix]
                im = ax.imshow(padded, aspect="auto", cmap=self.cmap_combo.currentText())
                self.figure.colorbar(im, ax=ax)
                ax.set_yticks(range(len(labels)))
                ax.set_yticklabels(labels)
                ax.set_xlabel(x_name)
                ax.set_ylabel("Series")

            elif chart == "Pie":
                s = series_list[0]
                labels = []
                values = []
                for label, value in zip(x_vals, s.values):
                    num = self._to_float(value)
                    if num is None:
                        continue
                    labels.append(str(label))
                    values.append(num)
                if not values:
                    raise ValueError("Pie chart requires numeric values.")
                autopct = "%1.1f%%" if self.data_labels_check.isChecked() else None
                ax.pie(values, labels=labels, autopct=autopct)

            elif chart in {"Line", "Area", "Step"}:
                plotted = 0
                categorical = any(self._to_float(x) is None for x in x_vals)
                x_plot = list(range(len(x_vals))) if categorical else [self._to_float(x) for x in x_vals]
                x_labels = [str(v) for v in x_vals]
                stacked_accum: list[float] | None = None
                for idx, s in enumerate(series_list):
                    if idx in skip_error_indices:
                        continue
                    y_nums = [self._to_float(v) for v in s.values]
                    if categorical:
                        pairs = [(i, y, i) for i, y in enumerate(y_nums) if y is not None]
                        xs = [i for i, _, _ in pairs]
                        ys = [y for _, y, _ in pairs]
                        labels = [x_labels[i] for i, _, _ in pairs]
                        src_indices = [i for _, _, i in pairs]
                    else:
                        pairs = [(x, y, str(lbl), idx0) for idx0, (x, y, lbl) in enumerate(zip(x_plot, y_nums, x_labels)) if x is not None and y is not None]
                        xs = [a for a, _, _, _ in pairs]
                        ys = [b for _, b, _, _ in pairs]
                        labels = [c for _, _, c, _ in pairs]
                        src_indices = [d for _, _, _, d in pairs]
                    if not ys:
                        continue
                    if chart == "Line":
                        ax.plot(xs, ys, label=s.name, linewidth=lw, marker=marker, markersize=ms)
                        self._plot_errorbars(ax, xs, ys, series_list, idx, src_indices)
                    elif chart == "Area":
                        if self.stacked_check.isChecked():
                            if stacked_accum is None or len(stacked_accum) != len(ys):
                                stacked_accum = [0.0] * len(ys)
                            new_top = [a + b for a, b in zip(stacked_accum, ys)]
                            ax.fill_between(xs, stacked_accum, new_top, alpha=0.45, label=s.name)
                            stacked_accum = new_top
                        else:
                            ax.fill_between(xs, ys, alpha=0.35, label=s.name)
                            ax.plot(xs, ys, linewidth=lw)
                    else:
                        ax.step(xs, ys, where="mid", label=s.name, linewidth=lw, marker=marker)
                        self._plot_errorbars(ax, xs, ys, series_list, idx, src_indices)
                    self._annotate_points(ax, xs, ys, labels)
                    plotted += 1
                if categorical:
                    ax.set_xticks(range(len(x_labels)))
                    ax.set_xticklabels(x_labels, rotation=20)
                if plotted == 0:
                    raise ValueError("Selected series do not contain numeric Y values.")
                ax.set_xlabel(x_name)
                ax.set_ylabel(y_name)

            elif chart in {"Bar", "Horizontal Bar"}:
                categorical_labels = [str(v) for v in x_vals]
                if not categorical_labels:
                    raise ValueError("Bar chart requires labels or X values.")
                filtered: list[tuple[int, SeriesSpec]] = [(i, s) for i, s in enumerate(series_list) if i not in skip_error_indices]
                n = len(categorical_labels)
                positions = list(range(n))
                multi = max(1, len(filtered))
                width = 0.8 / multi if not self.stacked_check.isChecked() else 0.8
                orientation = self.orientation_combo.currentText()
                bar_bottom = [0.0] * n
                for vis_idx, (src_idx, s) in enumerate(filtered):
                    y_nums = [self._to_float(v) if self._to_float(v) is not None else 0.0 for v in s.values[:n]]
                    while len(y_nums) < n:
                        y_nums.append(0.0)
                    yerr = None
                    if self.errorbar_check.isChecked():
                        if self.error_mode_combo.currentText() == "Constant":
                            yerr = self._constant_error_values(n)
                        else:
                            yerr = self._error_values_from_next_series(series_list, src_idx)
                    if self.stacked_check.isChecked():
                        if chart == "Horizontal Bar" or orientation == "Horizontal":
                            bars = ax.barh(positions, y_nums, left=bar_bottom, xerr=yerr, label=s.name)
                        else:
                            bars = ax.bar(positions, y_nums, bottom=bar_bottom, yerr=yerr, label=s.name)
                        bar_bottom = [a + b for a, b in zip(bar_bottom, y_nums)]
                    else:
                        offset = (-0.4 + width / 2.0) + vis_idx * width
                        pos = [p + offset for p in positions]
                        if chart == "Horizontal Bar" or orientation == "Horizontal":
                            bars = ax.barh(pos, y_nums, height=width, xerr=yerr, label=s.name)
                        else:
                            bars = ax.bar(pos, y_nums, width=width, yerr=yerr, label=s.name)
                    if self.data_labels_check.isChecked():
                        ax.bar_label(bars, fmt="%.3g", padding=2)
                if chart == "Horizontal Bar" or orientation == "Horizontal":
                    ax.set_yticks(positions)
                    ax.set_yticklabels(categorical_labels)
                    ax.set_xlabel(y_name)
                    ax.set_ylabel(x_name)
                else:
                    ax.set_xticks(positions)
                    ax.set_xticklabels(categorical_labels, rotation=20)
                    ax.set_xlabel(x_name)
                    ax.set_ylabel(y_name)

            elif chart in {"Scatter", "Scatter + Fit"}:
                stats_lines = []
                eq_lines = []
                for idx, s in enumerate(series_list):
                    if idx in skip_error_indices:
                        continue
                    xs, ys, labels, src_indices = self._series_numeric_pairs(x_vals, s)
                    if not ys:
                        continue
                    ax.scatter(xs, ys, label=s.name, s=max(10, ms * ms))
                    self._plot_errorbars(ax, xs, ys, series_list, idx, src_indices)
                    self._annotate_points(ax, xs, ys, labels)
                    fit = None
                    if chart == "Scatter + Fit" or self.trend_check.isChecked():
                        fit_label = f"{s.name} fit" if len(series_list) > 1 else "Fit"
                        fit = self._plot_trendline(ax, xs, ys, fit_label)
                    if self.corr_check.isChecked():
                        r = self._pearson_r(xs, ys)
                        if r is not None:
                            stats_lines.append(f"{s.name}: r={r:.4f}")
                    if self.regression_eq_check.isChecked() and fit is not None:
                        m, b = fit
                        eq_lines.append(f"{s.name}: y={m:.4g}x{b:+.4g}")
                if not ax.collections:
                    raise ValueError("Scatter chart requires numeric X and Y values.")
                ax.set_xlabel(x_name)
                ax.set_ylabel(y_name)
                self._last_stats = "\n".join(stats_lines + eq_lines)
                if self._last_stats:
                    ax.text(0.02, 0.98, self._last_stats, transform=ax.transAxes, va="top", ha="left", fontsize=9,
                            bbox={"facecolor": "white", "alpha": 0.85, "edgecolor": "0.8"})

            elif chart == "Combo Line/Bar":
                if not x_vals:
                    raise ValueError("Combo chart requires X values.")
                positions = list(range(len(x_vals)))
                labels = [str(v) for v in x_vals]
                legacy_secondary_idx = self.secondary_combo.currentIndex() - 1
                if 0 <= legacy_secondary_idx < len(series_list):
                    secondary_names.add(series_list[legacy_secondary_idx].name)
                ax2 = None
                handles = []
                labels_for_legend = []
                bar_offset_index = 0
                for idx, s in enumerate(series_list):
                    if idx in skip_error_indices:
                        continue
                    y_nums = [self._to_float(v) if self._to_float(v) is not None else 0.0 for v in s.values[:len(positions)]]
                    while len(y_nums) < len(positions):
                        y_nums.append(0.0)
                    is_secondary = s.name in secondary_names
                    target_ax = ax
                    if is_secondary:
                        if ax2 is None:
                            ax2 = ax.twinx()
                        target_ax = ax2
                        target_ax.plot(positions, y_nums, linewidth=lw, marker=marker, markersize=ms, label=s.name)
                        self._plot_errorbars(target_ax, positions, y_nums, series_list, idx)
                    else:
                        if self.stacked_check.isChecked():
                            if bar_offset_index == 0:
                                self._combo_bottom = [0.0] * len(positions)
                            bars = target_ax.bar(positions, y_nums, alpha=0.75, bottom=self._combo_bottom, label=s.name)
                            self._combo_bottom = [a + b for a, b in zip(self._combo_bottom, y_nums)]
                        else:
                            width = 0.75 / max(1, len([n for n in series_list if n.name not in secondary_names and series_list.index(n) not in skip_error_indices]))
                            offset = (-0.375 + width / 2.0) + bar_offset_index * width
                            bars = target_ax.bar([p + offset for p in positions], y_nums, width=width, alpha=0.75, label=s.name)
                        if self.data_labels_check.isChecked():
                            target_ax.bar_label(bars, fmt="%.3g", padding=2)
                        bar_offset_index += 1
                    h, l = target_ax.get_legend_handles_labels()
                    handles = h
                    labels_for_legend = l
                ax.set_xticks(positions)
                ax.set_xticklabels(labels, rotation=20)
                ax.set_xlabel(x_name)
                ax.set_ylabel(y_name)
                if ax2:
                    ax2.set_ylabel(self.y2_label_edit.text().strip() or "Secondary Y")
                    h2, l2 = ax2.get_legend_handles_labels()
                    handles += h2
                    labels_for_legend += l2
                if self.legend_check.isChecked() and handles:
                    ax.legend(handles, labels_for_legend)

            else:
                raise ValueError(f"Unsupported chart type: {chart}")

            title = self.title_edit.text().strip() or chart
            ax.set_title(title)
            self._apply_axes_style(ax)
            if chart != "Combo Line/Bar" and self.legend_check.isChecked() and len(series_list) > 1:
                ax.legend()
            if self.tight_check.isChecked():
                self.figure.tight_layout()
            self.canvas.draw()
        except Exception as e:
            self.series_info.setPlainText(f"Plot error:\n{e}")
            QMessageBox.warning(self, "Plot Error", str(e))

    def _save_png(self) -> None:
        path, _ = QFileDialog.getSaveFileName(self, "Save Chart as PNG", "chart.png", "PNG Files (*.png)")
        if not path:
            return
        try:
            self.figure.savefig(path, dpi=200, bbox_inches="tight")
        except Exception as e:
            QMessageBox.warning(self, "Save PNG", str(e))
