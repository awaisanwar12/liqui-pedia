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
    results_section_match = re.search(r'==\s*Results\s*==', wikitext, re.IGNORECASE)
    if not results_section_match:
        return {}

    results_wikitext = wikitext[results_section_match.end():]
    
    # Stop at the next level-2 section (avoid matching level-3/4 like === ... ===)
    next_section_match = re.search(r'^\s*==[^=].*?==\s*$\n?', results_wikitext, re.MULTILINE)
    if next_section_match:
        results_wikitext = results_wikitext[:next_section_match.start()]

    # Split by stages if they exist
    stage_split_pattern = r'===\s*\{\{Stage\|(.*?)\}\}\s*===\s*'
    parts = re.split(stage_split_pattern, results_wikitext)

    if len(parts) > 1:
        # Stages found via Stage template headers
        stages_data = {}
        for i in range(1, len(parts), 2):
            stage_name = parts[i].lower().strip().replace(' ', '_')
            stage_content = parts[i+1] if i+1 < len(parts) else ""
            stage_results = _parse_stage_content(stage_content)
            # Always include stages to show tournament structure
            stages_data[stage_name] = stage_results
        return stages_data
    else:
        # Try plain H3 stage headings (e.g., === Playoffs ===)
        plain_h3_pattern = r'===\s*([^=\{][^=]*?)\s*===\s*'
        h3_parts = re.split(plain_h3_pattern, results_wikitext)
        if len(h3_parts) > 1:
            stages_data = {}
            for i in range(1, len(h3_parts), 2):
                stage_name = h3_parts[i].lower().strip().replace(' ', '_')
                stage_content = h3_parts[i+1] if i+1 < len(h3_parts) else ""
                stage_results = _parse_stage_content(stage_content)
                # Always include stages to show tournament structure
                stages_data[stage_name] = stage_results
            return stages_data
        # No stages, treat as a single block
        return _parse_stage_content(results_wikitext)

def _parse_stage_content(stage_wikitext):
    # Check for sub-groups (e.g., Group A, Group B)
    sub_group_pattern = r'====\s*(.*?)\s*===='
    parts = re.split(sub_group_pattern, stage_wikitext)

    if len(parts) > 1:
        sub_groups_data = {}
        for i in range(1, len(parts), 2):
            sub_group_name = parts[i].lower().strip().replace(' ', '_')
            sub_group_content = parts[i+1]
            sub_groups_data[sub_group_name] = _parse_bracket_from_wikitext(sub_group_content)
        return sub_groups_data
    else:
        return _parse_bracket_from_wikitext(stage_wikitext)

def _parse_bracket_from_wikitext(wikitext):
    """
    Parses a chunk of wikitext that is expected to contain one bracket.
    This function contains the core logic of parsing a bracket.
    """
    wikicode = mwparserfromhell.parse(wikitext)
    bracket_templates = wikicode.filter_templates(matches=lambda t: t.name.strip().lower().startswith('bracket'))

    if not bracket_templates:
        return {}

    results = {}

    for bracket in bracket_templates:
        bracket_string = str(bracket)

        delimiters = []
        # Find comments as delimiters
        for m in re.finditer(r'<!--\s*(.*?)\s*-->', bracket_string):
            delimiters.append({'name': m.group(1).strip(), 'start': m.start(), 'end': m.end(), 'type': 'comment'})

        # Find headers as delimiters
        header_pattern = re.compile(r'^\|\s*(R\d+(?:M\d+)?header)\s*=\s*(.*)', re.MULTILINE)
        for m in header_pattern.finditer(bracket_string):
            delimiters.append({'name': m.group(2).strip(), 'start': m.start(), 'end': m.end(), 'type': 'header'})

        delimiters.sort(key=lambda x: x['start'])

        if not delimiters:
            # Fallback: parse by RnMk params
            fb = _parse_results_fallback(bracket)
            for k, v in fb.items():
                if v:
                    results.setdefault(k, []).extend(v)
            continue

        filtered_delimiters = []
        i = 0
        while i < len(delimiters):
            current_d = delimiters[i]
            if i + 1 < len(delimiters):
                next_d = delimiters[i+1]
                content_between = bracket_string[current_d['end']:next_d['start']]
                if '{{Match' not in content_between and 'match' not in content_between.lower():
                    if current_d['type'] == 'header' and next_d['type'] == 'comment':
                        filtered_delimiters.append(current_d)
                        i += 2
                        continue
            filtered_delimiters.append(current_d)
            i += 1

        for i, delim in enumerate(filtered_delimiters):
            stage_name_raw = delim['name']
            stage_name = stage_name_raw.lower().strip().replace(' ', '_')
            if not stage_name:
                continue
            
            start_pos = delim['end']
            end_pos = filtered_delimiters[i+1]['start'] if i + 1 < len(filtered_delimiters) else len(bracket_string)
            stage_content = bracket_string[start_pos:end_pos]
            
            dummy_wikitext = f"{{{{dummy {stage_content}}}}}"
            parsed_dummy = mwparserfromhell.parse(dummy_wikitext)
            
            try:
                dummy_template = parsed_dummy.filter_templates()[0]
                for param in dummy_template.params:
                    if 'match' in str(param.value).lower():
                        match_wikicode = mwparserfromhell.parse(str(param.value))
                        for template in match_wikicode.filter_templates(matches=lambda t: t.name.strip().lower() == 'match'):
                            match_data = _parse_match_template(template)
                            if match_data:
                                results.setdefault(stage_name, []).append(match_data)
            except (IndexError, ValueError):
                continue

    return results

def _parse_match_template(template):
    """Helper function to parse a single {{Match}} template."""
    match_data = {
        'opponent1': {'name': '', 'score': 0},
        'opponent2': {'name': '', 'score': 0},
        'winner': None
    }

    # Extract opponent names
    def _extract_name(value):
        code = mwparserfromhell.parse(value)
        # Support TeamOpponent, Opponent, Team templates
        tpl = code.filter_templates(matches=lambda t: t.name.strip().lower() in {'teamopponent','opponent','team'})
        if tpl:
            t = tpl[0]
            if t.has(1):
                return t.get(1).value.strip()
            if t.has('name'):
                return t.get('name').value.strip()
        return str(value).strip()

    if template.has('opponent1'):
        match_data['opponent1']['name'] = _extract_name(template.get('opponent1').value)
    if template.has('opponent2'):
        match_data['opponent2']['name'] = _extract_name(template.get('opponent2').value)

    # If both opponents empty, create placeholder match
    if not match_data['opponent1']['name'] and not match_data['opponent2']['name']:
        match_data['opponent1']['name'] = 'TBD'
        match_data['opponent2']['name'] = 'TBD'

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
                if map_template and map_template[0].has('finished') and map_template[0].get('finished').value.strip().lower() in {'true','t','yes','y','1'}:
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

    return match_data

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
            # Enhanced stage mapping for different bracket types
            stage_map = {
                'r1': 'round_1', 'r2': 'round_2', 'r3': 'round_3', 'r4': 'round_4', 'r5': 'round_5',
                'r6': 'round_6', 'r7': 'round_7', 'r8': 'round_8', 'r9': 'round_9'
            }
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
