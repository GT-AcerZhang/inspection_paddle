
import os
import sys

__dir__ = os.path.dirname(__file__)
sys.path.append(os.path.join(__dir__, 'PaddleOCR-release-2.0-rc1-0'))

import random
import numpy as np
from matplotlib import pyplot as plt
from paddle.io import Dataset
from ppocr.utils.logging import get_logger
from ppocr.data.imaug import transform, create_operators
from utils import draw_polylines

"""
Pipeline for decoding the labels

Sample label file: r"E:\Projects\Part_Number\baidu\icdar2015\text_localization\test_icdar2015_label.txt"
"""

class SimpleDataset(Dataset):
    def __init__(self, config, mode, logger):
        super(SimpleDataset, self).__init__()
        self.logger = logger
        
        global_config = config['Global']
        dataset_config = config[mode]['dataset']
        loader_config = config[mode]['loader']

        self.delimiter = dataset_config.get('delimiter', '\t')
        label_file_list = dataset_config.pop('label_file_list')
        data_source_num = len(label_file_list)
        ratio_list = dataset_config.get("ratio_list", [1.0])
        if isinstance(ratio_list, (float, int)):
            ratio_list = [float(ratio_list)] * int(data_source_num)

        assert len(
            ratio_list
        ) == data_source_num, "The length of ratio_list should be the same as the file_list."
        self.data_dir = dataset_config['data_dir']
        self.do_shuffle = loader_config['shuffle']

        logger.info("Initialize indexs of datasets:%s" % label_file_list)
        self.data_lines = self.get_image_info_list(label_file_list, ratio_list)
        self.data_idx_order_list = list(range(len(self.data_lines)))
        # if mode.lower() == "train":
        #     self.shuffle_data_random()
        self.ops = create_operators(dataset_config['transforms'], global_config)
        
    def get_image_info_list(self, file_list, ratio_list):
        if isinstance(file_list, str):
            file_list = [file_list]
        data_lines = []
        for idx, file in enumerate(file_list):
            with open(file, "rb") as f:
                lines = f.readlines()
                # lines = random.sample(lines,
                #                       round(len(lines) * ratio_list[idx]))
                data_lines.extend(lines)
        return data_lines

    def shuffle_data_random(self):
        if self.do_shuffle:
            random.shuffle(self.data_lines)
        return

    def __getitem__(self, idx):
        file_idx = self.data_idx_order_list[idx]
        data_line = self.data_lines[file_idx]
        try:
            data_line = data_line.decode('utf-8')
            substr = data_line.strip("\n").split(self.delimiter)
            file_name = substr[0]
            label = substr[1]
            img_path = os.path.join(self.data_dir, file_name)
            data = {'img_path': img_path, 'label': label}
            if not os.path.exists(img_path):
                raise Exception("{} does not exist!".format(img_path))
            with open(data['img_path'], 'rb') as f:
                img = f.read()
                data['image'] = img
            outs = transform(data, self.ops)
        except Exception as e:
            self.logger.error(
                "When parsing line {}, error happened with msg: {}".format(
                    data_line, e))
            outs = None
        if outs is None:
            return self.__getitem__(np.random.randint(self.__len__()))
        return outs

    def __len__(self):
        return len(self.data_idx_order_list)
        
    def display(self, top=100):
        if top is None: dsp_list = self.data_lines
        else: dsp_list = self.data_lines[:top]
        
        for data_line in dsp_list:
            data_line = data_line.decode('utf-8')
            substr = data_line.strip("\n").split(self.delimiter)
            file_name = substr[0]
            label = substr[1]
            img_path = os.path.join(self.data_dir, file_name)
            data = {'img_path': img_path, 'label': label}
            if not os.path.exists(img_path):
                raise Exception("{} does not exist!".format(img_path))
            with open(data['img_path'], 'rb') as f:
                img = f.read()
                data['image'] = img
            outs = transform(data, self.ops)
            
            #try:
            image = draw_polylines(outs['image'], outs['polys'], texts=outs['texts'])
            plt.imshow(image), plt.show()
            #except Exception as expt:
            #    print(expt)
        

CONFIG = {
    "Global": {
    },
    
    "Train": {
        "dataset": {
            "label_file_list": [r"E:\Projects\Part_Number\baidu\icdar2015\text_localization\train_icdar2015_label.txt"],
            "ratio_list": [1.0],
            "data_dir": r"E:\Projects\Part_Number\baidu\icdar2015\text_localization",
            "transforms": [{"DecodeImage":{"img_mode": "BGR", "channel_first": False}},
                           {"DetLabelEncode": None}],
        },
        "loader": {
            "shuffle": False,
        },
    },
}
    
    
if __name__ == "__main__":
    logger = get_logger(name='root', log_file="./log.txt")
    dataset = SimpleDataset(CONFIG, "Train", logger)
    outs = dataset.display(10)
    
    