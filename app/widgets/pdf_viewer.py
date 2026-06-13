import os
import math
import fitz
from PyQt5.QtWidgets import (QWidget, QVBoxLayout, QHBoxLayout,
                             QPushButton, QLabel, QStackedWidget)
from PyQt5.QtCore import Qt, QPointF, QRectF, pyqtSignal, QEvent, QDateTime
from PyQt5.QtGui import (QPixmap, QImage, QPainter, QMouseEvent,
                         QWheelEvent, QCursor, QNativeGestureEvent)
from PyQt5.QtWidgets import QGestureEvent, QPinchGesture

PDF_REPO = os.path.join(os.path.dirname(os.path.dirname(os.path.dirname(
    os.path.abspath(__file__)))), 'pdf_repo')

RENDER_DPI = 200
MIN_ZOOM = 1.0
MAX_ZOOM = 8.0
ZOOM_STEP = 0.12
PINCH_SENSITIVITY = 1.5    # amplify accumulated deltas (accum reaches ~1-2)
_REBUILD_INTERVAL_MS = 33  # throttle display rebuilds during pinch (~30 fps)


class ScoreCanvas(QWidget):
    """A zoomable, pannable score display widget."""

    def __init__(self, parent=None):
        super().__init__(parent)
        self._full_pixmap = None   # high-DPI source pixmap
        self._display_pixmap = None  # scaled for current zoom
        self._zoom = MIN_ZOOM
        self._offset = QPointF(0, 0)  # pan offset in image pixels at zoom 1.0
        self._dragging = False
        self._drag_start = QPointF(0, 0)
        self._offset_start = QPointF(0, 0)
        self._pinch_base_zoom = MIN_ZOOM  # zoom level at pinch start
        self._pinch_active = False
        self._last_rebuild_ms = 0
        self._last_gesture_ms = 0
        self.setMouseTracking(True)
        self.setCursor(Qt.OpenHandCursor)
        self.setStyleSheet('background-color: #e0e0e0; border: none;')
        self.setMinimumSize(200, 200)
        self.setAttribute(Qt.WA_AcceptTouchEvents, True)
        self.grabGesture(Qt.PinchGesture)

    def event(self, event):
        if event.type() == QEvent.Gesture:
            for gesture in event.gestures():
                if isinstance(gesture, QPinchGesture):
                    self._handle_pinch(gesture)
            return True
        return super().event(event)

    def _handle_native_gesture(self, event, anchor_pos=None):
        if not self._full_pixmap:
            return
        # Dedup: macOS may deliver same gesture to multiple NSViews
        now = QDateTime.currentMSecsSinceEpoch()
        if now - self._last_gesture_ms < 2:
            return
        self._last_gesture_ms = now
        gt = event.gestureType()
        if gt == Qt.BeginNativeGesture:
            if anchor_pos is None:
                anchor_pos = (event.posF() if hasattr(event, 'posF')
                              else QPointF(event.pos()))
            self._pinch_anchor = anchor_pos
            self._pinch_base_zoom = self._zoom
            self._pinch_accum = 0.0
            self._pinch_smooth = 0.0
            self._pinch_active = True
        elif gt == Qt.ZoomNativeGesture:
            self._pinch_accum += event.value()
            self._pinch_smooth = self._pinch_smooth * 0.70 + self._pinch_accum * 0.30
            v = self._pinch_smooth * PINCH_SENSITIVITY
            scale = math.pow(2.0, v)
            new_zoom = max(MIN_ZOOM, min(MAX_ZOOM,
                           self._pinch_base_zoom * scale))
            self._apply_zoom_at_point(new_zoom, self._pinch_anchor)
        elif gt == Qt.EndNativeGesture:
            self._pinch_active = False
            self._rebuild_display(force=True)
            self.update()

    def _handle_pinch(self, gesture):
        """Apply pinch-to-zoom from a QPinchGesture (touchscreen / cross-platform fallback)."""
        if not self._full_pixmap:
            return
        if gesture.state() == Qt.GestureStarted:
            self._pinch_base_zoom = self._zoom
            self._pinch_active = True
        elif gesture.state() == Qt.GestureUpdated and self._pinch_active:
            scale = gesture.scaleFactor()
            new_zoom = max(MIN_ZOOM, min(MAX_ZOOM, self._pinch_base_zoom * scale))
            center = gesture.centerPoint()
            self._apply_zoom_at_point(new_zoom, QPointF(center.x(), center.y()))
        elif gesture.state() in (Qt.GestureFinished, Qt.GestureCanceled):
            self._pinch_active = False
            self._rebuild_display(force=True)
            self.update()
            if self._zoom <= MIN_ZOOM + 0.001:
                self._offset = QPointF(0, 0)

    def _apply_zoom_at_point(self, new_zoom, widget_pos: QPointF):
        """Zoom to *new_zoom*, keeping *widget_pos* stationary on screen."""
        old_zoom = self._zoom
        if new_zoom == old_zoom:
            return
        self._zoom = new_zoom
        ratio = new_zoom / old_zoom
        center = QPointF(self.width() / 2.0, self.height() / 2.0)
        rel = widget_pos - center
        self._offset = self._offset * ratio + rel * (1.0 - ratio)
        self._clamp_offset()
        self._rebuild_display()
        self.update()

    def set_page(self, full_pixmap):
        """Set a new high-DPI pixmap, reset zoom/pan to fit."""
        self._full_pixmap = full_pixmap
        self._zoom = MIN_ZOOM
        self._offset = QPointF(0, 0)
        self._rebuild_display()
        self.update()

    def clear_page(self):
        self._full_pixmap = None
        self._display_pixmap = None
        self.update()

    def _base_size(self):
        """Size of the pixmap at zoom=1.0 (fit-to-widget)."""
        if not self._full_pixmap:
            return 0, 0
        pw = self._full_pixmap.width()
        ph = self._full_pixmap.height()
        ww = self.width()
        wh = self.height()
        if ww < 10 or wh < 10:
            return pw, ph
        scale = min(ww / pw, wh / ph)
        return int(pw * scale), int(ph * scale)

    def _rebuild_display(self, force=False):
        """Rebuild _display_pixmap at current zoom level.

        During an active pinch gesture, the method is throttled to
        avoid stuttering from expensive 200 DPI SmoothTransformation,
        and uses FastTransformation for speed.  A final high-quality
        rebuild is forced when the gesture ends (force=True).
        """
        if not self._full_pixmap:
            self._display_pixmap = None
            return

        # ── throttle during active pinch ──
        now = QDateTime.currentMSecsSinceEpoch()
        if self._pinch_active and not force:
            if now - self._last_rebuild_ms < _REBUILD_INTERVAL_MS:
                return

        bw, bh = self._base_size()
        tw = int(bw * self._zoom)
        th = int(bh * self._zoom)
        if tw < 1 or th < 1:
            self._display_pixmap = None
            return

        # Fast (bilinear) during pinch, smooth (bicubic) otherwise
        mode = Qt.FastTransformation if (self._pinch_active and not force) \
               else Qt.SmoothTransformation
        self._display_pixmap = self._full_pixmap.scaled(
            tw, th, Qt.KeepAspectRatio, mode)
        self._last_rebuild_ms = now

    def _image_pos_at(self, widget_pos):
        """Convert widget coordinate to image coordinate (zoom=1.0 space)."""
        bw, bh = self._base_size()
        if bw < 1 or bh < 1:
            return QPointF(0, 0)
        # Center of base image in widget
        cx = (self.width() - bw) / 2.0 + self._offset.x()
        cy = (self.height() - bh) / 2.0 + self._offset.y()
        return QPointF(widget_pos.x() - cx, widget_pos.y() - cy)

    def wheelEvent(self, event: QWheelEvent):
        # Ignore wheel while pinch is active — macOS sends both
        # NativeGesture and Wheel events during trackpad pinch.
        if self._pinch_active:
            return
        if not self._full_pixmap:
            return
        pos = event.posF() if hasattr(event, 'posF') else QPointF(event.pos())
        delta = event.angleDelta().y()
        if delta > 0:
            new_zoom = min(MAX_ZOOM, self._zoom + ZOOM_STEP)
        elif delta < 0:
            new_zoom = max(MIN_ZOOM, self._zoom - ZOOM_STEP)
        else:
            return
        self._apply_zoom_at_point(new_zoom, pos)
        if self._zoom <= MIN_ZOOM + 0.001:
            self._offset = QPointF(0, 0)

    def mousePressEvent(self, event: QMouseEvent):
        if event.button() == Qt.LeftButton and self._zoom > MIN_ZOOM + 0.001:
            self._dragging = True
            self._drag_start = QPointF(event.pos())
            self._offset_start = QPointF(self._offset)
            self.setCursor(Qt.ClosedHandCursor)
            event.accept()
        else:
            super().mousePressEvent(event)

    def mouseMoveEvent(self, event: QMouseEvent):
        if self._dragging:
            delta = QPointF(event.pos()) - self._drag_start
            self._offset = self._offset_start + delta
            self._clamp_offset()
            self.update()
            event.accept()
        else:
            super().mouseMoveEvent(event)

    def mouseReleaseEvent(self, event: QMouseEvent):
        if self._dragging and event.button() == Qt.LeftButton:
            self._dragging = False
            self.setCursor(Qt.OpenHandCursor if self._zoom > MIN_ZOOM + 0.001
                           else Qt.ArrowCursor)
            event.accept()
        else:
            super().mouseReleaseEvent(event)

    def _clamp_offset(self):
        """Prevent the image from drifting completely off-screen."""
        if not self._display_pixmap:
            return
        bw, bh = self._base_size()
        dw = self._display_pixmap.width()
        dh = self._display_pixmap.height()
        # Allow panning until at least some of the image is still visible
        margin = 100
        max_x = (dw + self.width()) / 2.0 + margin
        max_y = (dh + self.height()) / 2.0 + margin
        self._offset.setX(max(-max_x, min(max_x, self._offset.x())))
        self._offset.setY(max(-max_y, min(max_y, self._offset.y())))

    def paintEvent(self, event):
        painter = QPainter(self)
        painter.fillRect(self.rect(), Qt.lightGray)
        if not self._display_pixmap:
            painter.end()
            return

        bw, bh = self._base_size()
        cx = (self.width() - bw) / 2.0 + self._offset.x()
        cy = (self.height() - bh) / 2.0 + self._offset.y()

        # Scale the display pixmap around its center
        scale = self._zoom
        dw = self._display_pixmap.width()
        dh = self._display_pixmap.height()
        sx = cx + (bw - dw) / 2.0
        sy = cy + (bh - dh) / 2.0

        painter.drawPixmap(int(sx), int(sy), self._display_pixmap)
        painter.end()


class DualScoreCanvas(QWidget):
    """Zoomable, pannable dual-page score display.

    Displays two pages side-by-side with a gap. Zoom and pan are
    synchronized — both pages scale together and move as one unit.
    Falls back to centered single-page display when only one page
    is provided.
    """

    GAP = 40  # gap in full-resolution equivalent pixels (~0.2 inch @200DPI)

    def __init__(self, parent=None):
        super().__init__(parent)
        self._full_left = None
        self._full_right = None
        self._display_left = None
        self._display_right = None
        self._display_gap = 0
        self._zoom = MIN_ZOOM
        self._offset = QPointF(0, 0)
        self._dragging = False
        self._drag_start = QPointF(0, 0)
        self._offset_start = QPointF(0, 0)
        self._pinch_base_zoom = MIN_ZOOM
        self._pinch_active = False
        self._single_page = True
        self._last_rebuild_ms = 0
        self._last_gesture_ms = 0
        self.setMouseTracking(True)
        self.setCursor(Qt.OpenHandCursor)
        self.setStyleSheet('background-color: #e0e0e0; border: none;')
        self.setMinimumSize(200, 200)
        # Required on macOS for native touch events → Qt gestures
        self.setAttribute(Qt.WA_AcceptTouchEvents, True)
        self.grabGesture(Qt.PinchGesture)

    def event(self, event):
        if event.type() == QEvent.Gesture:
            for gesture in event.gestures():
                if isinstance(gesture, QPinchGesture):
                    self._handle_pinch(gesture)
            return True
        return super().event(event)

    def _handle_native_gesture(self, event, anchor_pos=None):
        if not self._full_left:
            return
        now = QDateTime.currentMSecsSinceEpoch()
        if now - self._last_gesture_ms < 2:
            return
        self._last_gesture_ms = now
        gt = event.gestureType()
        if gt == Qt.BeginNativeGesture:
            if anchor_pos is None:
                anchor_pos = (event.posF() if hasattr(event, 'posF')
                              else QPointF(event.pos()))
            self._pinch_anchor = anchor_pos
            self._pinch_base_zoom = self._zoom
            self._pinch_accum = 0.0
            self._pinch_smooth = 0.0
            self._pinch_active = True
        elif gt == Qt.ZoomNativeGesture:
            self._pinch_accum += event.value()
            self._pinch_smooth = self._pinch_smooth * 0.70 + self._pinch_accum * 0.30
            v = self._pinch_smooth * PINCH_SENSITIVITY
            scale = math.pow(2.0, v)
            new_zoom = max(MIN_ZOOM, min(MAX_ZOOM,
                           self._pinch_base_zoom * scale))
            self._apply_zoom_at_point(new_zoom, self._pinch_anchor)
        elif gt == Qt.EndNativeGesture:
            self._pinch_active = False
            self._rebuild_display(force=True)
            self.update()

    def _handle_pinch(self, gesture):
        """Apply pinch-to-zoom from a QPinchGesture (touchscreen fallback)."""
        if not self._full_left:
            return
        if gesture.state() == Qt.GestureStarted:
            self._pinch_base_zoom = self._zoom
            self._pinch_active = True
        elif gesture.state() == Qt.GestureUpdated and self._pinch_active:
            scale = gesture.scaleFactor()
            new_zoom = max(MIN_ZOOM, min(MAX_ZOOM, self._pinch_base_zoom * scale))
            center = gesture.centerPoint()
            self._apply_zoom_at_point(new_zoom, QPointF(center.x(), center.y()))
        elif gesture.state() in (Qt.GestureFinished, Qt.GestureCanceled):
            self._pinch_active = False
            self._rebuild_display(force=True)
            self.update()
            if self._zoom <= MIN_ZOOM + 0.001:
                self._offset = QPointF(0, 0)

    def _apply_zoom_at_point(self, new_zoom, widget_pos: QPointF):
        """Zoom to *new_zoom*, keeping *widget_pos* stationary on screen."""
        old_zoom = self._zoom
        if new_zoom == old_zoom:
            return
        self._zoom = new_zoom
        ratio = new_zoom / old_zoom
        center = QPointF(self.width() / 2.0, self.height() / 2.0)
        rel = widget_pos - center
        self._offset = self._offset * ratio + rel * (1.0 - ratio)
        self._clamp_offset()
        self._rebuild_display()
        self.update()

    def set_page(self, left_pixmap, right_pixmap=None):
        """Set pages for display.

        Args:
            left_pixmap: QPixmap for the left page.
            right_pixmap: QPixmap for the right page. If None,
                renders a single centered page.
        """
        self._full_left = left_pixmap
        self._full_right = right_pixmap
        self._single_page = (right_pixmap is None)
        self._zoom = MIN_ZOOM
        self._offset = QPointF(0, 0)
        self._rebuild_display()
        self.update()

    def clear_page(self):
        self._full_left = None
        self._full_right = None
        self._display_left = None
        self._display_right = None
        self.update()

    # ── layout math ──────────────────────────────────────────────────

    def _base_size(self):
        """Fit-to-widget size for a single page at zoom=1.0.

        In dual-page mode the scale accounts for both pages plus gap,
        so the full spread fits the widget at zoom=1.0.
        """
        if not self._full_left:
            return 0, 0
        pw = self._full_left.width()
        ph = self._full_left.height()
        ww = self.width()
        wh = self.height()
        if ww < 10 or wh < 10:
            return pw, ph

        if self._single_page:
            scale = min(ww / pw, wh / ph)
        else:
            pw_r = self._full_right.width()
            ph_r = self._full_right.height()
            total_pw = pw + pw_r + self.GAP
            max_ph = max(ph, ph_r)
            scale = min(ww / total_pw, wh / max_ph)

        return int(pw * scale), int(ph * scale)

    def _rebuild_display(self, force=False):
        """Rebuild display pixmaps at current zoom level.

        During pinch: throttled (max ~33 fps) + FastTransformation.
        Gesture end (force=True): final SmoothTransformation render.
        """
        if not self._full_left:
            self._display_left = None
            self._display_right = None
            return

        now = QDateTime.currentMSecsSinceEpoch()
        if self._pinch_active and not force:
            if now - self._last_rebuild_ms < _REBUILD_INTERVAL_MS:
                return

        bw, bh = self._base_size()
        zoom = self._zoom
        tw = int(bw * zoom)
        th = int(bh * zoom)
        if tw < 1 or th < 1:
            self._display_left = None
            self._display_right = None
            return

        mode = Qt.FastTransformation if (self._pinch_active and not force) \
               else Qt.SmoothTransformation

        self._display_left = self._full_left.scaled(
            tw, th, Qt.KeepAspectRatio, mode)

        if self._full_right and not self._single_page:
            scale = zoom * (bw / self._full_left.width())
            tw_r = int(self._full_right.width() * scale)
            th_r = int(self._full_right.height() * scale)
            self._display_right = self._full_right.scaled(
                tw_r, th_r, Qt.KeepAspectRatio, mode)
            self._display_gap = int(self.GAP * scale)
        else:
            self._display_right = None
            self._display_gap = 0

        self._last_rebuild_ms = now

    def _total_display_size(self):
        """Return (width, height) of the rendered spread in display pixels."""
        if not self._display_left:
            return 0, 0
        w = self._display_left.width()
        h = self._display_left.height()
        if self._display_right:
            w += self._display_gap + self._display_right.width()
            h = max(h, self._display_right.height())
        return w, h

    # ── painting ─────────────────────────────────────────────────────

    def paintEvent(self, event):
        painter = QPainter(self)
        painter.fillRect(self.rect(), Qt.lightGray)

        if not self._display_left:
            painter.end()
            return

        tdw, tdh = self._total_display_size()

        # Center the spread in widget, apply pan offset
        cx = (self.width() - tdw) / 2.0 + self._offset.x()
        cy = (self.height() - tdh) / 2.0 + self._offset.y()

        if self._single_page:
            painter.drawPixmap(int(cx), int(cy), self._display_left)
        else:
            # Left page — vertically centered within spread height
            ly = cy + (tdh - self._display_left.height()) / 2.0
            painter.drawPixmap(int(cx), int(ly), self._display_left)
            # Right page
            rx = cx + self._display_left.width() + self._display_gap
            ry = cy + (tdh - self._display_right.height()) / 2.0
            painter.drawPixmap(int(rx), int(ry), self._display_right)

        painter.end()

    # ── zoom / pan ───────────────────────────────────────────────────

    def wheelEvent(self, event: QWheelEvent):
        if self._pinch_active:
            return
        if not self._full_left:
            return
        pos = event.posF() if hasattr(event, 'posF') else QPointF(event.pos())
        delta = event.angleDelta().y()
        if delta > 0:
            new_zoom = min(MAX_ZOOM, self._zoom + ZOOM_STEP)
        elif delta < 0:
            new_zoom = max(MIN_ZOOM, self._zoom - ZOOM_STEP)
        else:
            return
        self._apply_zoom_at_point(new_zoom, pos)
        if self._zoom <= MIN_ZOOM + 0.001:
            self._offset = QPointF(0, 0)

    def mousePressEvent(self, event: QMouseEvent):
        if event.button() == Qt.LeftButton and self._zoom > MIN_ZOOM + 0.001:
            self._dragging = True
            self._drag_start = QPointF(event.pos())
            self._offset_start = QPointF(self._offset)
            self.setCursor(Qt.ClosedHandCursor)
            event.accept()
        else:
            super().mousePressEvent(event)

    def mouseMoveEvent(self, event: QMouseEvent):
        if self._dragging:
            delta = QPointF(event.pos()) - self._drag_start
            self._offset = self._offset_start + delta
            self._clamp_offset()
            self.update()
            event.accept()
        else:
            super().mouseMoveEvent(event)

    def mouseReleaseEvent(self, event: QMouseEvent):
        if self._dragging and event.button() == Qt.LeftButton:
            self._dragging = False
            self.setCursor(Qt.OpenHandCursor if self._zoom > MIN_ZOOM + 0.001
                           else Qt.ArrowCursor)
            event.accept()
        else:
            super().mouseReleaseEvent(event)

    def _clamp_offset(self):
        """Prevent the spread from drifting completely off-screen."""
        tdw, tdh = self._total_display_size()
        if tdw == 0:
            return
        margin = 100
        max_x = (tdw + self.width()) / 2.0 + margin
        max_y = (tdh + self.height()) / 2.0 + margin
        self._offset.setX(max(-max_x, min(max_x, self._offset.x())))
        self._offset.setY(max(-max_y, min(max_y, self._offset.y())))


class PdfViewerPanel(QWidget):
    fullscreen_toggle_requested = pyqtSignal()

    def __init__(self):
        super().__init__()
        self._docs = {}
        self._current_song = None
        self._current_page_offset = 0
        self._fullscreen = False
        self._init_ui()

    def _init_ui(self):
        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)

        # Stacked widget to swap between single-page and dual-page canvases
        self._canvas_stack = QStackedWidget()
        self._single_canvas = ScoreCanvas()
        self._dual_canvas = DualScoreCanvas()
        self._canvas_stack.addWidget(self._single_canvas)  # index 0
        self._canvas_stack.addWidget(self._dual_canvas)    # index 1
        self.canvas = self._single_canvas  # convenience ref — always points to active canvas
        layout.addWidget(self._canvas_stack, 1)

        nav_layout = QHBoxLayout()
        self.page_label = QLabel('')
        self.page_label.setAlignment(Qt.AlignCenter)
        self.prev_btn = QPushButton('◀ 上一页')
        self.next_btn = QPushButton('下一页 ▶')
        self.prev_btn.clicked.connect(self._prev_page)
        self.next_btn.clicked.connect(self._next_page)
        self.prev_btn.setEnabled(False)
        self.next_btn.setEnabled(False)
        self.toggle_btn = QPushButton('切换显示模式')
        self.toggle_btn.clicked.connect(self.fullscreen_toggle_requested.emit)
        self.toggle_btn.setStyleSheet(
            'QPushButton { padding: 4px 12px; font-size: 13px; }')

        nav_layout.addStretch()
        nav_layout.addWidget(self.prev_btn)
        nav_layout.addWidget(self.page_label)
        nav_layout.addWidget(self.next_btn)
        nav_layout.addWidget(self.toggle_btn)
        nav_layout.addStretch()
        layout.addLayout(nav_layout)

    def display_song(self, song_id):
        import app.database as db
        song = db.get_song(song_id)
        if not song:
            self.canvas.clear_page()
            self.page_label.setText('')
            self._current_song = None
            return
        self._current_song = song
        self._current_page_offset = 0
        self._render_current_page()

    def preview_page(self, volume, page_number):
        self._current_song = {
            'volume': volume,
            'pdf_start_page': page_number,
            'pdf_pages': 1,
        }
        self._current_page_offset = 0
        self._render_current_page()

    def _get_doc(self, volume):
        if not volume:
            return None
        if volume not in self._docs:
            path = os.path.join(PDF_REPO, volume)
            if not os.path.exists(path) and not volume.endswith('.pdf'):
                path = os.path.join(PDF_REPO, volume + '.pdf')
            if os.path.exists(path):
                self._docs[volume] = fitz.open(path)
        return self._docs.get(volume)

    def _render_page_pixmap(self, doc, page_idx):
        """Render a single PDF page to QPixmap at RENDER_DPI."""
        zoom = RENDER_DPI / 72.0
        mat = fitz.Matrix(zoom, zoom)
        pix = doc[page_idx].get_pixmap(matrix=mat)
        img = QImage(pix.samples, pix.width, pix.height, pix.stride,
                     QImage.Format_RGB888)
        return QPixmap.fromImage(img)

    def set_fullscreen(self, enabled):
        """Toggle fullscreen dual-page mode.

        When enabled, the dual-page canvas is shown and songs are
        rendered two pages side-by-side. When disabled, reverts to
        the single-page canvas.
        """
        if enabled == self._fullscreen:
            return
        self._fullscreen = enabled
        if enabled:
            self._canvas_stack.setCurrentWidget(self._dual_canvas)
            self.canvas = self._dual_canvas
        else:
            self._canvas_stack.setCurrentWidget(self._single_canvas)
            self.canvas = self._single_canvas
        # Re-render current song in the new mode
        self._render_current_page()

    def _render_current_page(self):
        if not self._current_song:
            return
        song = self._current_song
        doc = self._get_doc(song['volume'])
        if not doc:
            self.canvas.clear_page()
            self.page_label.setText('PDF 未找到')
            self.prev_btn.setEnabled(False)
            self.next_btn.setEnabled(False)
            return

        page_idx = song['pdf_start_page'] - 1 + self._current_page_offset
        total_pages = song['pdf_pages']

        if page_idx < 0 or page_idx >= doc.page_count:
            self.canvas.clear_page()
            self.page_label.setText('页码超出范围')
            return

        if self._fullscreen:
            # ── dual-page mode ──────────────────────────────────
            left_pixmap = self._render_page_pixmap(doc, page_idx)

            next_idx = page_idx + 1
            if (next_idx < doc.page_count
                    and self._current_page_offset + 1 < total_pages):
                right_pixmap = self._render_page_pixmap(doc, next_idx)
                visible_end = self._current_page_offset + 2
            else:
                right_pixmap = None
                visible_end = self._current_page_offset + 1

            self._dual_canvas.set_page(left_pixmap, right_pixmap)

            self.page_label.setText(
                f'{self._current_page_offset + 1}-{visible_end}/{total_pages}'
                f'  (PDF p.{page_idx + 1})')
            self.prev_btn.setEnabled(self._current_page_offset > 0)
            self.next_btn.setEnabled(
                self._current_page_offset + 1 < total_pages)
        else:
            # ── single-page mode ────────────────────────────────
            pixmap = self._render_page_pixmap(doc, page_idx)
            self._single_canvas.set_page(pixmap)

            self.page_label.setText(
                f'{self._current_page_offset + 1}/{total_pages}'
                f'  (PDF p.{page_idx + 1})')
            self.prev_btn.setEnabled(self._current_page_offset > 0)
            self.next_btn.setEnabled(
                self._current_page_offset < total_pages - 1)

    def _prev_page(self):
        if self._current_page_offset > 0:
            self._current_page_offset -= 1
            self._render_current_page()

    def _next_page(self):
        if self._current_song and self._current_page_offset < self._current_song['pdf_pages'] - 1:
            self._current_page_offset += 1
            self._render_current_page()

    def resizeEvent(self, event):
        super().resizeEvent(event)
        if self._current_song:
            self._render_current_page()

    def clear_cache(self):
        for doc in self._docs.values():
            doc.close()
        self._docs.clear()
