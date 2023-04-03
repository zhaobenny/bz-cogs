import re

def remove_template_from_response(response, bot_name):
    pattern = r'^User {} said:'
    # remove the User botname said: from the response if it exists
    return re.sub(pattern.format(bot_name), '', response)
