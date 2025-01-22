#this is the models API. You pass the model (name of the model) and prompt, the API will return the response out 
def model(model_name, prompt, image_path = ''):
    if(model_name is 'gpt4'):
        from models.gpt_4_model import gpt_4
        return gpt_4(prompt)
    if(model_name == 'gpt4o'):
        from models.gpt_4o import gpt_4o
        return gpt_4o(prompt)
    if(model_name == 'gpt4vision'):
        from models.gpt_4_vision import gpt_4o_vision
        return gpt_4o_vision(image_path,prompt)
    if(model_name == 'gpt4omini'):
        from models.gpt_4o_mini import gpt_4o_mini
        return gpt_4o_mini(prompt)
    if(model_name is 'gpt4_azure'):
        from models.gpt_4_azure import gpt_4_azure
        return gpt_4_azure(prompt)
    if(model_name is 'gpt4_long'):
        from models.gpt_4_long import gpt_4_long
        return gpt_4_long(prompt)
    return 'input model does not exist'


