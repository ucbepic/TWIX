

#this is the models API. You pass the model (name of the model) and prompt, the API will return the response out 
def model(model_name, prompt):
    if(model_name is 'bert'):
        from models.bert_model import bert
        return bert(prompt)
    if(model_name is 'gpt35'):
        from models.gpt_35_model import gpt_35
        return gpt_35(prompt)
    if(model_name is 'gpt35_azure'):
        from models.gpt_35_azure import gpt_35_azure
        return gpt_35_azure(prompt)
    if(model_name is 'gpt35long'):
        from models.gpt_35_long import gpt_35_long
        return gpt_35_long(prompt)
    if(model_name is 'gpt4'):
        from models.gpt_4_model import gpt_4
        return gpt_4(prompt)
    if(model_name == 'gpt4o'):
        from models.gpt_4o import gpt_4o
        return gpt_4o(prompt)
    if(model_name == 'gpt4omini'):
        from models.gpt_4o_mini import gpt_4o_mini
        return gpt_4o_mini(prompt)
    if(model_name is 'flant5small'):
        from models.flan_t5_small_model import flant5small
        return flant5small(prompt)
    if(model_name is 'flant5base'):
        from models.flan_t5_base_model import flant5base
        return flant5base(prompt)
    if(model_name is 'flant5large'):
        from models.flan_t5_large_model import flant5large
        return flant5large(prompt)
    if(model_name is 'ai21'):
        from models.ai21_model import ai21
        return ai21(prompt)
    if(model_name is 'gpt4_azure'):
        from models.gpt_4_azure import gpt_4_azure
        return gpt_4_azure(prompt)
    if(model_name is 'gpt4_long'):
        from models.gpt_4_long import gpt_4_long
        return gpt_4_long(prompt)
    return 'input model does not exist'


