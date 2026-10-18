from pathlib import Path
import json
import joblib
import numpy as np
import torch
from transformers import AutoTokenizer, AutoModelForSequenceClassification
from underthesea import word_tokenize
from neural_model import NeuralFusion

class Predictor:
    def __init__(self, model_dir, device='cpu'):
        root=Path(model_dir); self.device=torch.device(device)
        self.config=json.loads((root/'config.json').read_text(encoding='utf-8'))
        self.labels=self.config['labels']
        self.tokenizer=AutoTokenizer.from_pretrained(root/'phobert_text')
        self.text=AutoModelForSequenceClassification.from_pretrained(root/'phobert_text').to(self.device).eval()
        self.icon=joblib.load(root/'xgboost_icon.joblib')
        ck=torch.load(root/'neural_fusion.pt',map_location=self.device,weights_only=True)
        self.fusion=NeuralFusion(**ck['architecture']).to(self.device)
        self.fusion.load_state_dict(ck['state_dict']); self.fusion.eval()

    @torch.no_grad()
    def predict(self, text_no_icons, occurrences=None):
        # occurrences: one dict per icon, SAME extraction/schema as EDA notebook.
        # Raw icon extraction is intentionally delegated to the EDA preprocessing.
        occurrences=[] if occurrences is None else occurrences
        text=word_tokenize(text_no_icons,format='text') if text_no_icons.strip() else ''
        enc=self.tokenizer(text,return_tensors='pt',truncation=True,max_length=self.config['max_length'])
        pt=self.text(**{k:v.to(self.device) for k,v in enc.items()}).logits.softmax(-1)
        if occurrences:
            records=[]
            for row in occurrences:
                d={'icon='+str(row['icon']):1,'kind='+str(row['icon_kind']):1}
                for name in self.config['numeric_icon_features']:
                    value=row[name]; d[name]=float(value) if value is not None and np.isfinite(float(value)) else 0.0
                records.append(d)
            pi=self.icon['model'].predict_proba(self.icon['vectorizer'].transform(records)).mean(axis=0)
        else:
            pi=self.icon['prior']
        pi=torch.tensor(pi,dtype=torch.float32,device=self.device).unsqueeze(0)
        count=torch.tensor([[len(occurrences)]],dtype=torch.float32,device=self.device)
        lf,lt,li,g=self.fusion(pt,pi,count)
        prob=lf.softmax(-1)[0].cpu().numpy()
        return {'label':self.labels[int(prob.argmax())],
                'probabilities':dict(zip(self.labels,map(float,prob))), 'gate':float(g.item())}
