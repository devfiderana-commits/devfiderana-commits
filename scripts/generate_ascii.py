import io
import requests
from PIL import Image
import re

url = "https://github.com/Rajath2005.png"
response = requests.get(url)
img = Image.open(io.BytesIO(response.content)).convert('L')

# Crop to circle before ASCII to fit perfectly in the circular glow ring
width = 64
height = 32
img = img.resize((width, height), Image.Resampling.LANCZOS)

pixels = img.load()

# From dark to light (we have a dark background, so white pixels = dense characters)
CHARS = [' ', '.', ':', '-', '=', '+', '*', '#', '%', '@']

svg_lines = []
svg_lines.append('  <!-- ASCII Avatar -->')
svg_lines.append('  <g transform="translate(102, 102)">')
# Use nameGrad for cool cyan/violet animated color!
svg_lines.append('    <text font-family="\'JetBrains Mono\', monospace" font-size="3.7" fill="url(#nameGrad)" font-weight="900" xml:space="preserve" letter-spacing="0">')

for y in range(height):
    line = []
    for x in range(width):
        # Distance from center for circular crop
        cx = width / 2.0
        cy = height / 2.0
        # Normalize distance so radius is 1.0
        dx = (x - cx) / cx
        dy = (y - cy) / cy
        if dx*dx + dy*dy > 1.0:
            line.append('&#160;')
            continue
            
        p = pixels[x, y]
        idx = int((p / 255.0) * (len(CHARS) - 1))
        char = CHARS[idx]
        
        if char == ' ':
            line.append('&#160;')
        elif char == '&':
            line.append('&amp;')
        elif char == '<':
            line.append('&lt;')
        elif char == '>':
            line.append('&gt;')
        else:
            line.append(char)
    
    y_pos = (y + 1) * (136.0 / height)
    svg_lines.append(f'      <tspan x="0" y="{y_pos:.1f}">{"".join(line)}</tspan>')

svg_lines.append('    </text>')
svg_lines.append('  </g>')

ascii_svg = '\n'.join(svg_lines)

with open('d:/DevWorkspace/Github_Repos/Rajath2005/assets/header-banner.svg', 'r', encoding='utf-8') as f:
    content = f.read()

# Replace the original image with ASCII
content = re.sub(
    r'<!-- ASCII Avatar -->\s*<g transform="translate\(102, 102\)">[\s\S]*?</g>',
    ascii_svg,
    content
)

with open('d:/DevWorkspace/Github_Repos/Rajath2005/assets/header-banner.svg', 'w', encoding='utf-8') as f:
    f.write(content)

print("ASCII Avatar generated successfully!")
