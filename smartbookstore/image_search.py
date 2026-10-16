"""Cover and internal-figure similarity search using a simple perceptual dHash."""
from pathlib import Path
from PIL import Image
from . import database as db


def dhash(path):
    with Image.open(path) as im:
        im=im.convert('L').resize((9,8),Image.Resampling.LANCZOS)
        pixels=list(im.get_flattened_data() if hasattr(im,"get_flattened_data") else im.getdata())
    bits=0
    for row in range(8):
        for col in range(8):
            bits=(bits<<1) | (pixels[row*9+col]>pixels[row*9+col+1])
    return bits


def image_matches(filepath,max_results=5):
    target=dhash(filepath)
    matches=[]
    for b in db.rows('SELECT * FROM books'):
        best=None
        for field in ('cover_path','figure_path'):
            p=Path(b[field]) if b[field] else (db.ROOT/'sample_images'/f"{b['id']}.png" if field=='cover_path' else None)
            if p and p.is_file():
                try:
                    dist=(target^dhash(p)).bit_count()
                    best=dist if best is None else min(best,dist)
                except (OSError,ValueError):pass
        if best is not None: matches.append((best,b))
    matches.sort(key=lambda x:(x[0],x[1]['title']))
    return matches[:max_results]
