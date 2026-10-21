from utils.response_parser import web_search_parser

from utils.db_interactions import coordinate_funding_db, coordinate_outreach_db
from utils.agent_loop import agent_loop


class SearchAgent:
    def __init__(self, **kwargs):
        self.purpose = kwargs['purpose']
        self.db_file_path = kwargs['db_file_path']
        self.model = kwargs['model']
        self.api_key = kwargs['api_key']
        self.provider = kwargs['provider']
        self.tool_schema = kwargs['tool_schema']
        self.tool_registry = kwargs['tool_registry']
        self.messages = kwargs['messages']
        self.input_file_path = kwargs['input_file_path']

        self.final_output = None
        self.candidates = None
        self.confirmation = None

    def run_agent_loop(self):
        self.final_output = agent_loop(
            self.api_key,
            self.model,
            self.provider,
            self.tool_schema,
            self.tool_registry,
            self.messages,
        )

    def parse_web_search(self):
        self.candidates = web_search_parser(self.final_output)

    def save_to_db(self):
        if self.purpose == 'outreach':
            self.confirmation = coordinate_outreach_db(
                self.candidates,
                self.input_file_path,
                self.db_file_path,
            )
        elif self.purpose == 'funding':
            self.confirmation = coordinate_funding_db(
                self.candidates,
                self.db_file_path,
            )

    def execute_search(self):
        self.run_agent_loop()
        self.parse_web_search()
        self.save_to_db()

        if self.confirmation:
            print(self.confirmation)
        else:
            print('Failed... You suck... Or I do...')
            print('Blame AI.')
