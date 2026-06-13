"""Pinch gesture diagnostic testbench.

Records raw NativeGesture events to a JSON file for offline analysis.
Uses QApplication eventFilter for reliable macOS event capture.

Usage:
  python pinch_testbench.py          # record gestures
  python pinch_testbench.py -r       # replay & analyze last recording
"""

import sys, os, json, math
from datetime import datetime

from PyQt5.QtWidgets import (QApplication, QWidget, QVBoxLayout, QHBoxLayout,
                             QPushButton, QLabel, QTextEdit)
from PyQt5.QtCore import Qt, QEvent, QTimer, QPointF
from PyQt5.QtGui import QNativeGestureEvent

RECORD_FILE = '/tmp/pinch_record.json'


class Testbench(QWidget):
    def __init__(self):
        super().__init__()
        self.setWindowTitle('Pinch Testbench — 双指缩放诊断')
        self.resize(800, 600)
        self.setStyleSheet('background-color: #1a1a2e;')

        layout = QVBoxLayout(self)

        self.status = QLabel('在该窗口或主应用窗口内使用触控板做手势\n'
                            '全局捕获模式——不限于本窗口')
        self.status.setStyleSheet('color: #aaa; font-size: 15px; padding: 10px;')
        layout.addWidget(self.status)

        self.log = QTextEdit()
        self.log.setReadOnly(True)
        self.log.setStyleSheet('color: #0f0; background: #000; font: 13px monospace;')
        layout.addWidget(self.log, 1)

        btn_row = QHBoxLayout()
        self.save_btn = QPushButton('停止录制并分析')
        self.save_btn.setStyleSheet('color: #fff; background: #2196F3; padding: 10px 20px; font-size: 15px;')
        self.save_btn.clicked.connect(self._save_and_analyze)
        btn_row.addWidget(self.save_btn)

        self.clear_btn = QPushButton('清空重录')
        self.clear_btn.setStyleSheet('color: #aaa; padding: 10px 20px; font-size: 15px;')
        self.clear_btn.clicked.connect(self._clear)
        btn_row.addWidget(self.clear_btn)
        layout.addLayout(btn_row)

        self._gestures = []
        self._current = None
        self._event_seq = 0

        # ── USe QApplication eventFilter — same as main app ──
        QApplication.instance().installEventFilter(self)

    def eventFilter(self, obj, event):
        if event.type() == QEvent.NativeGesture:
            self._record(event)
            return False  # don't consume — let other filters also process
        return super().eventFilter(obj, event)

    def _record(self, event):
        gt = event.gestureType()
        val = event.value()
        ts = datetime.now().isoformat(timespec='milliseconds')
        self._event_seq += 1

        if gt == Qt.BeginNativeGesture:
            self._current = {'events': [], 'start_time': ts}
            self._log(f'● 手势开始', '#4af')
        elif gt == Qt.EndNativeGesture and self._current:
            self._current['events'].append({'seq': self._event_seq, 'type': 'End', 'ts': ts, 'value': val})
            self._gestures.append(self._current)
            self._log(f'○ 手势结束  (共 {len(self._current["events"])} 个事件)\n', '#f88')
            self._current = None
        elif gt == Qt.ZoomNativeGesture and self._current:
            self._current['events'].append({'seq': self._event_seq, 'type': 'Zoom', 'ts': ts, 'value': val})
            direction = '🔍' if val > 0 else '🔎'
            bar = '█' * min(40, int(abs(val) * 500))
            self._log(f'{direction} value={val:+.6f}  {bar}', '#fff' if val > 0 else '#f88')

    def _log(self, msg, color='#ccc'):
        self.log.append(f'<span style="color:{color}">{msg}</span>')

    def _save_and_analyze(self):
        if not self._gestures:
            self._log('\n⚠ 没有录制到任何手势!', '#ff0')
            return

        with open(RECORD_FILE, 'w') as f:
            json.dump(self._gestures, f, indent=2, ensure_ascii=False)

        self._log(f'\n✓ 已保存 {len(self._gestures)} 个手势到 {RECORD_FILE}', '#0f0')
        self._analyze()

    def _analyze(self):
        self._log('\n────────────── 分析报告 ──────────────', '#ff0')
        for i, g in enumerate(self._gestures):
            zooms = [e for e in g['events'] if e['type'] == 'Zoom']
            if not zooms:
                continue
            values = [e['value'] for e in zooms]
            v_min, v_max = min(values), max(values)
            peak = v_max if abs(v_max) >= abs(v_min) else v_min
            n = len(values)

            self._log(f'\n手势 {i+1}: {n} 个事件', '#ff0')
            self._log(f'  方向: {"放大" if peak > 0 else "缩小"}')
            self._log(f'  value 范围: {v_min:.6f} → {v_max:.6f}')
            self._log(f'  峰值 |v|: {abs(peak):.6f}')
            self._log(f'  等效缩放 (灵敏度3x): 2^({peak*3:.2f}) = {2**(peak*3):.2f}x')
            self._log(f'  value 序列:')
            self._log(f'    {", ".join(f"{v:+.4f}" for v in values)}')

        self._log('\n────────────── 建议 ──────────────', '#ff0')
        if self._gestures:
            zooms_all = [e['value'] for g in self._gestures
                        for e in g['events'] if e['type'] == 'Zoom']
            if zooms_all:
                abs_max = max(abs(v) for v in zooms_all)
                self._log(f'原始 value 最大 |v| = {abs_max:.6f}')
                self._log(f'累加后 scale = (accum / n_events * 0.3 * sensitivity)')

    def _clear(self):
        self._gestures = []
        self._current = None
        self._event_seq = 0
        self.log.clear()
        self._log('已清空，请重新手势', '#aaa')


def replay_analysis():
    if not os.path.exists(RECORD_FILE):
        print(f'找不到录制文件: {RECORD_FILE}')
        return
    with open(RECORD_FILE) as f:
        gestures = json.load(f)
    print(f'加载 {len(gestures)} 个手势\n')

    for i, g in enumerate(gestures):
        zooms = [e for e in g['events'] if e['type'] == 'Zoom']
        if not zooms:
            continue
        values = [e['value'] for e in zooms]

        print(f'=== 手势 {i+1}: {len(values)} 事件 ===')
        print(f'  value 序列: {[f"{v:+.5f}" for v in values]}')

        # Simulate our algorithm
        print(f'\n  模拟算法: PINCH_SENSITIVITY=3, accum+EMA')
        accum = 0.0
        smooth = 0.0
        base_zoom = 1.0
        zooms = []
        for v_raw in values:
            accum += v_raw
            smooth = smooth * 0.70 + accum * 0.30
            v = smooth * 3.0
            scale = 2.0 ** v
            new_zoom = max(1.0, min(8.0, base_zoom * scale))
            zooms.append(new_zoom)
            print(f'    raw={v_raw:+.5f} accum={accum:+.4f} smooth={smooth:+.4f} v={v:.4f} zoom={new_zoom:.2f}x')

        print(f'\n  zoom 变化: {[f"{z:.2f}" for z in zooms]}')


if __name__ == '__main__':
    if '-r' in sys.argv:
        replay_analysis()
    else:
        app = QApplication(sys.argv)
        w = Testbench()
        w.show()
        sys.exit(app.exec_())
