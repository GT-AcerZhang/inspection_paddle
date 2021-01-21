
import os
import sys
import cv2
import json
import numpy as np
from matplotlib import pyplot as plt
from utils import draw_polylines


def viewer(data_dir, label_file, top=None):
    with open(label_file, "rb") as fin:
        label_infor_list = fin.readlines()
        if top is None or top<=0: top = len(label_infor_list)
        
        for label_infor in label_infor_list[:top]:
            label_infor = label_infor.decode()
            label_infor = label_infor.encode('utf-8').decode('utf-8-sig')
            
            substr = label_infor.strip("\n").split("\t")
            img_path = os.path.join(data_dir, substr[0])
            #labels = json.loads(substr[1])
            labels = eval(substr[1])
            
            polys, txts = [], []
            for label in labels:
                polys.append(label['points'])
                txts.append(label['transcription'])
            
            image = cv2.imread(img_path, -1)
            image = draw_polylines(image, polys, txts)
            print("Showing image", img_path, "...")
            plt.imshow(image), plt.title("Labeled image"), plt.show()
            
 
if __name__ == "__main__":
    data_dir = r"E:\Projects\Part_Number\dataset"
    label_file = r"E:\Projects\Part_Number\dataset\20210112_valid\valid.txt"
    viewer(data_dir, label_file, top=10)