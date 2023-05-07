import re

def remove_template_from_response(response, bot_name):
    patterns = [
        rf'^(User )?"?{bot_name}"? (said|says|respond(ed|s)|replie[ds])( to [^":]+)?:?',
        rf'^As {bot_name}, I( might| would| could)? (respond|reply)( with)?:?',
        rf'^{bot_name}:',
    ]
    for pattern in patterns:
        response = re.sub(pattern, '', response).strip(' \n":')
        if response.count('"') == 1:
            response = response.replace('"', '')
    return response
