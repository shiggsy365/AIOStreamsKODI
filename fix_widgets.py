import os, re
path = 'skin.AIODI/1080i/'
for f in os.listdir(path):
    if f.endswith('.xml'):
        p = os.path.join(path, f)
        with open(p, 'r') as file: c = file.read()
        
        # 1. Restore posters (where aspectratio is scale)
        nc = re.sub(r'(<aspectratio>scale</aspectratio>\s*)<texture[^>]*>common/white.png</texture>', r'\1<texture background="true">$INFO[ListItem.Art(poster)]</texture>', c)
        
        # 2. Restore icons (where aspectratio is keep)
        nc = re.sub(r'(<aspectratio>keep</aspectratio>\s*)<texture[^>]*>common/white.png</texture>', r'\1<texture>$INFO[ListItem.Icon]</texture>', nc)
        
        # 3. Restore widgets focus borders (specific to 160x230 poster widgets)
        nc = re.sub(r'(<control type="image">\s*<left>0</left>\s*<top>0</top>\s*<width>160</width>\s*<height>230</height>\s*)<texture[^>]*>common/white.png</texture>', r'\1<texture colordiffuse="ThemeColor">lists/focus.png</texture>', nc, flags=re.S)

        # 4. Restore list navigation selection bars (generic)
        nc = re.sub(r'(<focusedlayout height="140" width="1800">\s*<control type="image">\s*<left>0</left>\s*<top>0</top>\s*<width>1800</width>\s*<height>140</height>\s*)<texture[^>]*>common/white.png</texture>', r'\1<texture colordiffuse="ThemeColor">lists/focus.png</texture>', nc, flags=re.S)

        if nc != c:
            with open(p, 'w') as file: file.write(nc)
