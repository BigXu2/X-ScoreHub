"""
改进版：OCR 匹配加入位置约束。
每首歌只在数据页码 ±15 页范围内搜索，避免目录/交叉引用误匹配。
"""
import json, sys, os
from collections import defaultdict
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import app.database as db


def find_song_starts(results_file='ocr_results.json', window=15):
    """分析 OCR 结果，用位置约束提取每首歌的真实起始页。"""
    with open(results_file, 'r') as f:
        all_results = json.load(f)

    db.init_db()
    all_songs = db.get_all_songs()
    song_by_id = {s['id']: s for s in all_songs}

    corrections = []

    for vol_name, pages in all_results.items():
        # Get songs in this volume, sorted by current data page
        vol_songs = [s for s in all_songs if s['volume'] == vol_name]
        vol_songs.sort(key=lambda s: s['pdf_start_page'])

        print(f"\n=== {vol_name}: {len(vol_songs)} songs, {len(pages)} pages ===")

        for song in vol_songs:
            expected_idx = song['pdf_start_page'] - 1  # 0-indexed from data
            sid = song['id']

            # Search within window around expected position
            best_idx = None
            best_score = 0
            search_start = max(0, expected_idx - window)
            search_end = min(len(pages) - 1, expected_idx + window)

            for idx in range(search_start, search_end + 1):
                p = pages[idx]
                if p['song_id'] == sid and p['score'] > best_score:
                    best_score = p['score']
                    best_idx = idx

            if best_idx is not None and best_score >= 50:
                new_start = best_idx + 1  # 1-indexed PDF viewer page

                # Determine page count: find next song's start
                # Look forward to find where next different song starts
                page_count = 1
                for look_idx in range(best_idx + 1, min(len(pages), best_idx + 20)):
                    p = pages[look_idx]
                    if p['song_id'] and p['song_id'] != sid and p['score'] >= 50:
                        page_count = look_idx - best_idx
                        break
                else:
                    # If no next song found, estimate conservatively
                    page_count = song['pdf_pages']

                if new_start != song['pdf_start_page']:
                    # Only correct start page; keep original page count (OCR unreliable for boundaries)
                    corrections.append({
                        'id': sid,
                        'name': song['name'],
                        'volume': vol_name,
                        'old_start': song['pdf_start_page'],
                        'new_start': new_start,
                        'old_pages': song['pdf_pages'],
                        'new_pages': song['pdf_pages'],  # preserve original
                        'score': best_score,
                    })
                    status = f"page {song['pdf_start_page']}→{new_start}"
                else:
                    status = "OK"
            else:
                status = "NOT FOUND (keeping original)"

            if 'OK' not in status:
                print(f"  {song['name']}: {status}")

    print(f"\n=== Total corrections: {len(corrections)} ===")
    return corrections


def apply_corrections(corrections, dry_run=True):
    db.init_db()
    for c in corrections:
        song = db.get_song(c['id'])
        if song:
            if not dry_run:
                song['pdf_start_page'] = c['new_start']
                song['pdf_pages'] = c['new_pages']
                db.update_song(c['id'], song)
    if not dry_run:
        print(f"Applied {len(corrections)} corrections to database.")


if __name__ == '__main__':
    dry = '--apply' not in sys.argv
    corrections = find_song_starts(window=20)
    print(f"\nRun with --apply to {'apply' if dry else 're-apply'} corrections.")
    if dry:
        # Count by confidence
        high = sum(1 for c in corrections if c['score'] >= 70)
        mid = sum(1 for c in corrections if 50 <= c['score'] < 70)
        print(f"High confidence (>=70): {high}")
        print(f"Medium confidence (50-69): {mid}")
    else:
        apply_corrections(corrections, dry_run=False)
