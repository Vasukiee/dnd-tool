import urllib.parse

svg_parts = [
    "<svg xmlns='http://www.w3.org/2000/svg' width='600' height='40' viewBox='0 0 600 40'>",
    "<g fill='rgba(156,122,60,0.7)' stroke='rgba(156,122,60,0.7)' stroke-width='1.2'>"
]

def note(x, y, stem_dir='down', type='quarter', dot=False):
    # Notehead
    svg_parts.append(f"<ellipse cx='{x}' cy='{y}' rx='3.5' ry='2.5' transform='rotate(-15 {x} {y})' stroke='none'/>")
    
    if type == 'half':
        # Overwrite with empty head
        svg_parts.append(f"<ellipse cx='{x}' cy='{y}' rx='2.5' ry='1.5' fill='#231e1a' transform='rotate(-15 {x} {y})' stroke='none'/>")

    if dot:
        svg_parts.append(f"<circle cx='{x+6}' cy='{y}' r='1' fill='rgba(156,122,60,0.7)' stroke='none'/>")

    # Stem
    if type in ['quarter', 'eighth', 'half']:
        if stem_dir == 'down':
            svg_parts.append(f"<rect x='{x-3.5}' y='{y}' width='1.2' height='15' stroke='none'/>")
        else:
            svg_parts.append(f"<rect x='{x+2.3}' y='{y-15}' width='1.2' height='15' stroke='none'/>")
            
    # Flag for eighth note
    if type == 'eighth':
        if stem_dir == 'down':
            svg_parts.append(f"<path d='M{x-2.3},{y+15} Q{x+2},{y+8} {x+5},{y+12} Q{x+1},{y+5} {x-2.3},{y+10}' fill='rgba(156,122,60,0.7)' stroke='none'/>")
        else:
            svg_parts.append(f"<path d='M{x+3.5},{y-15} Q{x+8},{y-8} {x+11},{y-12} Q{x+7},{y-5} {x+3.5},{y-10}' fill='rgba(156,122,60,0.7)' stroke='none'/>")

def slur(x1, y1, x2, y2, bend=-10):
    svg_parts.append(f"<path d='M{x1},{y1} Q{(x1+x2)/2},{min(y1,y2)+bend} {x2},{y2}' fill='none'/>")

def tie(x1, y1, x2, y2):
    svg_parts.append(f"<path d='M{x1},{y1} Q{(x1+x2)/2},{y1+6} {x2},{y2}' fill='none'/>")


# Phrase 1: Ri-di (E5, C5)
note(20, 9.5, 'down', 'quarter', dot=True)
note(70, 16.5, 'down', 'eighth')
slur(20, 5, 70, 10, -8)

# Phrase 2: Pa-gliac-cio (A4, G4, F#4)
note(110, 23.5, 'down', 'quarter')
note(150, 27, 'up', 'eighth')
note(190, 30.5, 'up', 'quarter', dot=True)
slur(110, 18, 190, 25, -10)
# Sharp for F#4
svg_parts.append("<path d='M178,28 L178,36 M182,26 L182,34 M176,33 L184,31 M176,30 L184,28' fill='none' stroke-width='0.8'/>")


# Phrase 3: sul tuo amore infranto (E4 F#4 G4 A4 G4 F#4 E4)
note(250, 34, 'up', 'eighth')
# sharp for F#4
svg_parts.append("<path d='M268,28 L268,36 M272,26 L272,34 M266,33 L274,31 M266,30 L274,28' fill='none' stroke-width='0.8'/>")
note(280, 30.5, 'up', 'eighth')
note(310, 27, 'up', 'eighth')
note(350, 23.5, 'down', 'quarter')
note(390, 27, 'up', 'eighth')
# sharp for F#4
svg_parts.append("<path d='M418,28 L418,36 M422,26 L422,34 M416,33 L424,31 M416,30 L424,28' fill='none' stroke-width='0.8'/>")
note(430, 30.5, 'up', 'quarter')
note(480, 34, 'up', 'half')

# Tie
tie(483, 36, 527, 36)
note(530, 34, 'up', 'half')

slur(250, 28, 480, 28, -25)

svg_parts.append("</g></svg>")

svg_string = "".join(svg_parts)
print("URL ENCODED:")
print("data:image/svg+xml," + urllib.parse.quote(svg_string))
