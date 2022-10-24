import torch
from torch import nn
from transformers import VisionEncoderDecoderModel
from transformers import BeitModel, BeitFeatureExtractor
from transformers import BertTokenizer, BertModel
import pytorch_lightning as pl
from evaluate import compute_bleu_scores

class BaselineModel(pl.LightningModule):

    def __init__(self,
                 image_encoder,
                 text_decoder,
                 beam_size=5,
                 ):

        super(BaselineModel, self).__init__()

        # if torch.cuda.is_available():
        #     self.device = torch.device('gpu')
        # else:
        #     self.device = torch.device('cpu')

        if image_encoder.lower() == 'beit':
            image_feature_extractor = BeitFeatureExtractor.from_pretrained("microsoft/beit-base-patch16-224-pt22k")
            image_encoder_path = "microsoft/beit-base-patch16-224-pt22k"

        if text_decoder.lower() == 'bert':
            decoder_tokenizer = BertTokenizer.from_pretrained("bert-base-uncased")
            text_decoder_path = "bert-base-uncased"

        self.model = VisionEncoderDecoderModel.from_encoder_decoder_pretrained(
            image_encoder_path,
            text_decoder_path,
        )
        self.image_feature_extractor = image_feature_extractor
        self.decoder_tokenizer = decoder_tokenizer
        self.model.config.decoder_start_token_id = self.decoder_tokenizer.cls_token_id
        self.model.config.pad_token_id = self.decoder_tokenizer.pad_token_id
        self.beam_size = beam_size

        self.save_hyperparameters()

    def forward(self, *args, **kwargs):
        return self.model(*args, **kwargs)

    def configure_optimizers(self):

        lr_config = {
            'max_lr': 0.001,
            'pct_start': 0.1,
            'div_factor': 1,
            'total_steps': 50,
            'anneal_strategy': 'linear'
        }
        optimizer = torch.optim.AdamW(self.model.parameters(), lr=0.001, eps=1e-8, weight_decay=0.01)
        lr_scheduler = torch.optim.lr_scheduler.OneCycleLR(optimizer, **lr_config)
        return {
            "optimizer": optimizer,
            "lr_scheduler": lr_scheduler,
        }

    def training_step(self, batch, batch_idx):

        inputs, labels = batch
        outputs = self.model(
            inputs, labels=labels, return_dict=True
        )
        train_loss = outputs.loss
        self.log_dict({"loss/train": train_loss.item()}, on_step=True)
        return train_loss

    def validation_step(self,batch, batch_idx):

        inputs, labels = batch
        outputs = self.model(
            inputs, labels=labels, return_dict=True
        )
        val_loss = outputs.loss
        output_sequences = self.model.generate(inputs)

        output_sequences, target_seq = self.detokenize(output_sequences), self.detokenize(labels)
        _, bleu_scores = compute_bleu_scores(output_sequences, target_seq)

        s = ''
        for i,_ in enumerate(output_sequences):
            s += f"# Example {i}\n\n"
            s += f"- gold\n```\n{target_seq[i]}\n```\n\n"
            s += f"- pred\n```\n{output_sequences[i]}\n```\n\n"
            s += f"- metrics\n\n"
            s += f"Bleu score: {bleu_scores[i]}\n"
            s += "\n"
        self.logger.experiment.add_text("examples/val", s, global_step=self.global_step)
        self.log_dict({"loss/val": val_loss.item()}, on_step=True)
        return val_loss

    def detokenize(self, sequences):

        pred = []
        for seq in sequences:
            pred.append(self.decoder_tokenizer.decode(seq, skip_special_tokens=True))
        return pred