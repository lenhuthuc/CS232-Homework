import torch
from torch import nn

class NeuralFusion(nn.Module):
    def __init__(self, n_classes=2, hidden=32, dropout=0.2):
        super().__init__()
        def branch():
            return nn.Sequential(nn.Linear(n_classes,hidden),nn.ReLU(),nn.Dropout(dropout),nn.Linear(hidden,hidden),nn.ReLU())
        def classifier():
            return nn.Sequential(nn.Linear(hidden,16),nn.ReLU(),nn.Dropout(dropout),nn.Linear(16,n_classes))
        self.text_mlp=branch()
        self.icon_mlp=branch()
        self.text_classifier=classifier()
        self.icon_classifier=classifier()
        self.gate=nn.Sequential(nn.Linear(2*hidden+1,24),nn.ReLU(),nn.Linear(24,1))
        self.fusion_classifier=classifier()

    def forward(self,pt,pi,count):
        ht=self.text_mlp(pt)
        hi=self.icon_mlp(pi)
        g=torch.sigmoid(self.gate(torch.cat([ht,hi,torch.log1p(count)],dim=1)))
        g=g*(count>0).to(g.dtype)
        logits_text=self.text_classifier(ht)
        logits_icon=self.icon_classifier(hi)
        logits_fused=self.fusion_classifier((1-g)*ht+g*hi)
        logits_fused=torch.where(count>0,logits_fused,logits_text)
        return logits_fused,logits_text,logits_icon,g
