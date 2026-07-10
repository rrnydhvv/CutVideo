import sys
import os
import re
import subprocess
import imageio_ffmpeg
from PyQt6.QtWidgets import (
    QApplication, QMainWindow, QWidget, QVBoxLayout, QHBoxLayout,
    QPushButton, QFileDialog, QLabel, QSlider, QComboBox, QMessageBox,
    QSizePolicy, QStyle, QProgressDialog, QStyleOptionSlider
)
from PyQt6.QtCore import Qt, QUrl, QTime, QThread, pyqtSignal
from PyQt6.QtMultimedia import QMediaPlayer, QAudioOutput
from PyQt6.QtMultimediaWidgets import QVideoWidget


def format_time(ms):
    """Convert milliseconds to HH:MM:SS format"""
    seconds = (ms // 1000) % 60
    minutes = (ms // 60000) % 60
    hours = (ms // 3600000)
    return f"{hours:02}:{minutes:02}:{seconds:02}"

def format_time_ffmpeg(ms):
    """Convert milliseconds to HH:MM:SS.mmm format for FFmpeg"""
    seconds = (ms // 1000) % 60
    minutes = (ms // 60000) % 60
    hours = (ms // 3600000)
    milliseconds = ms % 1000
    return f"{hours:02}:{minutes:02}:{seconds:02}.{milliseconds:03}"


class ClickableSlider(QSlider):
    def mousePressEvent(self, event):
        if event.button() == Qt.MouseButton.LeftButton:
            opt = QStyleOptionSlider()
            self.initStyleOption(opt)
            sr = self.style().subControlRect(QStyle.ComplexControl.CC_Slider, opt, QStyle.SubControl.SC_SliderHandle, self)
            
            # Bấm trúng tay nắm thì kéo thả bình thường
            if sr.contains(event.pos()):
                super().mousePressEvent(event)
                return
            
            # Tính toán vị trí click chuột trên thanh trượt
            percent = event.pos().x() / self.width()
            val = int(self.minimum() + percent * (self.maximum() - self.minimum()))
            
            # Cập nhật giá trị và trigger tín hiệu
            self.setValue(val)
            self.sliderMoved.emit(val)
            self.sliderReleased.emit()
            return
        super().mousePressEvent(event)


class FFmpegExportThread(QThread):
    progress_signal = pyqtSignal(int)
    finished_signal = pyqtSignal(bool, str)

    def __init__(self, cmd, total_duration_ms):
        super().__init__()
        self.cmd = cmd
        self.total_duration_ms = total_duration_ms
        self.process = None
        self._is_cancelled = False

    def run(self):
        try:
            creationflags = 0
            if sys.platform == "win32":
                creationflags = subprocess.CREATE_NO_WINDOW
                
            self.process = subprocess.Popen(
                self.cmd,
                stdout=subprocess.PIPE,
                stderr=subprocess.STDOUT,
                universal_newlines=True,
                creationflags=creationflags
            )

            time_regex = re.compile(r"time=(\d+):(\d+):(\d+\.\d+)")

            for line in self.process.stdout:
                if self._is_cancelled:
                    self.process.terminate()
                    self.process.wait()  # Chờ tiến trình đóng hẳn để nhả file
                    self.finished_signal.emit(False, "Đã hủy.")
                    return

                match = time_regex.search(line)
                if match:
                    h, m, s = match.groups()
                    current_ms = int(float(h) * 3600000 + float(m) * 60000 + float(s) * 1000)
                    if self.total_duration_ms > 0:
                        progress = int((current_ms / self.total_duration_ms) * 100)
                        self.progress_signal.emit(min(progress, 100))

            self.process.wait()
            
            if self._is_cancelled:
                self.finished_signal.emit(False, "Đã hủy.")
            elif self.process.returncode == 0:
                self.progress_signal.emit(100)
                self.finished_signal.emit(True, "Thành công.")
            else:
                self.finished_signal.emit(False, "Lỗi từ FFmpeg. Vui lòng kiểm tra lại.")
        except Exception as e:
            self.finished_signal.emit(False, str(e))

    def cancel(self):
        self._is_cancelled = True


class VideoCutterApp(QMainWindow):
    def __init__(self):
        super().__init__()

        self.setWindowTitle("Video Cutter App (MP4 Support)")
        self.setGeometry(100, 100, 800, 600)

        self.central_widget = QWidget()
        self.setCentralWidget(self.central_widget)
        self.layout = QVBoxLayout(self.central_widget)

        self.video_widget = QVideoWidget()
        self.layout.addWidget(self.video_widget, stretch=1)

        self.media_player = QMediaPlayer()
        self.audio_output = QAudioOutput()
        self.media_player.setAudioOutput(self.audio_output)
        self.media_player.setVideoOutput(self.video_widget)

        self.controls_layout = QVBoxLayout()
        self.layout.addLayout(self.controls_layout)

        self.top_controls_layout = QHBoxLayout()
        self.controls_layout.addLayout(self.top_controls_layout)

        self.open_btn = QPushButton("Mở Video")
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

        self.slider = ClickableSlider(Qt.Orientation.Horizontal)
        self.slider.setRange(0, 0)
        self.slider.sliderMoved.connect(self.set_position)
        self.slider.sliderReleased.connect(self.slider_released)
        self.controls_layout.addWidget(self.slider)

        self.cutting_controls_layout = QHBoxLayout()
        self.controls_layout.addLayout(self.cutting_controls_layout)

        self.start_btn = QPushButton("Đặt mốc bắt đầu")
        self.start_btn.clicked.connect(self.set_start_marker)
        self.start_btn.setEnabled(False)
        self.cutting_controls_layout.addWidget(self.start_btn)

        self.start_label = QLabel("Start: --:--:--")
        self.cutting_controls_layout.addWidget(self.start_label)

        self.end_btn = QPushButton("Đặt mốc kết thúc")
        self.end_btn.clicked.connect(self.set_end_marker)
        self.end_btn.setEnabled(False)
        self.cutting_controls_layout.addWidget(self.end_btn)

        self.end_label = QLabel("End: --:--:--")
        self.cutting_controls_layout.addWidget(self.end_label)
        
        self.cutting_controls_layout.addStretch()

        self.output_layout = QHBoxLayout()
        self.controls_layout.addLayout(self.output_layout)

        self.quality_label = QLabel("Chất lượng Output:")
        self.output_layout.addWidget(self.quality_label)

        self.quality_combo = QComboBox()
        self.quality_combo.addItem("Gốc (Cực nhanh - Không encode lại)", "-c copy")
        self.quality_combo.addItem("Cao (CPU - Sắc nét)", "-c:v libx264 -crf 18 -preset fast -threads 0")
        self.quality_combo.addItem("Trung bình (CPU - Cân bằng)", "-c:v libx264 -crf 23 -preset fast -threads 0")
        self.quality_combo.addItem("Thấp (CPU - Dung lượng nhỏ)", "-c:v libx264 -crf 28 -preset fast -threads 0")
        self.quality_combo.addItem("Cao (NVIDIA GPU - Siêu tốc)", "-c:v h264_nvenc -preset p4 -rc vbr -cq 19 -b:v 0")
        self.quality_combo.addItem("Trung bình (NVIDIA GPU - Siêu tốc)", "-c:v h264_nvenc -preset p4 -rc vbr -cq 26 -b:v 0")
        self.quality_combo.addItem("Thấp (NVIDIA GPU - Siêu tốc)", "-c:v h264_nvenc -preset p4 -rc vbr -cq 32 -b:v 0")
        self.output_layout.addWidget(self.quality_combo)
        
        self.output_layout.addStretch()

        self.cut_btn = QPushButton("Cắt Video")
        self.cut_btn.setMinimumHeight(40)
        self.cut_btn.setStyleSheet("font-weight: bold; background-color: #4CAF50; color: white;")
        self.cut_btn.clicked.connect(self.cut_video)
        self.cut_btn.setEnabled(False)
        self.output_layout.addWidget(self.cut_btn)

        self.video_path = None
        self.duration_ms = 0
        self.start_ms = 0
        self.end_ms = 0

        self.media_player.positionChanged.connect(self.position_changed)
        self.media_player.durationChanged.connect(self.duration_changed)

    def open_video(self):
        file_name, _ = QFileDialog.getOpenFileName(
            self, "Mở Video", "", "Video Files (*.mp4 *.mkv *.avi *.mov)"
        )
        if file_name:
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
        """Force a frame update when the slider is released while paused."""
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

        # Setup Progress Dialog
        self.progress_dialog = QProgressDialog("Đang xử lý video...", "Hủy", 0, 100, self)
        self.progress_dialog.setWindowTitle("Đang Export")
        self.progress_dialog.setWindowModality(Qt.WindowModality.WindowModal)
        self.progress_dialog.setAutoClose(True)
        self.progress_dialog.setAutoReset(True)
        
        # Disable buttons during export
        self.cut_btn.setEnabled(False)
        self.media_player.pause()
        self.play_btn.setIcon(self.style().standardIcon(QStyle.StandardPixmap.SP_MediaPlay))

        # Start thread
        self.export_thread = FFmpegExportThread(cmd, duration_ms)
        self.export_thread.progress_signal.connect(self.progress_dialog.setValue)
        self.export_thread.finished_signal.connect(lambda s, m: self.on_export_finished(s, m, output_path))
        
        self.progress_dialog.canceled.connect(self.export_thread.cancel)
        
        self.progress_dialog.show()
        self.export_thread.start()

    def on_export_finished(self, success, message, output_path):
        self.cut_btn.setEnabled(True)
        if success:
            QMessageBox.information(self, "Thành công", f"Đã lưu video tại:\n{output_path}")
        else:
            # Xóa file cắt dở nếu bấm Hủy hoặc bị lỗi
            if os.path.exists(output_path):
                try:
                    os.remove(output_path)
                except Exception as e:
                    print(f"Lỗi khi xóa file rác: {e}")

            if message == "Đã hủy.":
                QMessageBox.warning(self, "Đã hủy", "Quá trình export đã bị hủy. Hệ thống đã tự động dọn dẹp file rác.")
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


if __name__ == "__main__":
    app = QApplication(sys.argv)
    window = VideoCutterApp()
    window.show()
    sys.exit(app.exec())
