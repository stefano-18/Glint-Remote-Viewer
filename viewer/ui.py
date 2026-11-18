"""Main window of Glint Remote Viewer (PySide6)."""
from __future__ import annotations

import sys
import time
from pathlib import Path

from PySide6.QtCore import QByteArray, QObject, QSize, Qt, QTimer, QUrl, Signal
from PySide6.QtGui import QAction, QDesktopServices, QFont, QIcon, QKeySequence, QPainter, QPixmap
from PySide6.QtSvg import QSvgRenderer
from PySide6.QtWidgets import (
    QApplication, QButtonGroup, QCheckBox, QComboBox, QFileDialog, QGridLayout, QHBoxLayout, QLabel,
    QMainWindow, QMessageBox, QPushButton, QRadioButton, QScrollArea, QSizePolicy, QSlider,
    QStackedWidget, QToolButton, QVBoxLayout, QWidget,
)

from . import APP_NAME, __version__
from . import config as cfg
from .diagnostics import ESTIMATED, MEASURED, UNKNOWN, LogBuffer
from .profiles import PROFILES, get_profile
from .source import SourceError, parse_source
from .theme import QSS, T, icon_svg

STAT_ROWS = [
    ("resolution", "Resolution"),
    ("fps_source", "Stream FPS"),
    ("fps_shown", "Shown FPS"),
    ("dropped", "Dropped frames"),
    ("hwdec", "Decoding"),
    ("net_bitrate", "Download (network)"),
    ("video_bitrate", "Video bitrate"),
    ("buffer", "Buffer"),
    ("lag_edge", "Behind live edge"),
    ("lag_ingest", "Delay since ingest"),
    ("stalls", "Buffering stalls"),
    ("connect_time", "Connection time"),
    ("catchup", "Catch-up"),
]
STAT_HELP = {
    "lag_edge": "How far behind the latest segment published by Twitch/YouTube you are. "
                "Estimated from the segment timestamps; it does not depend on the PC clock.",
    "lag_ingest": "Time from the platform receiving that frame until you see it. Estimated: it relies on "
                  "the Windows clock being correct. It does not include the console's own delay.",
    "net_bitrate": "Actual speed at which the stream is being downloaded.",
    "fps_source": "Frames per second sent by the stream.",
    "fps_shown": "Frames actually being shown on screen.",
}


def make_icon(name: str, color: str = T["text"], size: int = 20) -> QIcon:
    r = QSvgRenderer(QByteArray(icon_svg(name, color)))
    pm = QPixmap(size * 2, size * 2)
    pm.fill(Qt.transparent)
    p = QPainter(pm)
    r.render(p)
    p.end()
    return QIcon(pm)


class Signals(QObject):
    event = Signal(str, str)   # (kind, text) from network / mpv threads
    key = Signal(str)          # keys captured by the mpv window


class VideoSurface(QWidget):
    """Native window that mpv renders into (no copies through Qt)."""

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setAttribute(Qt.WA_DontCreateNativeAncestors)
        self.setAttribute(Qt.WA_NativeWindow)
        self.setStyleSheet("background: #000;")
        self.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Expanding)
        self.setMinimumSize(320, 180)


class MainWindow(QMainWindow):
    def __init__(self, settings: cfg.Settings, logbuf: LogBuffer):
        super().__init__()
        self.settings = settings
        self.logbuf = logbuf
        self.sig = Signals()
        self.sig.event.connect(self._on_event)
        self.sig.key.connect(self._on_key)
        self.player = None
        self.session = None
        self._fs_prev_side = True
        self.setWindowTitle("Glint Remote")
        self.resize(1360, 800)
        self.setMinimumSize(800, 480)
        self._build()
        self._init_player()
        self._timer = QTimer(self)
        self._timer.setInterval(500)
        self._timer.timeout.connect(self._tick)
        self._timer.start()

    # ------------------------------------------------------------ layout
    def _build(self):
        root = QWidget(objectName="root")
        self.setCentralWidget(root)
        outer = QVBoxLayout(root)
        outer.setContentsMargins(0, 0, 0, 0)
        outer.setSpacing(0)

        # Top bar: brand, source, connect, status.
        self.topbar = QWidget(objectName="topbar")
        tb = QHBoxLayout(self.topbar)
        tb.setContentsMargins(16, 10, 16, 10)
        tb.setSpacing(10)
        b1, b2 = QLabel("GLINT", objectName="brand"), QLabel("REMOTE", objectName="brandAccent")
        tb.addWidget(b1)
        tb.addWidget(b2)
        tb.addSpacing(18)
        self.source_box = QComboBox()
        self.source_box.setEditable(True)
        self.source_box.setInsertPolicy(QComboBox.NoInsert)
        self.source_box.lineEdit().setPlaceholderText("Your friend's Twitch channel or the live stream URL")
        self.source_box.setToolTip("Examples: channelname · https://www.twitch.tv/channelname · "
                                   "https://www.youtube.com/watch?v=…")
        self.source_box.setAccessibleName("Channel or live stream URL")
        self.source_box.addItems(self.settings.history)
        self.source_box.setCurrentText(self.settings.last_source)
        self.source_box.setMinimumWidth(360)
        self.source_box.lineEdit().returnPressed.connect(self._connect_clicked)
        tb.addWidget(self.source_box, 1)
        self.connect_btn = QPushButton("Connect", objectName="primary")
        self.connect_btn.setCursor(Qt.PointingHandCursor)
        self.connect_btn.clicked.connect(self._connect_clicked)
        tb.addWidget(self.connect_btn)
        self.disconnect_btn = QPushButton("Disconnect", objectName="danger")
        self.disconnect_btn.setCursor(Qt.PointingHandCursor)
        self.disconnect_btn.clicked.connect(self._disconnect_clicked)
        self.disconnect_btn.setEnabled(False)
        tb.addWidget(self.disconnect_btn)
        self.browser_btn = QPushButton("Open in browser")
        self.browser_btn.setCursor(Qt.PointingHandCursor)
        self.browser_btn.setToolTip("Opens the stream in your usual browser, with your own session "
                                    "(needed for private YouTube streams).")
        self.browser_btn.clicked.connect(self._open_in_browser)
        tb.addWidget(self.browser_btn)
        tb.addSpacing(8)
        self.status = QLabel("Disconnected", objectName="status")
        self.status.setProperty("level", "idle")
        self.status.setAccessibleName("Connection status")
        tb.addWidget(self.status)
        outer.addWidget(self.topbar)

        self.banner = QLabel("", objectName="banner")
        self.banner.setWordWrap(True)
        self.banner.hide()
        outer.addWidget(self.banner)

        # Centre: video + side panel.
        mid = QHBoxLayout()
        mid.setContentsMargins(0, 0, 0, 0)
        mid.setSpacing(0)
        self.stack = QStackedWidget()
        self.empty = self._build_empty()
        self.video = VideoSurface()
        self.stack.addWidget(self.empty)
        self.stack.addWidget(self.video)
        mid.addWidget(self.stack, 1)
        self.side = self._build_side()
        mid.addWidget(self.side)
        outer.addLayout(mid, 1)

        # Bottom bar: audio and display.
        self.bottombar = QWidget(objectName="bottombar")
        bb = QHBoxLayout(self.bottombar)
        bb.setContentsMargins(12, 6, 12, 6)
        bb.setSpacing(8)
        self.mute_btn = QToolButton()
        self.mute_btn.setCheckable(True)
        self.mute_btn.setToolTip("Mute (M)")
        self.mute_btn.setAccessibleName("Mute")
        self.mute_btn.setIconSize(QSize(20, 20))
        self.mute_btn.toggled.connect(self._mute_toggled)
        bb.addWidget(self.mute_btn)
        self.vol = QSlider(Qt.Horizontal)
        self.vol.setRange(0, 130)
        self.vol.setFixedWidth(160)
        self.vol.setToolTip("Volume (↑/↓ arrow keys)")
        self.vol.setAccessibleName("Volume")
        self.vol.valueChanged.connect(self._volume_changed)
        bb.addWidget(self.vol)
        self.vol_label = QLabel("80 %", objectName="hint")
        self.vol_label.setFixedWidth(44)
        bb.addWidget(self.vol_label)
        bb.addStretch(1)
        self.quality_label = QLabel("", objectName="hint")
        bb.addWidget(self.quality_label)
        bb.addSpacing(8)
        self.panel_btn = QToolButton()
        self.panel_btn.setIcon(make_icon("panel"))
        self.panel_btn.setIconSize(QSize(20, 20))
        self.panel_btn.setCheckable(True)
        self.panel_btn.setChecked(self.settings.show_stats)
        self.side.setVisible(self.settings.show_stats)
        self.panel_btn.setToolTip("Show or hide the panel (P)")
        self.panel_btn.setAccessibleName("Side panel")
        self.panel_btn.toggled.connect(self._panel_toggled)
        bb.addWidget(self.panel_btn)
        self.fs_btn = QToolButton()
        self.fs_btn.setIcon(make_icon("fullscreen"))
        self.fs_btn.setIconSize(QSize(20, 20))
        self.fs_btn.setToolTip("Fullscreen (F11 or double-click · Esc to exit)")
        self.fs_btn.setAccessibleName("Fullscreen")
        self.fs_btn.clicked.connect(self.toggle_fullscreen)
        bb.addWidget(self.fs_btn)
        outer.addWidget(self.bottombar)

        # Keyboard shortcuts (also forwarded from the mpv window).
        for seq, fn in (("F11", self.toggle_fullscreen), ("Esc", self.exit_fullscreen),
                        ("M", lambda: self.mute_btn.toggle()), ("P", lambda: self.panel_btn.toggle()),
                        ("Up", lambda: self.vol.setValue(self.vol.value() + 5)),
                        ("Down", lambda: self.vol.setValue(self.vol.value() - 5))):
            a = QAction(self)
            a.setShortcut(QKeySequence(seq))
            a.setShortcutContext(Qt.ApplicationShortcut)
            a.triggered.connect(fn)
            self.addAction(a)

        self.mute_btn.setChecked(self.settings.muted)
        self._update_mute_icon()
        self.vol.setValue(self.settings.volume)

    def _build_empty(self) -> QWidget:
        w = QWidget()
        lay = QVBoxLayout(w)
        lay.setAlignment(Qt.AlignCenter)
        ic = QLabel()
        ic.setPixmap(make_icon("live", T["accent"], 40).pixmap(56, 56))
        ic.setAlignment(Qt.AlignCenter)
        t = QLabel("Watch your friend play", objectName="emptyTitle")
        t.setAlignment(Qt.AlignCenter)
        self.empty_body = QLabel(
            "1. Your friend starts broadcasting from their PS5 (Create button → Broadcast).\n"
            "2. Type their Twitch channel name above and press Connect.\n"
            "If they haven't started yet, the app waits and connects on its own.", objectName="emptyBody")
        self.empty_body.setAlignment(Qt.AlignCenter)
        self.empty_body.setWordWrap(True)
        self.empty_body.setMaximumWidth(560)
        for x in (ic, t, self.empty_body):
            lay.addWidget(x, 0, Qt.AlignHCenter)
        return w

    def _build_side(self) -> QScrollArea:
        area = QScrollArea(objectName="side")
        area.setWidgetResizable(True)
        area.setFixedWidth(330)
        area.setHorizontalScrollBarPolicy(Qt.ScrollBarAlwaysOff)
        inner = QWidget(objectName="sideInner")
        lay = QVBoxLayout(inner)
        lay.setContentsMargins(16, 8, 16, 16)
        lay.setSpacing(8)

        lay.addWidget(QLabel("MODE", objectName="section"))
        self.mode_group = QButtonGroup(self)
        self.mode_desc = QLabel("", objectName="hint")
        self.mode_desc.setWordWrap(True)
        for key, prof in PROFILES.items():
            rb = QRadioButton(prof.name)
            rb.setProperty("key", key)
            rb.setToolTip(prof.description)
            rb.setCursor(Qt.PointingHandCursor)
            self.mode_group.addButton(rb)
            lay.addWidget(rb)
            if key == self.settings.profile:
                rb.setChecked(True)
        self.mode_group.buttonToggled.connect(self._mode_toggled)
        lay.addWidget(self.mode_desc)
        self._update_mode_desc()

        lay.addWidget(QLabel("QUALITY", objectName="section"))
        self.quality_box = QComboBox()
        self.quality_box.setAccessibleName("Quality")
        self._fill_quality(cfg.QUALITY_CHOICES)
        self.quality_box.activated.connect(self._quality_changed)
        lay.addWidget(self.quality_box)

        lay.addWidget(QLabel("AUDIO", objectName="section"))
        self.device_box = QComboBox()
        self.device_box.setAccessibleName("Audio output")
        self.device_box.activated.connect(self._device_changed)
        lay.addWidget(self.device_box)

        lay.addWidget(QLabel("STATISTICS", objectName="section"))
        grid = QGridLayout()
        grid.setHorizontalSpacing(8)
        grid.setVerticalSpacing(4)
        self.stat_labels = {}
        for i, (key, title) in enumerate(STAT_ROWS):
            k = QLabel(title, objectName="statKey")
            v = QLabel("—", objectName="statVal")
            v.setTextInteractionFlags(Qt.TextSelectableByMouse)
            v.setProperty("kind", UNKNOWN)
            k.setToolTip(STAT_HELP.get(key, title))
            grid.addWidget(k, i, 0)
            grid.addWidget(v, i, 1)
            self.stat_labels[key] = v
        lay.addLayout(grid)
        legend = QLabel("<span style='color:%s'>white = measured</span> · <span style='color:%s'>amber = estimated"
                        "</span> · — = no data" % (T["text"], T["warn"]), objectName="hint")
        lay.addWidget(legend)

        lay.addWidget(QLabel("OPTIONS", objectName="section"))
        self.chk_reconnect = QCheckBox("Reconnect automatically")
        self.chk_reconnect.setChecked(self.settings.auto_reconnect)
        self.chk_reconnect.toggled.connect(self._opt_changed)
        lay.addWidget(self.chk_reconnect)
        self.chk_catchup = QCheckBox("Catch up with the live edge")
        self.chk_catchup.setToolTip("Speeds up slightly (pitch unchanged) or jumps to live if you fall behind.")
        self.chk_catchup.setChecked(self.settings.catchup_enabled)
        self.chk_catchup.toggled.connect(self._opt_changed)
        lay.addWidget(self.chk_catchup)
        self.chk_local = QCheckBox("Allow local test sources")
        self.chk_local.setToolTip("Testing only: accepts .m3u8 URLs on 127.0.0.1.")
        self.chk_local.setChecked(self.settings.allow_local_test)
        self.chk_local.toggled.connect(self._opt_changed)
        lay.addWidget(self.chk_local)
        hw_row = QHBoxLayout()
        hw_row.addWidget(QLabel("GPU decoding", objectName="statKey"))
        self.hw_box = QComboBox()
        self.hw_box.setAccessibleName("GPU decoding")
        for val, txt in (("d3d11va", "D3D11VA (recommended)"), ("auto-safe", "Automatic"), ("no", "Off")):
            self.hw_box.addItem(txt, val)
        self.hw_box.setCurrentIndex(max(0, self.hw_box.findData(self.settings.hwdec)))
        self.hw_box.activated.connect(self._hw_changed)
        hw_row.addWidget(self.hw_box, 1)
        lay.addLayout(hw_row)

        lay.addWidget(QLabel("DIAGNOSTICS", objectName="section"))
        self.diag_label = QLabel("Errors logged: 0", objectName="hint")
        lay.addWidget(self.diag_label)
        exp = QPushButton("Export log…")
        exp.setToolTip("Saves a log without passwords, tokens or personal paths.")
        exp.clicked.connect(self._export_log)
        lay.addWidget(exp)
        hist_clear = QPushButton("Clear channel history")
        hist_clear.clicked.connect(self._clear_history)
        lay.addWidget(hist_clear)
        ver = QLabel(f"{APP_NAME} {__version__}", objectName="hint")
        lay.addWidget(ver)
        lay.addStretch(1)
        area.setWidget(inner)
        return area

    def _fill_quality(self, names):
        current = self.settings.quality
        self.quality_box.clear()
        self.quality_box.addItem("Automatic (best)", "best")
        for n in names:
            if n not in ("best", "worst"):
                self.quality_box.addItem(n, n)
        self.quality_box.addItem("Lowest", "worst")
        idx = self.quality_box.findData(current)
        self.quality_box.setCurrentIndex(idx if idx >= 0 else 0)

    # --------------------------------------------------------------- mpv
    def _init_player(self):
        try:
            from .player import Player
            from .session import Session
            self.stack.setCurrentWidget(self.video)  # make sure the native winId exists
            QApplication.processEvents()
            wid = int(self.video.winId())
            self.player = Player(wid, self.settings.hwdec, log=self.logbuf.add)
            self.stack.setCurrentWidget(self.empty)
        except Exception as err:  # noqa: BLE001
            self.logbuf.add("fatal", f"could not start mpv: {err}")
            QMessageBox.critical(self, "Glint Remote",
                                 "The video player (libmpv) could not be started.\n\n"
                                 f"Details: {err}\n\nCheck that libmpv-2.dll is next to the program.")
            self.connect_btn.setEnabled(False)
            return
        self.player.set_volume(self.settings.volume)
        self.player.set_mute(self.settings.muted)
        for keydef, name in (("f", "fullscreen"), ("F11", "fullscreen"), ("ESC", "esc"),
                             ("m", "mute"), ("UP", "volup"), ("DOWN", "voldown"), ("p", "panel"),
                             ("MBTN_LEFT_DBL", "fullscreen")):
            self.player.m.register_key_binding(keydef, lambda *_a, n=name: self.sig.key.emit(n))
        self.session = Session(self.player, notify=self.sig.event.emit, log=self.logbuf.add,
                               auto_reconnect=self.settings.auto_reconnect,
                               catchup_enabled=self.settings.catchup_enabled)
        self._fill_devices()

    def _fill_devices(self):
        self.device_box.clear()
        for name, desc in self.player.audio_devices():
            self.device_box.addItem("System default" if name == "auto" else desc, name)
        idx = self.device_box.findData(self.settings.audio_device)
        if idx >= 0:
            self.device_box.setCurrentIndex(idx)
            self.player.set_audio_device(self.settings.audio_device)

    # ------------------------------------------------------------ actions
    def _connect_clicked(self):
        if self.session is None:
            return
        text = self.source_box.currentText()
        try:
            src = parse_source(text, allow_local=self.settings.allow_local_test)
        except SourceError as err:
            self._set_status(str(err), "error")
            self._show_banner(str(err))
            return
        self._hide_banner()
        self.settings.remember(text.strip())
        self._refresh_history()
        self._persist()
        self.stack.setCurrentWidget(self.video)
        self.connect_btn.setEnabled(False)
        self.disconnect_btn.setEnabled(True)
        self.session.start(src, get_profile(self.settings.profile), self.settings.quality)

    def _open_in_browser(self):
        """Opens the stream page in the default browser. Never reads or stores cookies or sessions."""
        try:
            src = parse_source(self.source_box.currentText(), allow_local=self.settings.allow_local_test)
        except SourceError as err:
            self._show_banner(str(err))
            return
        if not src.web_url:
            self._show_banner("Local test sources have no web page.")
            return
        QDesktopServices.openUrl(QUrl(src.web_url))
        if self.session and self.session.state != "idle":
            self._disconnect_clicked()  # avoid hearing the stream twice
        self._set_status("Opened in browser", "ok")

    def _disconnect_clicked(self):
        if self.session:
            self.session.stop()
        self.connect_btn.setEnabled(True)
        self.disconnect_btn.setEnabled(False)
        self.stack.setCurrentWidget(self.empty)
        self._hide_banner()
        self.quality_label.setText("")

    def _mode_toggled(self, btn, checked):
        if not checked:
            return
        key = btn.property("key")
        self.settings.profile = key
        self._update_mode_desc()
        self._persist()
        if self.session:
            self.session.set_profile(get_profile(key))

    def _update_mode_desc(self):
        self.mode_desc.setText(get_profile(self.settings.profile).description)

    def _quality_changed(self, _i):
        q = self.quality_box.currentData()
        self.settings.quality = q
        self._persist()
        if self.session:
            self.session.set_quality(q)

    def _device_changed(self, _i):
        name = self.device_box.currentData()
        self.settings.audio_device = name
        self._persist()
        if self.player:
            self.player.set_audio_device(name)

    def _hw_changed(self, _i):
        hw = self.hw_box.currentData()
        self.settings.hwdec = hw
        self._persist()
        if self.player:
            self.player.set_hwdec(hw)

    def _opt_changed(self, _v):
        self.settings.auto_reconnect = self.chk_reconnect.isChecked()
        self.settings.catchup_enabled = self.chk_catchup.isChecked()
        self.settings.allow_local_test = self.chk_local.isChecked()
        if self.session:
            self.session.auto_reconnect = self.settings.auto_reconnect
            self.session.catchup_enabled = self.settings.catchup_enabled
            if self.session.catchup:
                self.session.catchup.enabled = self.settings.catchup_enabled and self.session.catchup.params is not None
                if not self.settings.catchup_enabled and self.player:
                    self.player.set_speed(1.0)
        self._persist()

    def _volume_changed(self, v):
        self.vol_label.setText(f"{v} %")
        self.settings.volume = v
        if self.player:
            self.player.set_volume(v)
        self._save_later()

    def _mute_toggled(self, on):
        self.settings.muted = on
        if self.player:
            self.player.set_mute(on)
        self._update_mute_icon()
        self._persist()

    def _panel_toggled(self, on):
        self.side.setVisible(on)
        if not self.isFullScreen():
            self.settings.show_stats = on
            self._persist()

    def _update_mute_icon(self):
        on = self.mute_btn.isChecked()
        self.mute_btn.setIcon(make_icon("mute" if on else "volume", T["danger"] if on else T["text"]))

    def toggle_fullscreen(self):
        if self.isFullScreen():
            self.exit_fullscreen()
            return
        self._fs_prev_side = self.side.isVisible()
        for w in (self.topbar, self.bottombar, self.side, self.banner):
            w.hide()
        self.showFullScreen()

    def exit_fullscreen(self):
        if not self.isFullScreen():
            return
        self.showNormal()
        self.topbar.show()
        self.bottombar.show()
        self.side.setVisible(self._fs_prev_side and self.panel_btn.isChecked())

    def _on_key(self, name):
        {"fullscreen": self.toggle_fullscreen, "esc": self.exit_fullscreen,
         "mute": self.mute_btn.toggle, "panel": self.panel_btn.toggle,
         "volup": lambda: self.vol.setValue(self.vol.value() + 5),
         "voldown": lambda: self.vol.setValue(self.vol.value() - 5)}.get(name, lambda: None)()

    def _export_log(self):
        default = str(Path.home() / "Desktop" / f"glintremote-log-{time.strftime('%Y%m%d-%H%M%S')}.txt")
        path, _ = QFileDialog.getSaveFileName(self, "Export log", default, "Text (*.txt)")
        if not path:
            return
        header = (f"{APP_NAME} {__version__} · mode={self.settings.profile} · quality={self.settings.quality} · "
                  f"hwdec={self.settings.hwdec}")
        self.logbuf.export(Path(path), header)
        self._set_status("Log exported", "ok")

    def _clear_history(self):
        self.settings.history = []
        self.settings.last_source = ""
        self._refresh_history()
        self._persist()

    def _refresh_history(self):
        cur = self.source_box.currentText()
        self.source_box.blockSignals(True)
        self.source_box.clear()
        self.source_box.addItems(self.settings.history)
        self.source_box.setCurrentText(cur)
        self.source_box.blockSignals(False)

    # ------------------------------------------------------------ events
    def _on_event(self, kind: str, text: str):
        if kind == "state":
            busy = text.startswith("Connecting")
            self._set_status(text, "busy" if busy else ("ok" if text.startswith("Receiving") else "idle"))
            if text.startswith("Receiving"):
                self._hide_banner()
        elif kind == "waiting":
            self._set_status("Waiting for the broadcast", "warn")
            self._show_banner(text)
        elif kind == "error":
            self._set_status("Connection problem", "error")
            self._show_banner(text)
            if self.session and self.session.state == "idle":
                self.connect_btn.setEnabled(True)
                self.disconnect_btn.setEnabled(False)
        elif kind == "lost":
            self._set_status("Signal lost · reconnecting", "warn")
            self._show_banner("The stream signal was lost. Reconnecting automatically…"
                              if self.settings.auto_reconnect else "The stream signal was lost.")
        elif kind == "quality":
            self.quality_label.setText(f"Quality: {text}")
        elif kind == "available":
            names = [n for n in text.split(",") if n]
            if names:
                self._fill_quality(names)
        elif kind == "private":
            self._set_status("Private stream", "warn")
            self._show_banner(text)
            self.connect_btn.setEnabled(True)
            self.disconnect_btn.setEnabled(False)
            self.stack.setCurrentWidget(self.empty)
        elif kind == "info":
            self._show_banner(text)

    def _set_status(self, text, level):
        self.status.setText(text if len(text) <= 60 else text[:57] + "…")
        self.status.setToolTip(text)
        self.status.setProperty("level", level)
        self.status.style().unpolish(self.status)
        self.status.style().polish(self.status)

    def _show_banner(self, text):
        self.banner.setText(text)
        if not self.isFullScreen():
            self.banner.show()

    def _hide_banner(self):
        self.banner.hide()

    def _tick(self):
        if not self.session:
            return
        st = self.session.tick()
        self.last_stats = st
        if self.side.isVisible():
            for key, val in self.stat_labels.items():
                mt = st.metrics.get(key)
                kind = mt.kind if mt and mt.kind in (MEASURED, ESTIMATED) else UNKNOWN
                val.setText(mt.text if mt else "—")
                if val.property("kind") != kind:
                    val.setProperty("kind", kind)
                    val.setToolTip(f"{kind.capitalize()} value")
                    val.style().unpolish(val)
                    val.style().polish(val)
        self.diag_label.setText(f"Errors logged: {self.logbuf.errors}")

    # ------------------------------------------------------------ persistence
    def _persist(self):
        if getattr(self, "no_persist", False):  # automated tests: never touch the user's settings
            return
        try:
            cfg.save(self.settings)
        except OSError as err:
            self.logbuf.add("warn", f"could not save settings: {err}")

    def _save_later(self):
        if not hasattr(self, "_save_timer"):
            self._save_timer = QTimer(self)
            self._save_timer.setSingleShot(True)
            self._save_timer.setInterval(800)
            self._save_timer.timeout.connect(self._persist)
        self._save_timer.start()

    def closeEvent(self, e):
        self._timer.stop()
        self._persist()
        if self.session:
            self.session.stop()
        if self.player:
            self.player.terminate()
        super().closeEvent(e)


def run(argv=None) -> int:
    argv = sys.argv if argv is None else argv
    try:  # own taskbar icon and grouping (otherwise Windows uses pythonw.exe's)
        import ctypes
        ctypes.windll.shell32.SetCurrentProcessExplicitAppUserModelID("GlintRemote.Viewer")
    except (AttributeError, OSError):
        pass
    QApplication.setHighDpiScaleFactorRoundingPolicy(Qt.HighDpiScaleFactorRoundingPolicy.PassThrough)
    app = QApplication(argv)
    app.setApplicationName("Glint Remote")
    app.setFont(QFont("Segoe UI Variable Text", 10))
    app.setStyleSheet(QSS)
    app.setWindowIcon(make_icon("live", T["accent"], 32))
    logbuf = LogBuffer()
    settings = cfg.load()
    bench = _parse_bench(argv)
    if bench:
        import faulthandler
        # No faulthandler.enable(): on Windows it reports SEH exceptions that the D3D driver handles itself.
        faulthandler.dump_traceback_later(bench["seconds"] + 40, exit=True)  # never hang during tests
        settings = cfg.Settings(profile=bench["profile"], allow_local_test=True, volume=30)
    win = MainWindow(settings, logbuf)
    win.show()
    if "--smoke" in argv:  # automated test: open and close
        QTimer.singleShot(2500, win.close)
    if bench:
        win._bench = _BenchRunner(win, bench)  # keep a reference (otherwise the GC collects it)
    return app.exec()


def _parse_bench(argv):
    """--bench URL --profile ultra|balanced|stable --seconds N --out file.json [--fullscreen] [--actions]
    [--shots DIR --initial-text TEXT]"""
    if "--bench" not in argv:
        return None

    def val(flag, default):
        return argv[argv.index(flag) + 1] if flag in argv and argv.index(flag) + 1 < len(argv) else default
    return {"url": val("--bench", ""), "profile": val("--profile", "balanced"),
            "seconds": float(val("--seconds", "60")), "out": val("--out", "bench.json"),
            "fullscreen": "--fullscreen" in argv, "actions": "--actions" in argv,
            "shots": val("--shots", ""), "url_initial": val("--initial-text", None)}


class _BenchRunner:
    """Automated test: connects, takes one sample per second and optionally exercises the controls."""

    def __init__(self, win: MainWindow, opts: dict):
        import json
        import os

        import psutil
        self.json, self.win, self.o = json, win, opts
        win.no_persist = True
        self.proc = psutil.Process(os.getpid())
        self.proc.cpu_percent(None)
        self.samples, self.t0, self.events = [], time.monotonic(), []
        self.shots = Path(opts["shots"]) if opts["shots"] else None
        if self.shots:  # real screen captures (mpv renders with D3D11, so Qt's grab() would be black)
            self.shots.mkdir(parents=True, exist_ok=True)
            win.resize(1440, 860)
            win.source_box.setCurrentText(opts["url_initial"] or "")
            QTimer.singleShot(1500, lambda: self._shot("01-start.png"))
            QTimer.singleShot(2500, self._connect)
            QTimer.singleShot(13500, lambda: self.win.side.ensureWidgetVisible(self.win.stat_labels["catchup"]))
            QTimer.singleShot(14000, lambda: self._shot("02-playing-statistics.png"))
            QTimer.singleShot(15000, lambda: self.win.side.verticalScrollBar().setValue(10000))
            QTimer.singleShot(16000, lambda: self._shot("03-options-diagnostics.png"))
            QTimer.singleShot(17000, lambda: (self.win.side.verticalScrollBar().setValue(0),
                                              self.win.panel_btn.setChecked(False)))
            QTimer.singleShot(18500, lambda: self._shot("04-player-no-panel.png"))
        else:
            self._connect()
        if opts["fullscreen"]:
            QTimer.singleShot(3000, win.toggle_fullscreen)
        if opts["actions"]:
            plan = [(6, "vol50", lambda: win.vol.setValue(50)), (8, "mute", lambda: win.mute_btn.setChecked(True)),
                    (10, "unmute", lambda: win.mute_btn.setChecked(False)),
                    (12, "fullscreen", win.toggle_fullscreen), (16, "exit_fs", win.exit_fullscreen),
                    (18, "quality_second", self._pick_second_quality),
                    (30, "profile_ultra", lambda: self._pick_profile("ultra"))]
            for t, name, fn in plan:
                QTimer.singleShot(int(t * 1000), lambda n=name, f=fn: (f(), self.events.append((n, self._state()))))
        self.timer = QTimer(win)
        self.timer.timeout.connect(self._sample)
        self.timer.start(1000)

    def _connect(self):
        self.win.source_box.setCurrentText(self.o["url"])
        self.win._connect_clicked()

    def _shot(self, name):
        """Captures ONLY this window (PrintWindow + PW_RENDERFULLCONTENT, which includes D3D11 content).
        Unlike a screen grab, other windows can never end up in the image, even if they cover it."""
        import ctypes
        from ctypes import wintypes

        from PySide6.QtGui import QImage
        if self.win.isMinimized() or self.win.width() < 1000:
            self.win.showNormal()
            self.win.resize(1440, 860)
        QApplication.processEvents()
        user32, gdi32 = ctypes.windll.user32, ctypes.windll.gdi32
        for fn, args, res in ((user32.GetWindowDC, [wintypes.HWND], wintypes.HDC),
                              (user32.ReleaseDC, [wintypes.HWND, wintypes.HDC], ctypes.c_int),
                              (user32.PrintWindow, [wintypes.HWND, wintypes.HDC, wintypes.UINT], wintypes.BOOL),
                              (gdi32.CreateCompatibleDC, [wintypes.HDC], wintypes.HDC),
                              (gdi32.CreateCompatibleBitmap, [wintypes.HDC, ctypes.c_int, ctypes.c_int],
                               wintypes.HBITMAP),
                              (gdi32.SelectObject, [wintypes.HDC, wintypes.HGDIOBJ], wintypes.HGDIOBJ),
                              (gdi32.GetDIBits, [wintypes.HDC, wintypes.HBITMAP, wintypes.UINT, wintypes.UINT,
                                                 ctypes.c_void_p, ctypes.c_void_p, wintypes.UINT], ctypes.c_int),
                              (gdi32.DeleteObject, [wintypes.HGDIOBJ], wintypes.BOOL),
                              (gdi32.DeleteDC, [wintypes.HDC], wintypes.BOOL)):
            fn.argtypes, fn.restype = args, res
        hwnd = wintypes.HWND(int(self.win.winId()))
        rect = wintypes.RECT()
        user32.GetWindowRect(hwnd, ctypes.byref(rect))
        w, h = rect.right - rect.left, rect.bottom - rect.top
        hdc = user32.GetWindowDC(hwnd)
        mdc = gdi32.CreateCompatibleDC(hdc)
        bmp = gdi32.CreateCompatibleBitmap(hdc, w, h)
        old = gdi32.SelectObject(mdc, bmp)
        try:
            if not user32.PrintWindow(hwnd, mdc, 2):  # 2 = PW_RENDERFULLCONTENT
                return
            header = (ctypes.c_uint32 * 10)(40, w, (-h) & 0xFFFFFFFF, 1 | (32 << 16), 0, 0, 0, 0, 0, 0)
            buf = ctypes.create_string_buffer(w * h * 4)
            gdi32.GetDIBits(mdc, bmp, 0, h, buf, header, 0)
            QImage(buf.raw, w, h, w * 4, QImage.Format_RGB32).copy().save(str(self.shots / name))
        finally:
            gdi32.SelectObject(mdc, old)
            gdi32.DeleteObject(bmp)
            gdi32.DeleteDC(mdc)
            user32.ReleaseDC(hwnd, hdc)

    def _state(self):
        p = self.win.player
        return {"volume": p.get("volume"), "mute": p.get("mute"), "fullscreen": self.win.isFullScreen(),
                "quality_ui": self.win.quality_box.currentData(), "profile": self.win.settings.profile}

    def _pick_second_quality(self):
        box = self.win.quality_box
        if box.count() > 2:
            box.setCurrentIndex(2)  # 0 = automatic, 1 = best real one, 2 = the next one
            self.win._quality_changed(2)

    def _pick_profile(self, key):
        for b in self.win.mode_group.buttons():
            if b.property("key") == key:
                b.setChecked(True)

    def _sample(self):
        el = time.monotonic() - self.t0
        st = getattr(self.win, "last_stats", None)
        mem = self.proc.memory_info().rss / 1e6
        row = {"t": round(el, 1), "state": st.state if st else None, "cpu_pct": self.proc.cpu_percent(None),
               "rss_mb": round(mem, 1), "status": self.win.status.toolTip(),
               "banner": self.win.banner.text() if self.win.banner.isVisible() else "",
               "speed": self.win.player.get("speed") if self.win.player else None,
               "audio_codec": self.win.player.get("audio-codec-name") if self.win.player else None,
               "ao": self.win.player.get("current-ao") if self.win.player else None}
        if st:
            row.update({k: v.text for k, v in st.metrics.items()})
        self.samples.append(row)
        if el >= self.o["seconds"]:
            self.timer.stop()
            out = {"opts": self.o, "events": self.events, "samples": self.samples,
                   "log_tail": self.win.logbuf.lines()[-300:]}
            Path(self.o["out"]).write_text(self.json.dumps(out, indent=1, ensure_ascii=False), encoding="utf-8")
            self.win.close()
