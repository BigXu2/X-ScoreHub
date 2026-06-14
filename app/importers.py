import os
from app.utils import resource_path

PDF_REPO = resource_path('pdf_repo')


def _build_pdf_index():
    """Return a dict mapping normalized name → actual filename in pdf_repo.

    Keys are the filename without .pdf suffix, lowercased.
    """
    index = {}
    if os.path.exists(PDF_REPO):
        for f in os.listdir(PDF_REPO):
            if f.lower().endswith('.pdf'):
                base = os.path.splitext(f)[0]  # e.g. "557 Jazz Standards, Swing To Bop"
                index[base.lower()] = f
    return index


def _resolve_volume(raw_volume, pdf_index):
    """Match raw volume name from MD to actual PDF filename.

    Handles: missing suffix, wrong-case suffix (.PDF/.Pdf/.pdf),
    suffix-but-wrong-base.  Falls back to appending .pdf if unmatched.
    """
    # Strip trailing .pdf suffix in any case
    if raw_volume.lower().endswith('.pdf'):
        base = raw_volume[:-4]
    else:
        base = raw_volume

    key = base.lower()
    if key in pdf_index:
        return pdf_index[key]
    # Fallback: append .pdf (matches old behaviour)
    return base + '.pdf'

def parse_markdown_table(filepath):
    """Parse a markdown file and return a list of song dicts.

    Volume names in the file are resolved against actual PDF filenames
    in pdf_repo/ — this handles missing suffixes, wrong-case suffixes,
    and stale filename casing without manual correction.
    """
    songs = []
    pdf_index = _build_pdf_index()
    with open(filepath, 'r', encoding='utf-8') as f:
        lines = f.readlines()

    for line in lines:
        line = line.strip()
        if not line.startswith('|') or '序号' in line or '------' in line:
            continue
        parts = [p.strip() for p in line.split('|')]
        # Expected: ['', seq, name, name_cn, alias, difficulty, start_page, pages, volume, '']
        if len(parts) < 9:
            continue
        try:
            songs.append({
                'sequence': int(parts[1]),
                'name': parts[2],
                'name_cn': parts[3],
                'alias': parts[4],
                'difficulty': int(parts[5]) if parts[5] else 0,
                'pdf_start_page': int(parts[6]),
                'pdf_pages': int(parts[7]),
                'volume': _resolve_volume(parts[8], pdf_index),
                'notes': '',
                'favorite': 0,
            })
        except (ValueError, IndexError):
            continue
    return songs


def import_from_file(filepath, db_module):
    """Import songs from markdown file into database.

    Only the volumes referenced in the import file are replaced;
    songs in other volumes are left untouched. This makes imports
    additive by default — you can import multiple files to build
    the library incrementally.
    """
    songs = parse_markdown_table(filepath)
    # Replace only the volumes that appear in this file
    affected_volumes = list({s['volume'] for s in songs})
    db_module.delete_songs_by_volumes(affected_volumes)
    for song in songs:
        db_module.insert_song(song)
    return len(songs)
