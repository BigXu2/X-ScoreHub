import os
from PyQt5.QtWidgets import (QWidget, QVBoxLayout, QFormLayout, QLineEdit,
                             QSpinBox, QComboBox, QTextEdit, QPushButton,
                             QHBoxLayout, QLabel, QMessageBox)
from PyQt5.QtCore import pyqtSignal, Qt
import app.database as db
from app.utils import resource_path

PDF_REPO = resource_path('pdf_repo')


class SongInfoPanel(QWidget):
    data_saved = pyqtSignal(int)  # emits song_id after save
    page_preview = pyqtSignal(int)
    new_song_requested = pyqtSignal()

    def __init__(self):
        super().__init__()
        self._song_id = None
        self._favorite = False
        self._deleted = False
        self._init_ui()

    def _init_ui(self):
        layout = QVBoxLayout(self)
        layout.setContentsMargins(2, 4, 2, 4)
        layout.setSpacing(2)

        form = QFormLayout()
        form.setSpacing(4)
        form.setHorizontalSpacing(4)
        form.setFieldGrowthPolicy(QFormLayout.AllNonFixedFieldsGrow)

        self.name_edit = QLineEdit()
        form.addRow('曲名', self.name_edit)

        self.name_cn_edit = QLineEdit()
        form.addRow('译名', self.name_cn_edit)

        self.alias_edit = QLineEdit()
        form.addRow('别名', self.alias_edit)

        self.diff_spin = QSpinBox()
        self.diff_spin.setRange(1, 9)
        form.addRow('难度', self.diff_spin)

        self.page_spin = QSpinBox()
        self.page_spin.setRange(1, 9999)
        self.page_spin.valueChanged.connect(self._on_page_spin_changed)

        page_row = QHBoxLayout()
        self.prev_page_btn = QPushButton('◀')
        self.prev_page_btn.setFixedWidth(36)
        self.prev_page_btn.setToolTip('上一页')
        self.prev_page_btn.clicked.connect(self._prev_page)
        page_row.addWidget(self.prev_page_btn)

        page_row.addWidget(self.page_spin)

        self.next_page_btn = QPushButton('▶')
        self.next_page_btn.setFixedWidth(36)
        self.next_page_btn.setToolTip('下一页')
        self.next_page_btn.clicked.connect(self._next_page)
        page_row.addWidget(self.next_page_btn)
        form.addRow('页码', page_row)

        self.pages_spin = QSpinBox()
        self.pages_spin.setRange(1, 99)
        form.addRow('页数', self.pages_spin)

        self.volume_combo = QComboBox()
        self.volume_combo.setEditable(True)
        form.addRow('分册', self.volume_combo)

        layout.addLayout(form)

        layout.addWidget(QLabel('备注:'))
        self.notes_edit = QTextEdit()
        self.notes_edit.setMaximumHeight(120)
        layout.addWidget(self.notes_edit)

        # New + Favorite + Save buttons
        btn_layout = QHBoxLayout()
        self.new_btn = QPushButton('New')
        self.new_btn.setStyleSheet('QPushButton { color: #2196F3; font-weight: bold; }')
        self.new_btn.clicked.connect(self._on_new_clicked)
        btn_layout.addWidget(self.new_btn)

        self.fav_btn = QPushButton('☆ 收藏')
        self.fav_btn.setCheckable(True)
        self.fav_btn.clicked.connect(self._toggle_favorite)
        btn_layout.addWidget(self.fav_btn)

        self.save_btn = QPushButton('保存')
        self.save_btn.setStyleSheet('QPushButton { font-weight: bold; min-height: 28px; }')
        self.save_btn.clicked.connect(self._save)
        btn_layout.addWidget(self.save_btn)
        layout.addLayout(btn_layout)

        # Delete / Restore + Permanent delete
        del_row = QHBoxLayout()
        self.delete_btn = QPushButton('删除')
        self.delete_btn.clicked.connect(self._toggle_deleted)
        del_row.addWidget(self.delete_btn)

        self.perm_delete_btn = QPushButton('彻底删除')
        self.perm_delete_btn.setStyleSheet(
            'QPushButton { color: white; background-color: #d32f2f; '
            'min-height: 24px; font-weight: bold; }')
        self.perm_delete_btn.clicked.connect(self._permanent_delete)
        self.perm_delete_btn.hide()
        del_row.addWidget(self.perm_delete_btn)
        layout.addLayout(del_row)

        # Multi-select overlay hint (hidden normally)
        self.multi_hint = QLabel('已选中多首曲目\n\n使用左侧批量操作按钮\n进行删除/恢复/彻底删除')
        self.multi_hint.setAlignment(Qt.AlignCenter)
        self.multi_hint.setStyleSheet(
            'QLabel { color: #999; font-size: 14px; padding: 40px; }')
        self.multi_hint.hide()
        layout.addWidget(self.multi_hint)

        layout.addStretch()

    def display_song(self, song_id):
        song = db.get_song(song_id)
        if not song:
            self._song_id = None
            return
        self._song_id = song['id']
        self._favorite = bool(song['favorite'])
        self._deleted = bool(song.get('deleted', 0))

        # Populate volume BEFORE page_spin, because page_spin.valueChanged
        # triggers page_preview which reads volume_combo.currentText()
        self._populate_volume(song['volume'])

        self.name_edit.setText(song['name'])
        self.name_cn_edit.setText(song['name_cn'])
        self.alias_edit.setText(song['alias'])
        self.diff_spin.setValue(song['difficulty'] or 1)
        self.pages_spin.setValue(song['pdf_pages'])
        self.notes_edit.setPlainText(song['notes'])

        # Block page_preview during initial load to avoid overriding
        # pdf_pages with 1 (preview_page sets pdf_pages=1)
        self.page_spin.blockSignals(True)
        self.page_spin.setValue(song['pdf_start_page'])
        self.page_spin.blockSignals(False)

        self._update_fav_btn()
        self._update_delete_btn()

    def clear_for_new(self):
        """Clear all fields for creating a new song manually."""
        self._song_id = None
        self._favorite = False
        self._deleted = False
        self.name_edit.clear()
        self.name_cn_edit.clear()
        self.alias_edit.clear()
        self.diff_spin.setValue(3)
        self.page_spin.setValue(1)
        self.pages_spin.setValue(1)
        self.notes_edit.clear()
        self._populate_volume('')
        self._update_fav_btn()
        self._update_delete_btn()

    def _populate_volume(self, current_volume=''):
        self.volume_combo.clear()
        if os.path.exists(PDF_REPO):
            pdf_files = [f for f in os.listdir(PDF_REPO) if f.endswith('.pdf')]
            self.volume_combo.addItems(pdf_files)
        if current_volume:
            idx = self.volume_combo.findText(current_volume)
            if idx >= 0:
                self.volume_combo.setCurrentIndex(idx)
            else:
                self.volume_combo.setEditText(current_volume)

    def _prev_page(self):
        self.page_spin.setValue(self.page_spin.value() - 1)

    def _next_page(self):
        self.page_spin.setValue(self.page_spin.value() + 1)

    def _on_new_clicked(self):
        self.clear_for_new()
        self.new_song_requested.emit()

    def _on_page_spin_changed(self, value):
        # When user changes page number (via buttons or direct edit),
        # emit signal so PDF viewer can preview the page
        self.page_preview.emit(value)

    def _toggle_favorite(self):
        self._favorite = not self._favorite
        self._update_fav_btn()
        # Save immediately for favorite toggle
        if self._song_id:
            song = db.get_song(self._song_id)
            if song:
                song['favorite'] = 1 if self._favorite else 0
                db.update_song(self._song_id, song)
                self.data_saved.emit(self._song_id)

    def _update_fav_btn(self):
        if self._favorite:
            self.fav_btn.setText('★ 已收藏')
            self.fav_btn.setChecked(True)
        else:
            self.fav_btn.setText('☆ 收藏')
            self.fav_btn.setChecked(False)

    def _toggle_deleted(self):
        self._deleted = not self._deleted
        self._update_delete_btn()
        # Save immediately
        if self._song_id:
            song = db.get_song(self._song_id)
            if song:
                song['deleted'] = 1 if self._deleted else 0
                db.update_song(self._song_id, song)
                self.data_saved.emit(self._song_id)

    def _update_delete_btn(self):
        if self._deleted:
            self.delete_btn.setText('恢复')
            self.delete_btn.setStyleSheet('QPushButton { color: green; min-height: 24px; }')
            self.perm_delete_btn.show()
        else:
            self.delete_btn.setText('删除')
            self.delete_btn.setStyleSheet('QPushButton { color: red; min-height: 24px; }')
            self.perm_delete_btn.hide()

    def _permanent_delete(self):
        if not self._song_id or not self._deleted:
            return
        db.delete_song_permanently(self._song_id)
        self._song_id = None
        self.clear_for_new()
        self.data_saved.emit(0)

    def set_disabled(self, disabled):
        """Disable/enable all editing controls during multi-select."""
        self.name_edit.setDisabled(disabled)
        self.name_cn_edit.setDisabled(disabled)
        self.alias_edit.setDisabled(disabled)
        self.diff_spin.setDisabled(disabled)
        self.page_spin.setDisabled(disabled)
        self.prev_page_btn.setDisabled(disabled)
        self.next_page_btn.setDisabled(disabled)
        self.pages_spin.setDisabled(disabled)
        self.volume_combo.setDisabled(disabled)
        self.notes_edit.setDisabled(disabled)
        self.new_btn.setDisabled(disabled)
        self.fav_btn.setDisabled(disabled)
        self.save_btn.setDisabled(disabled)
        self.delete_btn.setDisabled(disabled)
        self.perm_delete_btn.setDisabled(disabled)
        self.multi_hint.setVisible(disabled)

    def _save(self):
        song_data = {
            'name': self.name_edit.text().strip(),
            'name_cn': self.name_cn_edit.text().strip(),
            'alias': self.alias_edit.text().strip(),
            'difficulty': self.diff_spin.value(),
            'pdf_start_page': self.page_spin.value(),
            'pdf_pages': self.pages_spin.value(),
            'volume': self.volume_combo.currentText().strip(),
            'notes': self.notes_edit.toPlainText(),
            'favorite': 1 if self._favorite else 0,
            'deleted': 1 if self._deleted else 0,
        }
        if not song_data['name']:
            QMessageBox.warning(self, '错误', '曲名不能为空。')
            return

        if self._song_id:
            db.update_song(self._song_id, song_data)
        else:
            # New song: auto-assign next sequence number
            existing = db.get_all_songs()
            song_data['sequence'] = max((s['sequence'] for s in existing), default=0) + 1
            db.insert_song(song_data)
            # Get the new ID
            songs = db.get_all_songs()
            if songs:
                self._song_id = songs[-1]['id']
        self.data_saved.emit(self._song_id if self._song_id else 0)
