import urllib.parse

svg_parts = [
    "<svg xmlns='http://www.w3.org/2000/svg' width='800' height='40' viewBox='0 0 800 40'>",
    "<g fill='rgba(156,122,60,0.6)' stroke='rgba(156,122,60,0.6)' stroke-width='1.2'>"
]

def note(x, y, stem_dir='down', type='quarter'):
    # Notehead
    svg_parts.append(f"<ellipse cx='{x}' cy='{y}' rx='3.5' ry='2.5' transform='rotate(-15 {x} {y})'/>")
    # Stem
    if type in ['quarter', 'eighth', 'sixteenth']:
        if stem_dir == 'down':
            svg_parts.append(f"<rect x='{x-3.5}' y='{y}' width='1.2' height='15' stroke='none'/>")
        else:
            svg_parts.append(f"<rect x='{x+2.3}' y='{y-15}' width='1.2' height='15' stroke='none'/>")

def chord(x, ys, stem_dir='down'):
    for y in ys:
        svg_parts.append(f"<ellipse cx='{x}' cy='{y}' rx='3.5' ry='2.5' transform='rotate(-15 {x} {y})'/>")
    # Stem for chord
    if stem_dir == 'down':
        svg_parts.append(f"<rect x='{x-3.5}' y='{min(ys)}' width='1.2' height='{max(ys)-min(ys)+15}' stroke='none'/>")
    else:
        svg_parts.append(f"<rect x='{x+2.3}' y='{min(ys)-15}' width='1.2' height='{max(ys)-min(ys)+15}' stroke='none'/>")

def beam(x1, y1, x2, y2):
    svg_parts.append(f"<polygon points='{x1},{y1} {x1},{y1+3} {x2},{y2+3} {x2},{y2}' stroke='none'/>")

def slur(x1, y1, x2, y2, control_y_offset=-10):
    svg_parts.append(f"<path d='M{x1},{y1} Q{(x1+x2)/2},{min(y1,y2)+control_y_offset} {x2},{y2}' fill='none'/>")

# "Ridi, pagliaccio" E minor massive chord
chord(30, [9.5, 16.5, 23.5, 34], 'down') # E5, C5, A4, E4
# Tremolo marks (just some angled lines across the stem)
svg_parts.append("<line x1='21' y1='25' x2='30' y2='22'/>")
svg_parts.append("<line x1='21' y1='28' x2='30' y2='25'/>")

# Descending chords
chord(90, [16.5, 23.5, 27], 'down')  # C5 chord
chord(130, [23.5, 27, 30.5], 'down') # A4 chord
chord(170, [27, 30.5, 34], 'up')     # G4 chord
chord(210, [30.5, 34, 37.5], 'up')   # F#4 chord

# Fast run (16th notes beamed)
start_x = 260
notes_y = [23.5, 20, 16.5, 13, 9.5, 13, 16.5, 20, 23.5, 27, 30.5, 34]
for i, y in enumerate(notes_y):
    x = start_x + i * 20
    note(x, y, 'down' if y < 24 else 'up')
# Beams for the run (group by 4)
for i in range(0, 12, 4):
    x1 = start_x + i * 20
    x2 = start_x + (i+3) * 20
    # Top beam
    if notes_y[i] < 24:
        beam(x1-3.5, notes_y[i]+15, x2-3.5, notes_y[i+3]+15)
        beam(x1-3.5, notes_y[i]+11, x2-3.5, notes_y[i+3]+11)
    else:
        beam(x1+2.3, notes_y[i]-15, x2+2.3, notes_y[i+3]-15)
        beam(x1+2.3, notes_y[i]-11, x2+2.3, notes_y[i+3]-11)

# Big final chords
chord(520, [16.5, 23.5, 27, 34], 'down')
chord(580, [16.5, 20, 27, 34], 'down')
chord(640, [9.5, 16.5, 23.5, 34], 'down')

# Slur over the run
slur(260, 5, 480, 5, -15)
slur(520, 5, 640, -5, -20)

svg_parts.append("</g></svg>")

svg_string = "".join(svg_parts)
print("URL ENCODED:")
print("data:image/svg+xml," + urllib.parse.quote(svg_string))
