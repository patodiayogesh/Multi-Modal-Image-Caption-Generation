from dataset import FlickrDatasetModule
from model import BaselineModel
import pytorch_lightning as pl
import argparse
from pytorch_lightning.callbacks import EarlyStopping, LearningRateMonitor
from seutil import LoggingUtils
from pytorch_lightning.utilities.cli import (
    LR_SCHEDULER_REGISTRY,
    OPTIMIZER_REGISTRY,
)
import transformers
import torch

class BaselineTrainer:

    def __init__(self,
                 image_encoder,
                 text_decoder,
                 dataset,
                 fast_dev):

        self.model = BaselineModel(image_encoder, text_decoder)
        if dataset == 'flickr30k':
            self.dataModule = FlickrDatasetModule()
        else:
            raise RuntimeError("Incorrect Dataset")
        self.dataModule.set_encoder_and_decoder_tokenizer(
            self.model.image_feature_extractor,
            self.model.decoder_tokenizer
        )

        early_stopping_callback = EarlyStopping(monitor='loss/train',
                                                mode='min',
                                                )
        lr_monitor_callback = LearningRateMonitor(logging_interval='step')
        self.trainer = pl.Trainer(
            fast_dev_run=fast_dev,
            num_sanity_val_steps=1,
            max_epochs=20,
            callbacks=[
                early_stopping_callback,
                lr_monitor_callback
            ],
            # GPU specific
            accelerator='gpu',
            devices=1,
            # accumulate_grad_batches=12,
            # strategy='ddp',
            # Validation between epoch
            # limit_val_batches=0.0,
            # check_val_every_n_epoch=1
        )

    def train_model(self):
        self.trainer.fit(self.model, self.dataModule)
        return

    def inference(self):
        self.trainer.fit(self.model, self.dataModule)


if __name__ == '__main__':

    parser = argparse.ArgumentParser()
    parser.add_argument('--image_encoder', type=str, default='beit', required=False)
    parser.add_argument('--text_decoder', type=str, default='bert', required=False)
    parser.add_argument('--dataset', type=str, default='flickr30k', required=False)
    parser.add_argument('--fast_dev', type=bool, default=False)
    args = parser.parse_args()

    LoggingUtils.setup(LoggingUtils.INFO, 'baselineModel.log')
    OPTIMIZER_REGISTRY.register_classes(
        transformers.optimization, torch.optim.Optimizer, override=True
    )
    LR_SCHEDULER_REGISTRY.register_classes(
        transformers.optimization, torch.optim.lr_scheduler._LRScheduler, override=True
    )

    trainer = BaselineTrainer(
        args.image_encoder,
        args.text_decoder,
        args.dataset,
        args.fast_dev
    )
    trainer.train_model()
