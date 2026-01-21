def generate_widget_vars():
    # Helper to generate the conditions matching ActiveWidgetID logic
    def get_condition(page, index, widget_id):
        if page == 'home':
            return f'String.IsEqual(Skin.String(SideMenuFocus),home) + String.IsEqual(Skin.String(Home_WidgetIndex),{index})'
        elif page == 'movies':
            return f'String.IsEqual(Skin.String(SideMenuFocus),movies) + String.IsEqual(Skin.String(Movies_WidgetIndex),{index})'
        elif page == 'tvshows':
            return f'String.IsEqual(Skin.String(SideMenuFocus),tvshows) + String.IsEqual(Skin.String(TV_WidgetIndex),{index})'

    widgets = []
    # Home: 10100 to 11100 (11 items)
    for i in range(11):
        widgets.append(('home', i, 10100 + (i * 100)))
    
    # Movies: 5100 to 5290 (20 items)
    for i in range(20):
        widgets.append(('movies', i, 5100 + (i * 10)))
        
    # TV Shows: 6100 to 6290 (20 items)
    for i in range(20):
        widgets.append(('tvshows', i, 6100 + (i * 10)))

    print('<variable name="CurrentWidgetTitle">')
    print('    <value condition="Control.HasFocus(7100)">[Container(7100).ListItem.Label]</value>')
    for page, idx, wid in widgets:
        cond = get_condition(page, idx, wid)
        # Check title then label
        print(f'    <value condition="{cond} + !String.IsEmpty(Container({wid}).ListItem.Title) + !String.Contains(Container({wid}).ListItem.Title,unknown)">[Container({wid}).ListItem.Title]</value>')
        print(f'    <value condition="{cond}">[Container({wid}).ListItem.Label]</value>')
    print('</variable>')

    print('<variable name="CurrentWidgetClearLogo">')
    for page, idx, wid in widgets:
        cond = get_condition(page, idx, wid)
        print(f'    <value condition="{cond} + !String.IsEmpty(Container({wid}).ListItem.Art(clearlogo))">[Container({wid}).ListItem.Art(clearlogo)]</value>')
        print(f'    <value condition="{cond} + !String.IsEmpty(Container({wid}).ListItem.Art(tvshow.clearlogo))">[Container({wid}).ListItem.Art(tvshow.clearlogo)]</value>')
        print(f'    <value condition="{cond}">[Container({wid}).ListItem.Art(logo)]</value>')
    print('</variable>')

    print('<variable name="CurrentWidgetPlot">')
    print('    <value condition="Control.HasFocus(7100)">[Container(7100).ListItem.Plot]</value>')
    for page, idx, wid in widgets:
        cond = get_condition(page, idx, wid)
        print(f'    <value condition="{cond}">[Container({wid}).ListItem.Plot]</value>')
    print('</variable>')
    
    print('<variable name="CurrentWidgetFanart">')
    print('    <value condition="Control.HasFocus(7100)">[Container(7100).ListItem.Art(fanart)]</value>')
    for page, idx, wid in widgets:
        cond = get_condition(page, idx, wid)
        print(f'    <value condition="{cond}">[Container({wid}).ListItem.Art(fanart)]</value>')
    print('</variable>')

    # Info is tricker due to extra logic, simplification:
    print('<variable name="CurrentWidgetInfo">')
    print('    <value condition="Control.HasFocus(7100)">[Container(7100).ListItem.Year][Container(7100).ListItem.Genre,  |  ]</value>')
    
    # Trakt Next Up (10100 specific)
    print('    <value condition="String.IsEqual(Skin.String(SideMenuFocus),home) + String.IsEqual(Skin.String(Home_WidgetIndex),0) + !String.IsEmpty(Container(10100).ListItem.Property(AiredDate))">[Container(10100).ListItem.Property(AiredDate)][Container(10100).ListItem.Duration,  |  , min][Container(10100).ListItem.Director,  |  ]</value>')

    # General Logic for others
    for page, idx, wid in widgets:
        if wid == 10100: continue # Handled above
        cond = get_condition(page, idx, wid)
        
        # Episode logic
        print(f'    <value condition="{cond} + !String.IsEmpty(Container({wid}).ListItem.Season)">[Container({wid}).ListItem.Season,S][Container({wid}).ListItem.Episode,E] - [Container({wid}).ListItem.Title][Container({wid}).ListItem.Duration,  |  , min]</value>')
        
        # AiredDate logic
        print(f'    <value condition="{cond} + !String.IsEmpty(Container({wid}).ListItem.Property(AiredDate))">[Container({wid}).ListItem.Property(AiredDate)][Container({wid}).ListItem.Genre,  |  ][Container({wid}).ListItem.Duration,  |  , min][Container({wid}).ListItem.Director,  |  ]</value>')
        
        # Fallback
        print(f'    <value condition="{cond}">[Container({wid}).ListItem.Year][Container({wid}).ListItem.Genre,  |  ][Container({wid}).ListItem.Duration,  |  , min]</value>')

    print('</variable>')

generate_widget_vars()
