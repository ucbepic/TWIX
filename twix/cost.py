import tiktoken

def cost(model_name, input_tokens, output_tokens, image_num = 0):
    if(model_name == 'gpt-4o'):
        m = 1000000
        input_unit = 5/m
        output_unit = 20/m
        return input_unit*input_tokens + output_unit*output_tokens 
    if(model_name == 'gpt-4o-mini'):
        m = 1000000
        input_unit = 0.3/m
        output_unit = 2.4/m
        return input_unit*input_tokens + output_unit*output_tokens 
    if(model_name == 'vision-gpt-4o'):
        m = 1000000
        input_unit = 5/m
        output_unit = 20/m
        image_tokens = 1105
        return image_num * image_tokens * input_unit + output_tokens*output_unit 
    if(model_name == 'vision-gpt-4o-mini'):
        m = 1000000
        input_unit = 0.3/m
        output_unit = 2.4/m
        image_tokens = 1105
        return image_num * image_tokens * input_unit + output_tokens*output_unit 
    
    return 0

def count_tokens(text, model_name):
    model = 'gpt-4o-mini'
    if 'gpt-4o-mini' in model_name:
        model = 'gpt-4o-mini'
    if 'gpt-4o' in model_name:
        model = 'gpt-4o'
    encoder = tiktoken.encoding_for_model(model)  # Get the tokenizer for the specific model
    tokens = encoder.encode(text)  # Encode text into tokens
    return len(tokens)