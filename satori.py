#!/usr/bin/env python

#from __future__ import print_function
import torch
from torch.utils import data
import torch.nn as nn
import torch.nn.functional as F
import torch.optim as optim
from torch.utils.data import Dataset, DataLoader
from torch.autograd import Variable
from torch.utils.data.sampler import SubsetRandomSampler
from torch.autograd import Function # import Function to create custom activations
from torch.nn.parameter import Parameter # import Parameter to create custom activations with learnable parameters
from torch import optim # import optimizers for demonstrations

from fastprogress import progress_bar
from scipy.special import comb  

import pdb

import pandas as pd
import numpy as np
from statsmodels.stats.multitest import multipletests

#from my_classes import BassetDataset
#from strat_sampler import StratifiedSampler
from torch.backends import cudnn
import numpy as np
from sklearn import metrics
from random import randint 

#from tqdm import tqdm
import math
import random

import pickle

#from gensim.models import Word2Vec
#from gensim.models.word2vec import LineSentence
#import gensim

#from skorch import NeuralNetRegressor
#from sklearn.model_selection import RandomizedSearchCV 

#from sklearn.model_selection import ParameterGrid
import os
import sys
from extract_motifs_deepRAM import get_motif

import matplotlib; matplotlib.use('Agg')
import matplotlib.pyplot as plt

import bottleneck as bn
from argparse import ArgumentParser 

from multiprocessing import Process
from multiprocessing import Pool

from scipy.stats import fisher_exact 
from statsmodels.stats.proportion import proportions_ztest
from scipy.stats import mannwhitneyu

import time
####################################################################################################################
##################################--------------Argument Parsing--------------######################################
def parseArgs():
    """Parse command line arguments
    
    Returns
    -------
    a : argparse.ArgumentParser
    
    """
    parser = ArgumentParser(description='Main deepSAMIREI script.')
    parser.add_argument('-v', '--verbose',dest='verbose', action='store_true', 
                        default=False, help="verbose output [default is quiet running]")
    
    parser.add_argument('-o','--outDir',dest='directory',type=str,
                        action='store',help="output directory", default='')
    parser.add_argument('-m','--mode', dest='mode',type=str,
                        action='store',help="Mode of operation: train or test.", default='train')     
    parser.add_argument('--deskload', dest='deskLoad',
                        action='store_true',default=False,
                        help="Load dataset from desk. If false, the data is converted into tensors and kept in main memory (not recommended for large datasets).")  
    parser.add_argument('-w','--numworkers',dest='numWorkers',type=int,
                        action='store',help="Number of workers used in data loader. For loading from the desk, use more than 1 for faster fetching. Also, this also determines number of workers used when inferring interactions.", default=1)        
    #parser.add_argument('-c','--cvtype',dest='cvtype',type=str,action='store',
    #                    help="Type of cross validation to use. Options are: chrom (leave-one-chrom-out), nfolds (N fold CV), and none (No CV, just regular train test split)",
    #                    default='none')
    #parser.add_argument('--numfolds',dest='numfolds',type=int,action='store',
    #                    help="Number of folds for N fold CV", default=10)
    parser.add_argument('--splittype',dest='splitType',type=str, action='store',
                        help="Either to use a percantage of data for valid,test or use specific chromosomes. In the later case, provide chrA,chrB for valid,test. Default value is percent and --splitperc value will be used.", default='percent')
    parser.add_argument('--splitperc',dest='splitperc',type=float, action='store',
                        help="Pecentages of test, and validation data splits, eg. 10 for 10 percent data used for testing and validation.", default=10)
    parser.add_argument('--motifanalysis', dest='motifAnalysis',
                        action='store_true',default=False,
                        help="Analyze CNN filters for motifs and search them against known TF database.")
    parser.add_argument('--scorecutoff',dest='scoreCutoff',type=float,
                        action='store',default=0.65,
                        help="In case of binary labels, the positive probability cutoff to use.")
    parser.add_argument('--tomtompath',dest='tomtomPath',
                        type=str,action='store',default=None,
                        help="Provide path to where TomTom (from MEME suite) is located.") 
    parser.add_argument('--database',dest='tfDatabase',type=str,action='store',
                        help="Provide path to the MEME TF database against which the CNN motifs are searched.", default=None)
    parser.add_argument('--annotate',dest='annotateTomTom',type=str,action='store',
                        default='No', help="Annotate tomtom motifs. The options are: 1. path to annotation file, 2. No (not to annotate the output)")                    
    parser.add_argument('-a','--attnfigs', dest='attnFigs',
                        action='store_true',default=False,
                        help="Generate Attention (matrix) figures for every test example.")
    parser.add_argument('-i','--interactions', dest='featInteractions',
                        action='store_true',default=False,
                        help="Self attention based feature(TF) interactions analysis.")
    parser.add_argument('-b','--background', dest='intBackground',type=str,
                        action='store',default=None,
                        help="Background used in interaction analysis: shuffle (for di-nucleotide shuffled sequences with embedded motifs.), negative (for negative test set). Default is not to use background (and significance test).")
    parser.add_argument('--attncutoff', dest='attnCutoff',type=float,
                        action='store',default=0.12,
                        help="Attention (probability) cutoff value to use while searching for maximum interaction. A value (say K) greater than 1.0 will mean using top K interaction values.") #In human promoter DHSs data analysis, lowering the cutoff leads to more TF interactions. 
    parser.add_argument('--intseqlimit', dest='intSeqLimit',type=int,
                        action='store',default = -1,
                        help="A limit on number of input sequences to test. Default is -1 (use all input sequences that qualify).")
    parser.add_argument('-s','--store', dest='storeInterCNN',
                        action='store_true',default=False,
                        help="Store per batch attention and CNN outpout matrices. If false, they are kept in the main memory.")
    parser.add_argument('--considertophit', dest='considerTopHit',
                        action='store_true',default=True,
                        help="[TO BE ADDED] Consider only the top matching TF/regulatory element for a filter (from TomTom results).")
    parser.add_argument('--numlabels', dest='numLabels',type=int,
                        action='store',default = 2,
                        help="Number of labels. 2 for binary (default). For multi-class, multi label problem, can be more than 2. ")
    parser.add_argument('--tomtomdist', dest='tomtomDist',type=str,
                        action='store',default = 'pearson',
                        help="TomTom distance parameter (pearson, kullback, ed etc). Default is pearson. See TomTom help from MEME suite.")
    parser.add_argument('--tomtompval', dest='tomtomPval',type=float,
                        action='store',default = 0.05,
                        help="Adjusted p-value cutoff from TomTom. Default is 0.05.")
    parser.add_argument('--testall', dest='testAll',
                        action='store_true',default=False,
                        help="Test on the entire dataset, including the training and validation sets (default False). Useful for interaction/motif analysis.")
    parser.add_argument('inputprefix', type=str,
                        help="Input file prefix for the data and the corresponding fasta file (sequences). Make sure the sequences are in .fa format whereas the metadata is tab delimited .txt format.")
    parser.add_argument('hparamfile',type=str,
                        help='Name of the hyperparameters file to be used.')
    
    
    
    args = parser.parse_args()
    #if not validateArgs( args ):
    #    raise Exception("Argument Errors: check arguments and usage!")
    return args



####################################################################################################################

####################################################################################################################
##############################################--------Main Network Class--------####################################

#credits: code taken from https://towardsdatascience.com/extending-pytorch-with-custom-activation-functions-2d8b065ef2fa
class soft_exponential(nn.Module):
    '''
    Implementation of soft exponential activation.
    Shape:
        - Input: (N, *) where * means, any number of additional
          dimensions
        - Output: (N, *), same shape as the input
    Parameters:
        - alpha - trainable parameter
    References:
        - See related paper:
        https://arxiv.org/pdf/1602.01321.pdf
    Examples:
        >>> a1 = soft_exponential(256)
        >>> x = torch.randn(256)
        >>> x = a1(x)
    '''
    def __init__(self, in_features, alpha = None):
        '''
        Initialization.
        INPUT:
            - in_features: shape of the input
            - aplha: trainable parameter
            aplha is initialized with zero value by default
        '''
        super(soft_exponential,self).__init__()
        self.in_features = in_features

        # initialize alpha
        if alpha == None:
            self.alpha = Parameter(torch.tensor(0.0)) # create a tensor out of alpha
        else:
            self.alpha = Parameter(torch.tensor(alpha)) # create a tensor out of alpha
            
        self.alpha.requiresGrad = True # set requiresGrad to true!

    def forward(self, x):
        '''
        Forward pass of the function.
        Applies the function to the input elementwise.
        '''
        if (self.alpha == 0.0):
            return x

        if (self.alpha < 0.0):
            return - torch.log(1 - self.alpha * (x + self.alpha)) / self.alpha

        if (self.alpha > 0.0):
            return (torch.exp(self.alpha * x) - 1)/ self.alpha + self.alpha

class PositionalEncoding(nn.Module):
    "Implement the PE function."
    def __init__(self, d_model, dropout, max_len=5000):
        super(PositionalEncoding, self).__init__()
        self.dropout = nn.Dropout(p=dropout)
       
        # Compute the positional encodings once in log space.
        pe = torch.zeros(max_len, d_model)
        position = torch.arange(0., max_len).unsqueeze(1)
        div_term = torch.exp(torch.arange(0., d_model, 2) *
                             -(math.log(10000.0) / d_model))
        pe[:, 0::2] = torch.sin(position * div_term)
        pe[:, 1::2] = torch.cos(position * div_term)
        pe = pe.unsqueeze(0)
        self.register_buffer('pe', pe)
       
    def forward(self, x):
        x = x + Variable(self.pe[:, :x.size(1)],
                         requires_grad=False)
        return self.dropout(x)
    
class Generalized_Net(nn.Module):
    def __init__(self, params, genPAttn=True, wvmodel=None, numClasses = 2):
        super(Generalized_Net, self).__init__()
        
        #if embedding:
        #model1 = gensim.models.Word2Vec.load(word2vec_model)
        
        self.embSize = params['embd_size']#embSize
        self.numMultiHeads = 8#numMultiHeads
        self.SingleHeadSize = params['singlehead_size']#SingleHeadSize
        self.MultiHeadSize = params['multihead_size']#MultiHeadSize
        self.usepooling = params['usepooling']
        self.pooling_val = params['pooling_val']
        self.readout_strategy = params['readout_strategy']
        self.kmerSize = params['kmer_size']
        self.useRNN = params['use_RNN']
        self.useCNN = params['use_CNN']
        self.usePE = params['use_posEnc']
        self.useCNNpool = params['use_CNNpool']
        self.RNN_hiddenSize = params['RNNhiddenSize']
        self.numCNNfilters = params['CNN_filters']
        self.filterSize = params['CNN_filtersize']
        self.CNNpoolSize = params['CNN_poolsize']
        self.numClasses = numClasses
        #self.seqLen
        
        self.genPAttn = genPAttn
        
        #weights = torch.FloatTensor(wvmodel.wv.vectors)
        #self.embedding = nn.Embedding.from_pretrained(weights, freeze=False) #False before
        if wvmodel == None:
            self.numInputChannels = params['input_channels'] #number of channels, one hot encoding
        else:
            self.numInputChannels = self.embSize
        
        if self.usePE:
            self.pe = PositionalEncoding(d_model = self.numInputChannels, dropout=0.1)
        
        if self.useCNN and self.useCNNpool:
            self.layer1  = nn.Sequential(nn.Conv1d(in_channels=self.numInputChannels, out_channels=self.numCNNfilters,
                                         kernel_size=self.filterSize, padding=6),nn.BatchNorm1d(num_features=self.numCNNfilters),
                                         nn.ReLU(),nn.MaxPool1d(kernel_size=self.CNNpoolSize))
            self.dropout1 = nn.Dropout(p=0.2)
        
        if self.useCNN and self.useCNNpool == False:
            self.layer1  = nn.Sequential(nn.Conv1d(in_channels=self.numInputChannels, out_channels=self.numCNNfilters,
                                         kernel_size=self.filterSize, padding=6),
                                         nn.BatchNorm1d(num_features=self.numCNNfilters),nn.ReLU())
            self.dropout1 = nn.Dropout(p=0.2)
        
        if self.useRNN:
            self.RNN = nn.LSTM(self.numInputChannels if self.useCNN==False else self.numCNNfilters, self.RNN_hiddenSize, num_layers=2, bidirectional=True)
            self.dropoutRNN = nn.Dropout(p=0.4)
            self.Q = nn.ModuleList([nn.Linear(in_features=2*self.RNN_hiddenSize, out_features=self.SingleHeadSize) for i in range(0,self.numMultiHeads)])
            self.K = nn.ModuleList([nn.Linear(in_features=2*self.RNN_hiddenSize, out_features=self.SingleHeadSize) for i in range(0,self.numMultiHeads)])
            self.V = nn.ModuleList([nn.Linear(in_features=2*self.RNN_hiddenSize, out_features=self.SingleHeadSize) for i in range(0,self.numMultiHeads)])
        
        if self.useRNN == False and self.useCNN == False:
            self.Q = nn.ModuleList([nn.Linear(in_features=self.numInputChannels, out_features=self.SingleHeadSize) for i in range(0,self.numMultiHeads)])
            self.K = nn.ModuleList([nn.Linear(in_features=self.numInputChannels, out_features=self.SingleHeadSize) for i in range(0,self.numMultiHeads)])
            self.V = nn.ModuleList([nn.Linear(in_features=self.numInputChannels, out_features=self.SingleHeadSize) for i in range(0,self.numMultiHeads)])
        
        if self.useRNN == False and self.useCNN == True:
            self.Q = nn.ModuleList([nn.Linear(in_features=self.numCNNfilters, out_features=self.SingleHeadSize) for i in range(0,self.numMultiHeads)])
            self.K = nn.ModuleList([nn.Linear(in_features=self.numCNNfilters, out_features=self.SingleHeadSize) for i in range(0,self.numMultiHeads)])
            self.V = nn.ModuleList([nn.Linear(in_features=self.numCNNfilters, out_features=self.SingleHeadSize) for i in range(0,self.numMultiHeads)])
            
        
        self.RELU = nn.ModuleList([nn.ReLU() for i in range(0,self.numMultiHeads)])
        
        self.MultiHeadLinear = nn.Linear(in_features=self.SingleHeadSize*self.numMultiHeads, out_features=self.MultiHeadSize)#50
        
        self.MHReLU = nn.ReLU()
        
    
        self.fc3 = nn.Linear(in_features=self.MultiHeadSize, out_features=self.numClasses)
    
#Credits: code from: http://nlp.seas.harvard.edu/2018/04/01/attention.html      
    def attention(self, query, key, value, mask=None, dropout=0.0):
        "Compute 'Scaled Dot Product Attention'"
        d_k = query.size(-1)
        scores = torch.matmul(query, key.transpose(-2, -1)) / math.sqrt(d_k)

        p_attn = F.softmax(scores, dim = -1)

        p_attn = F.dropout(p_attn, p=dropout)
        return torch.matmul(p_attn, value), p_attn
    
    def forward(self, inputs):
        #pdb.set_trace()

        output = inputs
        if self.usePE:
            output = self.pe(output)
        
        if self.useCNN:
            output = self.layer1(output)
            output = self.dropout1(output)
            output = output.permute(0,2,1)
        
        if self.useRNN:
            output, _ = self.RNN(output)
            F_RNN = output[:,:,:self.RNN_hiddenSize]
            R_RNN = output[:,:,self.RNN_hiddenSize:] #before I wrote :self.RNN_hiddenSize for the reverse part too (forwarnRNNonly results are based on that). That is basically forward RNN concatenated with itself (perhaps very similar to single direction LSTM)
            output = torch.cat((F_RNN,R_RNN),2)
            output = self.dropoutRNN(output)
        
        pAttn_concat = torch.Tensor([]).to(device)
        attn_concat = torch.Tensor([]).to(device)
        for i in range(0,self.numMultiHeads):
            query, key, value = self.Q[i](output), self.K[i](output), self.V[i](output)
            attnOut,p_attn = self.attention(query, key, value, dropout=0.2)
            attnOut = self.RELU[i](attnOut)
            if self.usepooling:
                attnOut = self.MAXPOOL[i](attnOut.permute(0,2,1)).permute(0,2,1)
            attn_concat = torch.cat((attn_concat,attnOut),dim=2)
            if self.genPAttn:
                pAttn_concat = torch.cat((pAttn_concat, p_attn), dim=2)
        
        output = self.MultiHeadLinear(attn_concat)
        
        output = self.MHReLU(output)

        if self.readout_strategy == 'normalize':
            output = output.sum(axis=1)
            output = (output-output.mean())/output.std()

        output = self.fc3(output)
    
        assert not torch.isnan(output).any()
    
        return output,pAttn_concat
    
######################################################################################################################   

######################################################################################################################
#####################################-------------------Data Processing Code------------##############################

##--------This is used when --deskload argument is NOT used. All data points are read and tensors are kept in memory.---------#
class ProcessedDataVersion2(Dataset):
    def __init__(self, df_path, num_labels = 2, for_embeddings=False):
        self.DNAalphabet = {'A':'0', 'C':'1', 'G':'2', 'T':'3'}
        df_path = df_path.split('.')[0] #just in case the user provide extension
        self.df_all = pd.read_csv(df_path+'.txt',delimiter='\t',header=None)
        self.df_seq = pd.read_csv(df_path+'.fa',header=None)
        strand = self.df_seq[0][0][-3:] #can be (+) or (.) 
        self.df_all['header'] = self.df_all.apply(lambda x: '>'+x[0]+':'+str(x[1])+'-'+str(x[2])+strand, axis=1)
        
        self.chroms = self.df_all[0].unique()
        self.df_seq_all = pd.concat([self.df_seq[::2].reset_index(drop=True), self.df_seq[1::2].reset_index(drop=True)], axis=1, sort=False)
        self.df_seq_all.columns = ["header","sequence"]
        #self.df_seq_all['chrom'] = self.df_seq_all['header'].apply(lambda x: x.strip('>').split(':')[0])
        self.df_seq_all['sequence'].apply(lambda x: x.upper())
        self.num_labels = num_labels
        
        self.df = self.df_all
        self.df_seq_final = self.df_seq_all
            

        self.df = self.df.reset_index()
        self.df_seq_final = self.df_seq_final.reset_index()
        #self.df['header'] = self.df.apply(lambda x: '>'+x[0]+':'+str(x[1])+'-'+str(x[2])+'('+x[5]+')', axis=1)
        if for_embeddings == False:
            self.One_hot_Encoded_Tensors = []
            self.Label_Tensors = []
            self.Seqs = []
            self.Header = []
            for i in progress_bar(range(0,self.df.shape[0])): #tqdm() before
                if self.num_labels == 2:
                    y = self.df[self.df.columns[-2]][i]
                else:
                    y = np.asarray(self.df[self.df.columns[-2]][i].split(',')).astype(int)
                    y = self.one_hot_encode_labels(y)
                header = self.df['header'][i]
                self.Header.append(header)
                X = self.df_seq_final['sequence'][self.df_seq_final['header']==header].array[0].upper()
                X = X.replace('N',list(self.DNAalphabet.keys())[randint(0,3)])
                X = X.replace('N',list(self.DNAalphabet.keys())[random.choice([0,1,2,3])])
                X = X.replace('S',list(self.DNAalphabet.keys())[random.choice([1,2])])
                X = X.replace('W',list(self.DNAalphabet.keys())[random.choice([0,3])])
                X = X.replace('K',list(self.DNAalphabet.keys())[random.choice([2,3])])
                X = X.replace('Y',list(self.DNAalphabet.keys())[random.choice([1,3])])
                X = X.replace('R',list(self.DNAalphabet.keys())[random.choice([0,2])])
                X = X.replace('M',list(self.DNAalphabet.keys())[random.choice([0,1])])
                self.Seqs.append(X)
                X = self.one_hot_encode(X)
                self.One_hot_Encoded_Tensors.append(torch.tensor(X))
                self.Label_Tensors.append(torch.tensor(y))
        
    def __len__(self):
        return self.df.shape[0]
    
    def get_all_data(self):
        return self.df, self.df_seq_final
    
    def get_all_chroms(self):
        return self.chroms
    
    def one_hot_encode(self,seq):
        mapping = dict(zip("ACGT", range(4)))    
        seq2 = [mapping[i] for i in seq]
        return np.eye(4)[seq2].T.astype(np.long)
  
    def one_hot_encode_labels(self,y):
        lbArr = np.zeros(self.num_labels)
        lbArr[y] = 1
        return lbArr.astype(np.float)
    
    def __getitem__(self, idx):
        return self.Header[idx],self.Seqs[idx],self.One_hot_Encoded_Tensors[idx],self.Label_Tensors[idx]


##--------This is used when --deskload argument is used. Batches of data are read from the desk----------#
class ProcessedDataVersion2A(Dataset): 
    def __init__(self, df_path, num_labels = 2, for_embeddings=False):
        self.DNAalphabet = {'A':'0', 'C':'1', 'G':'2', 'T':'3'}
        df_path = df_path.split('.')[0] #just in case the user provide extension
        self.df_all = pd.read_csv(df_path+'.txt',delimiter='\t',header=None)
        self.df_seq = pd.read_csv(df_path+'.fa',header=None)
        strand = self.df_seq[0][0][-3:] #can be (+) or (.) 
        self.df_all['header'] = self.df_all.apply(lambda x: '>'+x[0]+':'+str(x[1])+'-'+str(x[2])+strand, axis=1)

        
        self.chroms = self.df_all[0].unique()
        self.df_seq_all = pd.concat([self.df_seq[::2].reset_index(drop=True), self.df_seq[1::2].reset_index(drop=True)], axis=1, sort=False)
        self.df_seq_all.columns = ["header","sequence"]
        #self.df_seq_all['chrom'] = self.df_seq_all['header'].apply(lambda x: x.strip('>').split(':')[0])
        self.df_seq_all['sequence'].apply(lambda x: x.upper())
        self.num_labels = num_labels
        
        self.df = self.df_all
        self.df_seq_final = self.df_seq_all
            

        self.df = self.df.reset_index()
        self.df_seq_final = self.df_seq_final.reset_index()
        #self.df['header'] = self.df.apply(lambda x: '>'+x[0]+':'+str(x[1])+'-'+str(x[2])+'('+x[5]+')', axis=1)
        
    def __len__(self):
        return self.df.shape[0]
    
    def get_all_data(self):
        return self.df, self.df_seq_final
    
    def get_all_chroms(self):
        return self.chroms
    
    def one_hot_encode(self,seq):
        mapping = dict(zip("ACGT", range(4)))    
        seq2 = [mapping[i] for i in seq]
        return np.eye(4)[seq2].T.astype(np.long)
  
    def one_hot_encode_labels(self,y):
        lbArr = np.zeros(self.num_labels)
        lbArr[y] = 1
        return lbArr.astype(np.float)
    
    def __getitem__(self, idx):
        if self.num_labels == 2:
            y = self.df[self.df.columns[-2]][idx]
        else:
            y = np.asarray(self.df[self.df.columns[-2]][idx].split(',')).astype(int)
            y = self.one_hot_encode_labels(y)
        header = self.df['header'][idx]
        X = self.df_seq_final['sequence'][self.df_seq_final['header']==header].array[0].upper()
        X = X.replace('N',list(self.DNAalphabet.keys())[randint(0,3)])
        X = X.replace('N',list(self.DNAalphabet.keys())[random.choice([0,1,2,3])])
        X = X.replace('S',list(self.DNAalphabet.keys())[random.choice([1,2])])
        X = X.replace('W',list(self.DNAalphabet.keys())[random.choice([0,3])])
        X = X.replace('K',list(self.DNAalphabet.keys())[random.choice([2,3])])
        X = X.replace('Y',list(self.DNAalphabet.keys())[random.choice([1,3])])
        X = X.replace('R',list(self.DNAalphabet.keys())[random.choice([0,2])])
        X = X.replace('M',list(self.DNAalphabet.keys())[random.choice([0,1])])
        seq = X 
        X = self.one_hot_encode(X)
        return header,seq,torch.tensor(X),torch.tensor(y)

        
#######################################################################################################################

#######################################################################################################################
################################--------------Train and Evaluate Functions---------------##############################

#---Train for Multi Class probelm---#
def trainRegularMC(model, device, iterator, optimizer, criterion):
    model.train()
    running_loss = 0.0
    train_auc = []
    all_labels = []
    all_preds = []
    count = 0
    #pdb.set_trace()
    for batch_idx, (headers, seqs, data, target) in enumerate(iterator):
        #pdb.set_trace()
        data, target = data.to(device,dtype=torch.float), target.to(device,dtype=torch.float)
        optimizer.zero_grad()
        outputs,_ = model(data)
        loss = criterion(outputs, target)
        #loss = F.binary_cross_entropy(outputs, target)
        
        labels = target.cpu().numpy()
        
        softmax = torch.nn.Softmax(dim=0) #along columns
        pred = softmax(outputs)
        
        pred = pred.cpu().detach().numpy()
        
        all_labels+=labels.tolist()
        all_preds+=pred.tolist()

        loss.backward()
        optimizer.step()

        running_loss += loss.item()
        

    for j in range(0, len(all_labels[0])):
        cls_labels = np.asarray(all_labels)[:,j]
        pred_probs = np.asarray(all_preds)[:,j]
        auc_score = metrics.roc_auc_score(cls_labels.astype(int),pred_probs)
        train_auc.append(auc_score)
    
 
    return running_loss/len(train_loader),train_auc

#---Train for binary Class probelm---#
def trainRegular(model, device, iterator, optimizer, criterion):
    model.train()
    running_loss = 0.0
    train_auc = []
    for batch_idx, (headers, seqs, data, target) in enumerate(iterator):
        #pdb.set_trace()
        data, target = data.to(device,dtype=torch.float), target.to(device,dtype=torch.long)
        optimizer.zero_grad()
        outputs,_ = model(data)
        loss = criterion(outputs, target)
        #loss = F.binary_cross_entropy(outputs, target)
        
        labels = target.cpu().numpy()
        
        softmax = torch.nn.Softmax(dim=1)
        pred = softmax(outputs)
        pred = pred.cpu().detach().numpy()
        #print(pred)
        try:
            train_auc.append(metrics.roc_auc_score(labels, pred[:,1]))
        except:
            train_auc.append(0.0)

        loss.backward()
        optimizer.step()

        running_loss += loss.item()
        #return outputs
    return running_loss/len(train_loader),train_auc

#----evaluate for multi class problem----#
def evaluateRegularMC(net, iterator, criterion, out_dirc, getPAttn=False, storePAttn = False, getCNN=False, storeCNNout = False, getSeqs = False):
    
    running_loss = 0.0
    valid_auc = []
    
    net.eval()
    
    roc = np.asarray([[],[]]).T
    PAttn_all = {}
    all_labels = []
    all_preds = []
    
    
    running_loss = 0.0
    valid_auc = []
    
    net.eval()
    
    #embd = net.embedding #get the embeddings, we need that for first conv layer
    CNNlayer = net.layer1[0:3] #first conv layer without the maxpooling part

    #embd.eval()
    CNNlayer.eval()
    
    roc = np.asarray([[],[]]).T
    PAttn_all = {}
    
    per_batch_labelPreds = {}
    per_batch_CNNoutput = {}
    per_batch_testSeqs = {}
    per_batch_info = {}
    
    
    with torch.no_grad():
    
        for batch_idx, (headers, seqs, data, target) in enumerate(iterator):

            data, target = data.to(device,dtype=torch.float), target.to(device, dtype=torch.float)
            # Model computations
            outputs,PAttn = net(data)
            
            loss = criterion(outputs, target)
            #loss = F.binary_cross_entropy(outputs, target)
            
            labels=target.cpu().numpy()
            
            softmax = torch.nn.Softmax(dim=0) #along columns
            pred = softmax(outputs)
            pred = pred.cpu().detach().numpy()
        
            #pred = pred.cpu().detach().numpy()
        
            all_labels+=labels.tolist()
            all_preds+=pred.tolist()
            
            label_pred = {'labels':labels,'preds':pred}
            
            per_batch_labelPreds[batch_idx] = label_pred
            
            #softmax = torch.nn.Softmax(dim=1)
            
            
            #labels=target.cpu().numpy()
            
            #pred = softmax(outputs)
            #print(pred)
            #valid_auc.append(metrics.roc_auc_score(labels, pred))
            
            #pred = torch.argmax(pred, dim=1)
            if getPAttn == True:
                if storePAttn == True:
                    output_dir = out_dirc
                    if not os.path.exists(output_dir):
                        os.makedirs(output_dir)                 
                    with open(output_dir+'/PAttn_batch-'+str(batch_idx)+'.pckl','wb') as f:
                        pickle.dump(PAttn.cpu().detach().numpy(),f)
                    PAttn_all[batch_idx] = output_dir+'/PAttn_batch-'+str(batch_idx)+'.pckl' #paths to the pickle PAttention
                else:
                    PAttn_all[batch_idx] = PAttn.cpu().detach().numpy()
            #pred = torch.argmax(pred, dim=1)
            #pred=pred.cpu().detach().numpy()
            
            if getCNN == True:
                outputCNN = CNNlayer(data)
                if storeCNNout == True:
                    output_dir = out_dirc
                    if not os.path.exists(output_dir):
                        os.makedirs(output_dir) 
                    with open(output_dir+'/CNNout_batch-'+str(batch_idx)+'.pckl','wb') as f:
                        pickle.dump(outputCNN.cpu().detach().numpy(),f)
                    per_batch_CNNoutput[batch_idx] = output_dir+'/CNNout_batch-'+str(batch_idx)+'.pckl'
                else:
                    per_batch_CNNoutput[batch_idx] = outputCNN.cpu().detach().numpy()
                    
                    
            if getSeqs == True:
                per_batch_testSeqs[batch_idx] = np.column_stack((headers,seqs))
            
            #label_pred = np.column_stack((labels,pred[:,1]))
            #roc = np.row_stack((roc,label_pred))
            #print(pred)
            #try:
            #    valid_auc.append(metrics.roc_auc_score(labels, pred[:,1]))
            #except:
            #    valid_auc.append(0.0)
            

            
            running_loss += loss.item()
    
    for j in range(0, len(all_labels[0])):
        cls_labels = np.asarray(all_labels)[:,j]
        pred_probs = np.asarray(all_preds)[:,j]
        auc_score = metrics.roc_auc_score(cls_labels.astype(int),pred_probs)
        valid_auc.append(auc_score)
        
    return running_loss/len(iterator),valid_auc,roc,PAttn_all,per_batch_labelPreds,per_batch_CNNoutput,per_batch_testSeqs  


             
#---evaluate for binary class problem-----#
def evaluateRegular(net, iterator, criterion,out_dirc,getPAttn=False, storePAttn = False, getCNN=False, storeCNNout = False, getSeqs = False):
    
    running_loss = 0.0
    valid_auc = []
    
    net.eval()
    
    #embd = net.embedding #get the embeddings, we need that for first conv layer
    CNNlayer = net.layer1[0:3] #first conv layer without the maxpooling part

    #embd.eval()
    CNNlayer.eval()
    
    roc = np.asarray([[],[]]).T
    PAttn_all = {}
    
    per_batch_labelPreds = {}
    per_batch_CNNoutput = {}
    per_batch_testSeqs = {}
    per_batch_info = {}
    
    with torch.no_grad():
    
        for batch_idx, (headers, seqs, data, target) in enumerate(iterator):

            data, target = data.to(device,dtype=torch.float), target.to(device,dtype=torch.long)
            # Model computations
            outputs,PAttn = net(data)
            
            loss = criterion(outputs, target)
            #loss = F.binary_cross_entropy(outputs, target)
            
            softmax = torch.nn.Softmax(dim=1)
            
            
            labels=target.cpu().numpy()
            
            pred = softmax(outputs)
            
            #print(pred)
            #valid_auc.append(metrics.roc_auc_score(labels, pred))
            if getPAttn == True:
                if storePAttn == True:
                    output_dir = out_dirc
                    if not os.path.exists(output_dir):
                        os.makedirs(output_dir) 
                    with open(output_dir+'/PAttn_batch-'+str(batch_idx)+'.pckl','wb') as f:
                        pickle.dump(PAttn.cpu().detach().numpy(),f)
                    PAttn_all[batch_idx] = output_dir+'/PAttn_batch-'+str(batch_idx)+'.pckl' #paths to the pickle PAttention
                else:
                    PAttn_all[batch_idx] = PAttn.cpu().detach().numpy()
            #pred = torch.argmax(pred, dim=1)
            pred=pred.cpu().detach().numpy()
            
            label_pred = np.column_stack((labels,pred[:,1]))
            per_batch_labelPreds[batch_idx] = label_pred
            roc = np.row_stack((roc,label_pred))
            
            #print(pred)
            try:
                valid_auc.append(metrics.roc_auc_score(labels, pred[:,1]))
            except:
                valid_auc.append(0.0)
            
            
            running_loss += loss.item()
            
            
            #outputEmb = embd(data)
            #outputEmb = outputEmb.permute(0,2,1) #to make it compatible with next layer (CNN)
            outputCNN = CNNlayer(data).cpu().detach().numpy()


            #per_batch_Embdoutput[batch_idx] = outputEmb
            #per_batch_CNNoutput[batch_idx] = outputCNN
            if getCNN == True:
                outputCNN = CNNlayer(data)
                if storeCNNout == True:
                    output_dir = out_dirc
                    if not os.path.exists(output_dir):
                        os.makedirs(output_dir) 
                    with open(output_dir+'/CNNout_batch-'+str(batch_idx)+'.pckl','wb') as f:
                        pickle.dump(outputCNN.cpu().detach().numpy(),f)
                    per_batch_CNNoutput[batch_idx] = output_dir+'/CNNout_batch-'+str(batch_idx)+'.pckl'
                else:
                    per_batch_CNNoutput[batch_idx] = outputCNN.cpu().detach().numpy()


            #batch_test_indices = test_indices[batch_idx*batchSize:(batch_idx*batchSize)+batchSize]

            #batch_test_seqs = np.asarray(data_all.df_seq_all['sequence'][batch_test_indices])
            #batch_test_targets = np.asarray(data_all.df_all[7][batch_test_indices])
            
            if getSeqs == True:
                per_batch_testSeqs[batch_idx] = np.column_stack((headers,seqs))
            #per_batch_info[batch_idx] = [batch_test_targets,target]
            
            
    labels = roc[:,0]
    preds = roc[:,1]
    valid_auc = metrics.roc_auc_score(labels,preds)
        
    return running_loss/len(iterator),valid_auc,roc,PAttn_all,per_batch_labelPreds,per_batch_CNNoutput,per_batch_testSeqs    
    

    
########################################################################################################################

########################################################################################################################
##########################------------------Other Functions--------------------#########################################
########################################################################################################################

#----Credits: https://gist.github.com/tomerfiliba/3698403----#
#get top N values from an ND array
def top_n_indexes(arr, n):
    idx = bn.argpartition(arr, arr.size-n, axis=None)[-n:] #argparsort originally but new bottleneck doesn't have that
    width = arr.shape[1]
    return [divmod(i, width) for i in idx]
#------------------------------------------------------------#

#--------Get shuffled background-----------#
from deeplift_dinuc_shuffle import *
from Bio.motifs import minimal

def get_shuffled_background(tst_loader,argspace): #this function randomly embed the consensus sequence of filter motifs in shuffled input sequences
    labels_array = np.asarray([i for i in range(0,argSpace.numLabels)])
    final_fa = []
    final_bed = []
    for batch_idx, (headers,seqs,_,batch_targets) in enumerate(tst_loader):
        for i in range (0, len(headers)):
            header = headers[i]
            seq = seqs[i]
            targets = batch_targets[i]
            dinuc_shuffled_seq = dinuc_shuffle(seq)
            hdr = header.strip('>').split('(')[0]
            chrom = hdr.split(':')[0]
            start,end = hdr.split(':')[1].split('-')
            final_fa.append([header,seq])
            
            if type(targets) == torch.Tensor:
                targets = targets.cpu().detach().numpy()
                
            target = targets.astype(int)
            
            labels = ','.join(labels_array[np.where(target==1)].astype(str)) 
            
            final_bed.append([chrom,start,end,'.',labels])
    
    
    final_fa_to_write = []
    #--load motifs
    with open(argspace.directory+'/Motif_Analysis/filters_meme.txt') as f:
        filter_motifs = minimal.read(f)
    
    motif_len = filter_motifs[0].length
    
    seq_numbers = [i for i in range(0,len(final_bed))]  
    seq_positions = [i for i in range(0,len(final_fa[0][1])-motif_len)] #can't go beyond end of sequence so have to subtract motif_len
    for i in progress_bar(range(0, len(filter_motifs))):
        motif = filter_motifs[i]
        consensus = motif.consensus
        num_occ = motif.num_occurrences
        random_seqs = random.choices(seq_numbers, k = num_occ) #randomly picking num_occ sequences (note that num_occ can be greater than population in this case since a single sequence can have multile occurence of a filter activation)
        #print(num_occ, len(seq_positions))
        random_positions = random.choices(seq_positions, k = num_occ) #randomly pick a position for a motif to occur
        
        for seq_index, pos in zip(random_seqs,random_positions):
            seq = final_fa[seq_index][1]
            seq = seq[:pos]+str(motif.consensus)+seq[pos+len(motif.consensus):]
            
            final_fa[seq_index][1] = seq
    
    out_directory = argspace.directory+'/Temp_Data'
    if not os.path.exists(out_directory):
        os.makedirs(out_directory)
    
    np.savetxt(out_directory+'/'+'shuffled_background.fa',np.asarray(final_fa).flatten(),fmt='%s')
    np.savetxt(out_directory+'/'+'shuffled_background.txt',np.asarray(final_bed), fmt='%s',delimiter='\t')
    
    return out_directory+'/'+'shuffled_background' #name of the prefix to use
    #
    #return final_bed,final_fa
        


def get_shuffled_background_v2(tst_loader, num_filters, motif_len, argspace): #this function uses the actual filter activation k-mers to embed them randomly in the shuffled input sequences (instead of using the filter's consensus)
    labels_array = np.asarray([i for i in range(0,argSpace.numLabels)])
    final_fa = []
    final_bed = []
    for batch_idx, (headers,seqs,_,batch_targets) in enumerate(tst_loader):
        for i in range (0, len(headers)):
            header = headers[i]
            seq = seqs[i]
            targets = batch_targets[i]
            dinuc_shuffled_seq = dinuc_shuffle(seq)
            hdr = header.strip('>').split('(')[0]
            chrom = hdr.split(':')[0]
            start,end = hdr.split(':')[1].split('-')
            final_fa.append([header,seq])
            
            if type(targets) == torch.Tensor:
                targets = targets.cpu().detach().numpy()
                
            target = targets.astype(int)
            
            labels = ','.join(labels_array[np.where(target==1)].astype(str)) 
            
            final_bed.append([chrom,start,end,'.',labels])
    
    
    final_fa_to_write = []
    #--load motifs
    #with open(argspace.directory+'/Motif_Analysis/filters_meme.txt') as f:
    #   filter_motifs = minimal.read(f)
    
    #motif_len = filter_motifs[0].length
    
    seq_numbers = [i for i in range(0,len(final_bed))]  
    seq_positions = [i for i in range(0,len(final_fa[0][1])-motif_len)] #can't go beyond end of sequence so have to subtract motif_len
    for i in progress_bar(range(0, num_filters)):
        motif = np.loadtxt(argspace.directory+'/Motif_Analysis/filter'+str(i)+'_logo.fa',dtype=str)        #filter_motifs[i]
        #consensus = motif.consensus
        num_occ = int(len(motif)/2) #fasta file is twice the size (with header and seq on separate lines)
        random_seqs = random.choices(seq_numbers, k = num_occ) #randomly picking num_occ sequences (note that num_occ can be greater than population in this case since a single sequence can have multile occurence of a filter activation)
        #print(num_occ, len(seq_positions))
        random_positions = random.choices(seq_positions, k = num_occ) #randomly pick a position for a motif to occur
        
        count = 1
        for seq_index, pos in zip(random_seqs,random_positions):
            emb_kmer = motif[count]
            seq = final_fa[seq_index][1]
            seq = seq[:pos]+emb_kmer+seq[pos+len(emb_kmer):]
            
            final_fa[seq_index][1] = seq
            count += 2
    
    out_directory = argspace.directory+'/Temp_Data'
    if not os.path.exists(out_directory):
        os.makedirs(out_directory)
    
    np.savetxt(out_directory+'/'+'shuffled_background.fa',np.asarray(final_fa).flatten(),fmt='%s')
    np.savetxt(out_directory+'/'+'shuffled_background.txt',np.asarray(final_bed), fmt='%s',delimiter='\t')
    
    return out_directory+'/'+'shuffled_background' #name of the prefix to use
        
        
    ######--------For random embedding of filter seqs-------------######
###########background v3#########
def get_random_seq(pwm,alphabet=['A','C','G','T']):
    seq = ''
    for k in range(0,pwm.shape[0]):
        nc = np.random.choice(alphabet,1,p=pwm[k,:])
        seq += nc[0]
    return seq
        
    
def get_shuffled_background_v3(tst_loader,argspace): #this function is similar to the first one (get_shuffled_background()) however, instead of using consensus, it generates a random sequences (of same size as the PWM) based on the probability distributions in the matrix
    labels_array = np.asarray([i for i in range(0,argSpace.numLabels)])
    final_fa = []
    final_bed = []
    for batch_idx, (headers,seqs,_,batch_targets) in enumerate(tst_loader):
        for i in range (0, len(headers)):
            header = headers[i]
            seq = seqs[i]
            targets = batch_targets[i]
            dinuc_shuffled_seq = dinuc_shuffle(seq)
            hdr = header.strip('>').split('(')[0]
            chrom = hdr.split(':')[0]
            start,end = hdr.split(':')[1].split('-')
            final_fa.append([header,seq])
            
            if type(targets) == torch.Tensor:
                targets = targets.cpu().detach().numpy()
                
            target = targets.astype(int)
            
            labels = ','.join(labels_array[np.where(target==1)].astype(str)) 
            
            final_bed.append([chrom,start,end,'.',labels])
    
    
    final_fa_to_write = []
    #--load motifs
    with open(argspace.directory+'/Motif_Analysis/filters_meme.txt') as f:
        filter_motifs = minimal.read(f)
    
    motif_len = filter_motifs[0].length
    
    seq_numbers = [i for i in range(0,len(final_bed))]  
    seq_positions = [i for i in range(0,len(final_fa[0][1])-motif_len)] #can't go beyond end of sequence so have to subtract motif_len
    for i in progress_bar(range(0, len(filter_motifs))):
        motif = filter_motifs[i]
        pwm = np.column_stack((motif.pwm['A'],motif.pwm['C'],motif.pwm['G'],motif.pwm['T']))
        #consensus = motif.consensus
        
        num_occ = motif.num_occurrences
        random_seqs = random.choices(seq_numbers, k = num_occ) #randomly picking num_occ sequences (note that num_occ can be greater than population in this case since a single sequence can have multile occurence of a filter activation)
        #print(num_occ, len(seq_positions))
        random_positions = random.choices(seq_positions, k = num_occ) #randomly pick a position for a motif to occur
        
        for seq_index, pos in zip(random_seqs,random_positions):
            consensus = get_random_seq(pwm) #this will get us a random sequence generated based on the prob distribution of the PWM
            seq = final_fa[seq_index][1]
            seq = seq[:pos]+str(consensus)+seq[pos+len(consensus):]
            
            final_fa[seq_index][1] = seq
    
    out_directory = argspace.directory+'/Temp_Data'
    if not os.path.exists(out_directory):
        os.makedirs(out_directory)
    
    np.savetxt(out_directory+'/'+'shuffled_background.fa',np.asarray(final_fa).flatten(),fmt='%s')
    np.savetxt(out_directory+'/'+'shuffled_background.txt',np.asarray(final_bed), fmt='%s',delimiter='\t')
    
    return out_directory+'/'+'shuffled_background' #name of the prefix to use
    #
    #return final_bed,final_fa
    
    

#########################################################################################################################


##############################----------------Data Processing-----------------##########################################
argSpace = parseArgs()



inp_file_prefix = argSpace.inputprefix
#num_labels = int(sys.argv[2]) #num labels

#########################################################################################################################
#################################-------------------HyperParam Setup--------------------#################################
#########################################################################################################################

###Fixed parameters####
#stride = 1 #embeddings related
#batchSize = 172
#maxEpochs = 30

# CUDA for PyTorch
use_cuda = torch.cuda.is_available()
device = torch.device(torch.cuda.current_device() if use_cuda else "cpu")
cudnn.benchmark = True



#w2v_path = 'Word2Vec_Models/'
#######################

#################--------------Main Loop-------------------#####################
param_data = np.loadtxt(argSpace.hparamfile,dtype=str)
output_dir = argSpace.directory


if not os.path.exists(output_dir):
    os.makedirs(output_dir)

#save arguments to keep record
with open(argSpace.directory+'/arguments.txt','w') as f:
    f.writelines(str(argSpace))

if argSpace.verbose:
    print("Output Directory: ",output_dir)


params = {}
for entry in param_data:
    if entry[1] == 'False':
        params[entry[0]] = False
    elif entry[1] == 'True':
        params[entry[0]] = True
    else:
        try:
            params[entry[0]] = int(entry[1])
        except:
            params[entry[0]] = entry[1]

if argSpace.verbose:
    print("HyperParameters are: ")
    print(params)

#prefix = params['prefix']
num_labels = argSpace.numLabels


genPAttn = params['get_pattn']
getCNNout = params['get_CNNout']
getSequences = params['get_seqs']

batchSize = params['batch_size']
maxEpochs = params['num_epochs']

#if 'CNN' in :
#   genPAttn = True
#else:
#   genPAttn = False

#w2v_filename = 'Word2Vec_Model_kmerLen'+str(params['kmer_size'])+'_win'+str(params['embd_window'])+'_embSize'+str(params['embd_size'])
#modelwv = Word2Vec.load(w2v_path+w2v_filename)

modelwv = None #for now not using word2vec embedings



#some params
test_split = argSpace.splitperc/100 #we need 0.10 for 10% #10% valid,test split
print("test/validation split val: ", test_split)
shuffle_data = True  #internal param
seed_val = 100  #internal param



use_Embds = False #for now, no embeddings
if use_Embds==False:
    if argSpace.deskLoad == False:
        data_all = ProcessedDataVersion2(inp_file_prefix,num_labels) #get all data
    else:
        data_all = ProcessedDataVersion2A(inp_file_prefix,num_labels)   
    
    dataset_size = len(data_all)
    indices = list(range(dataset_size))

    split_val = int(np.floor(test_split*dataset_size))
    if shuffle_data == True:
        np.random.seed(seed_val)
        np.random.shuffle(indices)
    
    if argSpace.splitType != 'percent':
        chrValid, chrTest = argSpace.splitType.split(',') #chr8 for valid and chr18 for test (kundaje paper in plos One). we can try chr4,19,chr16 etc for test since chr18 has the second lowest examples
        df_tmp = data_all.df
        
        test_indices = df_tmp[df_tmp[0]==chrTest].index.to_list()
        valid_indices = df_tmp[df_tmp[0]==chrValid].index.to_list()
        train_indices = df_tmp[~df_tmp[0].isin([chrValid,chrTest])].index.to_list()
        
        
    else:
        if argSpace.mode == 'train':
            train_indices, test_indices, valid_indices = indices[2*split_val:], indices[:split_val], indices[split_val:2*split_val]
            #save test and valid indices
            np.savetxt(argSpace.directory+'/valid_indices.txt',valid_indices,fmt='%s')
            np.savetxt(argSpace.directory+'/test_indices.txt',test_indices,fmt='%s')
            np.savetxt(argSpace.directory+'/train_indices.txt',train_indices,fmt='%s')
        else:
            train_indices = np.loadtxt(argSpace.directory+'/train_indices.txt',dtype=int)
            test_indices = np.loadtxt(argSpace.directory+'/test_indices.txt',dtype=int)
            valid_indices = np.loadtxt(argSpace.directory+'/valid_indices.txt',dtype=int)
        
    train_sampler = SubsetRandomSampler(train_indices)
    test_sampler = SubsetRandomSampler(test_indices)
    valid_sampler = SubsetRandomSampler(valid_indices)
    
    train_loader = DataLoader(data_all, batch_size = batchSize, sampler = train_sampler, num_workers = argSpace.numWorkers)
    test_loader = DataLoader(data_all, batch_size = batchSize, sampler = test_sampler, num_workers = argSpace.numWorkers)
    valid_loader = DataLoader(data_all, batch_size = batchSize, sampler = valid_sampler, num_workers = argSpace.numWorkers)
    
    if argSpace.testAll:
        test_loader = DataLoader(data_all, batch_size = batchSize, sampler=train_sampler, num_workers = argSpace.numWorkers)


net = Generalized_Net(params, genPAttn, wvmodel = modelwv, numClasses = num_labels).to(device) 

if num_labels == 2:
    criterion = nn.CrossEntropyLoss(reduction='mean')
else:
    criterion = torch.nn.BCEWithLogitsLoss()

optimizer = optim.Adam(net.parameters())#, lr=0.002, weight_decay=0.01) #lr =0.002 #try it without lr and weight decay
#def evaluateRegular(net, iterator, criterion,out_dir,getPAttn=False, storePAttn = False, getCNN=False, storeCNNout = False, getSeqs = False):

##Saved Model Directory##
saved_model_dir = output_dir+'/Saved_Model'
if not os.path.exists(saved_model_dir):
    os.makedirs(saved_model_dir)
#########################    

###################-------------Training and Testing------------------#############
if argSpace.mode == 'train':    
    best_valid_loss = np.inf
    best_valid_auc = np.inf
    for epoch in progress_bar(range(1, maxEpochs + 1)):#tqdm
        if num_labels == 2:
            res_train = trainRegular(net, device, train_loader, optimizer, criterion)
        else:
            res_train = trainRegularMC(net, device, train_loader, optimizer, criterion)
        res_train_loss = res_train[0]
        res_train_auc = np.asarray(res_train[1]).mean()
        
        if argSpace.verbose:
            print("Train Results (Loss and AUC): ", res_train_loss, res_train_auc)
        
        if num_labels == 2:
            res_valid = evaluateRegular(net, valid_loader, criterion, output_dir+"/Stored_Values", getPAttn=False,
                                        storePAttn = False, getCNN = False,
                                        storeCNNout = False, getSeqs = False) #evaluateRegular(net,valid_loader,criterion)
            
            res_valid_loss = res_valid[0]
            res_valid_auc = res_valid[1]   
        else:
            res_valid = evaluateRegularMC(net, valid_loader, criterion, output_dir+"/Stored_Values", getPAttn=False,
                                        storePAttn = False, getCNN = False,
                                        storeCNNout = False, getSeqs = False) #evaluateRegular(net,valid_loader,criterion)
            
            res_valid_loss = res_valid[0]
            res_valid_auc = np.mean(res_valid[1])  
            
        if res_valid_loss < best_valid_loss:
            best_valid_loss = res_valid_loss
            best_valid_auc = res_valid_auc
            #if valid_chrom not in auc_dict:
            if argSpace.verbose:
                print("Best Validation (Loss and AUC): ",res_valid[0],res_valid_auc,"\n")
            torch.save({'epoch': epoch,
                           'model_state_dict': net.state_dict(),
                           'optimizer_state_dict':optimizer.state_dict(),
                           'loss':res_valid_loss
                           },saved_model_dir+'/model')

try:    
    checkpoint = torch.load(saved_model_dir+'/model')
    net.load_state_dict(checkpoint['model_state_dict'])
    optimizer.load_state_dict(checkpoint['optimizer_state_dict'])
    epoch = checkpoint['epoch']
    loss = checkpoint['loss']
except:
    print("No pre-trained model found! Please run with --mode set to train.")

if num_labels == 2:
    res_test = evaluateRegular(net, test_loader, criterion, output_dir+"/Stored_Values", getPAttn = genPAttn,
                                        storePAttn = argSpace.storeInterCNN, getCNN = getCNNout,
                                        storeCNNout = argSpace.storeInterCNN, getSeqs = getSequences)
                                        
    test_loss = res_test[0]
    test_auc = res_test[1]
    labels = res_test[2][:,0]
    preds = res_test[2][:,1]
    if argSpace.verbose:
        print("Test Loss and AUC: ",test_loss, test_auc)
    labels = res_test[2][:,0]
    preds = res_test[2][:,1]
    fpr,tpr,thresholds = metrics.roc_curve(labels,preds)
    roc_dict = {'fpr':fpr, 'tpr':tpr, 'thresholds':thresholds}
    with open(output_dir+'/ROC_dict.pckl','wb') as f:
        pickle.dump(roc_dict,f)
    some_res = [['Test_Loss','Test_AUC']]
    some_res.append([[test_loss,test_auc]])
    np.savetxt(output_dir+'/loss_and_auc.txt',some_res,delimiter='\t',fmt='%s')
else:
    res_test = evaluateRegularMC(net, test_loader, criterion, output_dir+"/Stored_Values", getPAttn = genPAttn,
                                        storePAttn = argSpace.storeInterCNN, getCNN = getCNNout,
                                        storeCNNout = argSpace.storeInterCNN, getSeqs = getSequences)
    test_loss = res_test[0]
    test_auc = res_test[1]
    if argSpace.verbose:
        print("Test Loss and mean AUC: ",test_loss, np.mean(test_auc))

    np.savetxt(output_dir+'/per_class_AUC.txt',test_auc,delimiter='\t',fmt='%s')


###############################################################################
##############----------Motif Interaction Analysis--------------###############
# running_loss/len(iterator),valid_auc,roc,PAttn_all,per_batch_labelPreds,per_batch_CNNoutput,per_batch_testSeqs

CNNWeights = net.layer1[0].weight.cpu().detach().numpy()
Prob_Attention_All = res_test[3] #for a single batch the dimensions are: BATCH_SIZE x NUM_FEATURES x (NUM_MULTI_HEADS x NUM_FEATURES) #NUM_FEATURES can be num_kmers or num_kmers/convolutionPoolsize (for embeddings)
pos_score_cutoff = argSpace.scoreCutoff

def motif_analysis(res_test, output_dir, argSpace, for_background = False):
    NumExamples = 0
    pos_score_cutoff = argSpace.scoreCutoff
    k = 0 #batch number
    per_batch_labelPreds = res_test[4][k]
    #per_batch_Embdoutput = res_test[5][k]
    CNNoutput = res_test[5][k]
    if argSpace.storeInterCNN:
        with open(CNNoutput,'rb') as f:
            CNNoutput = pickle.load(f)
    Seqs = np.asarray(res_test[6][k])
    
    
    if num_labels == 2:
        if for_background and argSpace.intBackground == 'negative':
            tp_indices = [i for i in range(0,per_batch_labelPreds.shape[0]) if (per_batch_labelPreds[i][0]==0 and per_batch_labelPreds[i][1]<(1-pos_score_cutoff))]
        elif for_background and argSpace.intBackground == 'shuffle':
            tp_indices = [i for i in range(0,per_batch_labelPreds.shape[0])]
        else:
            tp_indices = [i for i in range(0,per_batch_labelPreds.shape[0]) if (per_batch_labelPreds[i][0]==1 and per_batch_labelPreds[i][1]>pos_score_cutoff)]
        
    else:
        tp_indices = [i for i in range(0,per_batch_labelPreds['labels'].shape[0])]
    
    NumExamples += len(tp_indices)
        
    CNNoutput = CNNoutput[tp_indices]
    Seqs = Seqs[tp_indices]
    
    for k in range(1,len(res_test[3])):
        if argSpace.verbose:
            print("batch number: ",k)
            
        per_batch_labelPreds = res_test[4][k]
        #per_batch_Embdoutput = res_test[5][k]
        per_batch_CNNoutput = res_test[5][k]
        with open(per_batch_CNNoutput,'rb') as f:
            per_batch_CNNoutput = pickle.load(f)
        
        per_batch_seqs = np.asarray(res_test[6][k])
    
        if num_labels == 2:
            if for_background and argSpace.intBackground == 'negative':
                tp_indices = [i for i in range(0,per_batch_labelPreds.shape[0]) if (per_batch_labelPreds[i][0]==0 and per_batch_labelPreds[i][1]<(1-pos_score_cutoff))]
            elif for_background and argSpace.intBackground == 'shuffle':
                tp_indices = [i for i in range(0,per_batch_labelPreds.shape[0])]
            else:
                tp_indices = [i for i in range(0,per_batch_labelPreds.shape[0]) if (per_batch_labelPreds[i][0]==1 and per_batch_labelPreds[i][1]>pos_score_cutoff)]
        else:
            tp_indices = [i for i in range(0,per_batch_labelPreds['labels'].shape[0])]
        
        NumExamples += len(tp_indices)
        
        CNNoutput = np.concatenate((CNNoutput,per_batch_CNNoutput[tp_indices]),axis=0)
        Seqs = np.concatenate((Seqs,per_batch_seqs[tp_indices]))


    #get_motif(CNNWeights, CNNoutput, Seqs, dir1 = 'Interactions_Test_noEmbdAttn_'+prefix,embd=True,data='DNA',kmer=kmer_len,s=stride,tomtom='/s/jawar/h/nobackup/fahad/MEME_SUITE/meme-5.0.3/src/tomtom') 
    
    if argSpace.tfDatabase == None:
        dbpath = '/s/jawar/h/nobackup/fahad/MEME_SUITE/motif_databases/CIS-BP/Homo_sapiens.meme'
    else:
        dbpath = argSpace.tfDatabase
    
    if argSpace.tomtomPath == None:
        tomtomPath = '/s/jawar/h/nobackup/fahad/MEME_SUITE/meme-5.0.3/src/tomtom'
    else:
        tomtomPath = argSpace.tomtomPath
    
    if for_background and argSpace.intBackground != None:
        motif_dir = output_dir + '/Motif_Analysis_Negative'
    else:
        motif_dir = output_dir + '/Motif_Analysis'
    
    #dbpath = '/s/jawar/h/nobackup/fahad/MEME_SUITE/motif_databases/CIS-BP/Homo_sapiens.meme'
    #dbpath = '/s/jawar/h/nobackup/fahad/MEME_SUITE/motif_databases/Homo_sapiens_testDFIM.meme'
    #for AT
    #dbpath = '/s/jawar/h/nobackup/fahad/MEME_SUITE/motif_databases/ARABD/ArabidopsisDAPv1.meme'
    
    get_motif(CNNWeights, CNNoutput, Seqs, dbpath, dir1 = motif_dir, embd=False,data='DNA',tomtom=tomtomPath,tomtompval=argSpace.tomtomPval,tomtomdist=argSpace.tomtomDist) 
    
    ###-----------------Adding TF details to TomTom results----------------###
    if argSpace.annotateTomTom != 'No':
        tomtom_res = np.loadtxt(motif_dir+'/tomtom/tomtom.tsv',dtype=str,delimiter='\t')
        if argSpace.annotateTomTom == None:
            database = np.loadtxt('../Basset_Splicing_IR-iDiffIR/Analysis_For_none_network-typeB_lotus_posThresh-0.60/MEME_analysis/Homo_sapiens_2019_01_14_4_17_pm/TF_Information_all_motifs.txt',dtype=str,delimiter='\t')
        else:
            database = argSpace.annotateTomTom
                                          
        final = []                                     
        for entry in tomtom_res[1:]:
            motifID = entry[1]                         
            res = np.argwhere(database[:,3]==motifID)
            TFs = ','.join(database[res.flatten(),6])
            final.append(entry.tolist()+[TFs])
                                       
        np.savetxt(motif_dir+'/tomtom/tomtom_annotated.tsv',final,delimiter='\t',fmt='%s')
    return motif_dir, NumExamples


if argSpace.motifAnalysis:
    motif_dir,numPosExamples = motif_analysis(res_test, output_dir, argSpace, for_background = False)
    
    if argSpace.intBackground == 'negative':#!= None:
        motif_dir_neg,numNegExamples = motif_analysis(res_test, output_dir, argSpace, for_background = True)
        
    elif argSpace.intBackground == 'shuffle':
        bg_prefix = get_shuffled_background_v3(test_loader,argSpace) #get_shuffled_background_v2(test_loader, params['CNN_filters'], params['CNN_filtersize'], argSpace)  the version 2 doesn't work that well (average AUC 0.50 and 0 motifs in background)
        #data_bg = ProcessedDataVersion2(bg_prefix,num_labels)
        if argSpace.deskLoad == False:
            data_bg = ProcessedDataVersion2(bg_prefix,num_labels) #get all data
        else:
            data_bg = ProcessedDataVersion2A(bg_prefix,num_labels)
            
        test_loader_bg = DataLoader(data_bg,batch_size=batchSize,num_workers=argSpace.numWorkers)   
        if num_labels==2:
            res_test_bg = evaluateRegular(net, test_loader_bg, criterion, out_dirc = output_dir+"/Temp_Data/Stored_Values", getPAttn = genPAttn,
                                            storePAttn = argSpace.storeInterCNN, getCNN = getCNNout,
                                            storeCNNout = argSpace.storeInterCNN, getSeqs = getSequences)
            motif_dir_neg,numNegExamples = motif_analysis(res_test_bg, output_dir, argSpace, for_background = True) #in this case the background comes from shuffled sequences and won't be using negative predictions
        else:
            res_test_bg = evaluateRegularMC(net, test_loader_bg, criterion, out_dirc = output_dir+"/Temp_Data/Stored_Values", getPAttn = genPAttn,
                                            storePAttn = argSpace.storeInterCNN, getCNN = getCNNout,
                                            storeCNNout = argSpace.storeInterCNN, getSeqs = getSequences)
            motif_dir_neg,numNegExamples = motif_analysis(res_test_bg, output_dir, argSpace, for_background = True) #for_background doesn't matter in this case since num_labels are greater than 2
                
        
else: #this is when we want to skip motif analysis (if its already done) we will need motif directories for downstream analyses
    motif_dir = output_dir + '/Motif_Analysis'
    if argSpace.intBackground == 'negative':
        motif_dir_neg = output_dir + '/Motif_Analysis_Negative'
    elif argSpace.intBackground == 'shuffle':
        test_loader_bg = DataLoader(data_bg,batch_size=batchSize,num_workers=argSpace.numWorkers)
        if num_labels==2:
            res_test_bg = evaluateRegular(net, test_loader_bg, criterion, out_dirc = output_dir+"/Temp_Data/Stored_Values", getPAttn = genPAttn,
                                            storePAttn = argSpace.storeInterCNN, getCNN = getCNNout,
                                            storeCNNout = argSpace.storeInterCNN, getSeqs = getSequences)
            motif_dir_neg = output_dir + '/Motif_Analysis_Negative'
        else:
            res_test_bg = evaluateRegularMC(net, test_loader_bg, criterion, out_dirc = output_dir+"/Temp_Data/Stored_Values", getPAttn = genPAttn,
                                            storePAttn = argSpace.storeInterCNN, getCNN = getCNNout,
                                            storeCNNout = argSpace.storeInterCNN, getSeqs = getSequences)
            motif_dir_neg = output_dir + '/Motif_Analysis_Negative'
    
    ##########################################################################
####################################################################################

####################################################################################
#########------------Attention Probabilities Analysis-----------------##############

#-------drawing attention figures-------#
if argSpace.attnFigs:
    Attn_dir = output_dir + '/Attention_Figures'

    if not os.path.exists(Attn_dir):
        os.makedirs(Attn_dir)
    
    plt.close('all')
    plt.rcParams["figure.figsize"] = (9,5)
    
    count = 0
    for k in range(0,len(Prob_Attention_All)): #going through all batches
        if count == argSpace.intSeqLimit:
            break
        

        PAttn = Prob_Attention_All[k]
        if argSpace.storeInterCNN:
            with open(PAttn,'rb') as f:
                PAttn = pickle.load(f)
        
        
        per_batch_labelPreds = res_test[4][k]
        if num_labels == 2:
            tp_indices = [i for i in range(0,per_batch_labelPreds.shape[0]) if (per_batch_labelPreds[i][0]==1 and per_batch_labelPreds[i][1]>pos_score_cutoff)] #pos classified examples > 0.6
        else:
            tp_indices = [i for i in range(0,per_batch_labelPreds['labels'].shape[0])]
        #tp_indices = tp_indices[:10] #get top 5 from each batch
        
        feat_size = PAttn.shape[1]
        
        #ex = 165#7
        #plt.imshow(PAttn[ex,:,99*i:99*(i+1)])
        for ex in tp_indices:
            count += 1
            if count == argSpace.intSeqLimit:
                break
            plt.close('all')
            fig, ax = plt.subplots(nrows=2, ncols=4)
        
            for i in range(0,8):
                plt.subplot(2,4,i+1)
                attn_mat = PAttn[ex,:,feat_size*i:feat_size*(i+1)]
                plt.imshow(attn_mat)
                max_loc = np.unravel_index(attn_mat.argmax(), attn_mat.shape)
                plt.title('Single Head #'+str(i)+' Max Loc: '+str(max_loc),size=6)
                plt.grid(False)
            
            #plt.clf()
            #print('Done for: ',str(ex))
            
            plt.savefig(Attn_dir+'/'+'Batch-'+str(k)+'_PosExample-'+str(ex)+'_AttenMatrices.pdf')
        
        print("Done for batch: ",k)
        plt.close('all')
#######################################################################################

########################################################################################
################------------------Interactions Analysis-----------------################
#-----------Calculating Positive and Negative population------------#
per_batch_labelPreds = res_test[4]
#print(lohahi)

numPosExamples = 0

for j in range(0,len(per_batch_labelPreds)):
    if numPosExamples == argSpace.intSeqLimit:
            break
    
    batch_values = per_batch_labelPreds[j]
    if num_labels != 2:
        batch_values = batch_values['labels']
    for k in range(0,len(batch_values)):
        if num_labels == 2:
            if (batch_values[k][0]==1 and batch_values[k][1]>pos_score_cutoff):
                numPosExamples += 1
        else:
            numPosExamples += 1
        if numPosExamples == argSpace.intSeqLimit:
            break



numNegExamples = 0

for j in range(0,len(per_batch_labelPreds)):
    if numNegExamples == argSpace.intSeqLimit:
            break
    
    batch_values = per_batch_labelPreds[j]
    if num_labels != 2:
        batch_values = batch_values['labels']
    for k in range(0,len(batch_values)):
        if num_labels == 2:
            if argSpace.intBackground == 'negative':
                if (batch_values[k][0]==0 and batch_values[k][1]<(1-pos_score_cutoff)):
                    numNegExamples += 1
            elif argSpace.intBackground == 'shuffle':
                numNegExamples += 1
            
        else:
            numNegExamples += 1
        if numNegExamples == argSpace.intSeqLimit:
            break

print('Positive and Negative Population: ', numPosExamples, numNegExamples)     
#-------------------------------------------------------------------#



def get_filters_in_individual_seq(sdata):
    header,num_filters,filter_data_dict,CNNfirstpool = sdata
    s_info_dict = {}
    for j in range(0,num_filters):
        filter_data = filter_data_dict['filter'+str(j)] #np.loadtxt(motif_dir+'/filter'+str(j)+'_logo.fa',dtype=str)
        for k in range(0,len(filter_data),2):
            hdr = filter_data[k].split('_')[0]
            if hdr == header:
                pos = int(filter_data[k].split('_')[-1])
                pooled_pos = int(pos/CNNfirstpool)
                key = pooled_pos#header+'_'+str(pooled_pos)
                if key not in s_info_dict:
                    s_info_dict[key] = ['filter'+str(j)]
                else:
                    if 'filter'+str(j) not in s_info_dict[key]:
                        s_info_dict[key].append('filter'+str(j))
    return {header: s_info_dict}
                        
def get_filters_in_seq_dict(all_seqs,motif_dir,num_filters,CNNfirstpool,numWorkers=1):
    filter_data_dict = {}
    for i in range(0,num_filters):
        filter_data = np.loadtxt(motif_dir+'/filter'+str(i)+'_logo.fa',dtype=str)
        filter_data_dict['filter'+str(i)] = filter_data
    
    seq_info_dict = {}
    
    sdata = []
    for i in range(0,all_seqs.shape[0]):
        header = all_seqs[i][0]
        sdata.append([header,num_filters,filter_data_dict,CNNfirstpool])
    #count = 0
    with Pool(processes = numWorkers) as pool:
        result = pool.map(get_filters_in_individual_seq,sdata,chunksize=1)
        #pdb.set_trace()
        #count += 1
        #if count %10 == 0:
        #   print(count)
        for subdict in result:
            seq_info_dict.update(subdict)

    return seq_info_dict
    
    
def get_matching_filters_all(all_seqs, num_features, sequence_len, CNNfirstpool, num_filters, motif_dir):
    filter_data_dict = {}
    for i in range(0,200):
        filter_data = np.loadtxt(motif_dir+'/filter'+str(i)+'_logo.fa',dtype=str)
        filter_data_dict['filter'+str(i)] = filter_data
        
    filtersDict = {}
    
    for ii in progress_bar(range(0,all_seqs.shape[0])):
        headerQ = all_seqs[ii][0]
        for posQ in progress_bar(range(0,num_features)):
            for i in range(0,num_filters):
                filter_data = filter_data_dict['filter'+str(i)]#np.loadtxt(motif_dir+'/filter'+str(i)+'_logo.fa',dtype=str)
                for j in range(0,len(filter_data),2):
                    hdr = filter_data[j].split('_')[0]#+'_'+filter_data[j].split('_')[1]
                    if hdr == headerQ: #header of the current sequence matches header in the filter
                        pos = int(filter_data[j].split('_')[-1])
                        pooled_pos = int(pos/CNNfirstpool)
                        if pooled_pos == posQ:
                            key = headerQ+'^'+str(posQ)#'filter'+str(i)
                            if key not in filtersDict:
                                filtersDict[key] = ['filter'+str(i)]
                            else:
                                if 'filter'+str(i) not in filtersDict[key]:
                                    filtersDict[key].append('filter'+str(i))
                #key = str(pooled_pos)+'_'+str(pooled_pos*CNNfirstpool)+'-'+str(pooled_pos*CNNfirstpool+5)
                #pooled_pos_dict[key].append(['filter'+str(i),pos])
    
    return filtersDict


def get_matching_filters(posQ, headerQ, sequence_len, CNNfirstpool, num_filters, motif_dir):
    filtersDict = {}
    
    for i in range(0,num_filters):
        filter_data = np.loadtxt(motif_dir+'/filter'+str(i)+'_logo.fa',dtype=str)
        for j in range(0,len(filter_data),2):
            hdr = filter_data[j].split('_')[0]#+'_'+filter_data[j].split('_')[1]
            if hdr == headerQ: #header of the current sequence matches header in the filter
                pos = int(filter_data[j].split('_')[-1])
                pooled_pos = int(pos/CNNfirstpool)
                if pooled_pos == posQ:
                    key = 'filter'+str(i)
                    if key not in filtersDict:
                        filtersDict[key] = [[pooled_pos,pos]]
                    else:
                        filtersDict[key].append([pooled_pos,pos])
                #key = str(pooled_pos)+'_'+str(pooled_pos*CNNfirstpool)+'-'+str(pooled_pos*CNNfirstpool+5)
                #pooled_pos_dict[key].append(['filter'+str(i),pos])
    
    return filtersDict



def score_individual_head(data):
    
    count,header,seq_inf_dict,k,ex,params,tomtom_data,attn_cutoff,sequence_len,CNNfirstpool,num_filters,motif_dir,feat_size,storeInterCNN,considerTopHit = data
    #print(k,ex)
    global Prob_Attention_All# = res_test[3]
    global Seqs# = res_test[6]
    global LabelPreds# = res_test[4]
    #global Filter_Intr_Attn
    #global Filter_Intr_Pos
    global Filter_Intr_Keys
    
    filter_Intr_Attn = np.ones(len(Filter_Intr_Keys))*-1
    filter_Intr_Pos = np.ones(len(Filter_Intr_Keys)).astype(int)*-1
    
    y_ind = count#(k*params['batch_size']) + ex
    
    PAttn = Prob_Attention_All[k]
    if storeInterCNN:
        with open(PAttn,'rb') as f:
            PAttn = pickle.load(f)
    
    #filter_intr_dict = {}
    
    attn_mat = PAttn[ex,:,:]
    
    attn_mat = np.asarray([attn_mat[:,feat_size*i:feat_size*(i+1)] for i in range(0,params['numMultiHeads'])]) 
    attn_mat = np.max(attn_mat, axis=0) #out of the 8 attn matrices, get the max value at the corresponding positions
    
    for i in range(0, attn_mat.shape[0]):
        if i not in seq_inf_dict:
            continue
        for j in range(0, attn_mat.shape[1]):
            #pdb.set_trace()
            if j not in seq_inf_dict:
                continue
            if i==j:
                continue
            max_loc = [i,j]#attn_mat[i,j]
            
            pos_diff = CNNfirstpool * abs(max_loc[0]-max_loc[1])
            
            KeyA = i #seq_inf_dict already is for the current header and we just need to specify the Pooled position
            KeyB = j 
            
            attn_val = attn_mat[i,j]
            
            all_filters_posA = seq_inf_dict[KeyA]
            all_filters_posB = seq_inf_dict[KeyB]
            
            for keyA in all_filters_posA:
                for keyB in all_filters_posB:
                    if keyA == keyB:
                        continue
                    intr = keyA+'<-->'+keyB
                    rev_intr = keyB+'<-->'+keyA
                    if intr in Filter_Intr_Keys:
                        x_ind = Filter_Intr_Keys[intr]
                    elif rev_intr in Filter_Intr_Keys:
                        x_ind = Filter_Intr_Keys[rev_intr]
                            
                    if attn_val > filter_Intr_Attn[x_ind]:#[y_ind]:
                        filter_Intr_Attn[x_ind] = attn_val #[y_ind] = attn_val
                    filter_Intr_Pos[x_ind] = pos_diff#[y_ind] = pos_diff
                        
                
    return y_ind,filter_Intr_Attn,filter_Intr_Pos
            
            

def score_individual_head_bg(data):
    
    count,header,seq_inf_dict,k,ex,params,tomtom_data,attn_cutoff,sequence_len,CNNfirstpool,num_filters,motif_dir,feat_size,storeInterCNN,considerTopHit = data
    
    global Prob_Attention_All_neg# = res_test[3]
    global Seqs_neg# = res_test[6]
    global LabelPreds_neg# = res_test[4]
    #global Filter_Intr_Attn
    #global Filter_Intr_Pos
    global Filter_Intr_Keys
    
    filter_Intr_Attn = np.ones(len(Filter_Intr_Keys))*-1
    filter_Intr_Pos = np.ones(len(Filter_Intr_Keys)).astype(int)*-1
    
    y_ind = count#(k*params['batch_size']) + ex
    
    PAttn = Prob_Attention_All_neg[k]
    if storeInterCNN:
        with open(PAttn,'rb') as f:
            PAttn = pickle.load(f)
    
    attn_mat = PAttn[ex,:,:]
    
    attn_mat = np.asarray([attn_mat[:,feat_size*i:feat_size*(i+1)] for i in range(0,params['numMultiHeads'])]) 
    attn_mat = np.max(attn_mat, axis=0) #out of the 8 attn matrices, get the max value at the corresponding positions
    
    for i in range(0, attn_mat.shape[0]):
        if i not in seq_inf_dict:
            continue
        for j in range(0, attn_mat.shape[1]):
            #pdb.set_trace()
            if j not in seq_inf_dict:
                continue
            if i==j:
                continue
            max_loc = [i,j]#attn_mat[i,j]
            
            pos_diff = CNNfirstpool * abs(max_loc[0]-max_loc[1])
            
            KeyA = i #seq_inf_dict already is for the current header and we just need to specify the Pooled position
            KeyB = j 
            
            attn_val = attn_mat[i,j]
            
            all_filters_posA = seq_inf_dict[KeyA]
            all_filters_posB = seq_inf_dict[KeyB]
            
            for keyA in all_filters_posA:
                for keyB in all_filters_posB:
                    if keyA == keyB:
                        continue
                    intr = keyA+'<-->'+keyB
                    rev_intr = keyB+'<-->'+keyA
                    if intr in Filter_Intr_Keys:
                        x_ind = Filter_Intr_Keys[intr]
                    elif rev_intr in Filter_Intr_Keys:
                        x_ind = Filter_Intr_Keys[rev_intr]
                            
                    if attn_val > filter_Intr_Attn[x_ind]:#[y_ind]:
                        filter_Intr_Attn[x_ind] = attn_val #[y_ind] = attn_val
                    filter_Intr_Pos[x_ind] = pos_diff#[y_ind] = pos_diff
                        
                
    return y_ind,filter_Intr_Attn,filter_Intr_Pos


#def estimate_interactions(Seqs, Prob_Attention_All, LabelPreds, num_filters, params, tomtom_data, motif_dir, verbose = False, CNNfirstpool = 6, sequence_len = 200, pos_score_cutoff = 0.65, seq_limit = -1, attn_cutoff = 0.25, for_background = False, numWorkers=1):
def estimate_interactions(num_filters, params, tomtom_data, motif_dir, verbose = False, CNNfirstpool = 6, sequence_len = 200, pos_score_cutoff = 0.65, seq_limit = -1, attn_cutoff = 0.25, for_background = False, numWorkers=1, storeInterCNN = True, considerTopHit = True):
    
    global Prob_Attention_All# = res_test[3]
    global Seqs# = res_test[6]
    global LabelPreds# = res_test[4]
    global Filter_Intr_Attn
    global Filter_Intr_Pos
    global Filter_Intr_Keys
    global Filter_Intr_Attn_neg
    global Filter_Intr_Pos_neg

    
    final_all = [['Batch','ExNo','SeqHeader','SingleHeadNo','PositionA','PositionB','AveragePosDiff','AttnScore','PositionAInfo','PositionBInfo']]
    count = 0       
    for k in range(0,len(Prob_Attention_All)): #going through all batches
        start_time = time.time()
        if count == seq_limit: #break if seq_limit number of sequences tested
            break
        
        PAttn = Prob_Attention_All[k]
        if storeInterCNN:
            with open(PAttn,'rb') as f:
                PAttn = pickle.load(f)
        
        #PAttn = PAttn.detach().cpu().numpy()
        feat_size = PAttn.shape[1]
        per_batch_labelPreds = LabelPreds[k]
        
        if num_labels == 2:
            if for_background and argSpace.intBackground != None:
                tp_indices = [i for i in range(0,per_batch_labelPreds.shape[0]) if (per_batch_labelPreds[i][0]==0 and per_batch_labelPreds[i][1]<(1-pos_score_cutoff))]
            else:
                tp_indices = [i for i in range(0,per_batch_labelPreds.shape[0]) if (per_batch_labelPreds[i][0]==1 and per_batch_labelPreds[i][1]>pos_score_cutoff)]
        else:
            tp_indices = [i for i in range(0,per_batch_labelPreds['labels'].shape[0])]
        
        #if for_background:
        #   tp_indices = [i for i in range(0,per_batch_labelPreds.shape[0]) if (per_batch_labelPreds[i][0]==0 and per_batch_labelPreds[i][1]<(1-pos_score_cutoff))] #neg classified examples < (1-0.6)
        #else:
        #   tp_indices = [i for i in range(0,per_batch_labelPreds.shape[0]) if (per_batch_labelPreds[i][0]==1 and per_batch_labelPreds[i][1]>pos_score_cutoff)] #pos classified examples > 0.6
        
        print('generating sequence position information...')
        seq_info_dict = get_filters_in_seq_dict(Seqs[k],motif_dir,num_filters,CNNfirstpool,numWorkers=numWorkers)
        print('Done!')
        
        #tp_indices = tp_indices[:10] #get top 5 from each batch
        fdata = []
        for ex in tp_indices:
            header = np.asarray(Seqs[k])[ex][0]
            fdata.append([count,header,seq_info_dict[header],k,ex,params,tomtom_data,attn_cutoff,sequence_len,CNNfirstpool,num_filters,motif_dir,feat_size,storeInterCNN, considerTopHit])
            count += 1
            if count == seq_limit:
                break
            
            ##ex = 1#4
            #header = np.asarray(Seqs[k])[ex][0]
            
            ##############------New Code-------###############
            #score_individual_head(ex,PAttn,params,attn_cutoff,sequence_len,CNNfirstpool,num_filters,motif_dir,feat_size)
        with Pool(processes = numWorkers) as pool:
            result = pool.map(score_individual_head, fdata, chunksize=1)
        #pdb.set_trace()
        for element in result:
            bid = element[0]
            if for_background == False:
                Filter_Intr_Pos[:,bid] = element[2]
                Filter_Intr_Attn[:,bid] = element[1]
            else:
                Filter_Intr_Pos_neg[:,bid] = element[2]
                Filter_Intr_Attn_neg[:,bid] = element[1]
        
        #pdb.set_trace()    
            #final_all += [entry for ent in result for entry in ent] #unravel 

        end_time = time.time()
        if argSpace.verbose:    
            print("Done for Batch: ",k, "Sequences Done: ",count, "Time Taken: %d seconds"%round(end_time-start_time))
                #print("Done for batch: ",k, "example: ",ex, "count: ",count)
    pop_size = count * params['numMultiHeads'] #* int(np.ceil(attn_cutoff)) #total sequences tested x # multi heads x number of top attn scores allowed
    #return final_all, pop_size
    return pop_size

def estimate_interactions_bg(num_filters, params, tomtom_data, motif_dir, verbose = False, CNNfirstpool = 6, sequence_len = 200, pos_score_cutoff = 0.65, seq_limit = -1, attn_cutoff = 0.25, for_background = False, numWorkers=1, storeInterCNN = True, considerTopHit = True):
    
    global Prob_Attention_All_neg# = res_test[3]
    global Seqs_neg# = res_test[6]
    global LabelPreds_neg# = res_test[4]
    global Filter_Intr_Attn_neg
    global Filter_Intr_Pos_neg
    global Filter_Intr_Keys
    
    final_all = [['Batch','ExNo','SeqHeader','SingleHeadNo','PositionA','PositionB','AveragePosDiff','AttnScore','PositionAInfo','PositionBInfo']]
    count = 0       
    for k in range(0,len(Prob_Attention_All_neg)): #going through all batches
        start_time = time.time()
        if count == seq_limit: #break if seq_limit number of sequences tested
            break
        
        PAttn = Prob_Attention_All_neg[k]
        if storeInterCNN:
            with open(PAttn,'rb') as f:
                PAttn = pickle.load(f)
        
        #PAttn = PAttn.detach().cpu().numpy()
        feat_size = PAttn.shape[1]
        per_batch_labelPreds = LabelPreds_neg[k]
        
        if num_labels == 2:
            if for_background:
                tp_indices = [i for i in range(0,per_batch_labelPreds.shape[0])]
            else:
                tp_indices = [i for i in range(0,per_batch_labelPreds.shape[0]) if (per_batch_labelPreds[i][0]==1 and per_batch_labelPreds[i][1]>pos_score_cutoff)]
            #if for_background and argSpace.intBackground != None:
            #   tp_indices = [i for i in range(0,per_batch_labelPreds.shape[0]) if (per_batch_labelPreds[i][0]==0 and per_batch_labelPreds[i][1]<(1-pos_score_cutoff))]
            #else:
            #   tp_indices = [i for i in range(0,per_batch_labelPreds.shape[0]) if (per_batch_labelPreds[i][0]==1 and per_batch_labelPreds[i][1]>pos_score_cutoff)]
        else:
            tp_indices = [i for i in range(0,per_batch_labelPreds['labels'].shape[0])]
        
        #if for_background:
        #   tp_indices = [i for i in range(0,per_batch_labelPreds.shape[0]) if (per_batch_labelPreds[i][0]==0 and per_batch_labelPreds[i][1]<(1-pos_score_cutoff))] #neg classified examples < (1-0.6)
        #else:
        #   tp_indices = [i for i in range(0,per_batch_labelPreds.shape[0]) if (per_batch_labelPreds[i][0]==1 and per_batch_labelPreds[i][1]>pos_score_cutoff)] #pos classified examples > 0.6
        
        #tp_indices = tp_indices[:10] #get top 5 from each batch
        
        print('Generating sequence position information...')
        seq_info_dict = get_filters_in_seq_dict(Seqs_neg[k],motif_dir_neg,num_filters,CNNfirstpool,numWorkers=numWorkers)
        print('Done!')
        
        
        fdata = []
        for ex in tp_indices:
            header = np.asarray(Seqs_neg[k])[ex][0]
            fdata.append([count,header,seq_info_dict[header],k,ex,params,tomtom_data,attn_cutoff,sequence_len,CNNfirstpool,num_filters,motif_dir,feat_size,storeInterCNN, considerTopHit])
            count += 1
            if count == seq_limit:
                break
            
            ##ex = 1#4
            #header = np.asarray(Seqs[k])[ex][0]
            
            ##############------New Code-------###############
            #score_individual_head(ex,PAttn,params,attn_cutoff,sequence_len,CNNfirstpool,num_filters,motif_dir,feat_size)
        with Pool(processes = numWorkers) as pool:
            result = pool.map(score_individual_head_bg, fdata, chunksize=1)
        
        for element in result:
            bid = element[0]
            Filter_Intr_Pos_neg[:,bid] = element[2]
            Filter_Intr_Attn_neg[:,bid] = element[1]
        
        #pdb.set_trace()    
            #final_all += [entry for ent in result for entry in ent] #unravel 

        end_time = time.time()
        if argSpace.verbose:    
            print("Done for Batch: ",k, "Sequences Done: ",count, "Time Taken: %d seconds"%round(end_time-start_time))
                #print("Done for batch: ",k, "example: ",ex, "count: ",count)
    pop_size = count * params['numMultiHeads'] #* int(np.ceil(attn_cutoff)) #total sequences tested x # multi heads x number of top attn scores allowed
    #return final_all, pop_size
    return pop_size

def get_stats(Main_Res,Main_Pop,tomtomdata, considerTopHit = True):
    filter_dict = {}                                                                                                                                                                               
    for entry in Main_Res[1:]:    
        header = entry[2]                                                                                                                                                             
        A = entry[-2].split(',')                                                                                                                                                                   
        B = entry[-1].split(',')                                                                                                                                                                   
        for enA in A:                                                                                                                                                                              
            if enA.split(':')[2] == '-':                                                                                                                                                           
                continue                                                                                                                                                                           
            for enB in B:                                                                                                                                                                          
                if enB.split(':')[2] == '-':                                                                                                                                                       
                    continue                                                                                                                                                                       
                if enA.split(':')[2] == enB.split(':')[2]:                                                                                                                                         
                    continue                                                                                                                                                                       
                    
                intr = enA.split(':')[2]+'<-->'+enB.split(':')[2]
                intr_rev = enB.split(':')[2]+'<-->'+enA.split(':')[2]
                if (intr not in filter_dict) and (intr_rev not in filter_dict):
                    filter_dict[intr] = [header, 0,0,1, [entry[6]]]
                else:
                    if intr in filter_dict:
                        if filter_dict[intr][0] != header:
                            filter_dict[intr][0] = header
                            filter_dict[intr][-2] += 1
                            filter_dict[intr][-1].append(entry[6])  
                    elif intr_rev in filter_dict:
                        if filter_dict[intr_rev][0] != header:
                            filter_dict[intr_rev][0] = header
                            filter_dict[intr_rev][-2] += 1
                            filter_dict[intr_rev][-1].append(entry[6]) 
                
                
    #pdb.set_trace()
    #motifs = list(set(tomtom_data[1:,1])) 
    #motifs_dict = {}                                                                                                                                                                               
    #for entry in motifs:                                                                                                                                                                           
    #   motifs_dict[entry] = [0, []]    
    motifs_dict = {}    
    for i in range(0,num_filters):
        fltr = 'filter'+str(i)
        res = tomtomdata[np.argwhere(tomtomdata[:,0]==fltr).flatten()] 
        if len(res)!=0:
            if considerTopHit:
                res = res[np.argmin(res[:,5])][1] ###############!!!!!!!!!!!!!!!!!!! convert to float!!
                if res not in motifs_dict:
                    motifs_dict[res] = [1, [fltr]]
                else:
                    motifs_dict[res][0] += 1
                    motifs_dict[res][1].append(fltr)
            else:
                ress = res[:,1]
                for res in ress:
                    if res not in motifs_dict:
                        motifs_dict[res] = [1, [fltr]]
                    else:
                        motifs_dict[res][0] += 1
                        motifs_dict[res][1].append(fltr)
    
    for key in filter_dict:
        flag = False
        keyA, keyB = key.split('<-->')
        
        if keyA in motifs_dict:
            lA = motifs_dict[keyA][1]
        else:
            flag = True
        if keyB in motifs_dict:
            lB = motifs_dict[keyB][1]
        else:
            flag = True
        
        nA = len(list(set(lA)-set(lB)))
        nB = len(list(set(lB)-set(lA)))
        
        
        #nA,nB = len(lA),len(lB)
        if nA == 0 or nB == 0:
            flag = True
        
        if flag:
            filter_dict[key] = ['-',0, 0, 0, []]
            continue
        
        total_comp = nA*nB
        normalize_val = total_comp * Main_Pop
        
        filter_dict[key][1] = filter_dict[key][-2]
        filter_dict[key][2] = normalize_val
        filter_dict[key][-2] = filter_dict[key][1]/normalize_val
    
    return filter_dict

def get_motifs_interactions(fltr_intr_keys,tomtomData,considerTopHit=True,noHeaderTomTom = False):
    fltr_to_motif_dict = {}
    
    if noHeaderTomTom:
        motifsA = list(set(tomtomData[:,1]))
        motifsB = list(set(tomtomData[:,1]))
    else:   
        motifsA = list(set(tomtomData[1:,1]))
        motifsB = list(set(tomtomData[1:,1]))
    
    for mA in motifsA:
        for mB in motifsB:
            if mA != mB:
                resA = tomtomData[np.argwhere(tomtomData[:,1]==mA).flatten()]
                resB = tomtomData[np.argwhere(tomtomData[:,1]==mB).flatten()]
                
                fltrA = resA[np.argmin(resA[:,5].astype(float))][0]
                fltrB = resB[np.argmin(resB[:,5].astype(float))][0]
                
                if fltrA == fltrB:
                    continue
                key = fltrA+'<-->'+fltrB
                
                keyM = mA+'<-->'+mB
                rev_keyM = mB+'<-->'+mA
                
                if keyM not in fltr_to_motif_dict and rev_keyM not in fltr_to_motif_dict:
                        fltr_to_motif_dict[keyM] = [key]

    
    
    return fltr_to_motif_dict





if argSpace.featInteractions:
    Interact_dir = output_dir + '/Interactions_Results'

    if not os.path.exists(Interact_dir):
        os.makedirs(Interact_dir)
    
    #add this functionality later
    #background = get_background_seqs(Seqs, bg_type = argSpace.intBackground, limit = argSpace.intSeqLimit)
    tomtom_data = np.loadtxt(motif_dir+'/tomtom/tomtom.tsv',dtype=str,delimiter='\t')
    if argSpace.intBackground != None:
        tomtom_data_neg = np.loadtxt(motif_dir_neg+'/tomtom/tomtom.tsv',dtype=str,delimiter='\t')
    num_filters = params['CNN_filters']
    CNNfirstpool = params['CNN_poolsize']
    sequence_len = len(res_test[6][0][0][1])
    
    Prob_Attention_All = res_test[3]
    Seqs = res_test[6]
    LabelPreds = res_test[4]
    
    Filter_Intr_Keys = {}
    count_index = 0
    for i in range(0,num_filters):
        for j in range(0,num_filters):
            if i == j:
                continue
            intr = 'filter'+str(i)+'<-->'+'filter'+str(j)
            rev_intr = 'filter'+str(j)+'<-->'+'filter'+str(i)
            
            if intr not in Filter_Intr_Keys and rev_intr not in Filter_Intr_Keys:
                Filter_Intr_Keys[intr] = count_index
                count_index += 1
    
            
    Filter_Intr_Attn = np.ones((len(Filter_Intr_Keys),numPosExamples))*-1
    Filter_Intr_Pos = np.ones((len(Filter_Intr_Keys),numPosExamples)).astype(int)*-1
    
    
    
    Main_Pop = estimate_interactions(num_filters, params, tomtom_data, motif_dir, verbose = argSpace.verbose, CNNfirstpool = CNNfirstpool, 
                                               sequence_len = sequence_len, pos_score_cutoff = argSpace.scoreCutoff, seq_limit = argSpace.intSeqLimit, attn_cutoff = argSpace.attnCutoff,
                                               for_background = False, numWorkers = argSpace.numWorkers, storeInterCNN = argSpace.storeInterCNN, considerTopHit = argSpace.considerTopHit) #argSpace.intSeqLimit
    #print(lohahi)
    
    Filter_Intr_Attn_neg = np.ones((len(Filter_Intr_Keys),numNegExamples))*-1
    Filter_Intr_Pos_neg = np.ones((len(Filter_Intr_Keys),numNegExamples)).astype(int)*-1
    
    if argSpace.intBackground == 'negative':
        Bg_Pop = estimate_interactions(num_filters, params, tomtom_data_neg, motif_dir_neg, verbose = argSpace.verbose, CNNfirstpool = CNNfirstpool, 
                                               sequence_len = sequence_len, pos_score_cutoff = argSpace.scoreCutoff, seq_limit = argSpace.intSeqLimit, attn_cutoff = argSpace.attnCutoff,
                                               for_background = True, numWorkers = argSpace.numWorkers, storeInterCNN = argSpace.storeInterCNN, considerTopHit = argSpace.considerTopHit) 
    
    elif argSpace.intBackground == 'shuffle':
        Prob_Attention_All_neg = res_test_bg[3]
        Seqs_neg = res_test_bg[6]
        LabelPreds_neg = res_test_bg[4]

        
        Bg_Pop = estimate_interactions_bg(num_filters, params, tomtom_data_neg, motif_dir_neg, verbose = argSpace.verbose, CNNfirstpool = CNNfirstpool, 
                                               sequence_len = sequence_len, pos_score_cutoff = argSpace.scoreCutoff, seq_limit = argSpace.intSeqLimit, attn_cutoff = argSpace.attnCutoff,
                                               for_background = True, numWorkers = argSpace.numWorkers, storeInterCNN = argSpace.storeInterCNN, considerTopHit = argSpace.considerTopHit) 
    
    
    #Main_Res, Main_Pop = estimate_interactions(res_test[6], res_test[3], res_test[4], num_filters, params, tomtom_data, motif_dir, verbose = argSpace.verbose, CNNfirstpool = CNNfirstpool, 
    #                     sequence_len = sequence_len, pos_score_cutoff = argSpace.scoreCutoff, seq_limit = argSpace.intSeqLimit, attn_cutoff = argSpace.attnCutoff, for_background = False, numWorkers = argSpace.argSpace.numWorkers) #argSpace.intSeqLimit
    
    
    #Bg_Res, Bg_Pop = estimate_interactions(res_test[6], res_test[3], res_test[4], num_filters, params, tomtom_data_neg, motif_dir_neg, verbose = argSpace.verbose, CNNfirstpool = CNNfirstpool,
    #                     sequence_len = sequence_len, pos_score_cutoff = argSpace.scoreCutoff, seq_limit = argSpace.intSeqLimit , attn_cutoff = argSpace.attnCutoff, for_background = True, numWorkers = argSpace.argSpace.numWorkers) #argSpace.intSeqLimit
        
    
    
    #attnLimit = argSpace.attnCutoff if argSpace.attnCutoff != -1 else 0.10#np.mean(Filter_Intr_Attn[Filter_Intr_Attn!=-1])
    #print(attnLimit)
    
    
    with open(Interact_dir+'/interaction_keys_dict.pckl','wb') as f:
        pickle.dump(Filter_Intr_Keys,f)
    
    with open(Interact_dir+'/background_results_raw.pckl','wb') as f:
        pickle.dump([Filter_Intr_Attn_neg,Filter_Intr_Pos_neg],f)
        
    
    with open(Interact_dir+'/main_results_raw.pckl','wb') as f:
        pickle.dump([Filter_Intr_Attn,Filter_Intr_Pos],f)
        

    
    resMain = Filter_Intr_Attn[Filter_Intr_Attn!=-1]                                                                                                                                               
    resBg = Filter_Intr_Attn_neg[Filter_Intr_Attn_neg!=-1]
    resMainHist = np.histogram(resMain,bins=20)
    resBgHist = np.histogram(resBg,bins=20)
    plt.plot(resMainHist[1][1:],resMainHist[0]/sum(resMainHist[0]),linestyle='--',marker='o',color='g',label='main')
    plt.plot(resBgHist[1][1:],resBgHist[0]/sum(resBgHist[0]),linestyle='--',marker='x',color='r',label='background')

    plt.legend(loc='best',fontsize=10)
    plt.savefig(Interact_dir+'/normalized_Attn_scores_distributions.pdf')
    plt.clf()
    
    plt.hist(resMain,bins=20,color='g',label='main')
    plt.hist(resBg,bins=20,color='r',alpha=0.5,label='background')
    plt.legend(loc='best',fontsize=10)
    plt.savefig(Interact_dir+'/Attn_scores_distributions.pdf')
    plt.clf()
    
    
    Bg_MaxMean = []
    Main_MaxMean = []
    
    for entry in Filter_Intr_Attn:
        try:
            Main_MaxMean.append([np.max(entry[entry!=-1]),np.mean(entry[entry!=-1])])
        except:
            continue
        
    for entry in Filter_Intr_Attn_neg:
        try:
            Bg_MaxMean.append([np.max(entry[entry!=-1]),np.mean(entry[entry!=-1])])
        except:
            continue
        
    Bg_MaxMean = np.asarray(Bg_MaxMean)
    Main_MaxMean = np.asarray(Main_MaxMean)
    
    plt.hist(Main_MaxMean[:,0],bins=20,color='g',label='main')
    plt.hist(Bg_MaxMean[:,0],bins=20,color='r',alpha=0.5,label='background')
    plt.legend(loc='best',fontsize=10)
    plt.savefig(Interact_dir+'/Attn_scores_distributions_MaxPerInteraction.pdf')
    plt.clf()
    
    plt.hist(Main_MaxMean[:,1],bins=20,color='g',label='main')
    plt.hist(Bg_MaxMean[:,1],bins=20,color='r',alpha=0.5,label='background')
    plt.legend(loc='best',fontsize=10)
    plt.savefig(Interact_dir+'/Attn_scores_distributions_MeanPerInteraction.pdf')
    plt.clf()
    
    
    
    
    attnLimits = [argSpace.attnCutoff]#[argSpace.attnCutoff * i for i in range(1,11)] #save results for 10 different attention cutoff values (maximum per interaction) eg. [0.05, 0.10, 0.15, 0.20, 0.25, ...]
    
    for attnLimit in attnLimits:
        pval_info = []#{}
        for i in range(0,Filter_Intr_Attn.shape[0]):                                                                                                                                                   
            pos_attn = Filter_Intr_Attn[i,:]                                                                                                                                                              
            pos_attn = pos_attn[pos_attn!=-1]#pos_attn[pos_attn>0.04] #pos_attn[pos_attn!=-1]                                                                                                                                                                   
            neg_attn = Filter_Intr_Attn_neg[i,:]                                                                                                                                                          
            neg_attn = neg_attn[neg_attn!=-1]#neg_attn[neg_attn>0.04] #neg_attn[neg_attn!=-1] 
            
            
            num_pos = len(pos_attn)
            num_neg = len(neg_attn)
            
            if len(pos_attn) <= 1:# or len(neg_attn) <= 1:
                continue
            
            if len(neg_attn) <= 1: #if just 1 or 0 values in neg attn, get a vector with all values set to 0 (same length as pos_attn)
                neg_attn = np.asarray([0 for i in range(0,num_pos)])
            
            if np.max(pos_attn) < attnLimit: # 
                continue
            
            pos_posn = Filter_Intr_Pos[i,:]  
            #pos_posn_mean = pos_posn[pos_posn!=-1].mean()
            pos_posn_mean = pos_posn[np.argmax(Filter_Intr_Attn[i,:])] #just pick the max
            
            neg_posn = Filter_Intr_Pos_neg[i,:]  
            #neg_posn_mean = neg_posn[neg_posn!=-1].mean()
            neg_posn_mean = neg_posn[np.argmax(Filter_Intr_Attn_neg[i,:])] #just pick the max
                                                                                                                                                                            
                                                                                                                                                                                  
            stats,pval = mannwhitneyu(pos_attn,neg_attn,alternative='greater')#ttest_ind(pos_d,neg_d)#mannwhitneyu(pos_d,neg_d,alternative='greater')                                                        
            pval_info.append([i, pos_posn_mean, neg_posn_mean,num_pos,num_neg, stats,pval])#pval_dict[i] = [i,stats,pval]                                                                                                                                                              
            #if i%100==0:                                                                                                                                                                               
            #   print('Done: ',i) 
        
        
        pval_info = np.asarray(pval_info)
        
        res_final = pval_info#[pval_info[:,-1]<0.01] #can be 0.05 or any other threshold #For now, lets take care of this in post processing (jupyter notebook)
        
        res_final_int = []                                                                                                                                                                             
                                                                                                                                                                         
        for i in range(0,res_final.shape[0]):                                                                                                                                                          
            #res_final_int.append([res_final[i][-1],Filter_Intr_Keys[int(res_final[i][0])]])                                                                                                           
            value = int(res_final[i][0])                                                                                                                                                               
            pval = res_final[i][-1]
            pp_mean = res_final[i][1]
            np_mean = res_final[i][2]  
            num_pos = res_final[i][3]
            num_neg = res_final[i][4]         
            stats = res_final[i][-2]                                                                                                                                                         
            for key in Filter_Intr_Keys:                                                                                                                                                               
                if Filter_Intr_Keys[key] == value:                                                                                                                                                     
                    res_final_int.append([key,value,pp_mean,np_mean,num_pos,num_neg,stats,pval])  
        
        res_final_int = np.asarray(res_final_int) 
        qvals = multipletests(res_final_int[:,-1].astype(float), method='fdr_bh')[1] #res_final_int[:,1].astype(float)
        res_final_int = np.column_stack((res_final_int,qvals))
        
        final_interactions = [['filter_interaction','example_no','motif1','motif1_qval','motif2','motif2_qval','mean_distance','mean_distance_bg','num_obs','num_obs_bg','pval','adjusted_pval']]
        for entry in res_final_int:                                                                                                                                                                    
            f1,f2 = entry[0].split('<-->')                                                                                                                                                             
                                                                                                                                                                          
            m1_ind = np.argwhere(tomtom_data[:,0]==f1)                                                                                                                                                 
            m2_ind = np.argwhere(tomtom_data[:,0]==f2)                                                                                                                                                 
            #print(m1_ind,m2_ind)
            if len(m1_ind) == 0 or len(m2_ind) == 0:
                continue
            m1 = tomtom_data[m1_ind[0][0]][1]
            m2 = tomtom_data[m2_ind[0][0]][1]
            m1_pval = tomtom_data[m1_ind[0][0]][5]
            m2_pval = tomtom_data[m2_ind[0][0]][5]
            final_interactions.append([entry[0],entry[1],m1,m1_pval,m2,m2_pval,entry[2],entry[3],entry[4],entry[5],entry[-2],entry[-1]])
            #print(entry[-1],m1,m2,entry[0])
        
        
        np.savetxt(Interact_dir+'/interactions_summary_attnLimit-'+str(attnLimit)+'.txt',final_interactions,fmt='%s',delimiter='\t')
        
        with open(Interact_dir+'/processed_results_attnLimit-'+str(attnLimit)+'.pckl','wb') as f:
            pickle.dump([pval_info,res_final_int],f)
        
        print("Done for Attention Cutoff Value: ",str(attnLimit))
        

    
  
    
    
    
    

