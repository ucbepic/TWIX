
def get_relative_locations(path):
    line_number = 0
    phrases = {}
    with open(path, 'r') as file:
        # Iterate over each line in the file
        for line in file:
            phrase = line.strip()
            if(phrase not in phrases):
                phrases[phrase] = [line_number]
            else:
                phrases[phrase].append(line_number)
    return phrases
            

if __name__ == "__main__":
    a=0