
def generate_xml():
    # Widget Configurations
    # Home: 0-10, IDs 10100-11100 (step 100)
    # Movies: 0-19, IDs 5100-5290 (step 10)
    # TV: 0-19, IDs 6100-6290 (step 10)
    
    widgets = []
    
    # Home Widgets (IDs 10100 to 11100)
    for i in range(11):
        widgets.append({
            'section': 'home',
            'idx': i,
            'id': 10100 + (i * 100)
        })
        
    # Movie Widgets (IDs 5100 to 5290)
    for i in range(20):
        widgets.append({
            'section': 'movies',
            'idx': i,
            'id': 5100 + (i * 10)
        })

    # TV Widgets (IDs 6100 to 6290)
    for i in range(20):
        widgets.append({
            'section': 'tvshows',
            'idx': i,
            'id': 6100 + (i * 10)
        })

    def get_condition(w):
        if w['section'] == 'home':
             # Home widgets usually depend on Home_WidgetIndex
             return f"String.IsEqual(Skin.String(SideMenuFocus),{w['section']}) + String.IsEqual(Skin.String(Home_WidgetIndex),{w['idx']})"
        elif w['section'] == 'movies':
             return f"String.IsEqual(Skin.String(SideMenuFocus),{w['section']}) + String.IsEqual(Skin.String(Movies_WidgetIndex),{w['idx']})"
        elif w['section'] == 'tvshows':
             return f"String.IsEqual(Skin.String(SideMenuFocus),{w['section']}) + String.IsEqual(Skin.String(TV_WidgetIndex),{w['idx']})"
        return ""

    xml_lines = []
    
    # 1. CurrentWidgetTitle
    xml_lines.append('<variable name="CurrentWidgetTitle">')
    xml_lines.append('    <value condition="Control.HasFocus(7100)">$INFO[Container(7100).ListItem.Label]</value>')
    for w in widgets:
        cond = get_condition(w)
        # Check title vs label
        xml_lines.append(f'    <value condition="{cond} + !String.IsEmpty(Container({w["id"]}).ListItem.Title) + !String.Contains(Container({w["id"]}).ListItem.Title,unknown)">$INFO[Container({w["id"]}).ListItem.Title]</value>')
        xml_lines.append(f'    <value condition="{cond}">$INFO[Container({w["id"]}).ListItem.Label]</value>')
    xml_lines.append('</variable>')

    # 2. CurrentWidgetClearLogo
    xml_lines.append('<variable name="CurrentWidgetClearLogo">')
    for w in widgets:
        cond = get_condition(w)
        xml_lines.append(f'    <value condition="{cond} + !String.IsEmpty(Container({w["id"]}).ListItem.Art(clearlogo))">$INFO[Container({w["id"]}).ListItem.Art(clearlogo)]</value>')
        xml_lines.append(f'    <value condition="{cond} + !String.IsEmpty(Container({w["id"]}).ListItem.Art(tvshow.clearlogo))">$INFO[Container({w["id"]}).ListItem.Art(tvshow.clearlogo)]</value>')
        xml_lines.append(f'    <value condition="{cond}">$INFO[Container({w["id"]}).ListItem.Art(logo)]</value>')
    xml_lines.append('</variable>')

    # 3. CurrentWidgetPlot
    xml_lines.append('<variable name="CurrentWidgetPlot">')
    xml_lines.append('    <value condition="Control.HasFocus(7100)">$INFO[Container(7100).ListItem.Plot]</value>')
    for w in widgets:
        cond = get_condition(w)
        xml_lines.append(f'    <value condition="{cond}">$INFO[Container({w["id"]}).ListItem.Plot]</value>')
    xml_lines.append('</variable>')

    # 4. CurrentWidgetFanart
    xml_lines.append('<variable name="CurrentWidgetFanart">')
    xml_lines.append('    <value condition="Control.HasFocus(7100)">$INFO[Container(7100).ListItem.Art(fanart)]</value>')
    for w in widgets:
        cond = get_condition(w)
        xml_lines.append(f'    <value condition="{cond}">$INFO[Container({w["id"]}).ListItem.Art(fanart)]</value>')
    xml_lines.append('</variable>')

    # 5. CurrentWidgetInfo
    xml_lines.append('<variable name="CurrentWidgetInfo">')
    xml_lines.append('    <value condition="Control.HasFocus(7100)">$INFO[Container(7100).ListItem.Year]$INFO[Container(7100).ListItem.Genre,  |  ]</value>')
    for w in widgets:
        cond = get_condition(w)
        # Episode Type
        xml_lines.append(f'    <value condition="{cond} + !String.IsEmpty(Container({w["id"]}).ListItem.Season)">$INFO[Container({w["id"]}).ListItem.Season,S]$INFO[Container({w["id"]}).ListItem.Episode,E] - $INFO[Container({w["id"]}).ListItem.Title]$INFO[Container({w["id"]}).ListItem.Duration,  |  , min]</value>')
        # Movie/Show Type with AiredDate
        xml_lines.append(f'    <value condition="{cond} + !String.IsEmpty(Container({w["id"]}).ListItem.Property(AiredDate))">$INFO[Container({w["id"]}).ListItem.Property(AiredDate)]$INFO[Container({w["id"]}).ListItem.Genre,  |  ]$INFO[Container({w["id"]}).ListItem.Duration,  |  , min]$INFO[Container({w["id"]}).ListItem.Director,  |  ]</value>')
        # Fallback
        xml_lines.append(f'    <value condition="{cond}">$INFO[Container({w["id"]}).ListItem.Year]$INFO[Container({w["id"]}).ListItem.Genre,  |  ]$INFO[Container({w["id"]}).ListItem.Duration,  |  , min]</value>')
    xml_lines.append('</variable>')

    print("\n".join(xml_lines))

if __name__ == "__main__":
    generate_xml()
