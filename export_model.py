"""Run with a CPU torch environment; requires onnx and original weights in vendor/."""
from pathlib import Path
import torch
R=Path(__file__).resolve().parent
src=(R/'vendor/srvgg_arch.py').read_text().replace('from basicsr.utils.registry import ARCH_REGISTRY','').replace('@ARCH_REGISTRY.register()','')
ns={};exec(src,ns)
m=ns['SRVGGNetCompact'](num_conv=32,num_feat=64,upscale=4,act_type='prelu')
w=torch.load(R/'vendor/general-x4v3.pth',map_location='cpu',weights_only=True)
m.load_state_dict(w.get('params_ema',w.get('params',w)));m.eval()
torch.onnx.export(m,torch.zeros(1,3,64,64),str(R/'models/general-x4v3.onnx'),
    input_names=['input'],output_names=['output'],opset_version=17,dynamo=False,
    dynamic_axes={'input':{0:'batch',2:'height',3:'width'},'output':{0:'batch',2:'out_height',3:'out_width'}})
print('Exported dynamic N/H/W')
