def read_file(file):
    data = []
    with open(file, 'r') as file:
        # Iterate over each line in the file
        for line in file:
            # Print the line (you can replace this with other processing logic)
            data.append(line.strip())
    return data

def format(lst):
    l = []
    for v in lst:
        l.append(v.lower().strip())
    return l

def filter(truths, phrases):
    l = []
    for v in truths:
        if(v not in phrases):
            print('True key not in the extracted text: '+v)
        else:
            l.append(v)

    return l

def eval(truths, results):
    precision = 0
    recall = 0
    FP = []
    FN = []
    for v in results:
        if(v not in truths):
            FP.append(v)
        else:
            precision += 1
    for v in truths:
        if(v not in results):
            FN.append(v)
        else:
            recall += 1
    precision = precision / len(results)
    recall = recall / len(truths)

    return precision, recall, FP, FN