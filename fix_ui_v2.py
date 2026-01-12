import re

path = 'skin.AIODI/xml/Home.xml'
with open(path, 'r') as f: content = f.read()

# 1. Sidebar Collapse Logic
# We want the sidebar to be 100 wide when not focused, and 462 when focused.
# We also need to hide the labels when not focused.

# Replace the ContentPanel width parameter with a conditional
# <param name="width" value="522" /> -> <param name="width" value="$VAR[SidebarWidthVar]" />
content = content.replace('<param name="width" value="522" />', '<param name="width" value="$VAR[SidebarWidthVar]" />')

# Replace the list width
content = content.replace('<width>462</width>', '<width>$VAR[SidebarWidthVar]</width>')

# 2. Modify ItemLayout and FocusedLayout to hide labels based on focus
# We'll use a variable for label visibility or just a condition in the label's visible tag
label_visible_condition = 'ControlGroup(9000).HasFocus'
content = re.sub(r'(<control type="label">.*?)<visible>(.*?)</visible>', r'\1<visible>\2 + ' + label_visible_condition + '</visible>', content)
# But Estuary labels usually don't have a visible tag, they are just there.
# Let's add one to every label inside the list 9000.

# 3. Add SidebarWidthVar to Variables.xml
var_path = 'skin.AIODI/xml/Variables.xml'
with open(var_path, 'r') as f: var_content = f.read()

new_var = """
<variable name="SidebarWidthVar">
<value condition="ControlGroup(9000).HasFocus">462</value>
<value>100</value>
</variable>
"""
var_content = var_content.replace('</includes>', new_var + '</includes>')
with open(var_path, 'w') as f: f.write(var_content)

# 4. Final Menu Item Polish
# (AIOStreams logo, search, settings, remove weather/power already done in previous script or need re-run)
# I'll just re-run a clean version of the Home modification here to be safe.

def fix_home(c):
    # Logo
    c = c.replace('special://xbmc/media/vendor_logo.png', 'special://skin/media/aiostreams_logo.png')
    
    # Favorites (already there, just check)
    # Search & Settings (Add to bottom of content)
    # Weather (Remove)
    
    pattern = re.compile(r'<item>.*?</item>', re.DOTALL)
    items = pattern.findall(c)
    
    kept_items = []
    to_remove_ids = ['weather', 'musicvideos', 'radio', 'games', 'pictures', 'video']
    
    for item in items:
        if not any(f'<property name="id">{rid}</property>' in item for rid in to_remove_ids):
            kept_items.append(item)
            
    search_item = '<item><label>[137]</label><onclick>ActivateWindow(1107)</onclick><thumb>icons/sidemenu/search.png</thumb><property name="id">search</property></item>'
    settings_item = '<item><label>[5]</label><onclick>ActivateWindow(settings)</onclick><thumb>icons/sidemenu/settings.png</thumb><property name="id">settings</property></item>'
    
    final_items = kept_items + [search_item, settings_item]
    
    start_c = c.find('<content>')
    end_c = c.find('</content>') + 10
    if start_c != -1 and end_c != -1:
        new_c = c[:start_c] + '<content>' + '\n'.join(final_items) + '</content>' + c[end_c:]
        return new_c
    return c

content = fix_home(content)
with open(path, 'w') as f: f.write(content)
