import sys

with open('svg_data.txt', 'r') as f:
    lines = f.readlines()
    data_uri = lines[1].strip()

css_file = 'static/style.css'
with open(css_file, 'r') as f:
    content = f.read()

# Trova e sostituisci il blocco
old_block = """    background-image:
        url("data:image/svg+xml,%3Csvg xmlns='http://www.w3.org/2000/svg' width='220' height='40' viewBox='0 0 220 40'%3E%3Cg fill='rgba(156,122,60,0.5)'%3E%3Cellipse cx='20' cy='9.5' rx='3.5' ry='2.5' transform='rotate(-15 20 9.5)'/%3E%3Crect x='16.5' y='9.5' width='1.2' height='15'/%3E%3Cellipse cx='60' cy='16.5' rx='3.5' ry='2.5' transform='rotate(-15 60 16.5)'/%3E%3Crect x='56.5' y='16.5' width='1.2' height='15'/%3E%3Cellipse cx='100' cy='23.5' rx='3.5' ry='2.5' transform='rotate(-15 100 23.5)'/%3E%3Crect x='96.5' y='23.5' width='1.2' height='15'/%3E%3Cellipse cx='140' cy='27' rx='3.5' ry='2.5' transform='rotate(-15 140 27)'/%3E%3Crect x='142.3' y='12' width='1.2' height='15'/%3E%3Cellipse cx='180' cy='30.5' rx='3.5' ry='2.5' transform='rotate(-15 180 30.5)'/%3E%3Crect x='182.3' y='15.5' width='1.2' height='15'/%3E%3C/g%3E%3C/svg%3E"),
        repeating-linear-gradient(
            to bottom,
            transparent 0px,
            transparent 7px,
            rgba(156, 122, 60, 0.12) 7px,
            rgba(156, 122, 60, 0.12) 8px
        );
    background-size: 220px 40px, 100% 40px;
    background-position: 420px 0, center 0; /* Note nascoste fuori a destra */"""

new_block = f"""    background-image:
        url("{data_uri}"),
        repeating-linear-gradient(
            to bottom,
            transparent 0px,
            transparent 7px,
            rgba(156, 122, 60, 0.12) 7px,
            rgba(156, 122, 60, 0.12) 8px
        );
    background-size: 800px 40px, 100% 40px;
    background-position: 420px 0, center 0; /* Note nascoste fuori a destra */"""

content = content.replace(old_block, new_block)

old_keyframes = """@keyframes notesScrollX {
    0% { background-position: 420px 0, center 0; }
    100% { background-position: -220px 0, center 0; }
}"""

new_keyframes = """@keyframes notesScrollX {
    0% { background-position: 420px 0, center 0; }
    100% { background-position: -800px 0, center 0; }
}"""

content = content.replace(old_keyframes, new_keyframes)

old_hover = """animation: notesScrollX 4.5s linear infinite;"""
new_hover = """animation: notesScrollX 11s linear infinite;"""
content = content.replace(old_hover, new_hover)


with open(css_file, 'w') as f:
    f.write(content)
print("Updated style.css")
