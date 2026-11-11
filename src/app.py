from pathlib import Path
import argparse, json, os, queue, sys, threading, traceback, webbrowser
from engine import Config, Runner, Cancelled, resource

REPOSITORY_URL = 'https://github.com/zhonghonggg/Remote-Sensing-Super-Resolution'

def cli(args):
    p=argparse.ArgumentParser()
    p.add_argument('--input',required=True);p.add_argument('--output',required=True)
    p.add_argument('--resolution',type=float,default=.2);p.add_argument('--cpu',action='store_true')
    p.add_argument('--report');p.add_argument('--tile',type=int,default=256);p.add_argument('--batch',type=int,default=4)
    a=p.parse_args(args)
    events=[]
    def note(*e):
        events.append(e)
        if sys.stdout:print(json.dumps(e,ensure_ascii=False),flush=True)
    report={}
    try:
        result=Runner(Config(a.input,a.output,a.resolution,a.cpu,a.tile,a.batch),note).run()
        report={'success':True,'output':str(result)}
        return 0
    except Exception as exc:
        report={'success':False,'error':str(exc),'traceback':traceback.format_exc()}
        return 1
    finally:
        if a.report:Path(a.report).write_text(json.dumps(dict(report,events=events),ensure_ascii=False,indent=2),encoding='utf-8')

def gui():
    import tkinter as tk
    from tkinter import ttk,filedialog,messagebox
    from tkinter.scrolledtext import ScrolledText
    root=tk.Tk();root.title('遥感影像超分辨率工具V1.0');root.geometry('850x670');root.minsize(720,560)
    root.iconbitmap(str(resource('assets/geosr.ico')))
    root.columnconfigure(1,weight=1);root.rowconfigure(9,weight=1)
    source=tk.StringVar();output=tk.StringVar();res=tk.StringVar(value='0.2');cpu=tk.BooleanVar()
    status=tk.StringVar(value='就绪');device=tk.StringVar(value='设备：自动 DirectML / CPU')
    q=queue.Queue();cancel=threading.Event();running=False;logs=[];result=None
    def browse_in():
        f=filedialog.askopenfilename(filetypes=[('GeoTIFF','*.tif *.tiff')])
        if f:source.set(f)
    def browse_out():
        f=filedialog.askdirectory()
        if f:output.set(f)
    ttk.Label(root,text='遥感影像超分辨率工具',font=('Microsoft YaHei UI',19,'bold')).grid(row=0,column=0,columnspan=3,sticky='w',padx=18,pady=(16,6))
    intro=ttk.Frame(root)
    intro.grid(row=1,column=0,columnspan=3,sticky='ew',padx=18,pady=6)
    ttk.Label(intro,text='One-pass 4x AI enhancement, resampled to the target pixel size in metres. AI enhancement does not imply measured accuracy. Based on SRVGGNetCompact. Produced by ZhongHong',wraplength=780).pack(anchor='w')
    from tkinter import font as tkfont
    link_font=tkfont.nametofont('TkDefaultFont').copy()
    link_font.configure(underline=True)
    repository_link=ttk.Label(intro,text=REPOSITORY_URL,cursor='hand2',font=link_font,takefocus=True)
    repository_link.pack(anchor='w',pady=(2,0))
    def open_repository(event=None):
        try:
            if not webbrowser.open(REPOSITORY_URL,new=2):
                messagebox.showerror('打开仓库失败',f'请在浏览器中打开：\n{REPOSITORY_URL}')
        except Exception as exc:
            messagebox.showerror('打开仓库失败',f'{exc}\n{REPOSITORY_URL}')
        return 'break'
    repository_link.bind('<Button-1>',open_repository)
    repository_link.bind('<Return>',open_repository)
    repository_link.bind('<space>',open_repository)
    fields=[]
    for row,label,var,command in [(2,'原图 GeoTIFF',source,browse_in),(3,'成果保存目录',output,browse_out)]:
        ttk.Label(root,text=label).grid(row=row,column=0,sticky='w',padx=18,pady=6)
        e=ttk.Entry(root,textvariable=var);e.grid(row=row,column=1,sticky='ew',pady=6)
        b=ttk.Button(root,text='浏览…',command=command);b.grid(row=row,column=2,padx=18);fields.extend([e,b])
    ttk.Label(root,text='目标像元（米）').grid(row=4,column=0,padx=18,sticky='w')
    e=ttk.Entry(root,textvariable=res);e.grid(row=4,column=1,sticky='w');fields.append(e)
    cb=ttk.Checkbutton(root,text='强制 CPU',variable=cpu);cb.grid(row=4,column=2);fields.append(cb)
    bar=ttk.Progressbar(root,maximum=100);bar.grid(row=5,column=0,columnspan=3,sticky='ew',padx=18,pady=(16,8))
    ttk.Label(root,textvariable=status).grid(row=6,column=0,columnspan=2,sticky='w',padx=18)
    ttk.Label(root,textvariable=device).grid(row=6,column=2,sticky='e',padx=18)
    buttons=ttk.Frame(root);buttons.grid(row=7,column=0,columnspan=3,sticky='w',padx=18,pady=10)
    ttk.Label(root,text='支持 8/16 位灰度、RGB、RGBA；输出8位 RGB + Alpha。日志可另存。').grid(row=8,column=0,columnspan=3,sticky='w',padx=18)
    log=ScrolledText(root,wrap='word',font=('Microsoft YaHei UI',10),state='disabled')
    log.grid(row=9,column=0,columnspan=3,sticky='nsew',padx=18,pady=12)
    def append(text):
        import datetime
        line=f'{datetime.datetime.now():%H:%M:%S}  {text}'
        logs.append(line);log.configure(state='normal');log.insert('end',line+'\n');log.see('end');log.configure(state='disabled')
        # Bound GUI memory; user can save the retained recent 5000 messages.
        if len(logs)>5000:logs.pop(0);log.configure(state='normal');log.delete('1.0','2.0');log.configure(state='disabled')
    def worker(cfg):
        try:q.put(('success',Runner(cfg,lambda *e:q.put(('event',e)),cancel).run()))
        except Cancelled as exc:q.put(('cancel',str(exc)))
        except Exception:q.put(('error',traceback.format_exc()))
    def start():
        nonlocal running,result
        try:
            r=float(res.get())
            if not Path(source.get()).is_file():raise ValueError('请选择有效的原图')
            if not output.get():raise ValueError('请选择成果目录')
            if not 0<r<float('inf'):raise ValueError('目标像元必须为有限正数')
        except Exception as exc:messagebox.showerror('输入错误',str(exc));return
        running=True;result=None;cancel.clear();bar['value']=0
        for w in fields+[start_button]:w.configure(state='disabled')
        cancel_button.configure(state='normal');status.set('准备中')
        threading.Thread(target=worker,args=(Config(source.get(),output.get(),r,cpu.get()),),daemon=False).start()
    def stop():cancel.set();status.set('正在取消：等待当前推理 / 分块结束并清理');cancel_button.configure(state='disabled')
    def open_output():
        if output.get() and Path(output.get()).is_dir():os.startfile(output.get())
    def save_log():
        f=filedialog.asksaveasfilename(defaultextension='.txt',initialfile='超分日志.txt')
        if f:Path(f).write_text('\n'.join(logs),encoding='utf-8')
    start_button=ttk.Button(buttons,text='开始超分',command=start);start_button.pack(side='left',padx=(0,10))
    cancel_button=ttk.Button(buttons,text='取消',command=stop,state='disabled');cancel_button.pack(side='left',padx=(0,10))
    ttk.Button(buttons,text='打开成果目录',command=open_output).pack(side='left',padx=(0,10))
    ttk.Button(buttons,text='另存日志',command=save_log).pack(side='left')
    def poll():
        nonlocal running,result
        # Process at most 100 messages per tick so large jobs cannot starve the UI.
        for _ in range(100):
            try:kind,data=q.get_nowait()
            except queue.Empty:break
            if kind=='event':
                stage,percent,dev,message=data;bar['value']=percent;status.set(f'{stage} · {percent:.1f}%');device.set(f'设备：{dev}');append(f'[{stage}] {message}')
            else:
                running=False
                for w in fields+[start_button]:w.configure(state='normal')
                cancel_button.configure(state='disabled')
                if kind=='success':result=data;status.set('完成 · 已校验并清理临时文件');append(f'成果：{data}');messagebox.showinfo('完成',f'已生成：\n{data}')
                elif kind=='cancel':status.set('已取消 · 临时文件已清理');append(data)
                else:status.set('失败 · 查看日志');append(data);messagebox.showerror('处理失败',data.splitlines()[-1])
        root.after(100,poll)
    def close():
        if running:stop();append('请等待任务取消和清理结束后关闭窗口')
        else:root.destroy()
    root.protocol('WM_DELETE_WINDOW',close);poll();root.mainloop()

if __name__=='__main__':
    if '--input' in sys.argv:sys.exit(cli(sys.argv[1:]))
    gui()
