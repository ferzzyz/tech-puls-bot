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
    canvas = Image.new('RGB', (1280, 720), '#0B152B')
    draw = ImageDraw.Draw(canvas)
    cyan, violet = '#59E8FF', '#AA83FF'
    for x in range(960, 1280, 26):
        for y in range(0, 720, 26):
            draw.point((x, y), fill='#465584')
    draw.line([(64, 78), (83, 78), (98, 45), (112, 100), (128, 70), (147, 70)], fill=cyan, width=5)
    draw.text((164, 48), 'TECH PULS', font=font(39), fill='white')
    draw.line((64, 132, 1216, 132), fill='#39476C', width=2)
    draw.text((64, 185), category.upper(), font=font(32), fill=cyan)
    if category == 'ai':
        nodes = [(1020, 352), (1080, 290), (1080, 414), (1140, 352), (1200, 290), (1200, 414)]
        for a, b in ((0, 1), (0, 2), (1, 3), (2, 3), (3, 4), (3, 5)):
            draw.line((nodes[a], nodes[b]), fill=violet, width=4)
        for x, y in nodes:
            draw.ellipse((x-9, y-9, x+9, y+9), fill=cyan)
    elif category == 'gadgets':
        draw.rounded_rectangle((1072, 257, 1200, 465), 20, outline=violet, width=5)
        draw.rounded_rectangle((1040, 280, 1168, 488), 20, fill='#101F39', outline=cyan, width=5)
        draw.line((1082, 465, 1125, 465), fill=violet, width=4)
    else:
        draw.rounded_rectangle((1004, 285, 1218, 445), 16, outline=violet, width=4)
        draw.line((1004, 316, 1218, 316), fill=violet, width=3)
        draw.line([(1034, 347), (1056, 368), (1034, 389)], fill=cyan, width=5)
        draw.line((1070, 390, 1110, 390), fill=cyan, width=5)
    face = font(55)
    lines = ['']
    for word in title[:512].split():
        candidate = (lines[-1] + ' ' + word).strip()
        if draw.textlength(candidate, font=face) <= 905:
            lines[-1] = candidate
            continue
        if lines[-1]:
            lines.append('')
        for char in word:
            if draw.textlength(lines[-1] + char, font=face) > 905:
                lines.append('')
            lines[-1] += char
        if len(lines) > 4:
            break
    if len(lines) > 4:
        lines = lines[:4]
        while draw.textlength(lines[-1] + '…', font=face) > 905:
            lines[-1] = lines[-1][:-1]
        lines[-1] += '…'
    for index, line in enumerate(lines):
        draw.text((64, 261 + index * 72), line, font=face, fill='#F4F6FC')
    draw.line((64, 610, 1216, 610), fill='#344157', width=2)
    draw.text((64, 637), '@tech_puls3', font=font(24), fill=violet)
    output = BytesIO()
    canvas.save(output, format='JPEG', quality=90)
    return output.getvalue()
