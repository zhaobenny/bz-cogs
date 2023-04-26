import re

def remove_template_from_response(response, bot_name):
    patterns = [
        r'^User "{}" said:'.format(bot_name),
        r'^{}:'.format(bot_name),
    ]
    for pattern in patterns:
        response = re.sub(pattern, '', response)
    return response
