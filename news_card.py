from io import BytesIO

from PIL import Image, ImageDraw, ImageFont


def font(size):
    for name in ('DejaVuSans-Bold.ttf', 'arialbd.ttf'):
        try:
            return ImageFont.truetype(name, size)
        except OSError:
            continue
    raise OSError('A Cyrillic font is required')


def render_card(title, label, category):
    accent = {'ai': '#78E8D1', 'gadgets': '#FFBE78', 'it': '#A8AEFF'}[category]
    canvas = Image.new('RGB', (1080, 640), '#101A2B')
    draw = ImageDraw.Draw(canvas)
    draw.line([(64, 75), (82, 75), (94, 49), (108, 96), (120, 70), (140, 70)], fill=accent, width=5)
    draw.text((156, 48), 'Tech Puls', font=font(38), fill='white')
    draw.line((64, 129, 1016, 129), fill='#344157', width=2)
    draw.text((64, 166), label.upper(), font=font(28), fill=accent)
    face = font(54)
    lines = ['']
    for word in title[:512].split():
        candidate = (lines[-1] + ' ' + word).strip()
        if draw.textlength(candidate, font=face) <= 945:
            lines[-1] = candidate
            continue
        if lines[-1]:
            lines.append('')
        for char in word:
            if draw.textlength(lines[-1] + char, font=face) > 945:
                lines.append('')
            lines[-1] += char
        if len(lines) > 4:
            break
    if len(lines) > 4:
        lines = lines[:4]
        while draw.textlength(lines[-1] + '…', font=face) > 945:
            lines[-1] = lines[-1][:-1]
        lines[-1] += '…'
    for index, line in enumerate(lines):
        draw.text((64, 235 + index * 70), line, font=face, fill='#F4F6FC')
    draw.line((64, 560, 1016, 560), fill='#344157', width=2)
    draw.text((64, 578), '@tech_puls3', font=font(24), fill=accent)
    output = BytesIO()
    canvas.save(output, format='JPEG', quality=90)
    return output.getvalue()
