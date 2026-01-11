import re
path = 'skin.AIODI/xml/Home.xml'
with open(path, 'r') as f: content = f.read()

# IDs to remove based on user request:
# Music Videos (id=musicvideos)
# Radio (id=radio)
# Games (id=games)
# Pictures (id=pictures)
# Videos (id=video)

to_remove = ['musicvideos', 'radio', 'games', 'pictures', 'video']

# Regex to find <item> blocks
pattern = re.compile(r'<item>.*?</item>', re.DOTALL)

def should_keep(item):
    for id_val in to_remove:
        if f'<property name="id">{id_val}</property>' in item:
            return False
    return True

items = pattern.findall(content)
new_items = [item for item in items if should_keep(item)]

# Replace the entire <content> block with filtered items
content_pattern = re.compile(r'<content>(.*?)</content>', re.DOTALL)
match = content_pattern.search(content)
if match:
    old_content_inner = match.group(1)
    new_content_inner = "\n\\t\\t\\t\\t\\t".join([item.strip() for item in new_items])
    # Let's be safer and just replace the whole window content if needed, 
    # but we can try to just replace the inner content.
    new_content = "\n\\t\\t\\t\\t\\t" + "\n\\t\\t\\t\\t\\t".join(new_items) + "\n\\t\\t\\t\\t"
    # Actually, let's just do a string replace on the items themselves by commenting them out or removing them.
    # Re-reading the file to do a cleaner replacement.

# Alternative: replace each specific item with empty string
final_content = content
for item in items:
    if not should_keep(item):
        final_content = final_content.replace(item, "")

with open(path, 'w') as f: f.write(final_content)
