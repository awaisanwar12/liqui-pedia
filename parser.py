import mwparserfromhell

def parse_participants(wikitext):
    """
    Parses the participants section of a Liquipedia wikitext page.
    """
    participants = []
    wikicode = mwparserfromhell.parse(wikitext)
    
    # Find all TeamCard templates
    for template in wikicode.filter_templates(matches=lambda t: t.name.strip().lower() == 'teamcard'):
        team_data = {
            'team': '',
            'players': [],
            'coach': None,
            'qualifier': ''
        }

        if template.has('team'):
            team_data['team'] = template.get('team').value.strip()

        # Extract players
        for i in range(1, 6): # p1 to p5
            player_param = f'p{i}'
            if template.has(player_param):
                player_name = template.get(player_param).value.strip()
                team_data['players'].append(player_name)
        
        # Extract coach
        if template.has('c'):
            team_data['coach'] = template.get('c').value.strip()
        
        # Extract qualifier
        if template.has('qualifier'):
            team_data['qualifier'] = template.get('qualifier').value.strip()
            
        participants.append(team_data)
        
    return participants

def parse_results(wikitext):
    """
    Parses the results (bracket) section of a Liquipedia wikitext page,
    segregating matches by stage based on round parameter names (R1, R2, R3).
    """
    results = {
        "quarterfinals": [],
        "semifinals": [],
        "grand_final": []
    }
    wikicode = mwparserfromhell.parse(wikitext)
    
    bracket = wikicode.filter_templates(matches=lambda t: t.name.strip().lower().startswith('bracket'))
    
    if not bracket:
        return {}

    # Find all Match templates within the bracket's parameters
    for param in bracket[0].params:
        param_name = str(param.name).strip().lower()
        
        current_stage = None
        if param_name.startswith('r1'):
            current_stage = 'quarterfinals'
        elif param_name.startswith('r2'):
            current_stage = 'semifinals'
        elif param_name.startswith('r3'):
            current_stage = 'grand_final'

        if current_stage and 'match' in str(param.value).lower():
            match_wikicode = mwparserfromhell.parse(param.value)
            for template in match_wikicode.filter_templates(matches=lambda t: t.name.strip().lower() == 'match'):
                
                match_data = {
                    'opponent1': {'name': '', 'score': 0},
                    'opponent2': {'name': '', 'score': 0},
                    'winner': None
                }

                # Extract opponent names
                if template.has('opponent1'):
                    opp1_template = mwparserfromhell.parse(template.get('opponent1').value).filter_templates(matches=lambda t: t.name.strip().lower() == 'teamopponent')
                    if opp1_template and opp1_template[0].has(1):
                        match_data['opponent1']['name'] = opp1_template[0].get(1).value.strip()

                if template.has('opponent2'):
                    opp2_template = mwparserfromhell.parse(template.get('opponent2').value).filter_templates(matches=lambda t: t.name.strip().lower() == 'teamopponent')
                    if opp2_template and opp2_template[0].has(1):
                        match_data['opponent2']['name'] = opp2_template[0].get(1).value.strip()

                # Calculate scores from map results
                t1_score = 0
                t2_score = 0
                for i in range(1, 6):  # Check for up to 5 maps
                    map_param = f'map{i}'
                    if template.has(map_param):
                        map_template = mwparserfromhell.parse(template.get(map_param).value).filter_templates(matches=lambda t: t.name.strip().lower() == 'map')
                        if map_template and map_template[0].has('finished') and map_template[0].get('finished').value.strip() == 'true':
                            map_node = map_template[0]
                            
                            t1_map_score = 0
                            t2_map_score = 0
                            
                            # Regular time scores
                            if map_node.has('t1t'): t1_map_score += int(map_node.get('t1t').value.strip())
                            if map_node.has('t1ct'): t1_map_score += int(map_node.get('t1ct').value.strip())
                            if map_node.has('t2t'): t2_map_score += int(map_node.get('t2t').value.strip())
                            if map_node.has('t2ct'): t2_map_score += int(map_node.get('t2ct').value.strip())

                            # Overtime scores
                            for ot in range(1, 5): # Check up to 4 overtimes
                                if map_node.has(f'o{ot}t1t'): t1_map_score += int(map_node.get(f'o{ot}t1t').value.strip())
                                if map_node.has(f'o{ot}t1ct'): t1_map_score += int(map_node.get(f'o{ot}t1ct').value.strip())
                                if map_node.has(f'o{ot}t2t'): t2_map_score += int(map_node.get(f'o{ot}t2t').value.strip())
                                if map_node.has(f'o{ot}t2ct'): t2_map_score += int(map_node.get(f'o{ot}t2ct').value.strip())

                            if t1_map_score > t2_map_score:
                                t1_score += 1
                            elif t2_map_score > t1_map_score:
                                t2_score += 1
                
                match_data['opponent1']['score'] = t1_score
                match_data['opponent2']['score'] = t2_score
                
                if t1_score > t2_score:
                    match_data['winner'] = match_data['opponent1']['name']
                elif t2_score > t1_score:
                    match_data['winner'] = match_data['opponent2']['name']

                # Only add if we found opponents
                if match_data['opponent1']['name'] and match_data['opponent2']['name']:
                    results[current_stage].append(match_data)
                
    return results

def parse_tournament_data(wikitext):
    """
    Parses the wikitext to extract structured data.
    """
    return {
        'participants': parse_participants(wikitext),
        'results': parse_results(wikitext)
    }
