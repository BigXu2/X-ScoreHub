import os
from PyQt5.QtWidgets import (QMainWindow, QSplitter, QMenuBar, QAction,
                             QFileDialog, QMessageBox, QLineEdit, QTextEdit,
                             QSpinBox, QAbstractSpinBox, QShortcut)
from PyQt5.QtCore import Qt, QTimer
from PyQt5.QtGui import QKeySequence
from app.widgets.song_list import SongListPanel
from app.widgets.pdf_viewer import PdfViewerPanel
from app.widgets.song_info import SongInfoPanel
import app.database as db
from app.importers import import_from_file
from app.exporters import export_to_markdown


class MainWindow(QMainWindow):
    def __init__(self):
        super().__init__()
        self.setWindowTitle('X-ScoreHub - 乐谱浏览器')
        self.resize(1400, 900)
        self._selected_count = 0
        self._setup_menu()
        self._setup_ui()

    def _setup_menu(self):
        menubar = self.menuBar()

        file_menu = menubar.addMenu('文件')
        self.new_action = QAction('新增曲目', self)
        self.new_action.setShortcut('Ctrl+N')
        self.new_action.triggered.connect(self._new_song)
        file_menu.addAction(self.new_action)

        self.import_action = QAction('导入 Markdown...', self)
        self.import_action.triggered.connect(self._import_markdown)
        file_menu.addAction(self.import_action)

        self.export_action = QAction('导出 Markdown...', self)
        self.export_action.setShortcut('Ctrl+E')
        self.export_action.setEnabled(False)
        self.export_action.triggered.connect(self._export_markdown)
        file_menu.addAction(self.export_action)

        file_menu.addSeparator()
        exit_action = QAction('退出', self)
        exit_action.triggered.connect(self.close)
        file_menu.addAction(exit_action)

    def _setup_ui(self):
        self.splitter = QSplitter(Qt.Horizontal)
        self.splitter.setChildrenCollapsible(False)

        # Left panel: song list
        self.song_list = SongListPanel()
        self.song_list.setMinimumWidth(150)
        self.splitter.addWidget(self.song_list)

        # Center panel: PDF viewer — takes all remaining space
        self.pdf_viewer = PdfViewerPanel()
        self.splitter.addWidget(self.pdf_viewer)

        # Right panel: song info editor
        self.song_info = SongInfoPanel()
        self.song_info.setMinimumWidth(140)
        self.splitter.addWidget(self.song_info)

        self.splitter.setStretchFactor(1, 1)
        self.setCentralWidget(self.splitter)

        # Connect signals
        self.song_list.song_selected.connect(self._on_song_selected)
        self.song_list.multi_select_changed.connect(self._on_multi_select_changed)
        self.song_info.data_saved.connect(self._on_data_saved)
        self.song_info.page_preview.connect(self._on_page_preview)
        self.song_info.new_song_requested.connect(self._on_new_requested)

        # Select first song on startup
        if self.song_list.songs:
            self.song_list.list_widget.setCurrentRow(0)

        # Enforce initial splitter sizes after layout settles
        QTimer.singleShot(0, lambda: self.splitter.setSizes([340, 1000, 340]))

        # Global shortcut: Ctrl+Cmd+F toggles fullscreen score display
        self._fullscreen_shortcut = QShortcut(
            QKeySequence(Qt.ControlModifier | Qt.MetaModifier | Qt.Key_F), self)
        self._fullscreen_shortcut.activated.connect(self._toggle_fullscreen)

    def _on_song_selected(self, song_id):
        self.pdf_viewer.display_song(song_id)
        self.song_info.display_song(song_id)
        self._update_selection_count(1)

    def _on_multi_select_changed(self, count):
        """Handle multi-select mode changes."""
        self._update_selection_count(count)
        if count >= 2:
            self.song_info.set_disabled(True)
            self.pdf_viewer.setDisabled(True)
            self.new_action.setDisabled(True)
            self.import_action.setDisabled(True)
        else:
            self.song_info.set_disabled(False)
            self.pdf_viewer.setDisabled(False)
            self.new_action.setDisabled(False)
            self.import_action.setDisabled(False)

    def _update_selection_count(self, count):
        """Enable export action when songs are selected."""
        self._selected_count = count
        self.export_action.setEnabled(count > 0)

    def _on_page_preview(self, page_number):
        """Preview a specific page from the current volume without changing song selection."""
        volume = self.song_info.volume_combo.currentText()
        if volume:
            self.pdf_viewer.preview_page(volume, page_number)

    def _on_data_saved(self, song_id):
        self.song_list.refresh()
        if song_id:
            self.song_list.select_and_focus(song_id)

    def _on_new_requested(self):
        self.pdf_viewer.canvas.clear_page()
        self.pdf_viewer.page_label.setText('')
        self.song_list.list_widget.clearSelection()

    def _new_song(self):
        self.song_info.clear_for_new()
        self._on_new_requested()

    def _import_markdown(self):
        filepath, _ = QFileDialog.getOpenFileName(
            self, '选择 Markdown 文件', '', 'Markdown 文件 (*.md)')
        if filepath:
            try:
                count = import_from_file(filepath, db)
                self.song_list.refresh()
                self.pdf_viewer.clear_cache()
                if self.song_list.songs:
                    self.song_list.list_widget.setCurrentRow(0)
                QMessageBox.information(self, '导入成功', f'导入了 {count} 首曲目。')
            except Exception as e:
                QMessageBox.warning(self, '导入失败', str(e))

    def _export_markdown(self):
        ids = self.song_list.selected_song_ids()
        if not ids:
            QMessageBox.information(self, '提示', '请先在左侧列表中选中要导出的曲目。')
            return
        filepath, _ = QFileDialog.getSaveFileName(
            self, '导出 Markdown', '', 'Markdown 文件 (*.md)')
        if filepath:
            try:
                export_to_markdown(filepath, ids, db)
                QMessageBox.information(
                    self, '导出成功', f'已导出 {len(ids)} 首曲目到:\n{filepath}')
            except Exception as e:
                QMessageBox.warning(self, '导出失败', str(e))

    def _toggle_fullscreen(self):
        """Toggle between normal three-panel layout and fullscreen score view.

        In fullscreen mode the song list and info panels are hidden,
        and the PDF viewer shows two pages side-by-side.
        """
        is_fullscreen = self.pdf_viewer._fullscreen
        if not is_fullscreen:
            # ── enter fullscreen ────────────────────────────────
            self.song_list.hide()
            self.song_info.hide()
            # Hide splitter handles between the 3 panels
            for i in range(1, self.splitter.count()):
                self.splitter.handle(i).hide()
            self.pdf_viewer.set_fullscreen(True)
        else:
            # ── exit fullscreen ─────────────────────────────────
            self.pdf_viewer.set_fullscreen(False)
            self.song_list.show()
            self.song_info.show()
            for i in range(1, self.splitter.count()):
                self.splitter.handle(i).show()

    def keyPressEvent(self, event):
        key = event.key()
        if key in (Qt.Key_Left, Qt.Key_Right):
            fw = self.focusWidget()
            if isinstance(fw, (QLineEdit, QTextEdit, QAbstractSpinBox)):
                super().keyPressEvent(event)
                return
            if key == Qt.Key_Left:
                self.pdf_viewer._prev_page()
            else:
                self.pdf_viewer._next_page()
        else:
            super().keyPressEvent(event)

    def closeEvent(self, event):
        self.pdf_viewer.clear_cache()
        event.accept()
