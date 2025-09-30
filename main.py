# [PROTOCOL ACTIVATED]: Project XYZ Ciel - The SMART Protocol v30 - Definitive Master (PNG Runtime)
# EXECUTOR: XYZ Ciel
# DATE: 2025-10-02
# REVISION: Switched runtime icon loading to a PNG file as per the guide, while retaining the ICO for the build process, completing the final definitive icon strategy.

import sys
import os
import re
import shutil
import logging
import datetime
import time
import numpy as np
import sounddevice as sd
import soundfile as sf
from pydub import AudioSegment
import subprocess
from pathlib import Path

# --- PyQt6 Imports ---
from PyQt6.QtWidgets import (
    QApplication, QMainWindow, QWidget, QVBoxLayout, QHBoxLayout, QPushButton,
    QLabel, QLineEdit, QFrame, QScrollArea, QTabWidget, QSlider, QComboBox,
    QMessageBox, QInputDialog, QGraphicsDropShadowEffect, QCheckBox, QSplashScreen
)
from PyQt6.QtCore import Qt, QThread, pyqtSignal, QObject, QPropertyAnimation, QEasingCurve, QRect, QSize
from PyQt6.QtGui import QColor, QIcon, QPixmap, QImage, QKeyEvent

# --- Optional/Platform-Specific Imports with Resilience ---
try: from PIL import Image, ImageFilter; PIL_AVAILABLE = True
except ImportError: PIL_AVAILABLE = False
try: from comtypes import CLSCTX_ALL, cast, POINTER; from pycaw.pycaw import AudioUtilities, IAudioEndpointVolume; PYCAW_AVAILABLE = True
except ImportError: PYCAW_AVAILABLE = False
if sys.platform == 'win32':
    import ctypes
    import winreg

# =================================================================================
# PORTABILITY AND RESOURCE MANAGEMENT
# =================================================================================

def resource_path(relative_path):
    try: base_path = sys._MEIPASS
    except Exception: base_path = os.path.abspath(".")
    return os.path.join(base_path, relative_path)

def XYZ_get_documents_path():
    if sys.platform == 'win32':
        try:
            key = winreg.OpenKey(winreg.HKEY_CURRENT_USER, r'Software\Microsoft\Windows\CurrentVersion\Explorer\Shell Folders')
            documents_path, _ = winreg.QueryValueEx(key, 'Personal'); winreg.CloseKey(key); return documents_path
        except Exception as e: logging.warning(f"Could not query registry for Documents path, falling back. Error: {e}")
    return os.path.join(os.path.expanduser('~'), 'Documents')

APP_DATA_PATH = os.path.join(XYZ_get_documents_path(), "XYZ Project", "XYZ Dubbing Studio")

def XYZ_ensure_data_directory():
    try: os.makedirs(APP_DATA_PATH, exist_ok=True); logging.info(f"Data directory ensured at: {APP_DATA_PATH}")
    except OSError as e: logging.critical(f"Could not create data directory: {e}", exc_info=True)

def XYZ_set_windows_app_id():
    myappid = u'XYZ.DubberStudio.Master.Final.3'
    if sys.platform == 'win32':
        try: ctypes.windll.shell32.SetCurrentProcessExplicitAppUserModelID(myappid); logging.info(f"Windows AppUserModelID set via ctypes: {myappid}")
        except Exception as e: logging.error(f"Failed to set Windows AppUserModelID: {e}")

try:
    ffmpeg_path = resource_path("ffmpeg.exe")
    if os.path.exists(ffmpeg_path): AudioSegment.converter = ffmpeg_path; logging.info(f"Pydub converter set to bundled FFmpeg at: {ffmpeg_path}")
    else: logging.warning("Bundled ffmpeg.exe not found. Pydub may fail if FFmpeg is not in system PATH.")
except Exception as e: logging.error(f"Failed to configure pydub with FFmpeg: {e}")

# =================================================================================
# ARCHITECTURAL SETUP: LOGGING, EXCEPTIONS, AND WORKERS (UNCHANGED)
# =================================================================================
# ... (All worker classes and setup functions remain unchanged) ...
def XYZ_setup_logging():
    log_file_path = os.path.join(APP_DATA_PATH, "xyz_dubber_app.log")
    if not logging.getLogger().handlers: logging.basicConfig(level=logging.INFO, format='%(asctime)s - [%(levelname)s] - %(threadName)s - %(message)s', handlers=[logging.FileHandler(log_file_path, mode='w'), logging.StreamHandler(sys.stdout)])
    for logger_name in ["sounddevice", "PIL"]: logging.getLogger(logger_name).setLevel(logging.WARNING)
    logging.info("Logging system initialized.")
class AudioDeviceError(Exception): pass
class FileOperationError(Exception): pass
class WorkerSignals(QObject): finished = pyqtSignal(object); error = pyqtSignal(str); progress = pyqtSignal(float); status_update = pyqtSignal(str)
class XYZ_AudioRecorder(QThread):
    def __init__(self, device_index, samplerate, project_path): super().__init__(); self.signals = WorkerSignals(); self.device_index = device_index; self.samplerate = samplerate; self.project_path = project_path; self._is_running = True; self.audio_frames = []
    def run(self):
        try:
            self.signals.status_update.emit("● Recording started..."); cb = lambda i, f, t, s: self.audio_frames.append(i.copy())
            with sd.InputStream(device=self.device_index, channels=1, samplerate=self.samplerate, callback=cb):
                while self._is_running: self.signals.progress.emit(time.time()); sd.sleep(100)
            if not self.audio_frames: self.signals.finished.emit(None); return
            rec = np.concatenate(self.audio_frames, axis=0); ts = datetime.datetime.now().strftime("%Y%m%d_%H%M%S"); fp = os.path.join(self.project_path, f"segment_{ts}.wav"); sf.write(fp, rec, self.samplerate); self.signals.finished.emit(fp)
        except Exception: logging.exception("Rec thread error."); self.signals.error.emit(str(AudioDeviceError(f"Failed to record audio.")))
    def stop(self): self._is_running = False
class XYZ_AudioPlayer(QThread):
    def __init__(self, filepath, device_index, volume_db):
        super().__init__(); self.signals = WorkerSignals(); self.filepath = filepath; self.device_index = device_index; self.volume_db = volume_db; self._is_running = True
    def run(self):
        try:
            with sf.SoundFile(self.filepath, 'r') as sf_file:
                samplerate, total_frames, channels = sf_file.samplerate, len(sf_file), sf_file.channels
                def callback(outdata, frames, time, status):
                    if not self._is_running: raise sd.CallbackStop
                    data = sf_file.read(frames, dtype='float32', always_2d=True)
                    if not len(data): raise sd.CallbackStop
                    gain = 10 ** (self.volume_db / 20.0); final_data = np.clip(data * gain, -1.0, 1.0)
                    if len(final_data) < frames: outdata[:len(final_data)] = final_data; outdata[len(final_data):] = 0; raise sd.CallbackStop
                    else: outdata[:] = final_data
                    self.signals.progress.emit(sf_file.tell() / total_frames if total_frames > 0 else 1.0)
                with sd.OutputStream(samplerate=samplerate, device=self.device_index, channels=channels, callback=callback) as stream:
                    while self._is_running and stream.active: sd.sleep(100)
            self.signals.finished.emit(self.filepath)
        except Exception as e: logging.exception("Playback thread error."); self.signals.error.emit(str(AudioDeviceError(f"Could not play '{os.path.basename(self.filepath)}'. {e}")))
    def stop(self): self._is_running = False
class XYZ_FileProcessor(QThread):
    def __init__(self, approved_files, output_path): super().__init__(); self.signals = WorkerSignals(); self.approved_files = approved_files; self.output_path = output_path
    def run(self):
        try:
            if not self.approved_files: raise ValueError("No approved files."); self.signals.status_update.emit(f"Merging {len(self.approved_files)} segments...")
            combined = AudioSegment.empty()
            for i, fp in enumerate(self.approved_files): self.signals.progress.emit((i + 1) / len(self.approved_files)); combined += AudioSegment.from_wav(fp)
            combined.export(self.output_path, format="wav"); self.signals.status_update.emit(f"Merge successful: {os.path.basename(self.output_path)}"); self.signals.finished.emit(self.output_path)
        except Exception: logging.exception("Merge thread error."); self.signals.error.emit(str(FileOperationError(f"Failed to merge files.")))

# =================================================================================
# CUSTOM WIDGETS
# =================================================================================

class XYZ_StyleConstants:
    COLOR_BORDER = "rgba(68, 68, 68, 120)"; COLOR_BG_WIDGET = "rgba(46, 46, 46, 120)"; COLOR_BG_HOVER = "rgba(58, 58, 58, 120)"; COLOR_DELETE_BTN = "rgba(161, 50, 50, 120)"; COLOR_FINAL_MIX_BORDER = "rgba(0, 90, 158, 120)"; COLOR_PROJECT_ACTIVE_BG = "rgba(0, 90, 158, 120)"
class XYZ_SegmentWidget(QFrame):
    play_requested = pyqtSignal(str); delete_requested = pyqtSignal(str); approval_changed = pyqtSignal(str, bool); audacity_requested = pyqtSignal(str)
    def __init__(self, filepath, title, style: XYZ_StyleConstants, is_final_mix=False, audacity_path=None):
        super().__init__(); self.filepath = filepath; self.is_approved = False; self.setObjectName("SegmentWidget")
        border_style = f"border: 2px solid {style.COLOR_FINAL_MIX_BORDER};" if is_final_mix else f"border: 1px solid {style.COLOR_BORDER};"
        self.setStyleSheet(f"#SegmentWidget {{ {border_style} border-radius: 4px; background-color: {style.COLOR_BG_WIDGET}; }} #SegmentWidget:hover {{ background-color: {style.COLOR_BG_HOVER}; }}")
        main_layout = QHBoxLayout(self); info_panel = QWidget(); info_layout = QVBoxLayout(info_panel); info_layout.setContentsMargins(10, 5, 10, 5)
        self.title_label = QLabel(f"<b>{title}</b>");
        try:
            with sf.SoundFile(filepath) as f: duration = len(f) / f.samplerate
            timestamp = datetime.datetime.fromtimestamp(os.path.getmtime(filepath)).strftime('%d-%b-%Y %H:%M'); info_text = f"{duration:.1f}s | {timestamp}"
        except Exception as e: logging.error(f"Metadata read error for {filepath}: {e}", exc_info=True); info_text = "Error: Could not read file."
        self.info_label = QLabel(info_text); self.progress_slider = QSlider(Qt.Orientation.Horizontal); self.progress_slider.setFixedHeight(10); self.progress_slider.setEnabled(False)
        info_layout.addWidget(self.title_label); info_layout.addWidget(self.info_label); info_layout.addWidget(self.progress_slider)
        controls_panel = QWidget(); controls_layout = QHBoxLayout(controls_panel); controls_layout.setContentsMargins(5, 5, 5, 5)
        self.play_button = QPushButton("▶ Play"); self.play_button.setFixedWidth(80); self.play_button.clicked.connect(lambda: self.play_requested.emit(self.filepath))
        if is_final_mix:
            audacity_btn = QPushButton("Audacity"); audacity_btn.setFixedWidth(80); audacity_btn.clicked.connect(lambda: self.audacity_requested.emit(self.filepath))
            if audacity_path: audacity_btn.setToolTip(f"Edit this file in Audacity.")
            else: audacity_btn.setEnabled(False); audacity_btn.setToolTip("Could not find Audacity installation.")
            controls_layout.addWidget(audacity_btn); XYZ_apply_shadow_effect(audacity_btn)
        else:
            self.approve_checkbox = QCheckBox("Approve"); self.approve_checkbox.toggled.connect(self.on_approval_change); controls_layout.addWidget(self.approve_checkbox); XYZ_apply_shadow_effect(self.approve_checkbox)
        self.delete_button = QPushButton("🗑️ Delete"); self.delete_button.setFixedWidth(80); self.delete_button.setStyleSheet(f"background-color: {style.COLOR_DELETE_BTN};"); self.delete_button.clicked.connect(lambda: self.delete_requested.emit(self.filepath))
        controls_layout.insertWidget(0, self.play_button); controls_layout.addWidget(self.delete_button)
        main_layout.addWidget(info_panel); main_layout.addWidget(controls_panel)
        XYZ_apply_shadow_effect(self.play_button); XYZ_apply_shadow_effect(self.delete_button)
    def on_approval_change(self, checked: bool): self.is_approved = checked; self.approval_changed.emit(self.filepath, checked)
    def set_playing_state(self, is_playing: bool):
        if is_playing: self.play_button.setText("■ Stop")
        else: self.play_button.setText("▶ Play"); self.progress_slider.setValue(0)

# =================================================================================
# UTILITY FUNCTIONS
# =================================================================================

def XYZ_create_glass_background(image_path, blur_radius=5, vignette_strength=0.7) -> QPixmap:
    if not PIL_AVAILABLE: logging.warning("Pillow library not found."); pixmap = QPixmap(); pixmap.fill(QColor("#1e1e1e")); return pixmap
    try:
        with Image.open(image_path) as img: img = img.convert("RGBA")
        blurred_img = img.filter(ImageFilter.GaussianBlur(radius=blur_radius)); width, height = blurred_img.size; Y, X = np.ogrid[:height, :width]; center_y, center_x = height / 2, width / 2; dist_from_center = np.sqrt((X - center_x)**2 + (Y - center_y)**2); max_dist = np.sqrt(center_x**2 + center_y**2); norm_dist = dist_from_center / max_dist; vignette_alpha = 255 * (1 - norm_dist**2 * vignette_strength); vignette_alpha = np.clip(vignette_alpha, 0, 255).astype(np.uint8); mask = Image.fromarray(vignette_alpha, 'L'); black_overlay = Image.new("RGBA", (width, height), (0, 0, 0, 255)); final_img = Image.composite(blurred_img, black_overlay, mask); data = final_img.tobytes("raw", "RGBA"); q_image = QImage(data, final_img.size[0], final_img.size[1], QImage.Format.Format_RGBA8888); return QPixmap.fromImage(q_image)
    except Exception as e: logging.warning(f"Failed to create glass background from {image_path}: {e}", exc_info=True); pixmap = QPixmap(); pixmap.fill(QColor("#1e1e1e")); return pixmap

def XYZ_create_scaled_pixmap(pixmap: QPixmap, target_size: QSize) -> QPixmap:
    return pixmap.scaled(target_size, Qt.AspectRatioMode.KeepAspectRatioByExpanding, Qt.TransformationMode.SmoothTransformation)

def XYZ_find_audacity() -> str | None:
    if sys.platform == "win32":
        for path in [os.path.join(os.environ.get("ProgramFiles", "C:\\Program Files"), "Audacity", "audacity.exe"), os.path.join(os.environ.get("ProgramFiles(x86)", "C:\\Program Files (x86)"), "Audacity", "audacity.exe")]:
            if os.path.exists(path): logging.info(f"Audacity found at: {path}"); return path
    logging.warning("Could not find Audacity executable."); return None

def XYZ_apply_shadow_effect(widget: QWidget, blur_radius=15, offset_y=2):
    shadow = QGraphicsDropShadowEffect(widget); shadow.setBlurRadius(blur_radius); shadow.setColor(QColor(0, 0, 0, 160)); shadow.setOffset(1, offset_y); widget.setGraphicsEffect(shadow)

# =================================================================================
# MAIN APPLICATION WINDOW
# =================================================================================
class XYZ_DubberApp(QMainWindow):
    BG_PATH = resource_path("background.jpg")
    ICO_PNG_PATH = resource_path("icon.png") # Use PNG for runtime
    
    def __init__(self, initial_size: QSize, app_icon: QIcon):
        super().__init__()
        self.initial_size = initial_size
        self.app_icon = app_icon
        self.oldPos = None
        self.styles = XYZ_StyleConstants(); self.is_audio_busy = False; self.current_project_path = None; self.segment_widgets = {}; self.project_widgets = {}; self.mic_devices = {}; self.output_devices = {}; self.mic_volume_control = None; self.active_recorder = None; self.active_player = None; self.currently_playing_widget = None; self.final_mix_widgets = {}
        self.audacity_path = XYZ_find_audacity()
        self.XYZ_configure_window(); self.XYZ_init_ui(); self.XYZ_populate_device_lists(); self.XYZ_initialize_mic_volume(); self.XYZ_populate_project_list()

    def XYZ_configure_window(self):
        self.setWindowTitle("XYZ Dubbing Studio"); self.setWindowIcon(self.app_icon); self.setMinimumSize(1024, 720); self.resize(self.initial_size)
        self.setAttribute(Qt.WidgetAttribute.WA_TranslucentBackground); self.setWindowFlags(Qt.WindowType.FramelessWindowHint)
        self.background_label = QLabel(self); self.background_label.setGeometry(self.rect())
        processed_pixmap = XYZ_create_glass_background(self.BG_PATH)
        final_pixmap = XYZ_create_scaled_pixmap(processed_pixmap, self.size())
        self.background_label.setPixmap(final_pixmap); self.background_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.central_widget = QWidget(self); self.setCentralWidget(self.central_widget); self.central_widget.setObjectName("CentralWidget"); self.central_widget.setStyleSheet("#CentralWidget { background-color: rgba(30, 30, 30, 120); border-radius: 10px; }")
        shadow = QGraphicsDropShadowEffect(); shadow.setBlurRadius(30); shadow.setColor(QColor(0, 0, 0, 160)); shadow.setOffset(0, 0); self.central_widget.setGraphicsEffect(shadow)
        self.title_bar = QFrame(self); self.title_bar.setObjectName("TitleBar"); self.title_bar.setGeometry(0, 0, self.width(), 30); title_bar_layout = QHBoxLayout(self.title_bar)
        icon_label = QLabel(self.title_bar); icon_pixmap = self.app_icon.pixmap(20, 20); icon_label.setPixmap(icon_pixmap); icon_label.setFixedSize(20, 20)
        title_label = QLabel("XYZ Dubbing Studio", self.title_bar); title_label.setStyleSheet("color: white; font-weight: bold;")
        close_button = QPushButton("✕", self.title_bar); close_button.setFixedSize(30, 30); close_button.setStyleSheet("QPushButton { background-color: transparent; color: white; border: none; font-size: 16px; } QPushButton:hover { background-color: #D32F2F; }"); close_button.clicked.connect(self.close)
        title_bar_layout.setContentsMargins(10, 0, 0, 0); title_bar_layout.addWidget(icon_label); title_bar_layout.addWidget(title_label); title_bar_layout.addStretch(); title_bar_layout.addWidget(close_button)

    # ... (The rest of the code is identical and omitted for brevity)
    def resizeEvent(self, event):
        super().resizeEvent(event); self.background_label.setGeometry(self.rect())
        processed_pixmap = XYZ_create_glass_background(self.BG_PATH)
        final_pixmap = XYZ_create_scaled_pixmap(processed_pixmap, self.size())
        self.background_label.setPixmap(final_pixmap)
        if hasattr(self, 'title_bar'): self.title_bar.setGeometry(0, 0, self.width(), 30)
    def mousePressEvent(self, event):
        if event.buttons() == Qt.MouseButton.LeftButton: self.oldPos = event.globalPosition().toPoint()
    def mouseMoveEvent(self, event):
        if event.buttons() == Qt.MouseButton.LeftButton and self.oldPos: delta = event.globalPosition().toPoint() - self.oldPos; self.move(self.x() + delta.x(), self.y() + delta.y()); self.oldPos = event.globalPosition().toPoint()
    def mouseReleaseEvent(self, event): self.oldPos = None
    def keyPressEvent(self, event: QKeyEvent):
        key = event.key()
        if key == Qt.Key.Key_R:
            focused_widget = QApplication.focusWidget()
            if isinstance(focused_widget, QLineEdit): return super().keyPressEvent(event)
            if self.tab_view.currentWidget() is self.segments_tab and self.record_button.isEnabled():
                self.record_button.click(); event.accept()
            else: return super().keyPressEvent(event)
        else: return super().keyPressEvent(event)
    def XYZ_init_ui(self):
        outer_layout = QVBoxLayout(self.central_widget); outer_layout.setContentsMargins(10, 40, 10, 10); main_layout = QHBoxLayout()
        left_panel = QFrame(); left_panel.setFixedWidth(300); left_layout = QVBoxLayout(left_panel)
        self.new_project_button = QPushButton("➕ Create New Project"); self.new_project_button.setFixedHeight(40); self.new_project_button.setObjectName("NewProjectButton"); self.new_project_button.setToolTip("Click to open a dialog and create a new project folder."); self.new_project_button.clicked.connect(self.XYZ_prompt_for_new_project)
        self.project_list_scroll = QScrollArea(); self.project_list_scroll.setWidgetResizable(True)
        self.project_list_widget = QWidget(); self.project_list_widget.setObjectName("ScrollAreaContent")
        self.project_list_layout = QVBoxLayout(self.project_list_widget); self.project_list_layout.setAlignment(Qt.AlignmentFlag.AlignTop); self.project_list_scroll.setWidget(self.project_list_widget)
        left_layout.addWidget(QLabel("<b>Project Management</b>")); left_layout.addWidget(self.new_project_button); left_layout.addWidget(self.project_list_scroll)
        right_panel = QFrame(); right_layout = QVBoxLayout(right_panel); self.current_project_label = QLabel("<b>No Project Selected</b>")
        self.tab_view = QTabWidget(); self.segments_tab = QWidget(); self.final_mix_tab = QWidget(); self.XYZ_init_final_mix_tab()
        self.tab_view.addTab(self.segments_tab, "Segments"); self.tab_view.addTab(self.final_mix_tab, "Final Mix")
        self.XYZ_init_segments_tab(); self.XYZ_load_final_mix_tab()
        right_layout.addWidget(self.current_project_label); right_layout.addWidget(self.tab_view); main_layout.addWidget(left_panel); main_layout.addWidget(right_panel)
        self.status_label = QLabel("Welcome! Create or open a project to begin."); outer_layout.addLayout(main_layout); outer_layout.addWidget(self.status_label)
        self.XYZ_apply_stylesheet()
        XYZ_apply_shadow_effect(self.new_project_button)
    def XYZ_init_segments_tab(self):
        layout = QHBoxLayout(self.segments_tab); controls_frame = QFrame(); controls_frame.setFixedWidth(300); controls_layout = QVBoxLayout(controls_frame)
        self.mic_dropdown = QComboBox(); self.mic_dropdown.setToolTip("Select the microphone (input device) for recording.")
        self.output_device_dropdown = QComboBox(); self.output_device_dropdown.setToolTip("Select the speaker/headphone (output device) for playback.")
        self.input_volume_label = QLabel("Input Gain (Pedalboard): N/A")
        self.input_volume_slider = QSlider(Qt.Orientation.Horizontal); self.input_volume_slider.valueChanged.connect(self.XYZ_update_input_volume); self.input_volume_slider.setEnabled(False); self.input_volume_slider.setToolTip("Adjust the input gain of the default microphone.\nRequires 'pycaw' library.")
        self.timer_label = QLabel("00:00.0"); self.timer_label.setAlignment(Qt.AlignmentFlag.AlignCenter); self.timer_label.setStyleSheet("font-size: 48px; font-weight: bold;")
        self.record_button = QPushButton("Record"); self.record_button.setFixedHeight(40); self.record_button.setEnabled(False); self.record_button.clicked.connect(self.XYZ_toggle_recording); self.record_button.setToolTip("Start or stop recording a new audio segment (Hotkey: R).")
        self.output_volume_slider = QSlider(Qt.Orientation.Horizontal); self.output_volume_slider.setRange(-24, 12); self.output_volume_slider.setValue(0); self.output_volume_slider.valueChanged.connect(lambda v: self.XYZ_update_status(f"Playback Volume: {v} dB")); self.output_volume_slider.setToolTip("Adjust the playback volume in decibels (dB).")
        controls_layout.addWidget(QLabel("<b>Input Device:</b>")); controls_layout.addWidget(self.mic_dropdown); controls_layout.addWidget(self.input_volume_label); controls_layout.addWidget(self.input_volume_slider); controls_layout.addWidget(self.timer_label); controls_layout.addWidget(self.record_button); controls_layout.addStretch(); controls_layout.addWidget(QLabel("<b>Output Device:</b>")); controls_layout.addWidget(self.output_device_dropdown); controls_layout.addWidget(QLabel("Playback Volume:")); controls_layout.addWidget(self.output_volume_slider)
        segments_area = QFrame(); segments_layout = QVBoxLayout(segments_area); self.merge_button = QPushButton("Merge Approved"); self.merge_button.clicked.connect(self.XYZ_merge_segments); self.merge_button.setEnabled(False); self.merge_button.setToolTip("Combine all 'Approved' segments into a versioned 'Final Mix N.wav' file.")
        bulk_actions_layout = QHBoxLayout(); approve_all_btn = QPushButton("Approve All"); approve_all_btn.clicked.connect(lambda: self.XYZ_approve_all_segments(True)); approve_all_btn.setToolTip("Mark all segments in the list as 'Approved'."); unapprove_all_btn = QPushButton("Unapprove All"); unapprove_all_btn.clicked.connect(lambda: self.XYZ_approve_all_segments(False)); unapprove_all_btn.setToolTip("Unmark all segments in the list."); delete_all_btn = QPushButton("Delete All"); delete_all_btn.setObjectName("DeleteAllButton"); delete_all_btn.clicked.connect(self.XYZ_delete_all_segments); delete_all_btn.setToolTip("Permanently delete all segments in this project."); bulk_actions_layout.addWidget(approve_all_btn); bulk_actions_layout.addWidget(unapprove_all_btn); bulk_actions_layout.addWidget(delete_all_btn)
        self.segments_scroll = QScrollArea(); self.segments_scroll.setWidgetResizable(True); self.segments_list_widget = QWidget(); self.segments_list_widget.setObjectName("ScrollAreaContent")
        self.segments_list_layout = QVBoxLayout(self.segments_list_widget); self.segments_list_layout.setAlignment(Qt.AlignmentFlag.AlignTop); self.segments_scroll.setWidget(self.segments_list_widget)
        segments_layout.addWidget(self.merge_button); segments_layout.addLayout(bulk_actions_layout); segments_layout.addWidget(self.segments_scroll); layout.addWidget(controls_frame); layout.addWidget(segments_area)
        for widget in [self.mic_dropdown, self.output_device_dropdown, self.record_button, self.merge_button, approve_all_btn, unapprove_all_btn, delete_all_btn]: XYZ_apply_shadow_effect(widget)
    def XYZ_init_final_mix_tab(self):
        layout = QVBoxLayout(self.final_mix_tab); self.final_mix_scroll = QScrollArea(); self.final_mix_scroll.setWidgetResizable(True); self.final_mix_list_widget = QWidget(); self.final_mix_list_widget.setObjectName("ScrollAreaContent")
        self.final_mix_list_layout = QVBoxLayout(self.final_mix_list_widget); self.final_mix_list_layout.setAlignment(Qt.AlignmentFlag.AlignTop); self.final_mix_scroll.setWidget(self.final_mix_list_widget); layout.addWidget(self.final_mix_scroll)
    def XYZ_apply_stylesheet(self):
        self.setStyleSheet(f"""
            QWidget {{ color: #e0e0e0; font-family: Segoe UI; font-size: 10pt; }}
            QMainWindow {{ background: transparent; }}
            QFrame {{ background-color: transparent; }}
            QWidget#ScrollAreaContent {{ background-color: transparent; }}
            #NewProjectButton {{ background-color: {self.styles.COLOR_FINAL_MIX_BORDER}; font-size: 11pt; }}
            #DeleteAllButton {{ background-color: {self.styles.COLOR_DELETE_BTN}; }}
            QFrame#ProjectEntry {{ border: 1px solid {self.styles.COLOR_BORDER}; border-radius: 3px; background-color: transparent; }}
            QFrame#ProjectEntry[active="true"] {{ background-color: {self.styles.COLOR_PROJECT_ACTIVE_BG}; border: 1px solid rgba(255, 255, 255, 120); }}
            QPushButton {{ background-color: rgba(58, 58, 58, 120); border: 1px solid {self.styles.COLOR_BORDER}; padding: 5px; border-radius: 3px; min-height: 20px; }}
            QPushButton:hover {{ background-color: rgba(74, 74, 74, 120); border: 1px solid rgba(119, 119, 119, 120); }}
            QPushButton:pressed {{ background-color: rgba(42, 42, 42, 120); }}
            QPushButton:disabled {{ background-color: rgba(47, 47, 47, 120); color: #777; }}
            QLineEdit, QComboBox, QCheckBox {{ background-color: rgba(42, 42, 42, 120); border: 1px solid {self.styles.COLOR_BORDER}; padding: 5px; border-radius: 3px; }}
            QScrollArea {{ background-color: rgba(37, 37, 37, 120); border: 1px solid {self.styles.COLOR_BORDER}; }}
            QTabWidget::pane {{ border: 1px solid {self.styles.COLOR_BORDER}; }}
            QTabBar::tab {{ background: rgba(51, 51, 51, 120); padding: 8px; border: 1px solid {self.styles.COLOR_BORDER}; border-bottom: none; }}
            QTabBar::tab:selected {{ background: rgba(74, 74, 74, 120); }}
        """)
    def XYZ_populate_device_lists(self):
        try:
            hostapis = sd.query_hostapis(); mme_index = next(i for i, api in enumerate(hostapis) if 'MME' in api['name']); devices = sd.query_devices()
            self.mic_devices.clear(); self.output_devices.clear(); self.mic_dropdown.clear(); self.output_device_dropdown.clear()
            for i, d in enumerate(devices):
                if d['hostapi'] == mme_index:
                    if d['max_input_channels'] > 0: self.mic_devices[d['name']] = i; self.mic_dropdown.addItem(d['name'])
                    if d['max_output_channels'] > 0: self.output_devices[d['name']] = i; self.output_device_dropdown.addItem(d['name'])
            if not self.mic_devices: self.mic_dropdown.addItem("No MME Microphone Found")
            if not self.output_devices: self.output_device_dropdown.addItem("No MME Output Device Found")
        except StopIteration: self.XYZ_handle_error("Could not find the MME audio host API.")
        except Exception as e: logging.exception("Failed to query audio devices."); self.XYZ_handle_error(f"Could not query audio devices: {e}")
    def XYZ_set_ui_enabled(self, enabled: bool): is_project_loaded = self.current_project_path is not None; self.record_button.setEnabled(enabled and is_project_loaded); self.merge_button.setEnabled(enabled and is_project_loaded); self.new_project_button.setEnabled(enabled)
    def XYZ_initialize_mic_volume(self):
        if not PYCAW_AVAILABLE: self.input_volume_label.setText("Input Gain (Pedalboard): pycaw not found"); return
        try:
            mic_device = AudioUtilities.GetMicrophone(); interface = mic_device.Activate(IAudioEndpointVolume._iid_, CLSCTX_ALL, None); self.mic_volume_control = cast(interface, POINTER(IAudioEndpointVolume))
            min_db, max_db, _ = self.mic_volume_control.GetVolumeRange(); current_db = self.mic_volume_control.GetMasterVolumeLevel()
            self.input_volume_slider.setRange(int(min_db), int(max_db)); self.input_volume_slider.setValue(int(current_db)); self.input_volume_slider.setEnabled(True)
            self.input_volume_label.setText(f"Input Gain (Pedalboard): {current_db:.1f} dB")
        except Exception as e: logging.error(f"Could not initialize microphone volume control: {e}", exc_info=True); self.input_volume_label.setText("Input Gain (Pedalboard): Error"); self.mic_volume_control = None
    def XYZ_update_input_volume(self, value):
        if self.mic_volume_control:
            try: self.mic_volume_control.SetMasterVolumeLevel(float(value), None); self.input_volume_label.setText(f"Input Gain (Pedalboard): {float(value):.1f} dB")
            except Exception as e: logging.error(f"Failed to set input volume: {e}")
    def XYZ_open_project(self, project_name):
        self.current_project_path = os.path.join(APP_DATA_PATH, project_name); self.current_project_label.setText(f"<b>Current Project: {project_name}</b>"); self.XYZ_update_status(f"Opened project '{project_name}'."); self.record_button.setEnabled(True); self.merge_button.setEnabled(True); self.XYZ_clear_segment_list()
        for name, widget in self.project_widgets.items():
            is_active = (name == project_name); widget.setProperty("active", is_active)
            widget.style().unpolish(widget); widget.style().polish(widget)
        try:
            files = [f for f in os.listdir(self.current_project_path) if f.lower().endswith('.wav') and not f.lower().startswith('final mix')]
            files.sort(key=lambda f: os.path.getmtime(os.path.join(self.current_project_path, f)), reverse=True)
            for i, filename in enumerate(files): self.XYZ_add_segment_widget(os.path.join(self.current_project_path, filename), title=f"Segment {len(files) - i}")
        except Exception as e: self.XYZ_handle_error(f"Could not read project files: {e}")
        self.XYZ_load_final_mix_tab()
    def XYZ_load_final_mix_tab(self):
        while self.final_mix_list_layout.count():
            item = self.final_mix_list_layout.takeAt(0); widget = item.widget()
            if widget is not None: widget.deleteLater()
        self.final_mix_widgets.clear()
        if not self.current_project_path:
            label = QLabel("No project selected."); label.setAlignment(Qt.AlignmentFlag.AlignCenter); self.final_mix_list_layout.addWidget(label); return
        try:
            mix_files = [f for f in os.listdir(self.current_project_path) if f.lower().startswith('final mix') and f.lower().endswith('.wav')]
            mix_files.sort(key=lambda f: int(re.search(r'(\d+)', f).group(1)))
            if not mix_files: label = QLabel("No final mixes available.\nApprove and merge segments to create one."); label.setAlignment(Qt.AlignmentFlag.AlignCenter); self.final_mix_list_layout.addWidget(label)
            else:
                for filename in mix_files:
                    filepath = os.path.join(self.current_project_path, filename); title = os.path.splitext(filename)[0]
                    widget = XYZ_SegmentWidget(filepath, title, self.styles, is_final_mix=True, audacity_path=self.audacity_path)
                    widget.play_requested.connect(self.XYZ_play_segment); widget.delete_requested.connect(self.XYZ_delete_segment); widget.audacity_requested.connect(self.XYZ_open_in_audacity)
                    self.final_mix_list_layout.addWidget(widget); self.final_mix_widgets[filepath] = widget
        except Exception as e: self.XYZ_handle_error(f"Could not load final mixes: {e}")
        self.final_mix_list_layout.addStretch()
    def XYZ_open_in_audacity(self, filepath: str):
        if not self.audacity_path: self.XYZ_handle_error("Audacity path is not configured."); return
        try: self.XYZ_update_status(f"Opening {os.path.basename(filepath)} in Audacity..."); subprocess.Popen([self.audacity_path, filepath])
        except Exception as e: logging.exception("Failed to launch Audacity."); self.XYZ_handle_error(f"Could not open file in Audacity: {e}")
    def on_playback_progress(self, value: float):
        if self.currently_playing_widget: self.currently_playing_widget.progress_slider.setValue(int(value * 100))
    def on_playback_finished(self, filepath: str):
        if self.currently_playing_widget: self.currently_playing_widget.set_playing_state(False); self.currently_playing_widget = None
        self.is_audio_busy = False; self.active_player = None; self.XYZ_set_ui_enabled(True)
    def XYZ_populate_project_list(self):
        while self.project_list_layout.count():
            item = self.project_list_layout.takeAt(0); widget = item.widget()
            if widget is not None: widget.deleteLater()
        self.project_widgets.clear()
        try:
            project_dirs = [d for d in os.listdir(APP_DATA_PATH) if os.path.isdir(os.path.join(APP_DATA_PATH, d)) and not d.startswith('.')]
            for project_name in sorted(project_dirs):
                entry = QFrame(); entry.setObjectName("ProjectEntry"); layout = QHBoxLayout(entry); layout.setContentsMargins(0,0,0,0); open_btn = QPushButton(project_name); open_btn.clicked.connect(lambda _, p=project_name: self.XYZ_open_project(p)); open_btn.setStyleSheet("text-align: left; padding-left: 5px;"); open_btn.setToolTip(f"Open the '{project_name}' project."); rename_btn = QPushButton("Rename"); rename_btn.setFixedWidth(60); rename_btn.clicked.connect(lambda _, p=project_name: self.XYZ_rename_project(p)); rename_btn.setToolTip("Rename this project."); delete_btn = QPushButton("Delete"); delete_btn.setFixedWidth(60); delete_btn.clicked.connect(lambda _, p=project_name: self.XYZ_delete_project(p)); delete_btn.setStyleSheet(f"background-color: {self.styles.COLOR_DELETE_BTN};"); delete_btn.setToolTip("Permanently delete this project and all its files."); layout.addWidget(open_btn); layout.addWidget(rename_btn); layout.addWidget(delete_btn); self.project_list_layout.addWidget(entry)
                self.project_widgets[project_name] = entry
                XYZ_apply_shadow_effect(open_btn); XYZ_apply_shadow_effect(rename_btn); XYZ_apply_shadow_effect(delete_btn)
        except Exception as e: self.XYZ_handle_error(f"Failed to read project list: {e}")
    def XYZ_add_segment_widget(self, filepath: str, title: str, prepend: bool = False):
        if filepath in self.segment_widgets: return
        widget = XYZ_SegmentWidget(filepath, title, self.styles); widget.play_requested.connect(self.XYZ_play_segment); widget.delete_requested.connect(self.XYZ_delete_segment); widget.approval_changed.connect(lambda path, state: self.XYZ_update_status(f"'{os.path.basename(path)}' approved: {state}"))
        if prepend: self.segments_list_layout.insertWidget(0, widget)
        else: self.segments_list_layout.addWidget(widget)
        self.segment_widgets[filepath] = widget
    def XYZ_play_segment(self, filepath: str):
        if self.is_audio_busy and self.active_player:
            current_path = self.active_player.filepath; self.active_player.stop()
            if current_path == filepath: return
        self.is_audio_busy = True; self.XYZ_set_ui_enabled(False); self.currently_playing_widget = self.segment_widgets.get(filepath) or self.final_mix_widgets.get(filepath)
        if self.currently_playing_widget: self.currently_playing_widget.set_playing_state(True)
        device_index = self.output_devices.get(self.output_device_dropdown.currentText()); volume = self.output_volume_slider.value()
        self.active_player = XYZ_AudioPlayer(filepath, device_index, volume); self.active_player.signals.progress.connect(self.on_playback_progress); self.active_player.signals.finished.connect(self.on_playback_finished); self.active_player.signals.error.connect(self.XYZ_on_worker_error); self.active_player.start()
    def XYZ_merge_segments(self):
        approved = sorted([w.filepath for w in self.segment_widgets.values() if w.is_approved])
        if not approved: QMessageBox.information(self, "Nothing to Merge", "No segments have been approved."); return
        version = 1
        while os.path.exists(os.path.join(self.current_project_path, f"Final Mix {version}.wav")): version += 1
        output_path = os.path.join(self.current_project_path, f"Final Mix {version}.wav")
        self.XYZ_set_ui_enabled(False); self.merge_button.setText("Merging...")
        self.merge_worker = XYZ_FileProcessor(approved, output_path); self.merge_worker.signals.finished.connect(self.XYZ_on_merge_complete); self.merge_worker.signals.error.connect(self.XYZ_on_worker_error); self.merge_worker.signals.status_update.connect(self.XYZ_update_status); self.merge_worker.start()
    def XYZ_on_merge_complete(self, output_path: str): self.XYZ_set_ui_enabled(True); self.merge_button.setText("Merge Approved"); QMessageBox.information(self, "Success", f"Merged file '{os.path.basename(output_path)}' saved successfully."); self.XYZ_load_final_mix_tab(); self.tab_view.setCurrentWidget(self.final_mix_tab)
    def XYZ_update_status(self, message: str): logging.info(f"STATUS: {message}"); self.status_label.setText(message)
    def XYZ_handle_error(self, message: str): logging.error(f"UI ERROR: {message}"); msg_box = QMessageBox(self); msg_box.setIcon(self.app_icon); msg_box.setText("An Error Occurred"); msg_box.setInformativeText(message); msg_box.setWindowTitle("Error"); msg_box.exec()
    def XYZ_on_worker_error(self, error_message: str): self.is_audio_busy = False; self.active_recorder = None; self.active_player = None; self.start_time = 0; self.timer_label.setText("00:00.0"); self.record_button.setText("Record"); self.merge_button.setText("Merge Approved"); self.XYZ_set_ui_enabled(True); self.XYZ_handle_error(error_message); self.on_playback_finished(None)
    def XYZ_clear_segment_list(self): [w.deleteLater() for w in self.segment_widgets.values()]; self.segment_widgets.clear()
    def XYZ_on_recording_finished(self, filepath: str):
        self.is_audio_busy = False; self.active_recorder = None; self.start_time = 0; self.timer_label.setText("00:00.0"); self.record_button.setText("Record"); self.XYZ_set_ui_enabled(True)
        if filepath: self.XYZ_update_status(f"Saved: {os.path.basename(filepath)}"); self.XYZ_add_segment_widget(filepath, title=f"Segment {len(self.segment_widgets) + 1}", prepend=True)
    def XYZ_toggle_recording(self):
        if self.is_audio_busy and self.active_recorder: self.active_recorder.stop(); self.record_button.setText("Finalizing..."); self.record_button.setEnabled(False); return
        mic = self.mic_dropdown.currentText();
        if not mic or mic not in self.mic_devices: self.XYZ_handle_error("No valid microphone selected."); return
        self.is_audio_busy = True; self.XYZ_set_ui_enabled(False); self.record_button.setEnabled(True); self.record_button.setText("Stop"); dev_idx = self.mic_devices[mic]; self.active_recorder = XYZ_AudioRecorder(dev_idx, 44100, self.current_project_path)
        self.start_time = 0; self.active_recorder.signals.progress.connect(self.XYZ_update_timer); self.active_recorder.signals.finished.connect(self.XYZ_on_recording_finished); self.active_recorder.signals.error.connect(self.XYZ_on_worker_error); self.start_time = time.time(); self.active_recorder.start()
    def XYZ_update_timer(self, ts): elapsed = time.time() - self.start_time if self.start_time else 0; m, s = divmod(elapsed, 60); t = int((s * 10) % 10); self.timer_label.setText(f"{int(m):02d}:{int(s):02d}.{t}")
    def XYZ_prompt_for_new_project(self):
        name, ok = QInputDialog.getText(self, "Create New Project", "Enter the project name:")
        if ok and name: self.XYZ_execute_project_creation(name)
    def XYZ_execute_project_creation(self, name: str):
        name = name.strip()
        if not name: self.XYZ_handle_error("Project name cannot be empty."); return
        project_path = os.path.join(APP_DATA_PATH, re.sub(r'[\\/*?:"<>|]', "", name))
        try:
            if not os.path.exists(project_path): os.makedirs(project_path); self.XYZ_populate_project_list(); self.XYZ_open_project(os.path.basename(project_path))
            else: QMessageBox.warning(self, "Warning", f"A project named '{os.path.basename(project_path)}' already exists.")
        except OSError as e: logging.exception("Project creation failed."); self.XYZ_handle_error(f"Could not create project folder:\n{e}")
    def XYZ_rename_project(self, old):
        new, ok = QInputDialog.getText(self, "Rename Project", f"Enter new name for '{old}':")
        if ok and new:
            new_name = re.sub(r'[\\/*?:"<>|]', "", new.strip())
            old_path = os.path.join(APP_DATA_PATH, old); new_path = os.path.join(APP_DATA_PATH, new_name)
            if os.path.exists(new_path): self.XYZ_handle_error(f"A project named '{new_name}' already exists."); return
            try: os.rename(old_path, new_path); self.XYZ_update_status(f"Renamed '{old}' to '{new_name}'"); self.current_project_path = new_path if self.current_project_path == old_path else self.current_project_path; self.XYZ_populate_project_list()
            except OSError as e: self.XYZ_handle_error(f"Could not rename project: {e}")
    def XYZ_delete_project(self, name):
        project_path = os.path.join(APP_DATA_PATH, name)
        if QMessageBox.question(self, "Confirm Deletion", f"Permanently delete project '{name}' and all its files?", QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No) == QMessageBox.StandardButton.Yes:
            try:
                shutil.rmtree(project_path); self.XYZ_update_status(f"Deleted project '{name}'")
                if self.current_project_path == project_path: self.current_project_path = None; self.current_project_label.setText("<b>No Project Selected</b>"); self.XYZ_clear_segment_list(); self.XYZ_load_final_mix_tab(); self.XYZ_set_ui_enabled(False)
                self.XYZ_populate_project_list()
            except OSError as e: self.XYZ_handle_error(f"Could not delete project: {e}")
    def XYZ_delete_segment(self, fp):
        widget = self.segment_widgets.get(fp) or self.final_mix_widgets.get(fp)
        if widget and QMessageBox.question(self, "Confirm Deletion", f"Delete {os.path.basename(fp)}?", QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No) == QMessageBox.StandardButton.Yes:
            try:
                os.remove(fp); self.XYZ_update_status(f"Deleted: {os.path.basename(fp)}"); widget.deleteLater()
                if fp in self.segment_widgets: del self.segment_widgets[fp]
                if fp in self.final_mix_widgets: del self.final_mix_widgets[fp]
            except OSError as e: self.XYZ_handle_error(f"Could not delete file: {e}")
    def XYZ_approve_all_segments(self, state: bool): action = "Approved" if state else "Unapproved"; [w.approve_checkbox.setChecked(state) for w in self.segment_widgets.values()]; self.XYZ_update_status(f"{action} all segments.")
    def XYZ_delete_all_segments(self):
        if not self.segment_widgets: self.XYZ_update_status("No segments to delete."); return
        if QMessageBox.question(self, "Confirm Deletion", "Permanently delete ALL segments in this project?", QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No) == QMessageBox.StandardButton.Yes:
            for filepath in list(self.segment_widgets.keys()):
                try: widget = self.segment_widgets.pop(filepath); widget.deleteLater(); os.remove(filepath)
                except OSError as e: self.XYZ_handle_error(f"Could not delete {os.path.basename(filepath)}: {e}")
            self.XYZ_update_status("Deleted all segments.")

if __name__ == "__main__":
    XYZ_set_windows_app_id()
    XYZ_ensure_data_directory()
    XYZ_setup_logging()
    
    app = QApplication(sys.argv)
    
    # --- DEFINITIVE ICON LOADING ---
    ICO_PNG_PATH = resource_path("icon.png")
    app_icon = QIcon()
    try:
        pixmap = QPixmap()
        pixmap.loadFromData(Path(ICO_PNG_PATH).read_bytes())
        app_icon.addPixmap(pixmap)
    except Exception as e:
        logging.error(f"Failed to load icon from data: {e}")
        app_icon = QIcon(ICO_PNG_PATH) # Fallback to path-based loading
    app.setWindowIcon(app_icon)
    # --- END ICON LOADING ---

    SPLASH_PATH = resource_path("splash.jpg")
    splash_pix = QPixmap(SPLASH_PATH)
    if splash_pix.isNull(): logging.warning(f"Splash screen image not found at '{SPLASH_PATH}'. Skipping splash.")
    else: splash = QSplashScreen(splash_pix, Qt.WindowType.WindowStaysOnTopHint); splash.show(); app.processEvents()
    
    screen = app.primaryScreen(); available_size = screen.availableGeometry().size()
    initial_width = int(available_size.width() * 0.8); initial_height = int(available_size.height() * 0.8)
    initial_size = QSize(initial_width, initial_height)

    window = XYZ_DubberApp(initial_size=initial_size, app_icon=app_icon)
    screen_geometry = app.primaryScreen().geometry(); window_geometry = window.frameGeometry()
    center_point = screen_geometry.center() - window_geometry.center()
    end_rect = QRect(center_point, window_geometry.size())
    start_rect = end_rect.translated(0, -50)
    
    anim = QPropertyAnimation(window, b"geometry"); anim.setDuration(600); anim.setStartValue(start_rect); anim.setEndValue(end_rect); anim.setEasingCurve(QEasingCurve.Type.OutCubic)
    
    window.setGeometry(start_rect); window.show(); anim.start()
    
    if 'splash' in locals(): splash.finish(window)
    
    sys.exit(app.exec())
