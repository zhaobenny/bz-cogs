import requests
import json

class ProxyOpenAI:
    def __init__(self, url):
        self.url = url
        self.headers = {"Content-Type": "application/json"}
        self.parameters = {
            "max_new_tokens": 200,
            "seed": -1.0,
            "temperature": 0.7,
            "top_p": 0.1,
            "top_k": 40,
            "typical_p": 1.0,
            "repetition_penalty": 1.18,
            "encoder_repetition_penalty": 1.0,
            "no_repeat_ngram_size": 0,
            "do_sample": True,
            "penalty_alpha": 0,
            "num_beams": 1,
            "length_penalty": 1,
            "add_bos_token": True,
            "custom_stopping_strings": "",
            "name1": None,
            "name2": None,
            "context": None,
            "turn_template": "",
            "chat_prompt_size": 2048,
            "chat_generation_attempts": 1,
            "stop_at_newline": False,
            "mode": "cai-chat",
            "stream": True
        }
        # Save the original parameters
        self.original_parameters = self.parameters.copy()

    def generate_response(self, prompt):
        data = {
            "model": "text-davinci-002",
            "messages": [{"role": "system", "content": "You are a helpful assistant."}, {"role": "user", "content": prompt}],
            **self.parameters
        }

        response = requests.post(self.url, headers=self.headers, data=json.dumps(data))
        return response.json()

    def update_parameters(self, parameters):
        """Update the parameters for the AI user."""
        self.parameters.update(parameters)

    def reset_parameters(self):
        """Reset the parameters to their original values."""
        self.parameters = self.original_parameters.copy()
