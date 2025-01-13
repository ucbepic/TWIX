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

def get_openai_output(image_paths, prompt):
    image_url_1 = f'data:image/jpeg;base64,{encode_image(image_paths[0])}'
    image_url_2 = f'data:image/jpeg;base64,{encode_image(image_paths[1])}'
    response = client.chat.completions.create(
        model='gpt-4o-mini',
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
                        'image_url': {'url': image_url_1}
                    },
                    {
                        'type': 'image_url',
                        'image_url': {'url': image_url_2}
                    }
                ],
            }
        ]
    )
    output = response.choices[0].message.content

    return output


def gpt_4o_vision(image_paths, prompt):
    message_content = prompt
    return get_openai_output(image_paths, message_content)

