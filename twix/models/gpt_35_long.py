from openai import OpenAI

client = OpenAI()

path = '/Users/yiminglin/Documents/Codebase/config/openai/config.txt'

def read_key(path):
    with open(path, 'r') as file:
    # Iterate over each line in the file
        content = file.read()
        lines = content.split('\n')
    return lines[0], lines[1]

openai.organization,openai.api_key = read_key(path)

def chatGPT_api(message_content,temperature=0):
    ##message_content is string
    
    response = client.chat.completions.create(model = "gpt-3.5-turbo-16k",
    messages = [
        {"role": "user", "content": message_content}],
    temperature = temperature)

    # print(response["choices"][0]["message"]["content"])
    return response["choices"][0]["message"]["content"]

def gpt_35_long(prompt):
    message_content = prompt[0] + prompt[1]
    return chatGPT_api(message_content)

