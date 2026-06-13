from PyQt5.QtWidgets import (QWidget, QVBoxLayout, QHBoxLayout, QLineEdit,
                             QComboBox, QCheckBox, QListWidget, QListWidgetItem,
                             QScrollBar, QAbstractItemView, QFrame, QPushButton,
                             QLabel, QMessageBox)
from PyQt5.QtCore import pyqtSignal
import os
import re
import app.database as db

PDF_REPO = os.path.join(os.path.dirname(os.path.dirname(os.path.dirname(
    os.path.abspath(__file__)))), 'pdf_repo')

DIFFICULTY_STARS = ['', '★', '★★', '★★★', '★★★★', '★★★★★', '★★★★★★', '★★★★★★★', '★★★★★★★★', '★★★★★★★★★']

INITIAL_LOAD = 100
LOAD_MORE = 50
LOAD_THRESHOLD = 50  # trigger load when within this many items of the end


class SongListPanel(QWidget):
    song_selected = pyqtSignal(int)
    multi_select_changed = pyqtSignal(int)  # 选中数量，≤1 表示退出多选

    def __init__(self):
        super().__init__()
        self.songs = []
        self._order_by = 'page'
        self._only_favorites = False
        self._show_deleted = False
        self._volume_filter = None
        self._displayed_count = 0
        self._multi_select_active = False
        self._init_ui()
        self.refresh()

    def _init_ui(self):
        layout = QVBoxLayout(self)
        layout.setContentsMargins(2, 2, 2, 2)
        layout.setSpacing(2)

        self.search_box = QLineEdit()
        self.search_box.setPlaceholderText('搜索曲名...')
        self.search_box.textChanged.connect(self._on_search_changed)
        layout.addWidget(self.search_box)

        self.volume_combo = QComboBox()
        self.volume_combo.currentIndexChanged.connect(self._on_volume_changed)
        layout.addWidget(self.volume_combo)

        top_row = QHBoxLayout()
        self.sort_combo = QComboBox()
        self.sort_combo.addItems(['按页码顺序', '按录入顺序', '难度 ↑', '难度 ↓'])
        self.sort_combo.currentIndexChanged.connect(self._on_sort_changed)
        top_row.addWidget(self.sort_combo)

        self.fav_check = QCheckBox('仅收藏')
        self.fav_check.toggled.connect(self._on_fav_toggled)
        top_row.addWidget(self.fav_check)
        layout.addLayout(top_row)

        self.deleted_check = QCheckBox('被删除')
        self.deleted_check.toggled.connect(self._on_deleted_toggled)
        layout.addWidget(self.deleted_check)

        # --- Batch action bar (hidden until multi-select) ---
        self.batch_bar = QFrame()
        self.batch_bar.setFrameShape(QFrame.StyledPanel)
        batch_layout = QHBoxLayout(self.batch_bar)
        batch_layout.setContentsMargins(4, 2, 4, 2)
        batch_layout.setSpacing(6)

        self.batch_label = QLabel()
        batch_layout.addWidget(self.batch_label)

        self.batch_delete_btn = QPushButton('批量删除')
        self.batch_delete_btn.setStyleSheet(
            'QPushButton { color: red; font-weight: bold; min-height: 28px; }')
        self.batch_delete_btn.clicked.connect(self._on_batch_delete)
        batch_layout.addWidget(self.batch_delete_btn)

        self.batch_restore_btn = QPushButton('批量恢复')
        self.batch_restore_btn.setStyleSheet(
            'QPushButton { color: green; font-weight: bold; min-height: 28px; }')
        self.batch_restore_btn.clicked.connect(self._on_batch_restore)
        batch_layout.addWidget(self.batch_restore_btn)

        self.batch_perm_delete_btn = QPushButton('彻底删除')
        self.batch_perm_delete_btn.setStyleSheet(
            'QPushButton { color: white; background-color: #d32f2f; '
            'font-weight: bold; min-height: 28px; }')
        self.batch_perm_delete_btn.clicked.connect(self._on_batch_permanent_delete)
        batch_layout.addWidget(self.batch_perm_delete_btn)

        self.batch_bar.hide()
        layout.addWidget(self.batch_bar)

        # --- Song list ---
        self.list_widget = QListWidget()
        self.list_widget.setSelectionMode(QAbstractItemView.ExtendedSelection)
        self.list_widget.itemSelectionChanged.connect(self._on_selection_changed)
        self.list_widget.verticalScrollBar().valueChanged.connect(
            self._on_scroll)
        layout.addWidget(self.list_widget)

    # ── filter controls ──────────────────────────────────────────────

    def _set_filter_controls_enabled(self, enabled):
        """Enable/disable search and filter controls."""
        self.search_box.setEnabled(enabled)
        self.volume_combo.setEnabled(enabled)
        self.sort_combo.setEnabled(enabled)
        self.fav_check.setEnabled(enabled)
        self.deleted_check.setEnabled(enabled)

    # ── selection handling ───────────────────────────────────────────

    def _on_selection_changed(self):
        """Handle selection changes: single-select → normal mode,
        multi-select (≥2) → batch mode."""
        selected_ids = self._get_selected_song_ids()
        count = len(selected_ids)

        if count >= 2:
            # Enter multi-select mode
            if not self._multi_select_active:
                self._multi_select_active = True
                self.batch_bar.show()
                self._set_filter_controls_enabled(False)
            self._update_batch_bar(count)
            self.multi_select_changed.emit(count)
        elif count == 1:
            # Single selection → normal mode
            self._exit_multi_select()
            self.song_selected.emit(selected_ids[0])
        else:
            # No selection
            self._exit_multi_select()
            self.multi_select_changed.emit(0)

    def _exit_multi_select(self):
        """Exit multi-select mode, restore controls."""
        if self._multi_select_active:
            self._multi_select_active = False
            self.batch_bar.hide()
            self._set_filter_controls_enabled(True)
            self.multi_select_changed.emit(0)

    def _update_batch_bar(self, count):
        """Update batch bar labels, show/hide buttons based on deleted status."""
        active_ids, deleted_ids = self._get_selected_by_status()
        na, nd = len(active_ids), len(deleted_ids)

        self.batch_label.setText(f'已选 {count} 首:')

        # 批量删除 — only for non-deleted songs
        if na > 0:
            self.batch_delete_btn.setText(f'批量删除 ({na})')
            self.batch_delete_btn.show()
        else:
            self.batch_delete_btn.hide()

        # 批量恢复 — only for deleted songs
        if nd > 0:
            self.batch_restore_btn.setText(f'批量恢复 ({nd})')
            self.batch_restore_btn.show()
        else:
            self.batch_restore_btn.hide()

        # 彻底删除 — always visible during multi-select
        self.batch_perm_delete_btn.setText(f'彻底删除 ({count})')
        self.batch_perm_delete_btn.show()

    def _get_selected_song_ids(self):
        """Return list of song IDs for currently selected items."""
        ids = []
        for item in self.list_widget.selectedItems():
            song_id = item.data(1)
            if song_id is not None:
                ids.append(song_id)
        return ids

    def selected_song_ids(self):
        """Public accessor for selected song IDs."""
        return self._get_selected_song_ids()

    def _get_selected_by_status(self):
        """Return (active_ids, deleted_ids) tuples for current selection."""
        active_ids = []
        deleted_ids = []
        # Build a lookup from self.songs for quick deleted-flag check
        deleted_map = {s['id']: s['deleted'] for s in self.songs}
        for item in self.list_widget.selectedItems():
            song_id = item.data(1)
            if song_id is None:
                continue
            if deleted_map.get(song_id, 0):
                deleted_ids.append(song_id)
            else:
                active_ids.append(song_id)
        return active_ids, deleted_ids

    # ── batch operations ─────────────────────────────────────────────

    def _on_batch_delete(self):
        active_ids, _ = self._get_selected_by_status()
        if not active_ids:
            return
        reply = QMessageBox.question(
            self, '确认删除',
            f'确认将选中的 {len(active_ids)} 首曲目标记为删除？',
            QMessageBox.Yes | QMessageBox.No, QMessageBox.No)
        if reply == QMessageBox.Yes:
            db.batch_update_deleted(active_ids, 1)
            self._after_batch_operation()

    def _on_batch_restore(self):
        _, deleted_ids = self._get_selected_by_status()
        if not deleted_ids:
            return
        reply = QMessageBox.question(
            self, '确认恢复',
            f'确认恢复选中的 {len(deleted_ids)} 首曲目？',
            QMessageBox.Yes | QMessageBox.No, QMessageBox.No)
        if reply == QMessageBox.Yes:
            db.batch_update_deleted(deleted_ids, 0)
            self._after_batch_operation()

    def _on_batch_permanent_delete(self):
        ids = self._get_selected_song_ids()
        if not ids:
            return
        reply = QMessageBox.warning(
            self, '⚠ 彻底删除',
            f'将彻底删除选中的 {len(ids)} 首曲目，此操作不可撤销！',
            QMessageBox.Yes | QMessageBox.No, QMessageBox.No)
        if reply == QMessageBox.Yes:
            db.batch_permanent_delete(ids)
            self._after_batch_operation()

    def _after_batch_operation(self):
        """Refresh list and exit multi-select after batch operation."""
        # Block signals during clearSelection to avoid cascading
        # _on_selection_changed → _exit_multi_select before refresh()
        self.list_widget.blockSignals(True)
        self.list_widget.clearSelection()
        self.list_widget.blockSignals(False)
        # Manually exit multi-select (since signal was blocked)
        if self._multi_select_active:
            self._multi_select_active = False
            self.batch_bar.hide()
            self._set_filter_controls_enabled(True)
            self.multi_select_changed.emit(0)
        self.refresh()

    # ── data loading ─────────────────────────────────────────────────

    def _populate_volume_combo(self):
        current = self.volume_combo.currentText()
        self.volume_combo.blockSignals(True)
        self.volume_combo.clear()
        self.volume_combo.addItem('All')
        if os.path.exists(PDF_REPO):
            for f in sorted(os.listdir(PDF_REPO)):
                if f.endswith('.pdf'):
                    self.volume_combo.addItem(f)
        idx = self.volume_combo.findText(current)
        if idx >= 0:
            self.volume_combo.setCurrentIndex(idx)
        self.volume_combo.blockSignals(False)

    def refresh(self):
        """Reload full song list from DB, reset display to first N."""
        self._populate_volume_combo()
        self.songs = db.get_all_songs(order_by=self._order_by,
                                       only_favorites=self._only_favorites,
                                       show_deleted=self._show_deleted,
                                       volume=self._volume_filter)
        self._displayed_count = 0
        self._append_items(min(INITIAL_LOAD, len(self.songs)))
        self._apply_filter(self.search_box.text())

    def _append_items(self, count):
        """Append up to `count` more items to the list widget."""
        start = self._displayed_count
        end = min(start + count, len(self.songs))
        self.list_widget.blockSignals(True)
        if start == 0:
            self.list_widget.clear()
        if end <= start:
            self.list_widget.blockSignals(False)
            return
        for song in self.songs[start:end]:
            self.list_widget.addItem(self._make_list_item(song))
        self._displayed_count = end
        self.list_widget.blockSignals(False)

    def _compile_search_pattern(self, text):
        """Convert user search text (with optional * wildcards) to a
        case-insensitive compiled regex.  Returns None if text is empty."""
        if not text:
            return None
        # Escape regex metachars except * (our wildcard), then replace *
        escaped = re.escape(text)
        pattern = escaped.replace(r'\*', '.*')
        return re.compile(pattern, re.IGNORECASE)

    def _make_list_item(self, song):
        """Create a QListWidgetItem for a song dict."""
        stars = DIFFICULTY_STARS[min(song['difficulty'], 9)]
        prefix = '[已删] ' if song['deleted'] else ''
        text = f"{prefix}{song['name']}  {stars}"
        item = QListWidgetItem(text)
        item.setData(1, song['id'])
        return item

    def _rebuild_list_from(self, songs, select_id=None):
        """Clear list widget and rebuild from an iterable of song dicts.
        Optionally restore selection to *select_id*."""
        self.list_widget.blockSignals(True)
        self.list_widget.clear()
        first_idx = -1
        for song in songs:
            item = self._make_list_item(song)
            self.list_widget.addItem(item)
            idx = self.list_widget.count() - 1
            if first_idx < 0:
                first_idx = idx
            if select_id is not None and song['id'] == select_id:
                self.list_widget.setCurrentRow(idx)
        if select_id is not None and not self.list_widget.currentItem():
            # select_id not in the rebuilt list — pick first item or clear
            if first_idx >= 0:
                self.list_widget.setCurrentRow(first_idx)
            else:
                self.list_widget.clearSelection()
        self.list_widget.blockSignals(False)

    def _apply_filter(self, text):
        """Rebuild list to show only items matching search text (supports
        * wildcards).  When text is empty, restore the normal lazy-loaded
        view so keyboard navigation is unaffected."""
        pattern = self._compile_search_pattern(text)

        # Remember current selection to restore after rebuild
        current_song_id = None
        current_item = self.list_widget.currentItem()
        if current_item:
            current_song_id = current_item.data(1)

        if pattern is None:
            # No filter active — restore normal view (lazy-loaded subset)
            if self.list_widget.count() != self._displayed_count:
                self._rebuild_list_from(self.songs[:self._displayed_count],
                                        select_id=current_song_id)
            elif current_song_id is not None:
                # Ensure current selection is still visible
                for i in range(self.list_widget.count()):
                    if self.list_widget.item(i).data(1) == current_song_id:
                        self.list_widget.setCurrentRow(i)
                        break
            return

        # Filter active — show ONLY matching items from ALL songs
        matching = []
        for song in self.songs:
            if (pattern.search(song['name']) or
                    pattern.search(song['name_cn']) or
                    pattern.search(song['alias'])):
                matching.append(song)
        self._rebuild_list_from(matching, select_id=current_song_id)

    def _on_scroll(self, value):
        """Check if we're near the bottom — if so, load more items."""
        sb = self.list_widget.verticalScrollBar()
        if sb.maximum() - value < LOAD_THRESHOLD * 20:  # rough pixel estimate
            if self._displayed_count < len(self.songs):
                self._append_items(LOAD_MORE)

    def _on_search_changed(self, text):
        """On search change: if all items are displayed, just filter.
        Otherwise, display all items first, then filter."""
        if self._displayed_count < len(self.songs):
            # Display everything so search can filter across full dataset
            self._append_items(len(self.songs) - self._displayed_count)
        self._apply_filter(text)

    def _on_volume_changed(self, idx):
        if idx <= 0:
            self._volume_filter = None
        else:
            self._volume_filter = self.volume_combo.currentText()
        self.refresh()

    def _on_sort_changed(self, idx):
        mapping = {0: 'page', 1: 'sequence', 2: 'difficulty_asc', 3: 'difficulty_desc'}
        self._order_by = mapping.get(idx, 'sequence')
        self.refresh()

    def _on_fav_toggled(self, checked):
        self._only_favorites = checked
        self.refresh()

    def _on_deleted_toggled(self, checked):
        self._show_deleted = checked
        self.refresh()

    def is_showing_deleted(self):
        return self._show_deleted

    def select_and_focus(self, song_id):
        """Find and select the song by ID, then set focus to the list.
        Load all items first if needed."""
        # Ensure the target song is loaded
        for i, s in enumerate(self.songs):
            if s['id'] == song_id and i >= self._displayed_count:
                self._append_items(i - self._displayed_count + 1)
                break
        for i in range(self.list_widget.count()):
            item = self.list_widget.item(i)
            if item.data(1) == song_id:
                self.list_widget.setCurrentRow(i)
                self.list_widget.setFocus()
                return
