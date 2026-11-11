from __future__ import annotations

import shutil
import subprocess
import sys
import tempfile
import zipfile
from pathlib import Path

from PySide6.QtCore import Qt
from PySide6.QtGui import QPixmap
from PySide6.QtWidgets import (
    QApplication, QFileDialog, QHBoxLayout, QLabel, QListWidget,
    QListWidgetItem, QMainWindow, QMessageBox, QPushButton, QLineEdit,
    QPlainTextEdit, QSplitter, QVBoxLayout, QWidget
)

TEXT_SUFFIXES = {".xml", ".json", ".txt", ".properties", ".html", ".css", ".js"}
IMAGE_SUFFIXES = {".png", ".jpg", ".jpeg", ".webp", ".gif", ".bmp"}
MAX_TEXT_BYTES = 2 * 1024 * 1024


class ApkEditor(QMainWindow):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("Apkedite | APK Resource Studio")
        self.resize(1280, 820)
        self.apk_path: Path | None = None
        self.work_dir: Path | None = None
        self.current_entry: str | None = None
        self.dirty: dict[str, str] = {}
        self.package_name: str | None = None
        self.last_build_path: Path | None = None
        self.decoded_dir: Path | None = None
        self._build_ui()

    def _build_ui(self):
        root = QWidget()
        outer = QVBoxLayout(root)
        toolbar = QHBoxLayout()
        for label, handler in [
            ("Open APK", self.open_apk),
            ("Save resource", self.save_current),
            ("Rebuild APK", self.rebuild_apk),
            ("Install + launch", self.install_and_launch),
            ("Refresh device screenshot", self.capture_screenshot),
        ]:
            button = QPushButton(label)
            button.clicked.connect(handler)
            toolbar.addWidget(button)
        outer.addLayout(toolbar)
        self.status = QLabel("Open an APK you own or are authorized to modify.")
        outer.addWidget(self.status)

        split = QSplitter(Qt.Horizontal)
        left = QWidget()
        left_layout = QVBoxLayout(left)
        self.search = QLineEdit()
        self.search.setPlaceholderText("Filter files...")
        self.search.textChanged.connect(self.filter_entries)
        left_layout.addWidget(self.search)
        self.file_list = QListWidget()
        self.file_list.currentItemChanged.connect(self.select_entry)
        left_layout.addWidget(self.file_list)
        split.addWidget(left)

        right = QWidget()
        right_layout = QVBoxLayout(right)
        self.preview = QLabel("Select an XML/text or image resource")
        self.preview.setAlignment(Qt.AlignCenter)
        self.preview.setMinimumHeight(220)
        self.preview.setStyleSheet("QLabel { background: #20242b; color: #cbd5e1; border-radius: 8px; }")
        right_layout.addWidget(self.preview, 2)
        self.editor = QPlainTextEdit()
        self.editor.setPlaceholderText("Text/XML resource editor")
        self.editor.textChanged.connect(self.mark_dirty)
        right_layout.addWidget(self.editor, 3)
        split.addWidget(right)
        split.setSizes([360, 920])
        outer.addWidget(split)
        self.setCentralWidget(root)

    def open_apk(self):
        path, _ = QFileDialog.getOpenFileName(self, "Choose APK", "", "Android packages (*.apk)")
        if not path:
            return
        try:
            if self.work_dir:
                shutil.rmtree(self.work_dir, ignore_errors=True)
            self.work_dir = Path(tempfile.mkdtemp(prefix="apkedite_"))
            self.apk_path = Path(path)
            self.dirty.clear()
            self.last_build_path = None
            self.decoded_dir = None
            entries = []
            if shutil.which("apktool"):
                decoded = self.work_dir / "decoded"
                try:
                    subprocess.run(["apktool", "d", "-f", str(self.apk_path), "-o", str(decoded)],
                                   check=True, capture_output=True, text=True)
                    self.decoded_dir = decoded
                    entries = [p.relative_to(decoded).as_posix() for p in decoded.rglob("*") if p.is_file()]
                    self.status.setText("Decoded with Apktool. XML resources are editable source files.")
                except subprocess.CalledProcessError as exc:
                    self.status.setText("Apktool decode failed; showing raw archive (compiled XML is not editable).")
            if not entries:
                with zipfile.ZipFile(path) as archive:
                    bad = archive.testzip()
                    if bad:
                        raise ValueError(f"Archive integrity check failed: {bad}")
                    entries = [n for n in archive.namelist()
                               if not n.endswith("/") and not n.startswith("../") and "/../" not in n]
            self.file_list.clear()
            self.file_list.addItems(sorted(entries))
            self.status.setText(f"{self.apk_path.name} | {len(entries)} entries" +
                                (" | decoded workspace" if self.decoded_dir else " | raw archive view"))
            self.editor.clear()
            self.preview.setText("Select a resource to preview")
        except Exception as exc:
            QMessageBox.critical(self, "Cannot open APK", str(exc))

    def filter_entries(self, query: str):
        q = query.lower().strip()
        for i in range(self.file_list.count()):
            item = self.file_list.item(i)
            item.setHidden(q not in item.text().lower())

    def select_entry(self, current: QListWidgetItem, _previous: QListWidgetItem):
        if not current or not self.apk_path:
            return
        name = current.text()
        self.current_entry = name
        try:
            source = (self.decoded_dir / name) if self.decoded_dir else None
            if source and source.is_file():
                data = source.read_bytes()
            else:
                with zipfile.ZipFile(self.apk_path) as archive:
                    data = archive.read(name)
            suffix = Path(name).suffix.lower()
            if suffix in IMAGE_SUFFIXES:
                pix = QPixmap()
                pix.loadFromData(data)
                self.preview.setPixmap(pix.scaled(self.preview.size(), Qt.KeepAspectRatio, Qt.SmoothTransformation))
                self.editor.setReadOnly(True)
                self.editor.setPlainText("Image asset selected. Image replacement is planned for the next milestone.")
            elif suffix in TEXT_SUFFIXES and len(data) <= MAX_TEXT_BYTES:
                self.preview.setText(f"Text resource | {len(data):,} bytes")
                self.editor.setReadOnly(False)
                self.editor.setPlainText(self.dirty.get(name, data.decode("utf-8", errors="replace")))
            else:
                self.preview.setText(f"Binary resource | {len(data):,} bytes")
                self.editor.setReadOnly(True)
                note = "Install Apktool to decode compiled Android XML before editing." if suffix == ".xml" and not self.decoded_dir else "This file is not an editable text resource in this milestone."
                self.editor.setPlainText(note)
        except Exception as exc:
            QMessageBox.warning(self, "Read failed", str(exc))

    def mark_dirty(self):
        if self.current_entry and not self.editor.isReadOnly():
            self.status.setText(f"Unsaved edit: {self.current_entry}")

    def save_current(self):
        if self.current_entry and not self.editor.isReadOnly():
            self.dirty[self.current_entry] = self.editor.toPlainText()
            self.status.setText(f"Saved in workspace | {len(self.dirty)} changed resource(s)")

    def rebuild_apk(self):
        if not self.apk_path:
            QMessageBox.information(self, "Open APK first", "Choose an APK before rebuilding.")
            return
        self.save_current()
        if not shutil.which("apktool"):
            QMessageBox.warning(self, "Apktool not found", "Install Apktool and add it to PATH: https://apktool.org/")
            return
        try:
            out_dir = self.decoded_dir or (self.work_dir / "decoded")
            if self.decoded_dir is None:
                subprocess.run(["apktool", "d", "-f", str(self.apk_path), "-o", str(out_dir)],
                               check=True, capture_output=True, text=True)
                self.decoded_dir = out_dir
            for relative, content in self.dirty.items():
                target = (out_dir / relative).resolve()
                if out_dir.resolve() not in target.parents:
                    raise ValueError("Unsafe resource path")
                target.parent.mkdir(parents=True, exist_ok=True)
                target.write_text(content, encoding="utf-8")
            output, _ = QFileDialog.getSaveFileName(
                self, "Save rebuilt APK",
                str(self.apk_path.with_name(self.apk_path.stem + "-edited-unsigned.apk")),
                "APK (*.apk)")
            if not output:
                return
            subprocess.run(["apktool", "b", str(out_dir), "-o", output],
                           check=True, capture_output=True, text=True)
            self.last_build_path = Path(output)
            manifest = out_dir / "AndroidManifest.xml"
            if manifest.exists():
                import re
                match = re.search(r'package="([^"]+)"', manifest.read_text(encoding="utf-8", errors="ignore"))
                self.package_name = match.group(1) if match else None
            QMessageBox.information(self, "Build complete",
                                    f"Unsigned APK created:\n{output}\n\nSign it with Android SDK apksigner before installation.")
            self.status.setText(f"Build complete: {output}")
        except subprocess.CalledProcessError as exc:
            QMessageBox.critical(self, "Build failed", (exc.stderr or exc.stdout or str(exc))[-5000:])
        except Exception as exc:
            QMessageBox.critical(self, "Build failed", str(exc))

    def adb(self, *args: str):
        if not shutil.which("adb"):
            raise RuntimeError("ADB not found. Install Android SDK Platform Tools.")
        return subprocess.run(["adb", *args], capture_output=True, text=True, check=True)

    def install_and_launch(self):
        if not self.apk_path:
            return
        candidate = self.apk_path
        if self.last_build_path and self.last_build_path.exists():
            selected, _ = QFileDialog.getOpenFileName(
                self, "Choose signed APK to install",
                str(self.last_build_path.parent), "Android packages (*.apk)")
            if not selected:
                return
            candidate = Path(selected)
        confirm = QMessageBox.question(
            self, "Install test APK",
            f"Install {candidate.name} on the connected test device? Continue only if you are authorized to modify it.")
        if confirm != QMessageBox.Yes:
            return
        try:
            self.adb("install", "-r", str(candidate))
            if self.package_name:
                self.adb("shell", "monkey", "-p", self.package_name,
                         "-c", "android.intent.category.LAUNCHER", "1")
                self.status.setText(f"Installed and launched {self.package_name}")
                self.capture_screenshot()
            else:
                QMessageBox.information(self, "Installed",
                                        "APK installed. Open it manually on the connected test device, then refresh the screenshot.")
                self.status.setText("APK installed on connected device")
        except Exception as exc:
            QMessageBox.warning(self, "ADB action", str(exc))

    def capture_screenshot(self):
        try:
            if not shutil.which("adb"):
                raise RuntimeError("ADB not found.")
            result = subprocess.run(["adb", "exec-out", "screencap", "-p"], capture_output=True, check=True)
            pix = QPixmap()
            pix.loadFromData(result.stdout)
            if pix.isNull():
                raise RuntimeError("No screenshot returned. Check the connected emulator/device.")
            self.preview.setPixmap(pix.scaled(self.preview.size(), Qt.KeepAspectRatio, Qt.SmoothTransformation))
            self.status.setText("Device screenshot refreshed")
        except Exception as exc:
            QMessageBox.warning(self, "Screenshot unavailable", str(exc))


if __name__ == "__main__":
    app = QApplication(sys.argv)
    window = ApkEditor()
    window.show()
    sys.exit(app.exec())
