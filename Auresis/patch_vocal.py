import sys

with open('svg_data_vocal.txt', 'r') as f:
    lines = f.readlines()
    data_uri = lines[1].strip()

css_file = 'static/style.css'
with open(css_file, 'r') as f:
    content = f.read()

# Trova e sostituisci
old_url_start = '        url("data:image/svg+xml,%3Csvg xmlns=\'http://www.w3.org/2000/svg\' width=\'800\''
start_idx = content.find(old_url_start)
if start_idx == -1:
    old_url_start = '        url("data:image/svg+xml,'
    start_idx = content.find(old_url_start)

end_idx = content.find('"),', start_idx) + 2

old_block = content[start_idx:end_idx]
new_block = f'        url("{data_uri}")'

content = content.replace(old_block, new_block)

# Update size and position
old_size = 'background-size: 800px 40px, 100% 40px;'
new_size = 'background-size: 600px 40px, 100% 40px;'
content = content.replace(old_size, new_size)

old_keyframes = """@keyframes notesScrollX {
    0% { background-position: 420px 0, center 0; }
    100% { background-position: -800px 0, center 0; }
}"""

new_keyframes = """@keyframes notesScrollX {
    0% { background-position: 420px 0, center 0; }
    100% { background-position: -600px 0, center 0; }
}"""
content = content.replace(old_keyframes, new_keyframes)

old_hover = """animation: notesScrollX 11s linear infinite;"""
new_hover = """animation: notesScrollX 10s linear infinite;"""
content = content.replace(old_hover, new_hover)

with open(css_file, 'w') as f:
    f.write(content)

print("Updated style.css with vocal notes")
