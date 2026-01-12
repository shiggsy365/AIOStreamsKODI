import re
path = 'skin.AIODI/xml/Home.xml'
with open(path, 'r') as f: content = f.read()

# 1. Replace Kodi logo with AIOStreams logo
# vendor_logo.png is the kodi logo in estuary
content = content.replace('special://xbmc/media/vendor_logo.png', 'special://skin/media/aiostreams_logo.png')

# 2. Find specific items and modify/remove
pattern = re.compile(r'<item>.*?</item>', re.DOTALL)
items = pattern.findall(content)

new_items = []
for item in items:
    # Remove Weather
    if '<property name="id">weather</property>' in item:
        continue
    
    # We already removed others in v4.0.1, but let's be sure
    if any(id_v in item for id_v in ['musicvideos', 'radio', 'games', 'pictures', 'video']):
        continue
        
    new_items.append(item)

# 3. Add Search and Settings items to the list
search_item = """
<item>
<label>[137]</label>
<onclick>ActivateWindow(1107)</onclick>
<thumb>icons/sidemenu/search.png</thumb>
<property name="id">search</property>
</item>"""
settings_item = """
<item>
<label>[5]</label>
<onclick>ActivateWindow(settings)</onclick>
<thumb>icons/sidemenu/settings.png</thumb>
<property name="id">settings</property>
</item>"""

# Find the end of content block and insert
content_pattern = re.compile(r'</content>', re.DOTALL)
# First remove the old items that were stripped but left empty lines or whatever
# We'll just replace the whole content block with new_items + our additions
final_items = new_items + [search_item, settings_item]
new_content_block = '<content>' + ''.join(final_items) + '\n\\t\\t\\t\\t</content>'

# Find the start and end of <content>
start_content = content.find('<content>')
end_content = content.find('</content>') + 10
final_content = content[:start_content] + new_content_block + content[end_content:]

# 4. Remove power button and other items from top group 700
# We'll just hide the grouplist 700 or remove its content
# User said "remove the power button"
pattern_700 = re.compile(r'<control type="grouplist" id="700">.*?</control>', re.DOTALL)
final_content = pattern_700.sub('', final_content)

with open(path, 'w') as f: f.write(final_content)
