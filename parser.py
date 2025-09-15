import mwparserfromhell  # pyright: ignore[reportMissingImports]
import re

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
    dynamically identifying stages and segregating matches.
    """
    wikicode = mwparserfromhell.parse(wikitext)
    bracket_templates = wikicode.filter_templates(matches=lambda t: t.name.strip().lower().startswith('bracket'))

    if not bracket_templates:
        return {}

    bracket = bracket_templates[0]
    results = {}

    # Find commented sections and the wikitext that follows them
    bracket_string = str(bracket)
    # This pattern captures a comment's content and all text until the next comment or the end of the string
    sections = re.findall(r'<!--\s*(.*?)\s*-->(.*?)(?=<!--|$)', bracket_string, re.DOTALL)

    if not sections: # Fallback for brackets without comments
        return _parse_results_fallback(bracket)

    for stage_name_raw, stage_content in sections:
        stage_name = stage_name_raw.lower().strip().replace(' ', '_')
        if not stage_name:
            continue
        
        results[stage_name] = []

        # The content is just a string slice, so wrap it to be parsable
        dummy_wikitext = f"{{{{dummy {stage_content}}}}}"
        parsed_dummy = mwparserfromhell.parse(dummy_wikitext)
        
        try:
            dummy_template = parsed_dummy.filter_templates()[0]
        except IndexError:
            continue

        for param in dummy_template.params:
            if 'match' in str(param.value).lower():
                match_wikicode = mwparserfromhell.parse(str(param.value))
                for template in match_wikicode.filter_templates(matches=lambda t: t.name.strip().lower() == 'match'):
                    match_data = _parse_match_template(template)
                    if match_data:
                        results[stage_name].append(match_data)

    return results

def _parse_match_template(template):
    """Helper function to parse a single {{Match}} template."""
    match_data = {
        'opponent1': {'name': '', 'score': 0},
        'opponent2': {'name': '', 'score': 0},
        'winner': None
    }

    # Extract opponent names
    if template.has('opponent1'):
        opp1_wikicode = mwparserfromhell.parse(template.get('opponent1').value)
        opp1_template = opp1_wikicode.filter_templates(matches=lambda t: t.name.strip().lower() == 'teamopponent')
        if opp1_template and opp1_template[0].has(1):
            match_data['opponent1']['name'] = opp1_template[0].get(1).value.strip()

    if template.has('opponent2'):
        opp2_wikicode = mwparserfromhell.parse(template.get('opponent2').value)
        opp2_template = opp2_wikicode.filter_templates(matches=lambda t: t.name.strip().lower() == 'teamopponent')
        if opp2_template and opp2_template[0].has(1):
            match_data['opponent2']['name'] = opp2_template[0].get(1).value.strip()

    # Handle scores from walkover or explicit scores
    score1_raw = template.get('score1').value.strip().lower() if template.has('score1') else None
    score2_raw = template.get('score2').value.strip().lower() if template.has('score2') else None

    if score1_raw == 'w' or score2_raw == 'ff':
        match_data['winner'] = match_data['opponent1']['name']
        match_data['opponent1']['score'] = 1
        match_data['opponent2']['score'] = 0
    elif score2_raw == 'w' or score1_raw == 'ff':
        match_data['winner'] = match_data['opponent2']['name']
        match_data['opponent1']['score'] = 0
        match_data['opponent2']['score'] = 1
    elif score1_raw and score2_raw and score1_raw.isdigit() and score2_raw.isdigit():
        score1, score2 = int(score1_raw), int(score2_raw)
        match_data['opponent1']['score'] = score1
        match_data['opponent2']['score'] = score2
        if score1 > score2:
            match_data['winner'] = match_data['opponent1']['name']
        elif score2 > score1:
            match_data['winner'] = match_data['opponent2']['name']
    else: # Fallback to map calculation
        t1_score, t2_score = 0, 0
        for i in range(1, 6):  # Check up to 5 maps
            if template.has(f'map{i}'):
                map_wikicode = mwparserfromhell.parse(template.get(f'map{i}').value)
                map_template = map_wikicode.filter_templates(matches=lambda t: t.name.strip().lower() == 'map')
                if map_template and map_template[0].has('finished') and map_template[0].get('finished').value.strip() == 'true':
                    map_node = map_template[0]
                    t1_map_score, t2_map_score = 0, 0
                    
                    # Simplified score calculation
                    for side in ['t', 'ct']:
                        if map_node.has(f't1{side}'): t1_map_score += int(map_node.get(f't1{side}').value.strip())
                        if map_node.has(f't2{side}'): t2_map_score += int(map_node.get(f't2{side}').value.strip())
                    for ot in range(1, 5):
                        for side in ['t', 'ct']:
                            if map_node.has(f'o{ot}t1{side}'): t1_map_score += int(map_node.get(f'o{ot}t1{side}').value.strip())
                            if map_node.has(f'o{ot}t2{side}'): t2_map_score += int(map_node.get(f'o{ot}t2{side}').value.strip())
                            
                    if t1_map_score > t2_map_score: t1_score += 1
                    elif t2_map_score > t1_map_score: t2_score += 1
        
        match_data['opponent1']['score'] = t1_score
        match_data['opponent2']['score'] = t2_score
        if t1_score > t2_score:
            match_data['winner'] = match_data['opponent1']['name']
        elif t2_score > t1_score:
            match_data['winner'] = match_data['opponent2']['name']

    if match_data['opponent1']['name'] or match_data['opponent2']['name']:
        return match_data
    return None

def _parse_results_fallback(bracket):
    """Fallback parser for brackets without comments."""
    results = {}
    # This logic remains similar to the previous version for simple brackets
    round_names = {}
    for param in bracket.params:
        param_name = str(param.name).strip().lower()
        if param_name.endswith('-name'):
            round_id = param_name.split('-')[0]
            round_name = param.value.strip_code().strip()
            sanitized_name = round_name.lower().replace(' ', '_')
            round_names[round_id] = sanitized_name

    for param in bracket.params:
        param_name = str(param.name).strip().lower()
        match_info = re.match(r'^(r\d+)', param_name)
        if not (match_info and 'match' in str(param.value).lower()):
            continue

        round_id = match_info.group(1)
        current_stage = round_names.get(round_id)

        if not current_stage:
            stage_map = {'r1': 'quarterfinals', 'r2': 'semifinals', 'r3': 'grand_final'}
            current_stage = stage_map.get(round_id, f'round_{round_id[1:]}')

        if current_stage not in results:
            results[current_stage] = []

        match_wikicode = mwparserfromhell.parse(str(param.value))
        for template in match_wikicode.filter_templates(matches=lambda t: t.name.strip().lower() == 'match'):
            match_data = _parse_match_template(template)
            if match_data:
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
