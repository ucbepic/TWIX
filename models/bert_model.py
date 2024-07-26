from transformers import BertTokenizer, BertForQuestionAnswering
import torch

# Load the tokenizer and model
tokenizer = BertTokenizer.from_pretrained('bert-large-uncased-whole-word-masking-finetuned-squad')
model = BertForQuestionAnswering.from_pretrained('bert-large-uncased-whole-word-masking-finetuned-squad')

def bert(prompt):
    question = prompt[0]
    context = prompt[1]
    # Tokenize input
    inputs = tokenizer(question, context, return_tensors='pt', truncation=True, max_length=512)

    # Get predictions
    outputs = model(**inputs)
    start_scores, end_scores = outputs.start_logits, outputs.end_logits

    # Extract answer
    start_idx = torch.argmax(start_scores)
    end_idx = torch.argmax(end_scores)
    all_tokens = tokenizer.convert_ids_to_tokens(inputs["input_ids"][0])
    answer = ' '.join(all_tokens[start_idx: end_idx+1]).replace(' ##', '')
    
    return answer



