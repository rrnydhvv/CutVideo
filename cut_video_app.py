import sys
import os
import re
import tempfile
import subprocess
import imageio_ffmpeg
from PyQt6.QtWidgets import (
    QApplication, QMainWindow, QWidget, QVBoxLayout, QHBoxLayout,
    QPushButton, QFileDialog, QLabel, QSlider, QComboBox, QMessageBox,
    QSizePolicy, QStyle, QProgressDialog, QStyleOptionSlider, QTabWidget,
    QGroupBox, QLineEdit, QFrame
)
from PyQt6.QtCore import Qt, QUrl, QTime, QThread, pyqtSignal
from PyQt6.QtMultimedia import QMediaPlayer, QAudioOutput
from PyQt6.QtMultimediaWidgets import QVideoWidget


def format_time(ms):
    """Convert milliseconds to HH:MM:SS format"""
    if ms < 0:
        ms = 0
    seconds = (ms // 1000) % 60
    minutes = (ms // 60000) % 60
    hours = (ms // 3600000)
    return f"{hours:02}:{minutes:02}:{seconds:02}"


def format_time_ffmpeg(ms):
    """Convert milliseconds to HH:MM:SS.mmm format for FFmpeg"""
    if ms < 0:
        ms = 0
    seconds = (ms // 1000) % 60
    minutes = (ms // 60000) % 60
    hours = (ms // 3600000)
    milliseconds = ms % 1000
    return f"{hours:02}:{minutes:02}:{seconds:02}.{milliseconds:03}"


def get_video_info(video_path):
    """
    Extract duration_ms, width, height, vcodec, acodec, fps, pix_fmt,
    sample_rate, and audio availability via FFmpeg inspection.
    """
    if not video_path or not os.path.exists(video_path):
        return None
    try:
        ffmpeg_exe = imageio_ffmpeg.get_ffmpeg_exe()
        creationflags = subprocess.CREATE_NO_WINDOW if sys.platform == "win32" else 0
        p = subprocess.Popen(
            [ffmpeg_exe, "-i", video_path],
            stderr=subprocess.PIPE,
            stdout=subprocess.PIPE,
            universal_newlines=True,
            encoding="utf-8",
            errors="ignore",
            creationflags=creationflags
        )
        _, err = p.communicate()

        # Parse duration
        dur_match = re.search(r"Duration:\s*(\d+):(\d+):(\d+(?:\.\d+)?)", err)
        duration_ms = 0
        if dur_match:
            h, m, s = dur_match.groups()
            duration_ms = int(float(h) * 3600000 + float(m) * 60000 + float(s) * 1000)

        # Parse primary video stream (skip thumbnail / attached pic)
        v_stream_lines = [l for l in err.splitlines() if "Video:" in l and "attached pic" not in l]
        v_line = v_stream_lines[0] if v_stream_lines else ""

        v_match = re.search(r"Video:\s*([a-zA-Z0-9_-]+)", v_line)
        vcodec = v_match.group(1).lower() if v_match else "unknown"

        res_match = re.search(r"(\d{2,5})x(\d{2,5})", v_line)
        width, height = (int(res_match.group(1)), int(res_match.group(2))) if res_match else (1920, 1080)

        # Check rotation metadata (smartphone vertical video detection)
        rot_match = re.search(r"rotation of (-?\d+(?:\.\d+)?) degrees", err)
        if not rot_match:
            rot_match = re.search(r"rotate\s*:\s*(-?\d+)", err)
        if rot_match:
            rot = abs(float(rot_match.group(1))) % 360
            if 45 <= rot <= 135 or 225 <= rot <= 315:
                width, height = height, width

        fps_match = re.search(r"(\d+(?:\.\d+)?)\s*fps", v_line)
        if not fps_match:
            fps_match = re.search(r"(\d+(?:\.\d+)?)\s*tbr", v_line)
        fps = round(float(fps_match.group(1)), 2) if fps_match else 30.0

        pix_match = re.search(r"Video:.*?, ([a-zA-Z0-9_]+)(?:\(.*?\))?, \d+x\d+", v_line)
        pix_fmt = pix_match.group(1) if pix_match else "yuv420p"

        # Parse audio stream
        a_stream_match = re.search(r"Stream #\d+:\d+.*?: Audio:\s*([a-zA-Z0-9_-]+)", err)
        has_audio = a_stream_match is not None or "Audio:" in err
        acodec = a_stream_match.group(1).lower() if a_stream_match else None

        sr_match = re.search(r"Audio:.*?, (\d+) Hz", err)
        sample_rate = int(sr_match.group(1)) if sr_match else 48000

        return {
            "duration_ms": duration_ms,
            "width": width,
            "height": height,
            "vcodec": vcodec,
            "acodec": acodec,
            "fps": fps,
            "pix_fmt": pix_fmt,
            "has_audio": has_audio,
            "sample_rate": sample_rate
        }
    except Exception as e:
        print(f"Lỗi đọc thông tin video: {e}")
        return None


def format_video_info_text(info):
    """Format video info as a user-friendly label string"""
    if not info:
        return "Không thể đọc thông tin video."
    dur = format_time(info["duration_ms"])
    w, h = info["width"], info["height"]
    fps = info.get("fps", 30)
    vcodec = info.get("vcodec", "unknown")
    pix_fmt = info.get("pix_fmt", "yuv420p")
    if info.get("has_audio"):
        acodec = info.get("acodec", "aac")
        sr = info.get("sample_rate", 48000)
        audio_str = f"🔊 {acodec} ({sr // 1000}kHz)"
    else:
        audio_str = "🔇 Không có âm thanh"
    return f"⏱️ {dur} | 📐 {w}x{h} | ⚡ {fps} fps | 🎬 {vcodec} ({pix_fmt}) | {audio_str}"


def check_compatibility(info1, info2):
    """
    Evaluate stream compatibility between two videos.
    Returns (is_stream_copy_compatible, list_of_differences)
    """
    differences = []
    if not info1 or not info2:
        return True, []

    if (info1["width"], info1["height"]) != (info2["width"], info2["height"]):
        differences.append(f"Khác độ phân giải ({info1['width']}x{info1['height']} vs {info2['width']}x{info2['height']})")

    if info1["vcodec"] != info2["vcodec"]:
        differences.append(f"Khác codec video ({info1['vcodec']} vs {info2['vcodec']})")

    if info1["has_audio"] != info2["has_audio"]:
        differences.append("Một trong 2 video không có âm thanh")
    elif info1["has_audio"] and info1.get("acodec") != info2.get("acodec"):
        differences.append(f"Khác codec âm thanh ({info1.get('acodec')} vs {info2.get('acodec')})")

    fps1 = info1.get("fps", 30)
    fps2 = info2.get("fps", 30)
    if abs(fps1 - fps2) > 0.5:
        differences.append(f"Khác tốc độ khung hình ({fps1} fps vs {fps2} fps)")

    is_stream_copy_compatible = len(differences) == 0
    return is_stream_copy_compatible, differences


class ClickableSlider(QSlider):
    def mousePressEvent(self, event):
        if event.button() == Qt.MouseButton.LeftButton:
            opt = QStyleOptionSlider()
            self.initStyleOption(opt)
            sr = self.style().subControlRect(
                QStyle.ComplexControl.CC_Slider, opt, QStyle.SubControl.SC_SliderHandle, self
            )

            # Bấm trúng tay nắm thì kéo thả bình thường
            if sr.contains(event.pos()):
                super().mousePressEvent(event)
                return

            # Tính toán vị trí click chuột trên thanh trượt
            percent = max(0.0, min(1.0, event.pos().x() / self.width()))
            val = int(self.minimum() + percent * (self.maximum() - self.minimum()))

            self.setValue(val)
            self.sliderMoved.emit(val)
            self.sliderReleased.emit()
            return
        super().mousePressEvent(event)


class FFmpegExportThread(QThread):
    progress_signal = pyqtSignal(int)
    finished_signal = pyqtSignal(bool, str)

    def __init__(self, cmd, total_duration_ms, cleanup_files=None):
        super().__init__()
        self.cmd = cmd
        self.total_duration_ms = total_duration_ms
        self.cleanup_files = cleanup_files or []
        self.process = None
        self._is_cancelled = False

    def run(self):
        try:
            creationflags = subprocess.CREATE_NO_WINDOW if sys.platform == "win32" else 0

            self.process = subprocess.Popen(
                self.cmd,
                stdout=subprocess.PIPE,
                stderr=subprocess.STDOUT,
                universal_newlines=True,
                encoding="utf-8",
                errors="ignore",
                creationflags=creationflags
            )

            time_regex = re.compile(r"time=\s*(\d+):(\d+):(\d+(?:\.\d+)?)")
            output_tail = []

            for line in self.process.stdout:
                if self._is_cancelled:
                    self.process.terminate()
                    self.process.wait()
                    self._cleanup()
                    self.finished_signal.emit(False, "Đã hủy.")
                    return

                line_str = line.strip()
                if line_str:
                    output_tail.append(line_str)
                    if len(output_tail) > 30:
                        output_tail.pop(0)

                match = time_regex.search(line)
                if match:
                    h, m, s = match.groups()
                    current_ms = int(float(h) * 3600000 + float(m) * 60000 + float(s) * 1000)
                    if self.total_duration_ms > 0:
                        progress = int((current_ms / self.total_duration_ms) * 100)
                        self.progress_signal.emit(min(progress, 100))

            self.process.wait()
            self._cleanup()

            if self._is_cancelled:
                self.finished_signal.emit(False, "Đã hủy.")
            elif self.process.returncode == 0:
                self.progress_signal.emit(100)
                self.finished_signal.emit(True, "Thành công.")
            else:
                tail_err = "\n".join(output_tail[-5:]) if output_tail else "Không có chi tiết lỗi."
                self.finished_signal.emit(False, f"Lỗi từ FFmpeg (mã {self.process.returncode}):\n{tail_err}")
        except Exception as e:
            self._cleanup()
            self.finished_signal.emit(False, str(e))

    def _cleanup(self):
        for path in self.cleanup_files:
            if path and os.path.exists(path):
                try:
                    os.remove(path)
                except Exception as e:
                    print(f"Lỗi dọn file tạm: {e}")

    def cancel(self):
        self._is_cancelled = True


class CutVideoTab(QWidget):
    """Tab chức năng Cắt Video"""
    def __init__(self, parent=None):
        super().__init__(parent)

        self.video_path = None
        self.duration_ms = 0
        self.start_ms = 0
        self.end_ms = 0

        self.layout = QVBoxLayout(self)

        # Video preview widget
        self.video_widget = QVideoWidget()
        self.layout.addWidget(self.video_widget, stretch=1)

        self.media_player = QMediaPlayer()
        self.audio_output = QAudioOutput()
        self.media_player.setAudioOutput(self.audio_output)
        self.media_player.setVideoOutput(self.video_widget)

        self.controls_layout = QVBoxLayout()
        self.layout.addLayout(self.controls_layout)

        # Top controls
        self.top_controls_layout = QHBoxLayout()
        self.controls_layout.addLayout(self.top_controls_layout)

        self.open_btn = QPushButton("📁 Mở Video")
        self.open_btn.clicked.connect(self.open_video)
        self.top_controls_layout.addWidget(self.open_btn)

        self.play_btn = QPushButton()
        self.play_btn.setIcon(self.style().standardIcon(QStyle.StandardPixmap.SP_MediaPlay))
        self.play_btn.clicked.connect(self.play_video)
        self.play_btn.setEnabled(False)
        self.top_controls_layout.addWidget(self.play_btn)

        self.time_label = QLabel("00:00:00 / 00:00:00")
        self.top_controls_layout.addWidget(self.time_label)
        self.top_controls_layout.addStretch()

        self.mute_btn = QPushButton()
        self.mute_btn.setIcon(self.style().standardIcon(QStyle.StandardPixmap.SP_MediaVolume))
        self.mute_btn.setCheckable(True)
        self.mute_btn.clicked.connect(self.toggle_mute)
        self.top_controls_layout.addWidget(self.mute_btn)

        self.volume_slider = QSlider(Qt.Orientation.Horizontal)
        self.volume_slider.setRange(0, 100)
        self.volume_slider.setValue(100)
        self.volume_slider.setFixedWidth(100)
        self.volume_slider.valueChanged.connect(self.set_volume)
        self.top_controls_layout.addWidget(self.volume_slider)

        # Timeline Slider
        self.slider = ClickableSlider(Qt.Orientation.Horizontal)
        self.slider.setRange(0, 0)
        self.slider.sliderMoved.connect(self.set_position)
        self.slider.sliderReleased.connect(self.slider_released)
        self.controls_layout.addWidget(self.slider)

        # Cutting markers
        self.cutting_controls_layout = QHBoxLayout()
        self.controls_layout.addLayout(self.cutting_controls_layout)

        self.start_btn = QPushButton("🚩 Đặt mốc bắt đầu")
        self.start_btn.clicked.connect(self.set_start_marker)
        self.start_btn.setEnabled(False)
        self.cutting_controls_layout.addWidget(self.start_btn)

        self.start_label = QLabel("Start: --:--:--")
        self.cutting_controls_layout.addWidget(self.start_label)

        self.end_btn = QPushButton("🏁 Đặt mốc kết thúc")
        self.end_btn.clicked.connect(self.set_end_marker)
        self.end_btn.setEnabled(False)
        self.cutting_controls_layout.addWidget(self.end_btn)

        self.end_label = QLabel("End: --:--:--")
        self.cutting_controls_layout.addWidget(self.end_label)

        self.cutting_controls_layout.addStretch()

        # Output & Export layout
        self.output_layout = QHBoxLayout()
        self.controls_layout.addLayout(self.output_layout)

        self.quality_label = QLabel("Chất lượng Output:")
        self.output_layout.addWidget(self.quality_label)

        self.quality_combo = QComboBox()
        self.quality_combo.addItem("Gốc (Cực nhanh - Không encode lại)", "-c copy")
        self.quality_combo.addItem("Cao (CPU - Sắc nét)", "-c:v libx264 -crf 18 -preset fast -threads 0 -pix_fmt yuv420p -movflags +faststart")
        self.quality_combo.addItem("Trung bình (CPU - Cân bằng)", "-c:v libx264 -crf 23 -preset fast -threads 0 -pix_fmt yuv420p -movflags +faststart")
        self.quality_combo.addItem("Thấp (CPU - Dung lượng nhỏ)", "-c:v libx264 -crf 28 -preset fast -threads 0 -pix_fmt yuv420p -movflags +faststart")
        self.quality_combo.addItem("Cao (NVIDIA GPU - Siêu tốc)", "-c:v h264_nvenc -preset p4 -rc vbr -cq 19 -b:v 0 -pix_fmt yuv420p -movflags +faststart")
        self.quality_combo.addItem("Trung bình (NVIDIA GPU - Siêu tốc)", "-c:v h264_nvenc -preset p4 -rc vbr -cq 26 -b:v 0 -pix_fmt yuv420p -movflags +faststart")
        self.quality_combo.addItem("Thấp (NVIDIA GPU - Siêu tốc)", "-c:v h264_nvenc -preset p4 -rc vbr -cq 32 -b:v 0 -pix_fmt yuv420p -movflags +faststart")
        self.output_layout.addWidget(self.quality_combo)

        self.output_layout.addStretch()

        self.cut_btn = QPushButton("✂️ Cắt Video")
        self.cut_btn.setMinimumHeight(38)
        self.cut_btn.setStyleSheet("font-weight: bold; background-color: #2E7D32; color: white; padding: 0 20px; border-radius: 4px;")
        self.cut_btn.clicked.connect(self.cut_video)
        self.cut_btn.setEnabled(False)
        self.output_layout.addWidget(self.cut_btn)

        self.media_player.positionChanged.connect(self.position_changed)
        self.media_player.durationChanged.connect(self.duration_changed)

    def pause(self):
        if self.media_player.playbackState() == QMediaPlayer.PlaybackState.PlayingState:
            self.media_player.pause()
            self.play_btn.setIcon(self.style().standardIcon(QStyle.StandardPixmap.SP_MediaPlay))

    def open_video(self):
        file_name, _ = QFileDialog.getOpenFileName(
            self, "Mở Video", "", "Video Files (*.mp4 *.mkv *.avi *.mov *.wmv *.flv *.webm)"
        )
        if file_name:
            self.load_video(file_name)

    def load_video(self, file_name):
        if os.path.exists(file_name):
            self.video_path = file_name
            self.media_player.setSource(QUrl.fromLocalFile(file_name))
            self.play_btn.setEnabled(True)
            self.start_btn.setEnabled(True)
            self.end_btn.setEnabled(True)
            self.cut_btn.setEnabled(True)
            self.play_video()

    def play_video(self):
        if self.media_player.playbackState() == QMediaPlayer.PlaybackState.PlayingState:
            self.media_player.pause()
            self.play_btn.setIcon(self.style().standardIcon(QStyle.StandardPixmap.SP_MediaPlay))
        else:
            self.media_player.play()
            self.play_btn.setIcon(self.style().standardIcon(QStyle.StandardPixmap.SP_MediaPause))

    def position_changed(self, position):
        if not self.slider.isSliderDown():
            self.slider.setValue(position)
        self.update_time_label(position)

    def duration_changed(self, duration):
        self.slider.setRange(0, duration)
        self.duration_ms = duration
        self.end_ms = duration
        self.update_time_label(self.media_player.position())
        self.start_label.setText(f"Start: {format_time(self.start_ms)}")
        self.end_label.setText(f"End: {format_time(self.end_ms)}")

    def set_position(self, position):
        self.media_player.setPosition(position)
        self.update_time_label(position)

    def slider_released(self):
        if self.media_player.playbackState() == QMediaPlayer.PlaybackState.PausedState:
            self.media_player.play()
            self.media_player.pause()

    def update_time_label(self, position):
        self.time_label.setText(f"{format_time(position)} / {format_time(self.duration_ms)}")

    def set_start_marker(self):
        self.start_ms = self.media_player.position()
        self.start_label.setText(f"Start: {format_time(self.start_ms)}")
        if self.start_ms > self.end_ms:
            self.end_ms = self.duration_ms
            self.end_label.setText(f"End: {format_time(self.end_ms)}")

    def set_end_marker(self):
        self.end_ms = self.media_player.position()
        if self.end_ms < self.start_ms:
            self.end_ms = self.start_ms
        self.end_label.setText(f"End: {format_time(self.end_ms)}")

    def cut_video(self):
        if not self.video_path:
            return

        output_path, _ = QFileDialog.getSaveFileName(
            self, "Lưu Video Mới",
            self.video_path.rsplit('.', 1)[0] + "_cut.mp4",
            "MP4 Files (*.mp4)"
        )
        if not output_path:
            return

        start_time_str = format_time_ffmpeg(self.start_ms)
        duration_ms = self.end_ms - self.start_ms
        if duration_ms <= 0:
            QMessageBox.warning(self, "Lỗi", "Thời gian kết thúc phải lớn hơn thời gian bắt đầu!")
            return

        duration_str = format_time_ffmpeg(duration_ms)
        quality_args = self.quality_combo.currentData().split(" ")
        ffmpeg_exe = imageio_ffmpeg.get_ffmpeg_exe()

        hwaccel_args = []
        if "nvenc" in self.quality_combo.currentData():
            hwaccel_args = ["-hwaccel", "cuda"]

        cmd = [
            ffmpeg_exe,
            "-y",
        ] + hwaccel_args + [
            "-ss", start_time_str,
            "-i", self.video_path,
            "-t", duration_str,
        ] + quality_args + [output_path]

        self.progress_dialog = QProgressDialog("Đang xử lý cắt video...", "Hủy", 0, 100, self)
        self.progress_dialog.setWindowTitle("Đang Export Video")
        self.progress_dialog.setWindowModality(Qt.WindowModality.WindowModal)
        self.progress_dialog.setAutoClose(True)
        self.progress_dialog.setAutoReset(True)

        self.cut_btn.setEnabled(False)
        self.pause()

        self.export_thread = FFmpegExportThread(cmd, duration_ms)
        self.export_thread.progress_signal.connect(self.progress_dialog.setValue)
        self.export_thread.finished_signal.connect(lambda s, m: self.on_export_finished(s, m, output_path))
        self.progress_dialog.canceled.connect(self.export_thread.cancel)

        self.progress_dialog.show()
        self.export_thread.start()

    def on_export_finished(self, success, message, output_path):
        self.cut_btn.setEnabled(True)
        if success:
            QMessageBox.information(self, "Thành công", f"Đã lưu video đã cắt tại:\n{output_path}")
        else:
            if os.path.exists(output_path):
                try:
                    os.remove(output_path)
                except Exception as e:
                    print(f"Lỗi khi xóa file tạm: {e}")

            if message == "Đã hủy.":
                QMessageBox.warning(self, "Đã hủy", "Quá trình export đã bị hủy. Hệ thống đã tự động dọn dẹp file tạm.")
            else:
                QMessageBox.critical(self, "Lỗi khi cắt", f"Lỗi:\n{message}")

    def toggle_mute(self):
        is_muted = self.mute_btn.isChecked()
        self.audio_output.setMuted(is_muted)
        if is_muted:
            self.mute_btn.setIcon(self.style().standardIcon(QStyle.StandardPixmap.SP_MediaVolumeMuted))
        else:
            self.mute_btn.setIcon(self.style().standardIcon(QStyle.StandardPixmap.SP_MediaVolume))

    def set_volume(self, volume):
        self.audio_output.setVolume(volume / 100.0)
        if volume == 0:
            self.mute_btn.setChecked(True)
            self.mute_btn.setIcon(self.style().standardIcon(QStyle.StandardPixmap.SP_MediaVolumeMuted))
        elif self.mute_btn.isChecked():
            self.mute_btn.setChecked(False)
            self.mute_btn.setIcon(self.style().standardIcon(QStyle.StandardPixmap.SP_MediaVolume))


class AppendVideoTab(QWidget):
    """Tab chức năng Nối (Append / Ghép) 2 Video với Khả Năng Tương Thích Tối Đa"""
    def __init__(self, parent=None):
        super().__init__(parent)

        self.video1_path = None
        self.video2_path = None
        self.video1_info = None
        self.video2_info = None
        self.last_mode_used = "reencode"

        main_layout = QHBoxLayout(self)

        # Left panel: Input controls, options, export button
        left_widget = QWidget()
        left_layout = QVBoxLayout(left_widget)
        left_layout.setContentsMargins(0, 0, 0, 0)
        main_layout.addWidget(left_widget, stretch=3)

        # Video 1 Group
        self.v1_group = QGroupBox("1️⃣ Video Đầu (Video 1)")
        v1_layout = QVBoxLayout(self.v1_group)

        v1_file_row = QHBoxLayout()
        self.v1_path_edit = QLineEdit()
        self.v1_path_edit.setPlaceholderText("Chưa chọn Video 1...")
        self.v1_path_edit.setReadOnly(True)
        v1_file_row.addWidget(self.v1_path_edit)

        self.v1_browse_btn = QPushButton("Chọn Video 1")
        self.v1_browse_btn.clicked.connect(self.select_video1)
        v1_file_row.addWidget(self.v1_browse_btn)

        self.v1_preview_btn = QPushButton("👁️ Xem thử")
        self.v1_preview_btn.clicked.connect(lambda: self.preview_video(self.video1_path))
        self.v1_preview_btn.setEnabled(False)
        v1_file_row.addWidget(self.v1_preview_btn)
        v1_layout.addLayout(v1_file_row)

        self.v1_info_label = QLabel("Chưa chọn video")
        self.v1_info_label.setStyleSheet("color: #555; font-size: 11px;")
        v1_layout.addWidget(self.v1_info_label)
        left_layout.addWidget(self.v1_group)

        # Swap button
        swap_layout = QHBoxLayout()
        swap_layout.addStretch()
        self.swap_btn = QPushButton("⇅ Đổi thứ tự (Video 1 ⇄ Video 2)")
        self.swap_btn.setToolTip("Hoán đổi vị trí nối giữa Video 1 và Video 2")
        self.swap_btn.clicked.connect(self.swap_videos)
        self.swap_btn.setEnabled(False)
        swap_layout.addWidget(self.swap_btn)
        swap_layout.addStretch()
        left_layout.addLayout(swap_layout)

        # Video 2 Group
        self.v2_group = QGroupBox("2️⃣ Video Nối Tiếp (Video 2)")
        v2_layout = QVBoxLayout(self.v2_group)

        v2_file_row = QHBoxLayout()
        self.v2_path_edit = QLineEdit()
        self.v2_path_edit.setPlaceholderText("Chưa chọn Video 2...")
        self.v2_path_edit.setReadOnly(True)
        v2_file_row.addWidget(self.v2_path_edit)

        self.v2_browse_btn = QPushButton("Chọn Video 2")
        self.v2_browse_btn.clicked.connect(self.select_video2)
        v2_file_row.addWidget(self.v2_browse_btn)

        self.v2_preview_btn = QPushButton("👁️ Xem thử")
        self.v2_preview_btn.clicked.connect(lambda: self.preview_video(self.video2_path))
        self.v2_preview_btn.setEnabled(False)
        v2_file_row.addWidget(self.v2_preview_btn)
        v2_layout.addLayout(v2_file_row)

        self.v2_info_label = QLabel("Chưa chọn video")
        self.v2_info_label.setStyleSheet("color: #555; font-size: 11px;")
        v2_layout.addWidget(self.v2_info_label)
        left_layout.addWidget(self.v2_group)

        # Compatibility Assessment Badge
        self.compat_frame = QFrame()
        self.compat_frame.setStyleSheet("background-color: #F8F9FA; border: 1px solid #E0E0E0; border-radius: 6px; padding: 6px;")
        compat_layout = QVBoxLayout(self.compat_frame)
        compat_layout.setContentsMargins(8, 6, 8, 6)

        self.compat_label = QLabel("💡 Vui lòng chọn cả 2 video để kiểm tra tính tương thích.")
        self.compat_label.setWordWrap(True)
        self.compat_label.setStyleSheet("color: #666; font-size: 12px;")
        compat_layout.addWidget(self.compat_label)
        left_layout.addWidget(self.compat_frame)

        # Export settings group
        settings_group = QGroupBox("⚙️ Cấu hình xuất video tối ưu")
        settings_layout = QVBoxLayout(settings_group)

        self.total_duration_label = QLabel("⏱️ Tổng thời lượng dự kiến: 00:00:00")
        self.total_duration_label.setStyleSheet("font-weight: bold; font-size: 13px; color: #1565C0;")
        settings_layout.addWidget(self.total_duration_label)

        # Mode row
        mode_row = QHBoxLayout()
        mode_row.addWidget(QLabel("Chế độ nối:"))
        self.mode_combo = QComboBox()
        self.mode_combo.addItem("Tương thích cao (Khuyên dùng - Chuẩn hóa hình & tiếng, khử lệch)", "reencode")
        self.mode_combo.addItem("Siêu tốc (Stream Copy - Ghép tức thì, yêu cầu cùng định dạng)", "copy")
        self.mode_combo.currentIndexChanged.connect(self.mode_changed)
        mode_row.addWidget(self.mode_combo, stretch=1)
        settings_layout.addLayout(mode_row)

        # Target Resolution row
        self.res_row = QHBoxLayout()
        self.res_row.addWidget(QLabel("Khung hình đích:"))
        self.resolution_combo = QComboBox()
        self.resolution_combo.addItem("Tự động (Theo Video 1 - Giữ nguyên video chính)", "auto_v1")
        self.resolution_combo.addItem("Lớn nhất (Max Width x Max Height)", "max")
        self.resolution_combo.addItem("Full HD (1920x1080 - 16:9 ngang)", "1080p")
        self.resolution_combo.addItem("HD (1280x720 - 16:9 ngang)", "720p")
        self.resolution_combo.addItem("Shorts / TikTok / Reels (1080x1920 - 9:16 dọc)", "vertical_1080p")
        self.resolution_combo.addItem("Theo Video 2", "auto_v2")
        self.res_row.addWidget(self.resolution_combo, stretch=1)
        settings_layout.addLayout(self.res_row)

        # FPS row
        self.fps_row = QHBoxLayout()
        self.fps_row.addWidget(QLabel("Tốc độ khung hình:"))
        self.fps_combo = QComboBox()
        self.fps_combo.addItem("Tự động (Theo nguồn - Tối đa 60 FPS)", "auto")
        self.fps_combo.addItem("30 FPS (Tiêu chuẩn - Tương thích mọi thiết bị)", "30")
        self.fps_combo.addItem("60 FPS (Mượt mà cao)", "60")
        self.fps_row.addWidget(self.fps_combo, stretch=1)
        settings_layout.addLayout(self.fps_row)

        # Quality row
        self.quality_row = QHBoxLayout()
        self.quality_row.addWidget(QLabel("Chất lượng xuất:"))
        self.quality_combo = QComboBox()
        self.quality_combo.addItem("Cao (CPU - Khuyên dùng)", "cpu_high")
        self.quality_combo.addItem("Trung bình (CPU - Cân bằng)", "cpu_mid")
        self.quality_combo.addItem("Thấp (CPU - Dung lượng nhỏ)", "cpu_low")
        self.quality_combo.addItem("Cao (NVIDIA GPU - Siêu tốc)", "gpu_high")
        self.quality_combo.addItem("Trung bình (NVIDIA GPU - Siêu tốc)", "gpu_mid")
        self.quality_row.addWidget(self.quality_combo, stretch=1)
        settings_layout.addLayout(self.quality_row)

        self.note_label = QLabel("💡 Chế độ tương thích cao: Tự động điều chỉnh kích thước không méo hình (letterbox/pad), chuẩn hóa YUV420p, đồng bộ âm thanh 48kHz stereo & khử hoàn toàn lệch tiếng.")
        self.note_label.setWordWrap(True)
        self.note_label.setStyleSheet("color: #666; font-size: 11px;")
        settings_layout.addWidget(self.note_label)

        left_layout.addWidget(settings_group)
        left_layout.addStretch()

        # Append action button
        self.append_btn = QPushButton("🔗 Nối (Append) 2 Video")
        self.append_btn.setMinimumHeight(44)
        self.append_btn.setStyleSheet("font-weight: bold; font-size: 14px; background-color: #1976D2; color: white; border-radius: 4px;")
        self.append_btn.clicked.connect(lambda: self.append_videos())
        self.append_btn.setEnabled(False)
        left_layout.addWidget(self.append_btn)

        # Right panel: Video Preview
        right_widget = QWidget()
        right_layout = QVBoxLayout(right_widget)
        right_layout.setContentsMargins(0, 0, 0, 0)
        main_layout.addWidget(right_widget, stretch=2)

        preview_group = QGroupBox("📺 Khung Xem Trước Video")
        preview_layout = QVBoxLayout(preview_group)

        self.preview_video_widget = QVideoWidget()
        preview_layout.addWidget(self.preview_video_widget, stretch=1)

        self.preview_player = QMediaPlayer()
        self.preview_audio = QAudioOutput()
        self.preview_player.setAudioOutput(self.preview_audio)
        self.preview_player.setVideoOutput(self.preview_video_widget)

        self.preview_status_label = QLabel("Chọn video và bấm 'Xem thử' để phát.")
        self.preview_status_label.setStyleSheet("color: #888; font-style: italic;")
        preview_layout.addWidget(self.preview_status_label)

        # Preview player controls
        p_ctrl_layout = QHBoxLayout()
        self.p_play_btn = QPushButton()
        self.p_play_btn.setIcon(self.style().standardIcon(QStyle.StandardPixmap.SP_MediaPlay))
        self.p_play_btn.clicked.connect(self.toggle_preview_playback)
        self.p_play_btn.setEnabled(False)
        p_ctrl_layout.addWidget(self.p_play_btn)

        self.p_slider = ClickableSlider(Qt.Orientation.Horizontal)
        self.p_slider.setRange(0, 0)
        self.p_slider.sliderMoved.connect(self.preview_player.setPosition)
        p_ctrl_layout.addWidget(self.p_slider)

        self.p_time_label = QLabel("00:00:00 / 00:00:00")
        p_ctrl_layout.addWidget(self.p_time_label)

        preview_layout.addLayout(p_ctrl_layout)
        right_layout.addWidget(preview_group)

        self.preview_player.positionChanged.connect(self.preview_position_changed)
        self.preview_player.durationChanged.connect(self.preview_duration_changed)

    def pause(self):
        if self.preview_player.playbackState() == QMediaPlayer.PlaybackState.PlayingState:
            self.preview_player.pause()
            self.p_play_btn.setIcon(self.style().standardIcon(QStyle.StandardPixmap.SP_MediaPlay))

    def mode_changed(self):
        is_reencode = (self.mode_combo.currentData() == "reencode")
        self.quality_combo.setEnabled(is_reencode)
        self.resolution_combo.setEnabled(is_reencode)
        self.fps_combo.setEnabled(is_reencode)

        if is_reencode:
            self.note_label.setText("💡 Chế độ tương thích cao: Tự động điều chỉnh kích thước không méo hình (letterbox/pad), chuẩn hóa YUV420p, đồng bộ âm thanh 48kHz stereo & khử hoàn toàn lệch tiếng.")
            self.note_label.setStyleSheet("color: #666; font-size: 11px;")
        else:
            is_compat, diffs = check_compatibility(self.video1_info, self.video2_info)
            if not is_compat and diffs:
                self.note_label.setText("⚠️ Cảnh báo: 2 video không cùng chuẩn. Ghép siêu tốc có thể gây lỗi hiển thị, đứng hình hoặc mất tiếng. Khuyên dùng 'Tương thích cao'.")
                self.note_label.setStyleSheet("color: #D32F2F; font-size: 11px; font-weight: bold;")
            else:
                self.note_label.setText("⚡ Chế độ siêu tốc: Ghép nối dữ liệu trực tiếp trong vài giây mà không cần encode lại.")
                self.note_label.setStyleSheet("color: #2E7D32; font-size: 11px;")

    def select_video1(self):
        file_name, _ = QFileDialog.getOpenFileName(
            self, "Chọn Video 1 (Đầu)", "", "Video Files (*.mp4 *.mkv *.avi *.mov *.wmv *.flv *.webm *.ts)"
        )
        if file_name:
            self.load_video1(file_name)

    def select_video2(self):
        file_name, _ = QFileDialog.getOpenFileName(
            self, "Chọn Video 2 (Nối tiếp)", "", "Video Files (*.mp4 *.mkv *.avi *.mov *.wmv *.flv *.webm *.ts)"
        )
        if file_name:
            self.load_video2(file_name)

    def load_video1(self, file_path):
        self.video1_path = file_path
        self.v1_path_edit.setText(file_path)
        self.video1_info = get_video_info(file_path)

        if self.video1_info:
            self.v1_info_label.setText(format_video_info_text(self.video1_info))
            self.v1_preview_btn.setEnabled(True)
        else:
            self.v1_info_label.setText("Không thể đọc thông tin video.")

        self.update_state()

    def load_video2(self, file_path):
        self.video2_path = file_path
        self.v2_path_edit.setText(file_path)
        self.video2_info = get_video_info(file_path)

        if self.video2_info:
            self.v2_info_label.setText(format_video_info_text(self.video2_info))
            self.v2_preview_btn.setEnabled(True)
        else:
            self.v2_info_label.setText("Không thể đọc thông tin video.")

        self.update_state()

    def swap_videos(self):
        path1, path2 = self.video1_path, self.video2_path
        if path1 and path2:
            self.load_video1(path2)
            self.load_video2(path1)

    def update_state(self):
        has_both = bool(self.video1_path and self.video2_path)
        self.swap_btn.setEnabled(has_both)
        self.append_btn.setEnabled(has_both)

        if has_both and self.video1_info and self.video2_info:
            total_ms = self.video1_info["duration_ms"] + self.video2_info["duration_ms"]
            self.total_duration_label.setText(f"⏱️ Tổng thời lượng dự kiến: {format_time(total_ms)}")

            w1, h1 = self.video1_info["width"], self.video1_info["height"]
            w2, h2 = self.video2_info["width"], self.video2_info["height"]
            max_w, max_h = max(w1, w2), max(h1, h2)

            # Cập nhật danh sách độ phân giải động
            current_res_choice = self.resolution_combo.currentData() or "auto_v1"
            self.resolution_combo.blockSignals(True)
            self.resolution_combo.clear()
            self.resolution_combo.addItem(f"Tự động (Theo Video 1: {w1}x{h1}) [Khuyên dùng]", "auto_v1")
            self.resolution_combo.addItem(f"Lớn nhất ({max_w}x{max_h})", "max")
            self.resolution_combo.addItem("Full HD (1920x1080 - 16:9 ngang)", "1080p")
            self.resolution_combo.addItem("HD (1280x720 - 16:9 ngang)", "720p")
            self.resolution_combo.addItem("Shorts / TikTok / Reels (1080x1920 - 9:16 dọc)", "vertical_1080p")
            self.resolution_combo.addItem(f"Theo Video 2 ({w2}x{h2})", "auto_v2")

            # Restore previous selection if possible
            idx = self.resolution_combo.findData(current_res_choice)
            if idx >= 0:
                self.resolution_combo.setCurrentIndex(idx)
            self.resolution_combo.blockSignals(False)

            # Đánh giá tính tương thích giữa 2 video
            is_compat, differences = check_compatibility(self.video1_info, self.video2_info)
            if is_compat:
                self.compat_label.setText("🟢 Hai video hoàn toàn cùng chuẩn định dạng! Bạn có thể sử dụng chế độ 'Siêu tốc' hoặc 'Tương thích cao'.")
                self.compat_label.setStyleSheet("color: #2E7D32; font-weight: bold; font-size: 11px;")
                self.compat_frame.setStyleSheet("background-color: #E8F5E9; border: 1px solid #A5D6A7; border-radius: 6px; padding: 6px;")
            else:
                diff_text = " • ".join(differences)
                self.compat_label.setText(f"🟡 Khác biệt định dạng: {diff_text}\n➡️ Khuyên dùng chế độ 'Tương thích cao' để đảm bảo hình ảnh chuẩn nét và không bị lệch tiếng.")
                self.compat_label.setStyleSheet("color: #E65100; font-weight: bold; font-size: 11px;")
                self.compat_frame.setStyleSheet("background-color: #FFF3E0; border: 1px solid #FFCC80; border-radius: 6px; padding: 6px;")

            self.mode_changed()

    def preview_video(self, file_path):
        if file_path and os.path.exists(file_path):
            self.preview_player.setSource(QUrl.fromLocalFile(file_path))
            self.preview_status_label.setText(f"Đang phát: {os.path.basename(file_path)}")
            self.p_play_btn.setEnabled(True)
            self.preview_player.play()
            self.p_play_btn.setIcon(self.style().standardIcon(QStyle.StandardPixmap.SP_MediaPause))

    def toggle_preview_playback(self):
        if self.preview_player.playbackState() == QMediaPlayer.PlaybackState.PlayingState:
            self.preview_player.pause()
            self.p_play_btn.setIcon(self.style().standardIcon(QStyle.StandardPixmap.SP_MediaPlay))
        else:
            self.preview_player.play()
            self.p_play_btn.setIcon(self.style().standardIcon(QStyle.StandardPixmap.SP_MediaPause))

    def preview_position_changed(self, position):
        if not self.p_slider.isSliderDown():
            self.p_slider.setValue(position)
        total = self.preview_player.duration()
        self.p_time_label.setText(f"{format_time(position)} / {format_time(total)}")

    def preview_duration_changed(self, duration):
        self.p_slider.setRange(0, duration)
        self.p_time_label.setText(f"{format_time(self.preview_player.position())} / {format_time(duration)}")

    def append_videos(self, preset_output_path=None):
        if not self.video1_path or not self.video2_path:
            QMessageBox.warning(self, "Lỗi", "Vui lòng chọn đầy đủ cả Video 1 và Video 2!")
            return

        mode = self.mode_combo.currentData()

        # Kiểm tra tính tương thích nếu người dùng chọn chế độ copy
        is_compat, differences = check_compatibility(self.video1_info, self.video2_info)
        if mode == "copy" and not is_compat:
            diff_list_str = "\n".join([f"• {d}" for d in differences])
            reply = QMessageBox.question(
                self, "Cảnh báo tương thích khi nối siêu tốc",
                f"Phát hiện sự không đồng nhất giữa 2 video:\n{diff_list_str}\n\n"
                "Nếu tiếp tục với chế độ Siêu tốc, video xuất ra có thể bị đứng hình, giật lag hoặc mất tiếng.\n\n"
                "Bạn có muốn tự động chuyển sang chế độ 'Tương thích cao' (Khuyên dùng) không?",
                QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
                QMessageBox.StandardButton.Yes
            )
            if reply == QMessageBox.StandardButton.Yes:
                self.mode_combo.setCurrentIndex(0)
                mode = "reencode"

        self.last_mode_used = mode

        if preset_output_path:
            output_path = preset_output_path
        else:
            default_name = self.video1_path.rsplit('.', 1)[0] + "_append.mp4"
            output_path, _ = QFileDialog.getSaveFileName(
                self, "Lưu Video Ghép Mới", default_name, "MP4 Files (*.mp4)"
            )
        if not output_path:
            return

        ffmpeg_exe = imageio_ffmpeg.get_ffmpeg_exe()
        quality = self.quality_combo.currentData()

        total_duration_ms = 0
        if self.video1_info and self.video2_info:
            total_duration_ms = self.video1_info["duration_ms"] + self.video2_info["duration_ms"]

        cleanup_files = []

        if mode == "copy":
            # Chế độ Stream Copy sử dụng concat demuxer với khử lỗi timestamp ban đầu
            temp_fd, temp_txt_path = tempfile.mkstemp(prefix="cutvideo_concat_", suffix=".txt")
            os.close(temp_fd)
            cleanup_files.append(temp_txt_path)

            def escape_demuxer_path(p):
                clean_p = os.path.abspath(p).replace('\\', '/')
                return clean_p.replace("'", "'\\''")

            with open(temp_txt_path, "w", encoding="utf-8") as f:
                f.write(f"file '{escape_demuxer_path(self.video1_path)}'\n")
                f.write(f"file '{escape_demuxer_path(self.video2_path)}'\n")

            cmd = [
                ffmpeg_exe,
                "-y",
                "-avoid_negative_ts", "make_zero",
                "-f", "concat",
                "-safe", "0",
                "-i", temp_txt_path,
                "-c", "copy",
                "-movflags", "+faststart",
                output_path
            ]
        else:
            # Chế độ Tương thích cao: Scale, pad căn giữa, chuẩn hóa SAR, format YUV420p, khử lệch PTS
            w1 = self.video1_info["width"] if self.video1_info else 1920
            h1 = self.video1_info["height"] if self.video1_info else 1080
            w2 = self.video2_info["width"] if self.video2_info else 1920
            h2 = self.video2_info["height"] if self.video2_info else 1080

            # Xác định kích thước đích theo lựa chọn của người dùng
            res_choice = self.resolution_combo.currentData()
            if res_choice == "max":
                target_w, target_h = max(w1, w2), max(h1, h2)
            elif res_choice == "1080p":
                target_w, target_h = 1920, 1080
            elif res_choice == "720p":
                target_w, target_h = 1280, 720
            elif res_choice == "vertical_1080p":
                target_w, target_h = 1080, 1920
            elif res_choice == "auto_v2":
                target_w, target_h = w2, h2
            else:  # auto_v1 (default)
                target_w, target_h = w1, h1

            # Đảm bảo kích thước chia hết cho 2 (chuẩn YUV420p)
            if target_w % 2 != 0:
                target_w += 1
            if target_h % 2 != 0:
                target_h += 1

            # Xác định tốc độ khung hình đích
            fps1 = self.video1_info.get("fps", 30.0) if self.video1_info else 30.0
            fps2 = self.video2_info.get("fps", 30.0) if self.video2_info else 30.0
            fps_choice = self.fps_combo.currentData()
            if fps_choice == "60":
                target_fps = 60
            elif fps_choice == "30":
                target_fps = 30
            else:  # auto
                target_fps = 60 if max(fps1, fps2) >= 48 else 30

            # Chuẩn bị luồng video với scale, pad, setsar=1, fps, format=yuv420p và reset timestamp
            filter_parts = [
                f"[0:v]scale={target_w}:{target_h}:force_original_aspect_ratio=decrease:force_divisible_by=2,pad={target_w}:{target_h}:-1:-1:color=black,setsar=1,fps={target_fps},setpts=PTS-STARTPTS,format=yuv420p[v0]",
                f"[1:v]scale={target_w}:{target_h}:force_original_aspect_ratio=decrease:force_divisible_by=2,pad={target_w}:{target_h}:-1:-1:color=black,setsar=1,fps={target_fps},setpts=PTS-STARTPTS,format=yuv420p[v1]"
            ]

            # Xử lý âm thanh đa dạng: khử lệch sample rate, chuẩn hóa stereo 48kHz, bù âm thanh tĩnh nếu thiếu
            has_a1 = self.video1_info["has_audio"] if self.video1_info else True
            has_a2 = self.video2_info["has_audio"] if self.video2_info else True
            dur1_s = max(0.1, (self.video1_info["duration_ms"] / 1000.0) if self.video1_info and self.video1_info.get("duration_ms") else 1.0)
            dur2_s = max(0.1, (self.video2_info["duration_ms"] / 1000.0) if self.video2_info and self.video2_info.get("duration_ms") else 1.0)

            if has_a1 and has_a2:
                filter_parts.append("[0:a]aresample=async=1:first_pts=0,aformat=sample_rates=48000:channel_layouts=stereo,asetpts=PTS-STARTPTS[a0]")
                filter_parts.append("[1:a]aresample=async=1:first_pts=0,aformat=sample_rates=48000:channel_layouts=stereo,asetpts=PTS-STARTPTS[a1]")
                filter_parts.append("[v0][a0][v1][a1]concat=n=2:v=1:a=1[outv][outa]")
                has_out_audio = True
            elif has_a1 and not has_a2:
                filter_parts.append("[0:a]aresample=async=1:first_pts=0,aformat=sample_rates=48000:channel_layouts=stereo,asetpts=PTS-STARTPTS[a0]")
                filter_parts.append(f"anullsrc=channel_layout=stereo:sample_rate=48000,atrim=duration={dur2_s:.3f},asetpts=PTS-STARTPTS[a1]")
                filter_parts.append("[v0][a0][v1][a1]concat=n=2:v=1:a=1[outv][outa]")
                has_out_audio = True
            elif not has_a1 and has_a2:
                filter_parts.append(f"anullsrc=channel_layout=stereo:sample_rate=48000,atrim=duration={dur1_s:.3f},asetpts=PTS-STARTPTS[a0]")
                filter_parts.append("[1:a]aresample=async=1:first_pts=0,aformat=sample_rates=48000:channel_layouts=stereo,asetpts=PTS-STARTPTS[a1]")
                filter_parts.append("[v0][a0][v1][a1]concat=n=2:v=1:a=1[outv][outa]")
                has_out_audio = True
            else:
                filter_parts.append("[v0][v1]concat=n=2:v=1:a=0[outv]")
                has_out_audio = False

            filter_complex_str = ";".join(filter_parts)

            hwaccel_args = []
            if quality.startswith("gpu"):
                hwaccel_args = ["-hwaccel", "cuda"]

            if quality == "gpu_high":
                video_encode_args = ["-c:v", "h264_nvenc", "-preset", "p4", "-rc", "vbr", "-cq", "19", "-b:v", "0"]
            elif quality == "gpu_mid":
                video_encode_args = ["-c:v", "h264_nvenc", "-preset", "p4", "-rc", "vbr", "-cq", "26", "-b:v", "0"]
            elif quality == "cpu_high":
                video_encode_args = ["-c:v", "libx264", "-crf", "18", "-preset", "fast", "-threads", "0"]
            elif quality == "cpu_low":
                video_encode_args = ["-c:v", "libx264", "-crf", "28", "-preset", "fast", "-threads", "0"]
            else:  # cpu_mid
                video_encode_args = ["-c:v", "libx264", "-crf", "23", "-preset", "fast", "-threads", "0"]

            # Tham số tương thích cao tuyệt đối: YUV420p, CFR, Faststart
            compatibility_flags = [
                "-pix_fmt", "yuv420p",
                "-fps_mode", "cfr",
                "-movflags", "+faststart"
            ]

            audio_encode_args = ["-c:a", "aac", "-b:a", "192k", "-ar", "48000"] if has_out_audio else []

            maps = ["-map", "[outv]"]
            if has_out_audio:
                maps += ["-map", "[outa]"]

            cmd = [
                ffmpeg_exe,
                "-y",
            ] + hwaccel_args + [
                "-i", self.video1_path,
                "-i", self.video2_path,
                "-filter_complex", filter_complex_str,
            ] + maps + video_encode_args + compatibility_flags + audio_encode_args + [output_path]

        self.pause()

        self.progress_dialog = QProgressDialog("Đang tiến hành ghép nối 2 video...", "Hủy", 0, 100, self)
        self.progress_dialog.setWindowTitle("Đang Ghép Nối Video")
        self.progress_dialog.setWindowModality(Qt.WindowModality.WindowModal)
        self.progress_dialog.setAutoClose(True)
        self.progress_dialog.setAutoReset(True)

        self.append_btn.setEnabled(False)

        self.export_thread = FFmpegExportThread(cmd, total_duration_ms, cleanup_files=cleanup_files)
        self.export_thread.progress_signal.connect(self.progress_dialog.setValue)
        self.export_thread.finished_signal.connect(lambda s, m: self.on_append_finished(s, m, output_path, mode, quality))
        self.progress_dialog.canceled.connect(self.export_thread.cancel)

        self.progress_dialog.show()
        self.export_thread.start()

    def on_append_finished(self, success, message, output_path, mode="reencode", quality="cpu_mid"):
        self.append_btn.setEnabled(True)
        if success:
            QMessageBox.information(self, "Thành công", f"Đã nối 2 video thành công!\nFile đã lưu tại:\n{output_path}")
        else:
            if os.path.exists(output_path):
                try:
                    os.remove(output_path)
                except Exception as e:
                    print(f"Lỗi dọn file: {e}")

            if message == "Đã hủy.":
                QMessageBox.warning(self, "Đã hủy", "Quá trình ghép nối video đã bị hủy. Hệ thống đã dọn dẹp file tạm.")
            elif mode == "copy":
                # Tự động gợi ý người dùng thử lại bằng chế độ Tương thích cao
                reply = QMessageBox.question(
                    self, "Lỗi ghép siêu tốc",
                    f"Ghép siêu tốc (Stream Copy) thất bại do luồng dữ liệu 2 video không hoàn toàn đồng nhất.\n\n"
                    f"Chi tiết: {message}\n\n"
                    "Bạn có muốn tự động ghép lại bằng chế độ 'Tương thích cao' (Re-encode) để xử lý triệt để không?",
                    QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
                    QMessageBox.StandardButton.Yes
                )
                if reply == QMessageBox.StandardButton.Yes:
                    self.mode_combo.setCurrentIndex(0)  # Tương thích cao
                    self.append_videos(preset_output_path=output_path)
            elif quality.startswith("gpu") and ("nvenc" in message.lower() or "cuda" in message.lower()):
                # Gợi ý chuyển sang CPU nếu máy tính không hỗ trợ card đồ họa NVIDIA
                reply = QMessageBox.question(
                    self, "Lỗi tăng tốc phần cứng GPU",
                    f"Máy tính không thể kích hoạt mã hóa NVIDIA NVENC:\n\n{message}\n\n"
                    "Bạn có muốn tự động chuyển sang chế độ CPU (Chất lượng cao) để tiếp tục không?",
                    QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
                    QMessageBox.StandardButton.Yes
                )
                if reply == QMessageBox.StandardButton.Yes:
                    self.quality_combo.setCurrentIndex(0)  # CPU cao
                    self.append_videos(preset_output_path=output_path)
            else:
                QMessageBox.critical(self, "Lỗi khi nối video", f"Lỗi:\n{message}")


class VideoCutterApp(QMainWindow):
    """Cửa sổ chính ứng dụng Cắt & Nối Video"""
    def __init__(self):
        super().__init__()

        self.setWindowTitle("Video Tool - Cắt & Nối Video (Cut & Append Video)")
        self.setGeometry(100, 100, 1000, 720)

        # Tab Widget
        self.tab_widget = QTabWidget()
        self.setCentralWidget(self.tab_widget)

        # Tab 1: Cắt Video
        self.cut_tab = CutVideoTab(self)
        self.tab_widget.addTab(self.cut_tab, "✂️ Cắt Video")

        # Tab 2: Nối Video
        self.append_tab = AppendVideoTab(self)
        self.tab_widget.addTab(self.append_tab, "🔗 Nối (Append) 2 Video")

        self.tab_widget.currentChanged.connect(self.on_tab_changed)

    def on_tab_changed(self, index):
        # Dừng phát video tab cũ khi chuyển tab
        self.cut_tab.pause()
        self.append_tab.pause()

    def load_video(self, file_name):
        self.cut_tab.load_video(file_name)


if __name__ == "__main__":
    app = QApplication(sys.argv)
    window = VideoCutterApp()

    if len(sys.argv) > 1:
        video_file = sys.argv[1]
        window.load_video(video_file)

    window.show()
    sys.exit(app.exec())
