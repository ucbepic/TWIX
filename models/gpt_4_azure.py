import os
from openai import AzureOpenAI


path = '/Users/yiminglin/Documents/Codebase/config/openai/config_azure.txt'

def read_key(path):
    with open(path, 'r') as file:
    # Iterate over each line in the file
        content = file.read()
        lines = content.split('\n')
    return lines[0], lines[1], lines[2], lines[3]



API_type, API_base, API_version, API_key = read_key(path)
endpoint = 'https://text-db.openai.azure.com/openai/deployments/gpt-4-text-db/chat/completions?api-version=2023-07-01-preview'

client = AzureOpenAI(
  api_key = API_key,
  api_version = API_version,
  azure_endpoint = endpoint
)

def chatGPT_api(message_content,temperature=0):
    message_text = [{"role":"user","content":message_content}]

    response = client.chat.completions.create(
        model="gpt-4-text-db",
        messages = message_text,
        temperature=temperature,
        max_tokens=800,
        top_p=0.95,
        frequency_penalty=0,
        presence_penalty=0,
        stop=None
        )
    return response.choices[0].message.content

def gpt_4_azure(prompt):
    message_content = prompt[0] + prompt[1]
    return chatGPT_api(message_content)