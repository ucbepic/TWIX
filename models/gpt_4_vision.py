from openai import OpenAI
import openai
import base64
import os 
client = OpenAI()


# Access the API key from the environment variable
api_key = os.getenv('OPENAI_API_KEY')
openai.api_key = api_key

#print(api_key)

def encode_image(image_path):
    with open(image_path, 'rb') as image_file:
        return base64.b64encode(image_file.read()).decode('utf-8')

def get_openai_output(image_path, prompt):
    image_url = f'data:image/jpeg;base64,{encode_image(image_path)}'
    response = client.chat.completions.create(
        model='gpt-4-vision-preview',
        messages=[
            {
                'role': 'user',
                'content': [
                    {
                        'type': 'text',
                        'text': prompt
                    },
                    {
                        'type': 'image_url',
                        'image_url': {'url': image_url}
                    }
                ],
            }
        ]
    )
    output = response.choices[0].message.content
    #output = output.replace("```\n", "").replace("\n```", "")

    return output

def gpt_4o_vision(image_path, prompt):
    message_content = prompt[0] + prompt[1]
    return get_openai_output(image_path, message_content)

