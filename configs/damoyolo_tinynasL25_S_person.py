#!/usr/bin/env python3

import os
from pathlib import Path

from damo import Config as MyConfig


class Config(MyConfig):
    def __init__(self):
        super(Config, self).__init__()
        project_root = Path(__file__).resolve().parent.parent

        self.miscs.exp_name = os.path.split(
            os.path.realpath(__file__))[1].split('.')[0]
        self.miscs.eval_interval_epochs = 10
        self.miscs.ckpt_interval_epochs = 10
        self.miscs.output_dir = str(project_root / "workdir" / "damoyolo_tinynasL25_Person")
        self.train.batch_size = 12
        self.train.base_lr_per_img = 0.01 / 64
        self.train.min_lr_ratio = 0.05
        self.train.weight_decay = 5e-4
        self.train.momentum = 0.9
        self.train.no_aug_epochs = 16
        self.train.warmup_epochs = 5

        # augment
        self.train.augment.transform.image_max_range = (512, 512)
        self.train.augment.mosaic_mixup.mixup_prob = 0.10
        self.train.augment.mosaic_mixup.degrees = 10.0
        self.train.augment.mosaic_mixup.translate = 0.2
        self.train.augment.mosaic_mixup.shear = 2.0
        self.train.augment.mosaic_mixup.mosaic_scale = (0.1, 2.0)

        # self.train.finetune_path = '/mnt/nfs-k8s/share/models/damo-yolo/damoyolo_tinynasL25_S.pt'//优化学习
        self.dataset.train_ann = ('person_train_coco', )
        self.dataset.val_ann = ('person_val_coco', )

        # backbone
        structure = self.read_structure(
            str(project_root / "configs" / "tinynas_L25_k1kx.txt"))
        TinyNAS = {
            'name': 'TinyNAS_res',
            'net_structure_str': structure,
            'out_indices': (2, 4, 5),
            'with_spp': True,
            'use_focus': True,
            'act': 'relu',
            'reparam': True,
        }

        self.model.backbone = TinyNAS

        GiraffeNeckV2 = {
            'name': 'GiraffeNeckV2',
            'depth': 1.0,
            'hidden_ratio': 0.75,
            'in_channels': [128, 256, 512],
            'out_channels': [128, 256, 512],
            'act': 'relu',
            'spp': False,
            'block_name': 'BasicBlock_3x3_Reverse',
        }

        self.model.neck = GiraffeNeckV2

        ZeroHead = {
            'name': 'ZeroHead',
            'num_classes': 1,
            'in_channels': [128, 256, 512],
            'stacked_convs': 0,
            'reg_max': 16,
            'act': 'silu',
            'nms_conf_thre': 0.05,
            'nms_iou_thre': 0.7,
            'legacy': False,
        }
        self.model.head = ZeroHead

        self.dataset.class_names = ['person']
