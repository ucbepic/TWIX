import csv,os


# output_cleaned_json_root = '/Users/yiminglin/Documents/Codebase/Dataset/pdf_reverse/baseline_results/gpt4-vision-cleaned_predicted_kv_pairs' 
# os.makedirs(output_cleaned_json_root, exist_ok=True)

def get_txt_files(input_dir):
    """
    Retrieves a list of all TXT files within the input_dir directory.
    
    Args:
        input_dir (str): Path to the directory containing TXT files.
    
    Returns:
        list: List of full paths to TXT files.
    """
    txt_files = []
    print(input_dir)
    for entry in os.listdir(input_dir):
        full_path = os.path.join(input_dir, entry)
        if os.path.isfile(full_path) and entry.lower().endswith('.csv'):
            txt_files.append(full_path)
            #print(full_path)
    return txt_files


def parse_txt_to_records(txt_file_path):
    records = {}
    current_record_num = None

    with open(txt_file_path, 'r', encoding='utf-8') as file:
        for line in file:
            if "record" in line:
                key, value = line.split(':', 1)
                value = value.strip().strip('},') 
                current_record_num = value
                print(current_record_num)
            elif "type" in line or "content" in line:
                continue
            elif ":" in line:
                if current_record_num not in records:
                    records[current_record_num] = []
                key, value = line.split(':', 1)
                key = key.strip().strip('{')
                value = value.strip().strip('},')
                records[current_record_num].append((key, value))
    return records


def dump_to_csv(records, output_file):
    # Flatten records into a list of dictionaries for CSV writing
    csv_data = []
    for record_num, kv_pairs in records.items():
        for key, value in kv_pairs:
            csv_data.append({'Record': record_num, 'Key': key, 'Value': value})
    
    # Write the data to a CSV file
    with open(output_file, mode='w', newline='') as file:
        writer = csv.DictWriter(file, fieldnames=['Record', 'Key', 'Value'])
        writer.writeheader()
        writer.writerows(csv_data)


if __name__ == "__main__":

    txt_files = get_txt_files('/Users/yiminglin/Documents/Codebase/Dataset/pdf_reverse/baseline_results/gpt4-vision-cleaned_predicted_kv_pairs/')
    for txt_file in txt_files:
        print(txt_file)
        # records = parse_txt_to_records(txt_file)
        # print(records)
        # break