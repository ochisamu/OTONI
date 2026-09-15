"""Raster title cards: user text never enters FFmpeg filter expressions."""
from pathlib import Path
import re
from PIL import Image, ImageDraw, ImageFilter, ImageFont, ImageOps

FONT = Path('/usr/share/fonts/opentype/ipafont-gothic/ipagp.ttf')


def fit_lines(text, width, max_lines, maximum, minimum):
    text = ' '.join(str(text).split())
    for size in range(maximum, minimum - 1, -1):
        font = ImageFont.truetype(str(FONT), size)
        lines = ['']
        for token in re.findall(r"[A-Za-z0-9]+(?:['’][A-Za-z]+)*|.", text):
            pieces = list(token) if font.getlength(token) > width else [token]
            for piece in pieces:
                if lines[-1] and font.getlength(lines[-1] + piece) > width:
                    lines.append('')
                lines[-1] += piece if lines[-1] else piece.lstrip()
        if len(lines) <= max_lines and len(lines) * size * 1.3 <= 250:
            return lines, font
    raise ValueError('動画内の曲名が表示領域に収まりません')


def title_card(cover, album, title, number, count, destination):
    with Image.open(cover) as source:
        art = ImageOps.exif_transpose(source).convert('RGB')
        canvas = ImageOps.fit(art, (1280, 720)).filter(ImageFilter.GaussianBlur(48))
        canvas = Image.blend(canvas, Image.new('RGB', canvas.size, '#090d15'), .82)
        jacket = ImageOps.contain(art, (500, 500), Image.Resampling.LANCZOS)
    draw = ImageDraw.Draw(canvas)
    draw.rounded_rectangle((65, 109, 583, 627), radius=12, fill='#0b0e14')
    canvas.paste(jacket, (74 + (500-jacket.width)//2, 110 + (500-jacket.height)//2))
    draw = ImageDraw.Draw(canvas)
    small = ImageFont.truetype(str(FONT), 18)
    draw.text((650, 144), 'N O W   P L A Y I N G', font=small, fill='#a7bdc7')
    draw.text((650, 184), f'{number:02d}  /  {count:02d}', font=ImageFont.truetype(str(FONT), 28), fill='#f2f5f7')
    draw.line((650, 244, 710, 244), fill='#aecfd5', width=3)
    lines, font = fit_lines(title, 550, 5, 46, 22)
    y = 278
    for line in lines:
        draw.text((650, y), line, font=font, fill='#f8fafb', stroke_width=0)
        y += int(font.size * 1.3)
    album_lines, album_font = fit_lines(album, 550, 3, 21, 16)
    y = 563
    for line in album_lines:
        draw.text((650, y), line, font=album_font, fill='#b4bfc8')
        y += 26
    # A quiet album-position strip, separate from playback time.
    for i in range(count):
        x = 650 + i * (550 / count)
        draw.rounded_rectangle((x, 662, x + 550/count - 5, 665), radius=1,
                               fill='#d7e8ed' if i == number-1 else '#39414b')
    draw.text((74, 654), 'O T O N I', font=small, fill='#a7b1bd')
    canvas.save(destination)
