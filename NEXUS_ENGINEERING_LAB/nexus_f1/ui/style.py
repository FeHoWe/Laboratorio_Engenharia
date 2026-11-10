"""Tema HUD (ciano/âmbar sobre azul-petróleo escuro)."""

BG = "#06101a"
PANEL = "#0b1b29"
PANEL2 = "#0f2538"
CYAN = "#19d3f5"
CYAN_DIM = "#0f7f95"
AMBER = "#ffb02e"
RED = "#ff4d4d"
GREEN = "#2ee6a6"
TEXT = "#cfeaf5"
MUTED = "#6f93a6"

QSS = f"""
QMainWindow, QWidget {{ background: {BG}; color: {TEXT}; font-family: 'Segoe UI', 'Inter', sans-serif; font-size: 12px; }}
QGroupBox {{ border: 1px solid {CYAN_DIM}; border-radius: 6px; margin-top: 14px; padding: 8px 6px 6px 6px; background: {PANEL}; }}
QGroupBox::title {{ subcontrol-origin: margin; left: 10px; color: {CYAN}; font-weight: 600; letter-spacing: 1px; }}
QTabWidget::pane {{ border: 1px solid {CYAN_DIM}; border-radius: 6px; background: {PANEL}; top: -1px; }}
QTabBar::tab {{ background: {PANEL2}; color: {MUTED}; padding: 7px 14px; border: 1px solid #12394d; border-bottom: none; margin-right: 2px; border-top-left-radius: 6px; border-top-right-radius: 6px; }}
QTabBar::tab:selected {{ color: {CYAN}; background: {PANEL}; border-color: {CYAN_DIM}; }}
QPushButton {{ background: {PANEL2}; color: {CYAN}; border: 1px solid {CYAN_DIM}; border-radius: 5px; padding: 6px 12px; font-weight: 600; }}
QPushButton:hover {{ background: #123a52; border-color: {CYAN}; }}
QPushButton:pressed {{ background: #0a2536; }}
QPushButton#primary {{ background: #0c4a60; color: white; border-color: {CYAN}; }}
QPushButton:disabled {{ color: #3d5a69; border-color: #17384a; }}
QComboBox, QSpinBox, QDoubleSpinBox, QLineEdit {{ background: #081824; border: 1px solid #14465c; border-radius: 4px; padding: 3px 6px; color: {TEXT}; selection-background-color: {CYAN_DIM}; }}
QComboBox QAbstractItemView {{ background: #081824; color: {TEXT}; selection-background-color: {CYAN_DIM}; }}
QTableWidget, QTextEdit, QPlainTextEdit {{ background: #07141f; border: 1px solid #14465c; gridline-color: #12394d; color: {TEXT}; }}
QHeaderView::section {{ background: {PANEL2}; color: {CYAN}; border: 1px solid #12394d; padding: 4px; font-weight: 600; }}
QSlider::groove:horizontal {{ height: 4px; background: #14465c; border-radius: 2px; }}
QSlider::handle:horizontal {{ background: {CYAN}; width: 12px; margin: -5px 0; border-radius: 6px; }}
QSlider::sub-page:horizontal {{ background: {CYAN_DIM}; border-radius: 2px; }}
QCheckBox {{ spacing: 6px; }}
QLabel#title {{ color: {CYAN}; font-size: 18px; font-weight: 700; letter-spacing: 3px; }}
QLabel#sub {{ color: {MUTED}; }}
QLabel#bad {{ color: {RED}; }}
QLabel#good {{ color: {GREEN}; }}
QLabel#warn {{ color: {AMBER}; }}
QScrollArea {{ border: none; }}
QStatusBar {{ background: {PANEL}; color: {MUTED}; }}
QToolTip {{ background: {PANEL2}; color: {TEXT}; border: 1px solid {CYAN_DIM}; }}
"""
