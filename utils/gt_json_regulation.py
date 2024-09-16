#this script translates the ground truth data into json format 
import pandas as pd
def regulate_table(path):
    # Read the CSV file into a pandas DataFrame
    df = pd.read_csv(path)
    
    for index, row in df.iterrows():
        print(index)
        for key,val in row.items():
            print(key, val)
        if(index >= 0):
            break

if __name__ == "__main__":
    path = '/Users/yiminglin/Documents/Codebase/Pdf_reverse/data/truths/key_value_truth/certification/CT/DecertifiedOfficersRev_9622 Emilie Munson.csv'
    regulate_table(path)
    


