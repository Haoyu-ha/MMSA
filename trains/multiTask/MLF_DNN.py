import os
import time
import argparse
import numpy as np
from glob import glob
from tqdm import tqdm

import torch.nn as nn
from torch import optim

from utils.functions import dict_to_str
from utils.metricsTop import MetricsTop

class EF_LSTM():
    def __init__(self, args):
        assert args.tasks in ['M']

        self.args = args
        self.criterion = nn.L1Loss()
        self.metrics = MetricsTop().getMetics(args.metricsName)

    def do_train(self, model, dataloader):
        optimizer = optim.Adam(model.parameters(), lr=self.args.learning_rate, weight_decay=self.args.weight_decay)
        # initilize results
        best_acc = 0
        epochs, best_epoch = 0, 0
        # loop util earlystop
        while True: 
            epochs += 1
            # train
            y_pred = {'M': [], 'T': [], 'A': [], 'V': []}
            y_true = {'M': [], 'T': [], 'A': [], 'V': []}
            losses = []
            model.train()
            train_loss = 0.0
            with tqdm(dataloader['train']) as td:
                for batch_data in td:
                    vision = batch_data['vision'].to(self.args.device)
                    audio = batch_data['audio'].to(self.args.device)
                    text = batch_data['text'].to(self.args.device)
                    labels = batch_data['labels']
                    for k in labels.keys():
                        labels[k] = labels[k].to(self.args.device).view(-1, 1)
                # clear gradient
                    # clear gradient
                    optimizer.zero_grad()
                    # forward
                    outputs = model(text, audio, vision)
                    # compute loss
                    loss = self.criterion(outputs, labels)
                    # backward
                    loss.backward()
                    # update
                    optimizer.step()
                    # store results
                    train_loss += loss.item()
                    y_pred.append(outputs[self.args.tasks].cpu())
                    y_true.append(labels[self.args.tasks].cpu())
            train_loss = train_loss / len(dataloader['train'])
            print("TRAIN-(%s) (%d/%d/%d)>> loss: %.4f " % (args.modelName, \
                        epochs - best_epoch, epochs, args.cur_time, train_loss))
            pred, true = torch.cat(y_pred), torch.cat(y_true)
            train_results = metrics(pred, true)
            print('%s: >> ' %(self.args.tasks) + dict_to_str(train_results))
            # validation
            val_results = do_test(model, dataloader['valid'], mode="VAL")
            val_acc = val_results[self.args.tasks][self.args.KeyEval]
            # save best model
            if val_acc > best_acc:
                best_acc, best_epoch = val_acc, epochs
                old_models = glob(os.path.join(args.model_save_path,\
                                    f'{self.args.modelName}-{self.args.datasetName}-{self.args.tasks}.pth'))
                for old_model_path in old_models:
                    os.remove(old_model_path)
                # save model
                new_model_path = os.path.join(args.model_save_path,\
                                    f'{self.args.modelName}-{self.args.datasetName}-{self.args.tasks}.pth')
                torch.save(model.cpu().state_dict(), new_model_path)
                model.to(self.args.device)
            # early stop
            if epochs - best_epoch >= args.early_stop:
                return

    def do_test(self, model, dataloader, mode="VAL"):
        model.eval()
        y_pred, y_true = [], []
        eval_loss = 0.0
        with torch.no_grad():
            with tqdm(dataloader) as td:
                for batch_data in td:
                    vision = batch_data['vision'].to(self.args.device)
                    audio = batch_data['audio'].to(self.args.device)
                    text = batch_data['text'].to(self.args.device)
                    labels = batch_data['labels'][self.args.tasks].to(self.args.device).view(-1, 1)
                    outputs = model(text, audio, vision)
                    loss = self.criterion(outputs, labels)
                    eval_loss += loss.item()
                    y_pred.append(outputs[self.args.tasks].cpu())
                    y_true.append(labels[self.args.tasks].cpu())
        eval_loss = eval_loss / len(dataloader)
        print(mode+"-(%s)" % self.args.modelName + " >> loss: %.4f " % eval_loss)
        pred, true = torch.cat(y_pred), torch.cat(y_true)
        results = metrics(pred, true)
        print('%s: >> ' %(self.args.tasks) + dict_to_str(results))
        return results