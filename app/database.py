import sqlite3
import os

DB_PATH = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), 'scores.db')

def get_connection():
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    return conn

def init_db():
    conn = get_connection()
    conn.execute('''
        CREATE TABLE IF NOT EXISTS songs (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            sequence INTEGER,
            name TEXT NOT NULL,
            name_cn TEXT DEFAULT '',
            alias TEXT DEFAULT '',
            difficulty INTEGER DEFAULT 0,
            pdf_start_page INTEGER NOT NULL,
            pdf_pages INTEGER NOT NULL DEFAULT 1,
            volume TEXT NOT NULL,
            notes TEXT DEFAULT '',
            favorite INTEGER DEFAULT 0,
            deleted INTEGER DEFAULT 0,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
    ''')
    # Migration: add deleted column if it doesn't exist
    try:
        conn.execute('ALTER TABLE songs ADD COLUMN deleted INTEGER DEFAULT 0')
    except:
        pass
    conn.commit()
    conn.close()

def insert_song(data):
    conn = get_connection()
    conn.execute('''
        INSERT INTO songs (sequence, name, name_cn, alias, difficulty,
                          pdf_start_page, pdf_pages, volume, notes, favorite)
        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
    ''', (
        data.get('sequence', 0),
        data['name'],
        data.get('name_cn', ''),
        data.get('alias', ''),
        data.get('difficulty', 0),
        data['pdf_start_page'],
        data.get('pdf_pages', 1),
        data['volume'],
        data.get('notes', ''),
        data.get('favorite', 0),
    ))
    conn.commit()
    conn.close()

def update_song(song_id, data):
    conn = get_connection()
    conn.execute('''
        UPDATE songs SET
            name = ?, name_cn = ?, alias = ?, difficulty = ?,
            pdf_start_page = ?, pdf_pages = ?, volume = ?,
            notes = ?, favorite = ?, deleted = ?
        WHERE id = ?
    ''', (
        data['name'],
        data.get('name_cn', ''),
        data.get('alias', ''),
        data.get('difficulty', 0),
        data['pdf_start_page'],
        data.get('pdf_pages', 1),
        data['volume'],
        data.get('notes', ''),
        data.get('favorite', 0),
        data.get('deleted', 0),
        song_id,
    ))
    conn.commit()
    conn.close()

def get_all_songs(order_by='sequence', only_favorites=False, show_deleted=False, volume=None):
    conn = get_connection()
    allowed = {'sequence': 'sequence ASC', 'difficulty_asc': 'difficulty ASC',
               'difficulty_desc': 'difficulty DESC',
               'page': 'volume ASC, pdf_start_page ASC'}
    order = allowed.get(order_by, 'sequence ASC')
    conditions = []
    if only_favorites:
        conditions.append('favorite = 1')
    if show_deleted:
        conditions.append('deleted = 1')
    else:
        conditions.append('deleted = 0')
    if volume:
        conditions.append('volume = ?')
    query = 'SELECT * FROM songs'
    if conditions:
        query += ' WHERE ' + ' AND '.join(conditions)
    query += f' ORDER BY {order}'
    params = (volume,) if volume else ()
    rows = conn.execute(query, params).fetchall()
    conn.close()
    return [dict(r) for r in rows]

def get_song(song_id):
    conn = get_connection()
    row = conn.execute('SELECT * FROM songs WHERE id = ?', (song_id,)).fetchone()
    conn.close()
    return dict(row) if row else None

def delete_song_permanently(song_id):
    conn = get_connection()
    conn.execute('DELETE FROM songs WHERE id = ?', (song_id,))
    conn.commit()
    conn.close()

def get_song_count():
    conn = get_connection()
    count = conn.execute('SELECT COUNT(*) FROM songs').fetchone()[0]
    conn.close()
    return count

def get_volumes():
    """Return distinct volume names from the database."""
    conn = get_connection()
    rows = conn.execute('SELECT DISTINCT volume FROM songs ORDER BY volume').fetchall()
    conn.close()
    return [r['volume'] for r in rows]

def batch_update_deleted(song_ids, deleted):
    """批量设置 deleted 标志: deleted=1 软删除, deleted=0 恢复"""
    if not song_ids:
        return
    conn = get_connection()
    placeholders = ','.join(['?'] * len(song_ids))
    conn.execute(
        f'UPDATE songs SET deleted = ? WHERE id IN ({placeholders})',
        [deleted] + list(song_ids))
    conn.commit()
    conn.close()


def batch_permanent_delete(song_ids):
    """批量彻底删除"""
    if not song_ids:
        return
    conn = get_connection()
    placeholders = ','.join(['?'] * len(song_ids))
    conn.execute(f'DELETE FROM songs WHERE id IN ({placeholders})', list(song_ids))
    conn.commit()
    conn.close()


def delete_all_songs():
    conn = get_connection()
    conn.execute('DELETE FROM songs')
    conn.commit()
    conn.close()


def delete_songs_by_volumes(volumes):
    """Delete all songs belonging to the given volume names."""
    if not volumes:
        return
    conn = get_connection()
    placeholders = ','.join(['?'] * len(volumes))
    conn.execute(f'DELETE FROM songs WHERE volume IN ({placeholders})', tuple(volumes))
    conn.commit()
    conn.close()
