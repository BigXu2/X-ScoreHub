def export_to_markdown(filepath, song_ids, db_module):
    """Export selected songs to a markdown file matching the import format."""
    songs = [db_module.get_song(sid) for sid in song_ids]
    songs = [s for s in songs if s is not None]

    # Sort by sequence to reproduce original import order
    songs.sort(key=lambda s: s.get('sequence', 0))

    def _cell(val):
        """Format a single cell: ' value ' for non-empty, ' ' for empty."""
        s = str(val)
        return f' {s} ' if s else ' '

    with open(filepath, 'w', encoding='utf-8') as f:
        # Header
        f.write('| 序号 | 曲名 | 翻译曲名 | 别名 | 难度 | PDF 起始页码 | 占用页数 | 所属分册 |\n')
        f.write('|------|------|---------|------|------|-------------|---------|---------|\n')
        # Data rows
        for song in songs:
            seq = song.get('sequence', '')
            name = song.get('name', '')
            name_cn = song.get('name_cn', '') or ''
            alias = song.get('alias', '') or ''
            difficulty = str(song['difficulty']) if song.get('difficulty', 0) else ''
            start_page = song.get('pdf_start_page', '')
            pages = song.get('pdf_pages', '')
            volume = song.get('volume', '')
            cells = [_cell(seq), _cell(name), _cell(name_cn), _cell(alias),
                     _cell(difficulty), _cell(start_page), _cell(pages), _cell(volume)]
            f.write('|' + '|'.join(cells) + '|\n')
