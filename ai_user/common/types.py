from collections import namedtuple
from typing import Literal

ContextOptions = namedtuple('ContextOptions', ['start_time', 'ignore_regex', 'cached_messages'])
RoleType = Literal['user', 'assistant', 'system']
