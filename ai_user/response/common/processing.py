import re

from discord import Member


def remove_patterns_from_response(response: str, bot_member: Member) -> str:
    patterns = [
        rf'^(User )?"?{bot_member.name}"? (said|says|respond(ed|s)|replie[ds])( to [^":]+)?:?',
        rf'^As "?{bot_member.name}"?, (I|you)( might| would| could)? (respond|reply|say)( with)?( something like)?:?',
        rf'^[<({{\[]{bot_member.name}[>)}}\]]',  # [name], {name}, <name>, (name)
        rf'^{bot_member.name}:',
        rf'^(User )?"?{bot_member.nick}"? (said|says|respond(ed|s)|replie[ds])( to [^":]+)?:?',
        rf'^As "?{bot_member.nick}"?, (I|you)( might| would| could)? (respond|reply|say)( with)?( something like)?:?',
        rf'^[<({{\[]{bot_member.nick}[>)}}\]]',  # [name], {name}, <name>, (name)
        rf'^{bot_member.nick}:',
    ]
    response = response.strip(' "')
    for pattern in patterns:
        response = re.sub(pattern, '', response).strip(' \n":')
        if response.count('"') == 1:
            response = response.replace('"', '')
    return response
