"""Design tokens and Qt stylesheet (dark theme, cyan accent)."""

T = {
    "bg": "#07090C",          # app background (near black: the video stands out)
    "surface": "#0F141A",     # panels
    "surface2": "#161D25",    # fields / cards
    "border": "#222C38",
    "text": "#F1F5F9",        # 17:1 on bg
    "muted": "#94A3B8",       # 7.4:1 on bg
    "accent": "#22D3EE",      # cyan
    "accent_hi": "#67E8F9",
    "on_accent": "#06222A",
    "ok": "#34D399",
    "warn": "#FBBF24",
    "danger": "#F87171",
    "radius": "8px",
}

FONT_FAMILY = "Segoe UI Variable Text"

QSS = f"""
* {{ font-family: "{FONT_FAMILY}", "Segoe UI"; font-size: 10pt; color: {T['text']}; }}
QMainWindow, QWidget#root {{ background: {T['bg']}; }}
QWidget#topbar, QWidget#bottombar {{ background: {T['surface']}; border: 0; }}
QWidget#topbar {{ border-bottom: 1px solid {T['border']}; }}
QWidget#bottombar {{ border-top: 1px solid {T['border']}; }}
QScrollArea#side, QWidget#sideInner {{ background: {T['surface']}; border: 0; }}
QScrollArea#side {{ border-left: 1px solid {T['border']}; }}
QLabel#brand {{ font-size: 11pt; font-weight: 700; letter-spacing: 2px; color: {T['text']}; }}
QLabel#brandAccent {{ font-size: 11pt; font-weight: 700; letter-spacing: 2px; color: {T['accent']}; }}
QLabel#section {{ color: {T['muted']}; font-size: 8.5pt; font-weight: 600; letter-spacing: 1px;
                  padding-top: 10px; }}
QLabel#hint {{ color: {T['muted']}; font-size: 9pt; }}
QLabel#statKey {{ color: {T['muted']}; }}
QLabel#statVal {{ font-family: "Cascadia Mono", "Consolas"; font-size: 9.5pt; color: {T['muted']}; }}
QLabel#statVal[kind="measured"] {{ color: {T['text']}; }}
QLabel#statVal[kind="estimated"] {{ color: {T['warn']}; }}
QLabel#status {{ padding: 4px 10px; border-radius: 11px; background: {T['surface2']};
                 border: 1px solid {T['border']}; color: {T['muted']}; }}
QLabel#status[level="ok"] {{ color: {T['ok']}; border-color: #1F5B47; }}
QLabel#status[level="busy"] {{ color: {T['accent']}; border-color: #155E6B; }}
QLabel#status[level="warn"] {{ color: {T['warn']}; border-color: #6B5214; }}
QLabel#status[level="error"] {{ color: {T['danger']}; border-color: #6B2626; }}
QLabel#emptyTitle {{ font-size: 18pt; font-weight: 600; }}
QLabel#emptyBody {{ color: {T['muted']}; font-size: 10.5pt; }}
QLabel#banner {{ background: #2A1A08; color: {T['warn']}; padding: 6px 12px;
                 border-bottom: 1px solid #6B5214; }}

QComboBox, QLineEdit {{ background: {T['surface2']}; border: 1px solid {T['border']};
    border-radius: {T['radius']}; padding: 6px 10px; min-height: 22px;
    selection-background-color: {T['accent']}; selection-color: {T['on_accent']}; }}
QComboBox:focus, QLineEdit:focus {{ border-color: {T['accent']}; }}
QComboBox::drop-down {{ border: 0; width: 22px; }}
QComboBox QAbstractItemView {{ background: {T['surface2']}; border: 1px solid {T['border']};
    selection-background-color: #12414B; outline: 0; }}

QPushButton {{ background: {T['surface2']}; border: 1px solid {T['border']};
    border-radius: {T['radius']}; padding: 7px 14px; min-height: 22px; }}
QPushButton:hover {{ border-color: #3A4757; background: #1B232D; }}
QPushButton:focus {{ border-color: {T['accent']}; }}
QPushButton:disabled {{ color: #5B6675; }}
QPushButton#primary {{ background: {T['accent']}; color: {T['on_accent']}; border: 1px solid {T['accent']};
    font-weight: 600; }}
QPushButton#primary:hover {{ background: {T['accent_hi']}; }}
QPushButton#primary:focus {{ border: 2px solid #E0FBFF; }}
QPushButton#primary:disabled {{ background: {T['surface2']}; color: #5B6675; border-color: {T['border']}; }}
QPushButton#danger {{ background: transparent; color: {T['danger']}; border-color: #6B2626; font-weight: 600; }}
QPushButton#danger:hover {{ background: #2A1212; }}
QPushButton#danger:disabled {{ color: #5B6675; border-color: {T['border']}; }}
QToolButton {{ background: transparent; border: 1px solid transparent; border-radius: {T['radius']};
    padding: 6px; min-width: 32px; min-height: 32px; }}
QToolButton:hover {{ background: #1B232D; }}
QToolButton:focus {{ border-color: {T['accent']}; }}
QToolButton:checked {{ background: #12414B; }}

QRadioButton {{ spacing: 8px; padding: 8px 10px; border: 1px solid {T['border']};
    border-radius: {T['radius']}; background: {T['surface2']}; }}
QRadioButton:checked {{ border-color: {T['accent']}; background: #0E2A31; }}
QRadioButton:focus {{ border-color: {T['accent_hi']}; }}
QRadioButton::indicator {{ width: 10px; height: 10px; border-radius: 7px; border: 2px solid {T['muted']};
    background: transparent; }}
QRadioButton::indicator:checked {{ border: 2px solid {T['accent']}; background: {T['accent']}; }}
QCheckBox::indicator {{ width: 14px; height: 14px; border-radius: 4px; border: 2px solid {T['muted']}; }}
QCheckBox::indicator:checked {{ border-color: {T['accent']}; background: {T['accent']}; }}
QCheckBox {{ spacing: 8px; padding: 3px 0; }}
QCheckBox:focus {{ color: {T['accent_hi']}; }}

QSlider::groove:horizontal {{ height: 4px; background: {T['border']}; border-radius: 2px; }}
QSlider::sub-page:horizontal {{ background: {T['accent']}; border-radius: 2px; }}
QSlider::handle:horizontal {{ width: 14px; height: 14px; margin: -5px 0; border-radius: 7px;
    background: {T['text']}; }}
QSlider:focus::handle:horizontal {{ background: {T['accent_hi']}; }}
QScrollBar:vertical {{ background: transparent; width: 8px; }}
QScrollBar::handle:vertical {{ background: {T['border']}; border-radius: 4px; min-height: 30px; }}
QScrollBar::add-line, QScrollBar::sub-line {{ height: 0; }}
QToolTip {{ background: {T['surface2']}; color: {T['text']}; border: 1px solid {T['border']}; padding: 4px; }}
"""

# SVG icons (Lucide-style strokes), coloured at runtime.
ICONS = {
    "volume": '<path d="M11 5 6 9H2v6h4l5 4V5z"/><path d="M15.5 8.5a5 5 0 0 1 0 7"/><path d="M19 5a10 10 0 0 1 0 14"/>',
    "mute": '<path d="M11 5 6 9H2v6h4l5 4V5z"/><line x1="22" y1="9" x2="16" y2="15"/><line x1="16" y1="9" x2="22" y2="15"/>',
    "fullscreen": '<path d="M8 3H5a2 2 0 0 0-2 2v3"/><path d="M21 8V5a2 2 0 0 0-2-2h-3"/>'
                  '<path d="M3 16v3a2 2 0 0 0 2 2h3"/><path d="M16 21h3a2 2 0 0 0 2-2v-3"/>',
    "panel": '<rect x="3" y="3" width="18" height="18" rx="2"/><line x1="15" y1="3" x2="15" y2="21"/>',
    "live": '<circle cx="12" cy="12" r="2"/><path d="M16.2 7.8a6 6 0 0 1 0 8.4"/><path d="M7.8 16.2a6 6 0 0 1 0-8.4"/>'
            '<path d="M19.1 4.9a10 10 0 0 1 0 14.2"/><path d="M4.9 19.1a10 10 0 0 1 0-14.2"/>',
}


def icon_svg(name: str, color: str) -> bytes:
    body = ICONS[name]
    return (f'<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 24 24" fill="none" stroke="{color}" '
            f'stroke-width="2" stroke-linecap="round" stroke-linejoin="round">{body}</svg>').encode()
