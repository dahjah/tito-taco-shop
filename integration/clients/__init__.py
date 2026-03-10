import importlib

def get_client(team):
    module = importlib.import_module(f'integration.clients.{team.chat_type}')
    return module.Client(team)
