import re
import os

def clean_ass_to_txt(input_file, output_file):
    with open(input_file, 'r', encoding='utf-8-sig', errors='ignore') as f:
        lines = f.readlines()

    buffer = {} 
    
    for line in lines:
        if line.startswith('Dialogue:'):
            parts = line.split(',', 9)
            if len(parts) < 10: continue
            
            style = parts[3].strip()
            name = parts[4].strip()
            text = parts[9].strip()
            
            clean_text = re.sub(r'\{.*?\}', '', text).replace(r'\N', ' ')
            time_code = parts[1] + parts[2]
            
            if time_code not in buffer: 
                buffer[time_code] = {'name': name}
            
            if '中文' in style:
                buffer[time_code]['cn'] = clean_text
            elif '日语' in style:
                buffer[time_code]['jp'] = clean_text

    with open(output_file, 'w', encoding='utf-8') as f:
        for key in sorted(buffer.keys()):
            data = buffer[key]
            if 'cn' in data and 'jp' in data:
                speaker = data['name'] if data['name'] else "未知"
                f.write(f"【{speaker}】\n原文：{data['jp']}\n译文：{data['cn']}\n\n")

for file in os.listdir('.'):
    if file.endswith('.ass'):
        clean_ass_to_txt(file, file.replace('.ass', '_cleaned.txt'))
        print(f"已清洗并保留人名: {file}")