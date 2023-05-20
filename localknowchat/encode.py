import os
import chardet

# 指定文件夹路径
folder_path = "./train_data"

# 遍历文件夹中的文件
for file_name in os.listdir(folder_path):
    # 构建文件的完整路径
    file_path = os.path.join(folder_path, file_name)

    # 仅处理txt文件
    if file_name.endswith(".txt"):
        # 使用 chardet 检测文件编码格式
        with open(file_path, 'rb') as f:
            raw_data = f.read()
            result = chardet.detect(raw_data)
            encoding = result['encoding']

        print(f"文件: {file_name} 的编码格式为: {encoding}")
