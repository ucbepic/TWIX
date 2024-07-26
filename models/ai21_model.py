import requests

url = "https://api.ai21.com/studio/v1/answer"

def read_key(path):
    with open(path, 'r') as file:
    # Iterate over each line in the file
        content = file.read()
    return content.strip()

path = '/Users/yiminglin/Documents/Codebase/config/ai21/config.txt'
api_key = read_key(path)

def ai21(prompt):
    #prompt[0]: question 
    #prompt[1]: context
    payload = {"context" : prompt[1], "question": prompt[0]}
    headers = {
        "accept": "application/json",
        "content-type": "application/json",
        "Authorization": "Bearer " + api_key
    }
    response = requests.post(url, json=payload, headers=headers)

    return response.text     





