import os
import gc
import re
import warnings  # 导入警告控制模块
import threading  # 引入多线程支持，防止大文件处理时界面卡死

# === 1. 忽略所有 Matplotlib/UserWarning 警告 ===
warnings.filterwarnings("ignore")

import tkinter as tk
from tkinter import ttk, filedialog, messagebox
import pandas as pd
import numpy as np

# === 2. 强制设置 Matplotlib 后端为 'TkAgg' ===
import matplotlib

matplotlib.use('TkAgg')

# === 3. 动态加载 Windows 系统内置字体文件 ===
from matplotlib import font_manager

if os.name == 'nt':  # 仅在 Windows 环境下执行
    font_paths = [
        r'C:\Windows\Fonts\simsun.ttc',  # 宋体
        r'C:\Windows\Fonts\times.ttf',  # Times New Roman 常规
        r'C:\Windows\Fonts\timesbd.ttf',  # Times New Roman 粗体
        r'C:\Windows\Fonts\timesi.ttf',  # Times New Roman 斜体
        r'C:\Windows\Fonts\timesbi.ttf',  # Times New Roman 粗斜体
        r'C:\Windows\Fonts\msyh.ttc',  # 微软雅黑
        r'C:\Windows\Fonts\simhei.ttf'  # 黑体
    ]
    for path in font_paths:
        if os.path.exists(path):
            try:
                font_manager.fontManager.addfont(path)
            except Exception:
                pass

import matplotlib.pyplot as plt
import matplotlib.dates as mdates
from matplotlib.backends.backend_tkagg import FigureCanvasTkAgg, NavigationToolbar2Tk
from datetime import datetime

# === 4. 学术中英混排核心字体配置 ===
# 全局默认字体设为 Times New Roman，纯数字/纯英文章节（如坐标刻度）将自动直接调用
plt.rcParams['font.family'] = 'serif'
plt.rcParams['font.serif'] = ['Times New Roman', 'DejaVu Serif', 'serif']
# 启用 stix 数学字体集（该字体集的正体与 Times New Roman 视觉效果高度一致）
plt.rcParams['mathtext.fontset'] = 'stix'
plt.rcParams['axes.unicode_minus'] = False  # 正常显示负号

# 内置表头定义（对应 title.txt 前25列）
COLUMNS = [
    "点名", "北坐标", "东坐标", "高程", "编码", "解状态",
    "RMSH", "RMSV", "卫星数", "PDOP", "日期", "时间",
    "里程", "偏距", "天线高", "实际平滑次数", "基站空间距",
    "基站平面距", "差分Age", "存储类型", "点名_备份", "存储位置",
    "中桩里程", "中桩高程", "GPS时间"
]

# 统一的文件选择器过滤器，确保在各种操作系统下均能正常筛选并选择 CSV 文件
COMMON_FILETYPES = [
    ("所有支持的数据文件", "*.txt *.dat *.csv"),
    ("CSV 逗号分隔文件 (*.csv)", "*.csv"),
    ("南方RTK数据文件 (*.dat)", "*.dat"),
    ("文本文件 (*.txt)", "*.txt"),
    ("所有文件 (*.*)", "*.*")
]

# === 5. 内置 Base64 格式的专业级软件默认图标 ===
DEFAULT_ICON_BASE64 = """
iVBORw0KGgoAAAANSUhEUgAAABAAAAAQCAYAAAAf8/9hAAAABGdBTUEAALGPC/xhBQAAACBjSFJN
AAB6JgAAgIQAAPoAAACA6AAAdTAAAOpgAAA6mAAAF3CculE8AAAACXBIWXMAAAsTAAALEwEAmpwY
AAABbWlUWHRYTUw6Y29tLmFkb2JlLnhtcAAAAAAAPHg6eG1wbWV0YSB4bWxuczp4PSJhZG9iZTpu
YW1lOnNwYWNlLyIgeDp4bXB0az0iQWRvYmUgWF1QIEZsZXggU0DKIDQuNi4wLjIzMTg5IiI+IDxy
ZGY6UkRGIHhtbG5zOnJkZj0iaHR0cDovL3d3dy53My5vcmcvMTk5OS8wMi8yMi1yZGYtc3ludGF4
LW5zIyI+IDxyZGY6RGVzY3JpcHRpb24gcmRmOmFib3V0PSIiIHhtbG5zOnhtcD0iaHR0cDovL25z
LmFkb2JlLmNvbS94YXAvMS4wLyI+IDx4bXA6Q3JlYXRvclRvb2w+QWRvYmUgUGhvdG9zaG9wIENT
NS4xIFdpbmRvd3M8L3htcDpDcmVhdG9yVG9vbD4gPC9yZGY6RGVzY3JpcHRpb24+IDwvcmRmOlJE
Rj4A/b88bAAAALxJREFUOMvFkkEKwkAMReeCDvQWehEvIHiHeAtvIuIdvInSg7gRL+ApeglvInOD
0IUIDvInIig9iAt6ClpQUBfSgXQhZpD/kvmQP69MofT9ZzYpCFFbA638g8VvQAe7X8M8+O2B
90uKuWjWn4UAn+489UBe6G5fFv4ZzXf7AbeG/9E68B6rE69C73gVekfeU9mAV6E9VvYFv6+tG3Xg
9bZ1ow687rZu1IHXW1e7GvB6Kz8B7z+e9bQz8E808A68fU9f6v3nS84/Yv8Hl2YhE7R4f98AAAAASUVO
RK5CYII="""


# === 6. 中英文智能分流渲染函数 ===
def to_academic_font(text):
    """自动将文本中的所有连续英文字母、数字和常见符号包裹在 $\mathrm{...}$ 内
    以便在强制调用宋体（SimSun）时，英数部分通过 stix 引擎渲染为 Times New Roman 字形
    """
    if not text:
        return ""
    # 匹配英文字母、数字、小数点、横杠、冒号、斜杠，以及它们之间可能夹带的单空格
    pattern = r'[A-Za-z0-9\.\-\:\/]+(?:\s+[A-Za-z0-9\.\-\:\/]+)*'

    def repl(match):
        s = match.group(0)
        s_escaped = s.replace(" ", r"\ ")  # 在数学公式模式中，空格需要被转义，否则会被忽略
        return f"$\\mathrm{{{s_escaped}}}$"

    return re.sub(pattern, repl, text)


# === 7. 自定义鼠标滚轮支持的滑动容器组件 ===
class ScrollableFrame(ttk.Frame):
    def __init__(self, container, width=340, *args, **kwargs):
        super().__init__(container, *args, **kwargs)

        self.canvas = tk.Canvas(self, borderwidth=0, highlightthickness=0, width=width)
        self.scrollbar = ttk.Scrollbar(self, orient="vertical", command=self.canvas.yview)

        self.scrollable_frame = ttk.Frame(self.canvas, padding=5)

        self.scrollable_frame.bind(
            "<Configure>",
            lambda e: self.canvas.configure(
                scrollregion=self.canvas.bbox("all")
            )
        )

        self.canvas_window = self.canvas.create_window((0, 0), window=self.scrollable_frame, anchor="nw")
        self.canvas.bind('<Configure>', self._on_canvas_configure)
        self.canvas.configure(yscrollcommand=self.scrollbar.set)

        self.canvas.pack(side="left", fill="both", expand=True)
        self.scrollbar.pack(side="right", fill="y")

        self.scrollable_frame.bind("<Enter>", self._bind_wheel)
        self.scrollable_frame.bind("<Leave>", self._unbind_wheel)

    def _on_canvas_configure(self, event):
        self.canvas.itemconfig(self.canvas_window, width=event.width)

    def _bind_wheel(self, event):
        self.canvas.bind_all("<MouseWheel>", self._on_mousewheel)

    def _unbind_wheel(self, event):
        self.canvas.unbind_all("<MouseWheel>")

    def _on_mousewheel(self, event):
        self.canvas.yview_scroll(int(-1 * (event.delta / 120)), "units")


# === 8. 主程序应用类 ===
class GNSSProcessorApp:
    def __init__(self, root):
        self.root = root
        self.root.title("GNSS 数据分析软件（.dat...）")
        self.root.geometry("1300x860")
        self.root.minsize(1024, 768)

        # 存储加载的数据与绘图对象句柄，以便内存管理
        self.single_df = None
        self.single_filepath = ""
        self.last_df_resampled = None
        self.single_fig = None

        self.ref_df = None
        self.ref_filepath = ""
        self.target_files = {}  # filepath: df
        self.last_dfs_dict = None
        self.multi_fig = None

        self.setup_ui()  # 加载顶层界面排版布局
        self.setup_style()  # 初始化风格
        self.set_window_icon()  # 启动时载入专业窗口图标

    def setup_ui(self):
        """初始化顶层标签页"""
        self.tab_control = ttk.Notebook(self.root)
        self.tab_single = ttk.Frame(self.tab_control)
        self.tab_multi = ttk.Frame(self.tab_control)

        self.tab_control.add(self.tab_single, text="  南方.dat单文件数据处理  ")
        self.tab_control.add(self.tab_multi, text="  南方.dat文件对比分析  ")
        self.tab_control.pack(expand=1, fill="both")

        self.build_single_tab()
        self.build_multi_tab()

        # 最底部实时状态栏
        self.status_bar = ttk.Frame(self.root, relief=tk.SUNKEN, padding=(10, 2))
        self.status_bar.pack(side=tk.BOTTOM, fill=tk.X)
        self.lbl_status = ttk.Label(self.status_bar, text="准备就绪", anchor=tk.W, foreground="#4a4a4a")
        self.lbl_status.pack(side=tk.LEFT, fill=tk.X)

    def setup_style(self):
        """专业外观主题样式微调"""
        self.style = ttk.Style()
        self.style.configure("TLabel", font=("SimSun", 9))
        self.style.configure("TButton", font=("SimSun", 9))
        self.style.configure("TLabelframe.Label", font=("SimSun", 9, "bold"), foreground="#1e3d59")

    def set_window_icon(self):
        """设置软件窗口图标（支持内置默认图标与外部 app.ico/app.png 自动覆盖）"""
        icon_candidates = ["app.ico", "logo.ico", "icon.ico", "app.png", "logo.png"]
        for icon_name in icon_candidates:
            if os.path.exists(icon_name):
                try:
                    if icon_name.endswith('.ico'):
                        self.root.iconbitmap(icon_name)
                    else:
                        img = tk.PhotoImage(file=icon_name)
                        self.root.tk.call('wm', 'iconphoto', self.root._w, img)
                    return
                except Exception:
                    pass

        try:
            icon_img = tk.PhotoImage(data=DEFAULT_ICON_BASE64)
            self.root.tk.call('wm', 'iconphoto', self.root._w, icon_img)
        except Exception:
            pass

    def set_status(self, msg):
        """线程安全的实时状态更新机制"""
        self.lbl_status.config(text=msg)
        self.root.update_idletasks()

    def run_async(self, task_func, args=(), callback=None):
        """通用异步线程启动助手，确保大文件运算不阻塞UI操作"""

        def thread_target():
            try:
                result = task_func(*args)
                if callback:
                    self.root.after(0, lambda: callback(result))
            except Exception as e:
                self.root.after(0, lambda: self.handle_thread_error(e))

        threading.Thread(target=thread_target, daemon=True).start()

    def handle_thread_error(self, err):
        """线程捕获报错时的诊断输出"""
        self.set_status("操作发生异常终止")
        messagebox.showerror("运行时错误", f"后台处理任务时发生异常:\n{str(err)}")

    # --- 南方.dat处理界面设计 ---
    def build_single_tab(self):
        main_pane = ttk.PanedWindow(self.tab_single, orient=tk.HORIZONTAL)
        main_pane.pack(fill=tk.BOTH, expand=True)

        # 控制面板重构为带滚动条的 ScrollableFrame
        left_scroll = ScrollableFrame(main_pane, width=340)
        left_frame = left_scroll.scrollable_frame

        right_frame = ttk.Frame(main_pane, padding=10)

        main_pane.add(left_scroll, weight=1)
        main_pane.add(right_frame, weight=3)

        # 1. 数据导入
        file_lf = ttk.LabelFrame(left_frame, text="数据导入", padding=5)
        file_lf.pack(fill=tk.X, pady=4)

        self.btn_load_single = ttk.Button(file_lf, text="选择数据文件", command=self.load_single_file)
        self.btn_load_single.pack(fill=tk.X, pady=2)

        self.lbl_single_path = ttk.Label(file_lf, text="未加载文件", wraplength=300, foreground="gray")
        self.lbl_single_path.pack(fill=tk.X, pady=2)

        # 新增选项：移动点文件/固定点文件
        ttk.Label(file_lf, text="文件模式 (移动点/固定点):").pack(anchor=tk.W, pady=(4, 0))
        self.cmb_file_mode = ttk.Combobox(file_lf, values=["移动点文件", "固定点文件"], state="readonly")
        self.cmb_file_mode.set("移动点文件")
        self.cmb_file_mode.pack(fill=tk.X, pady=2)

        # 2. 配置参数
        config_lf = ttk.LabelFrame(left_frame, text="分析配置", padding=5)
        config_lf.pack(fill=tk.X, pady=4)

        ttk.Label(config_lf, text="文件起止时间:").pack(anchor=tk.W)
        self.lbl_single_range = ttk.Label(config_lf, text="-", foreground="blue")
        self.lbl_single_range.pack(anchor=tk.W, pady=2)

        ttk.Label(config_lf, text="开始时间 (YYYY-MM-DD HH:MM:SS):").pack(anchor=tk.W, pady=(4, 0))
        self.ent_single_start = ttk.Entry(config_lf)
        self.ent_single_start.pack(fill=tk.X, pady=2)

        ttk.Label(config_lf, text="结束时间 (YYYY-MM-DD HH:MM:SS):").pack(anchor=tk.W, pady=(4, 0))
        self.ent_single_end = ttk.Entry(config_lf)
        self.ent_single_end.pack(fill=tk.X, pady=2)

        ttk.Label(config_lf, text="时间分辨率 (秒, 默认1):").pack(anchor=tk.W, pady=(4, 0))
        self.ent_single_res = ttk.Entry(config_lf)
        self.ent_single_res.insert(0, "1")
        self.ent_single_res.pack(fill=tk.X, pady=2)

        # 3. 绘图自定义配置
        plot_lf = ttk.LabelFrame(left_frame, text="图表自定义配置", padding=5)
        plot_lf.pack(fill=tk.X, pady=4)

        ttk.Label(plot_lf, text="总标题:").grid(row=0, column=0, sticky='w', pady=2)
        self.ent_single_title = ttk.Entry(plot_lf)
        self.ent_single_title.insert(0, "GNSS 定位质量指标随时间变化图")
        self.ent_single_title.grid(row=0, column=1, columnspan=3, sticky='ew', pady=2)

        ttk.Label(plot_lf, text="X轴标签:").grid(row=1, column=0, sticky='w', pady=2)
        self.ent_single_xlabel = ttk.Entry(plot_lf)
        self.ent_single_xlabel.insert(0, "Local Time")
        self.ent_single_xlabel.grid(row=1, column=1, columnspan=3, sticky='ew', pady=2)

        # 行 2：Y1 (RMSH) 与 Y2 (RMSV)
        ttk.Label(plot_lf, text="Y1(RMSH):").grid(row=2, column=0, sticky='w', pady=2)
        self.ent_single_y1 = ttk.Entry(plot_lf, width=10)
        self.ent_single_y1.insert(0, "RMSH/m")
        self.ent_single_y1.grid(row=2, column=1, sticky='ew', pady=2)

        ttk.Label(plot_lf, text="Y2(RMSV):").grid(row=2, column=2, sticky='w', pady=2, padx=(5, 0))
        self.ent_single_y2 = ttk.Entry(plot_lf, width=10)
        self.ent_single_y2.insert(0, "RMSV/m")
        self.ent_single_y2.grid(row=2, column=3, sticky='ew', pady=2)

        # 行 3：Y3 (PDOP) 与 Y4 (卫星)
        ttk.Label(plot_lf, text="Y3(PDOP):").grid(row=3, column=0, sticky='w', pady=2)
        self.ent_single_y3 = ttk.Entry(plot_lf, width=10)
        self.ent_single_y3.insert(0, "PDOP")
        self.ent_single_y3.grid(row=3, column=1, sticky='ew', pady=2)

        ttk.Label(plot_lf, text="Y4(卫星):").grid(row=3, column=2, sticky='w', pady=2, padx=(5, 0))
        self.ent_single_y4 = ttk.Entry(plot_lf, width=10)
        self.ent_single_y4.insert(0, "Sat Num")
        self.ent_single_y4.grid(row=3, column=3, sticky='ew', pady=2)

        # 行 4：Y5 (Age) 与线型
        ttk.Label(plot_lf, text="Y5(Age):").grid(row=4, column=0, sticky='w', pady=2)
        self.ent_single_y5 = ttk.Entry(plot_lf, width=10)
        self.ent_single_y5.insert(0, "Diff Age/s")
        self.ent_single_y5.grid(row=4, column=1, sticky='ew', pady=2)

        ttk.Label(plot_lf, text="线型:").grid(row=4, column=2, sticky='w', pady=2, padx=(5, 0))
        self.cmb_single_ls = ttk.Combobox(plot_lf, values=['-', '--', ':', '-.'], width=8, state='readonly')
        self.cmb_single_ls.set('-')
        self.cmb_single_ls.grid(row=4, column=3, sticky='ew', pady=2)

        # 行 5：线宽 与 X刻度字号
        ttk.Label(plot_lf, text="线宽:").grid(row=5, column=0, sticky='w', pady=2)
        self.ent_single_lw = ttk.Entry(plot_lf, width=8)
        self.ent_single_lw.insert(0, "1.2")
        self.ent_single_lw.grid(row=5, column=1, sticky='ew', pady=2)

        ttk.Label(plot_lf, text="X刻度字号:").grid(row=5, column=2, sticky='w', pady=2, padx=(5, 0))
        self.ent_single_xtick = ttk.Entry(plot_lf, width=8)
        self.ent_single_xtick.insert(0, "9")
        self.ent_single_xtick.grid(row=5, column=3, sticky='ew', pady=2)

        # 行 6：Y刻度字号 与 X轴题字号
        ttk.Label(plot_lf, text="Y刻度字号:").grid(row=6, column=0, sticky='w', pady=2)
        self.ent_single_ytick = ttk.Entry(plot_lf, width=8)
        self.ent_single_ytick.insert(0, "9")
        self.ent_single_ytick.grid(row=6, column=1, sticky='ew', pady=2)

        ttk.Label(plot_lf, text="X轴题字号:").grid(row=6, column=2, sticky='w', pady=2, padx=(5, 0))
        self.ent_single_xtitle_sz = ttk.Entry(plot_lf, width=8)
        self.ent_single_xtitle_sz.insert(0, "10")
        self.ent_single_xtitle_sz.grid(row=6, column=3, sticky='ew', pady=2)

        # 行 7：Y轴题字号 与 图例位置
        ttk.Label(plot_lf, text="Y轴题字号:").grid(row=7, column=0, sticky='w', pady=2)
        self.ent_single_ytitle_sz = ttk.Entry(plot_lf, width=8)
        self.ent_single_ytitle_sz.insert(0, "10")
        self.ent_single_ytitle_sz.grid(row=7, column=1, sticky='ew', pady=2)

        ttk.Label(plot_lf, text="图例位置:").grid(row=7, column=2, sticky='w', pady=2, padx=(5, 0))
        self.cmb_single_leg = ttk.Combobox(plot_lf,
                                           values=['best', 'upper right', 'upper left', 'lower right', 'lower left',
                                                   'center'], width=8, state='readonly')
        self.cmb_single_leg.set('best')
        self.cmb_single_leg.grid(row=7, column=3, sticky='ew', pady=2)

        # 行 8：输出DPI 与 图例字号
        ttk.Label(plot_lf, text="输出DPI:").grid(row=8, column=0, sticky='w', pady=2)
        self.ent_single_dpi = ttk.Entry(plot_lf, width=8)
        self.ent_single_dpi.insert(0, "300")
        self.ent_single_dpi.grid(row=8, column=1, sticky='ew', pady=2)

        ttk.Label(plot_lf, text="图例字号:").grid(row=8, column=2, sticky='w', pady=2, padx=(5, 0))
        self.ent_single_leg_sz = ttk.Entry(plot_lf, width=8)
        self.ent_single_leg_sz.insert(0, "8")
        self.ent_single_leg_sz.grid(row=8, column=3, sticky='ew', pady=2)

        # 行 9：显示格网
        self.var_single_grid = tk.BooleanVar(value=True)
        self.chk_single_grid = ttk.Checkbutton(plot_lf, text="显示格网", variable=self.var_single_grid)
        self.chk_single_grid.grid(row=9, column=0, columnspan=2, sticky='w', pady=2)

        # 行 10：新增子图宽度与高度设置（可自定义导出子图的纵横比尺寸）
        ttk.Label(plot_lf, text="子图宽度:").grid(row=10, column=0, sticky='w', pady=2)
        self.ent_single_sub_w = ttk.Entry(plot_lf, width=8)
        self.ent_single_sub_w.insert(0, "16")
        self.ent_single_sub_w.grid(row=10, column=1, sticky='ew', pady=2)

        ttk.Label(plot_lf, text="子图高度:").grid(row=10, column=2, sticky='w', pady=2, padx=(5, 0))
        self.ent_single_sub_h = ttk.Entry(plot_lf, width=8)
        self.ent_single_sub_h.insert(0, "4")
        self.ent_single_sub_h.grid(row=10, column=3, sticky='ew', pady=2)

        plot_lf.columnconfigure(1, weight=1)
        plot_lf.columnconfigure(3, weight=1)

        # 4. 操作按钮
        btn_lf = ttk.Frame(left_frame, padding=2)
        btn_lf.pack(fill=tk.X, pady=6)

        self.btn_single_run = ttk.Button(btn_lf, text="开始分析并绘图", command=self.process_single)
        self.btn_single_run.pack(fill=tk.X, pady=2)

        self.btn_single_export_report = ttk.Button(btn_lf, text="导出指标报告 (TXT)", command=self.export_single_report,
                                                   state=tk.DISABLED)
        self.btn_single_export_report.pack(fill=tk.X, pady=2)

        self.btn_single_export_data = ttk.Button(btn_lf, text="导出时段数据 (CSV)", command=self.export_single_data,
                                                 state=tk.DISABLED)
        self.btn_single_export_data.pack(fill=tk.X, pady=2)

        self.btn_single_save_plot = ttk.Button(btn_lf, text="保存完整合成图表", command=self.save_single_plot,
                                               state=tk.DISABLED)
        self.btn_single_save_plot.pack(fill=tk.X, pady=2)

        self.btn_single_save_sep = ttk.Button(btn_lf, text="分别保存5个子图", command=self.save_single_subplots_separately,
                                              state=tk.DISABLED)
        self.btn_single_save_sep.pack(fill=tk.X, pady=2)

        self.btn_single_reset_plot = ttk.Button(btn_lf, text="重置绘图区", command=self.reset_single_plot)
        self.btn_single_reset_plot.pack(fill=tk.X, pady=2)

        self.btn_single_reset_all = ttk.Button(btn_lf, text="重置整个文件 (结束处理)", command=self.reset_single_all)
        self.btn_single_reset_all.pack(fill=tk.X, pady=2)

        # 右侧图表及文本
        right_pane = ttk.PanedWindow(right_frame, orient=tk.VERTICAL)
        right_pane.pack(fill=tk.BOTH, expand=True)

        self.plot_container_single = ttk.Frame(right_pane)
        right_pane.add(self.plot_container_single, weight=3)

        text_frame = ttk.LabelFrame(right_pane, text="指标统计输出")
        right_pane.add(text_frame, weight=1)

        self.txt_single_output = tk.Text(text_frame, height=8, wrap=tk.WORD)
        self.txt_single_output.pack(fill=tk.BOTH, expand=True, padx=5, pady=5)

    # --- 多文件对比界面设计 ---
    def build_multi_tab(self):
        main_pane = ttk.PanedWindow(self.tab_multi, orient=tk.HORIZONTAL)
        main_pane.pack(fill=tk.BOTH, expand=True)

        left_scroll = ScrollableFrame(main_pane, width=340)
        left_frame = left_scroll.scrollable_frame

        right_frame = ttk.Frame(main_pane, padding=10)

        main_pane.add(left_scroll, weight=1)
        main_pane.add(right_frame, weight=3)

        # 1. 基准参考数据导入
        ref_lf = ttk.LabelFrame(left_frame, text="基准/参考文件导入", padding=5)
        ref_lf.pack(fill=tk.X, pady=4)

        self.btn_load_ref = ttk.Button(ref_lf, text="选择参考文件", command=self.load_ref_file)
        self.btn_load_ref.pack(fill=tk.X, pady=2)

        self.lbl_ref_path = ttk.Label(ref_lf, text="未导入参考文件", wraplength=300, foreground="gray")
        self.lbl_ref_path.pack(fill=tk.X, pady=2)

        # 2. 待处理多数据导入
        targets_lf = ttk.LabelFrame(left_frame, text="待处理文件导入", padding=5)
        targets_lf.pack(fill=tk.X, pady=4)

        self.btn_load_targets = ttk.Button(targets_lf, text="添加待处理文件", command=self.load_target_files)
        self.btn_load_targets.pack(fill=tk.X, pady=2)

        self.lst_targets = tk.Listbox(targets_lf, height=3)
        self.lst_targets.pack(fill=tk.X, pady=2)

        self.btn_clear_targets = ttk.Button(targets_lf, text="清空待处理文件", command=self.clear_target_files)
        self.btn_clear_targets.pack(fill=tk.X, pady=2)

        # 3. 统一分析配置
        config_lf = ttk.LabelFrame(left_frame, text="统一时间分析配置", padding=5)
        config_lf.pack(fill=tk.X, pady=4)

        # 多文件新增选择“移动点/固定点”模式选项
        ttk.Label(config_lf, text="文件模式 (移动点/固定点):").pack(anchor=tk.W, pady=(4, 0))
        self.cmb_multi_file_mode = ttk.Combobox(config_lf, values=["移动点文件", "固定点文件"], state="readonly")
        self.cmb_multi_file_mode.set("移动点文件")
        self.cmb_multi_file_mode.pack(fill=tk.X, pady=2)

        ttk.Label(config_lf, text="多文件重叠时间范围:").pack(anchor=tk.W, pady=(4, 0))
        self.lbl_multi_range = ttk.Label(config_lf, text="-", foreground="blue", wraplength=300)
        self.lbl_multi_range.pack(anchor=tk.W, pady=2)

        ttk.Label(config_lf, text="开始时间 (YYYY-MM-DD HH:MM:SS):").pack(anchor=tk.W, pady=(4, 0))
        self.ent_multi_start = ttk.Entry(config_lf)
        self.ent_multi_start.pack(fill=tk.X, pady=2)

        ttk.Label(config_lf, text="结束时间 (YYYY-MM-DD HH:MM:SS):").pack(anchor=tk.W, pady=(4, 0))
        self.ent_multi_end = ttk.Entry(config_lf)
        self.ent_multi_end.pack(fill=tk.X, pady=2)

        ttk.Label(config_lf, text="时间分辨率 (秒, 默认1):").pack(anchor=tk.W, pady=(4, 0))
        self.ent_multi_res = ttk.Entry(config_lf)
        self.ent_multi_res.insert(0, "1")
        self.ent_multi_res.pack(fill=tk.X, pady=2)

        # 4. 多文件自定义配置
        plot_lf = ttk.LabelFrame(left_frame, text="图表自定义配置", padding=5)
        plot_lf.pack(fill=tk.X, pady=4)

        ttk.Label(plot_lf, text="总标题:").grid(row=0, column=0, sticky='w', pady=2)
        self.ent_multi_title = ttk.Entry(plot_lf)
        self.ent_multi_title.insert(0, "多终端定位质量指标对比图")
        self.ent_multi_title.grid(row=0, column=1, columnspan=3, sticky='ew', pady=2)

        ttk.Label(plot_lf, text="X轴标签:").grid(row=1, column=0, sticky='w', pady=2)
        self.ent_multi_xlabel = ttk.Entry(plot_lf)
        self.ent_multi_xlabel.insert(0, "Local Time")
        self.ent_multi_xlabel.grid(row=1, column=1, columnspan=3, sticky='ew', pady=2)

        # 行 2：Y1 (RMSH) 与 Y2 (RMSV)
        ttk.Label(plot_lf, text="Y1(RMSH):").grid(row=2, column=0, sticky='w', pady=2)
        self.ent_multi_y1 = ttk.Entry(plot_lf, width=10)
        self.ent_multi_y1.insert(0, "RMSH/m")
        self.ent_multi_y1.grid(row=2, column=1, sticky='ew', pady=2)

        ttk.Label(plot_lf, text="Y2(RMSV):").grid(row=2, column=2, sticky='w', pady=2, padx=(5, 0))
        self.ent_multi_y2 = ttk.Entry(plot_lf, width=10)
        self.ent_multi_y2.insert(0, "RMSV/m")
        self.ent_multi_y2.grid(row=2, column=3, sticky='ew', pady=2)

        # 行 3：Y3 (PDOP) 与 Y4 (卫星)
        ttk.Label(plot_lf, text="Y3(PDOP):").grid(row=3, column=0, sticky='w', pady=2)
        self.ent_multi_y3 = ttk.Entry(plot_lf, width=10)
        self.ent_multi_y3.insert(0, "PDOP")
        self.ent_multi_y3.grid(row=3, column=1, sticky='ew', pady=2)

        ttk.Label(plot_lf, text="Y4(卫星):").grid(row=3, column=2, sticky='w', pady=2, padx=(5, 0))
        self.ent_multi_y4 = ttk.Entry(plot_lf, width=10)
        self.ent_multi_y4.insert(0, "Sat Num")
        self.ent_multi_y4.grid(row=3, column=3, sticky='ew', pady=2)

        # 行 4：Y5 (Age) 与线型
        ttk.Label(plot_lf, text="Y5(Age):").grid(row=4, column=0, sticky='w', pady=2)
        self.ent_multi_y5 = ttk.Entry(plot_lf, width=10)
        self.ent_multi_y5.insert(0, "Diff Age/s")
        self.ent_multi_y5.grid(row=4, column=1, sticky='ew', pady=2)

        ttk.Label(plot_lf, text="线型:").grid(row=4, column=2, sticky='w', pady=2, padx=(5, 0))
        self.cmb_multi_ls = ttk.Combobox(plot_lf, values=['-', '--', ':', '-.'], width=8, state='readonly')
        self.cmb_multi_ls.set('-')
        self.cmb_multi_ls.grid(row=4, column=3, sticky='ew', pady=2)

        # 行 5：线宽 与 X刻度字号
        ttk.Label(plot_lf, text="线宽:").grid(row=5, column=0, sticky='w', pady=2)
        self.ent_multi_lw = ttk.Entry(plot_lf, width=8)
        self.ent_multi_lw.insert(0, "1.2")
        self.ent_multi_lw.grid(row=5, column=1, sticky='ew', pady=2)

        ttk.Label(plot_lf, text="X刻度字号:").grid(row=5, column=2, sticky='w', pady=2, padx=(5, 0))
        self.ent_multi_xtick = ttk.Entry(plot_lf, width=8)
        self.ent_multi_xtick.insert(0, "9")
        self.ent_multi_xtick.grid(row=5, column=3, sticky='ew', pady=2)

        # 行 6：Y刻度字号 与 X轴题字号
        ttk.Label(plot_lf, text="Y刻度字号:").grid(row=6, column=0, sticky='w', pady=2)
        self.ent_multi_ytick = ttk.Entry(plot_lf, width=8)
        self.ent_multi_ytick.insert(0, "9")
        self.ent_multi_ytick.grid(row=6, column=1, sticky='ew', pady=2)

        ttk.Label(plot_lf, text="X轴题字号:").grid(row=6, column=2, sticky='w', pady=2, padx=(5, 0))
        self.ent_multi_xtitle_sz = ttk.Entry(plot_lf, width=8)
        self.ent_multi_xtitle_sz.insert(0, "10")
        self.ent_multi_xtitle_sz.grid(row=6, column=3, sticky='ew', pady=2)

        # 行 7：Y轴题字号 与 图例位置
        ttk.Label(plot_lf, text="Y轴题字号:").grid(row=7, column=0, sticky='w', pady=2)
        self.ent_multi_ytitle_sz = ttk.Entry(plot_lf, width=8)
        self.ent_multi_ytitle_sz.insert(0, "10")
        self.ent_multi_ytitle_sz.grid(row=7, column=1, sticky='ew', pady=2)

        ttk.Label(plot_lf, text="图例位置:").grid(row=7, column=2, sticky='w', pady=2, padx=(5, 0))
        self.cmb_multi_leg = ttk.Combobox(plot_lf,
                                          values=['best', 'upper right', 'upper left', 'lower right', 'lower left',
                                                  'center'], width=8, state='readonly')
        self.cmb_multi_leg.set('best')
        self.cmb_multi_leg.grid(row=7, column=3, sticky='ew', pady=2)

        # 行 8：输出DPI 与 图例字号
        ttk.Label(plot_lf, text="输出DPI:").grid(row=8, column=0, sticky='w', pady=2)
        self.ent_multi_dpi = ttk.Entry(plot_lf, width=8)
        self.ent_multi_dpi.insert(0, "300")
        self.ent_multi_dpi.grid(row=8, column=1, sticky='ew', pady=2)

        ttk.Label(plot_lf, text="图例字号:").grid(row=8, column=2, sticky='w', pady=2, padx=(5, 0))
        self.ent_multi_leg_sz = ttk.Entry(plot_lf, width=8)
        self.ent_multi_leg_sz.insert(0, "7")
        self.ent_multi_leg_sz.grid(row=8, column=3, sticky='ew', pady=2)

        # 行 9：显示格网
        self.var_multi_grid = tk.BooleanVar(value=True)
        self.chk_multi_grid = ttk.Checkbutton(plot_lf, text="显示格网", variable=self.var_multi_grid)
        self.chk_multi_grid.grid(row=9, column=0, columnspan=2, sticky='w', pady=2)

        # 行 10：新增多图对比下的子图宽度与高度设置（可自定义导出子图的纵横比尺寸）
        ttk.Label(plot_lf, text="子图宽度:").grid(row=10, column=0, sticky='w', pady=2)
        self.ent_multi_sub_w = ttk.Entry(plot_lf, width=8)
        self.ent_multi_sub_w.insert(0, "16")
        self.ent_multi_sub_w.grid(row=10, column=1, sticky='ew', pady=2)

        ttk.Label(plot_lf, text="子图高度:").grid(row=10, column=2, sticky='w', pady=2, padx=(5, 0))
        self.ent_multi_sub_h = ttk.Entry(plot_lf, width=8)
        self.ent_multi_sub_h.insert(0, "4")
        self.ent_multi_sub_h.grid(row=10, column=3, sticky='ew', pady=2)

        # 5. 多文件控制按钮
        btn_lf = ttk.Frame(left_frame, padding=2)
        btn_lf.pack(fill=tk.X, pady=6)

        self.btn_multi_run = ttk.Button(btn_lf, text="进行对比分析与绘图", command=self.process_multi)
        self.btn_multi_run.pack(fill=tk.X, pady=2)

        self.btn_multi_export_report = ttk.Button(btn_lf, text="导出多文件对比报告", command=self.export_multi_report,
                                                  state=tk.DISABLED)
        self.btn_multi_export_report.pack(fill=tk.X, pady=2)

        self.btn_multi_export_data = ttk.Button(btn_lf, text="导出合并时段数据 (CSV)", command=self.export_multi_data,
                                                state=tk.DISABLED)
        self.btn_multi_export_data.pack(fill=tk.X, pady=2)

        self.btn_multi_save_plot = ttk.Button(btn_lf, text="保存统一对比大图", command=self.save_multi_plot, state=tk.DISABLED)
        self.btn_multi_save_plot.pack(fill=tk.X, pady=2)

        self.btn_multi_save_sep = ttk.Button(btn_lf, text="分别保存5个对比子图", command=self.save_multi_subplots_separately,
                                             state=tk.DISABLED)
        self.btn_multi_save_sep.pack(fill=tk.X, pady=2)

        self.btn_multi_reset_plot = ttk.Button(btn_lf, text="重置绘图区", command=self.reset_multi_plot)
        self.btn_multi_reset_plot.pack(fill=tk.X, pady=2)

        self.btn_multi_reset_all = ttk.Button(btn_lf, text="重置所有文件", command=self.reset_multi_all)
        self.btn_multi_reset_all.pack(fill=tk.X, pady=2)

        # 右侧图表及文本
        right_pane = ttk.PanedWindow(right_frame, orient=tk.VERTICAL)
        right_pane.pack(fill=tk.BOTH, expand=True)

        self.plot_container_multi = ttk.Frame(right_pane)
        right_pane.add(self.plot_container_multi, weight=3)

        text_frame = ttk.LabelFrame(right_pane, text="对比指标与坐标精度输出")
        right_pane.add(text_frame, weight=1)

        self.txt_multi_output = tk.Text(text_frame, height=8, wrap=tk.WORD)
        self.txt_multi_output.pack(fill=tk.BOTH, expand=True, padx=5, pady=5)

    # --- 数据解析核心逻辑（丢弃指定列数据，智能表头/BOM处理） ---
    def parse_gnss_file(self, filepath):
        try:
            # 智能嗅探文件分隔符，确保打开各种 comma/tab/space 分隔格式
            with open(filepath, 'r', encoding='utf-8', errors='ignore') as f:
                first_line = f.readline()
            if ',' in first_line:
                sep_detected = ','
            elif '\t' in first_line:
                sep_detected = '\t'
            elif ';' in first_line:
                sep_detected = ';'
            else:
                sep_detected = r'\s+'  # 空格自适应

            # 智能嗅探首行是否包含表头关键词，以兼容普通带有表头的 CSV 格式
            has_header = False
            header_keywords = ["北坐标", "Datetime", "点名", "日期", "时间", "RMSH"]
            if any(kw in first_line for kw in header_keywords):
                has_header = True

            if has_header:
                # 含有表头，按照表头名字读取并自动清理可能存在的 Windows UTF-8 BOM 字符
                df = pd.read_csv(filepath, sep=sep_detected, engine='python', on_bad_lines='skip')
                df.columns = [str(c).strip().lstrip('\ufeff') for c in df.columns]

                # 如果包含 Datetime 复合时间列，则直接解析它，若没有"日期"和"时间"则从中还原
                if 'Datetime' in df.columns:
                    df['Datetime'] = pd.to_datetime(df['Datetime'], errors='coerce')
                    if '日期' not in df.columns:
                        df['日期'] = df['Datetime'].dt.strftime('%Y/%m/%d')
                    if '时间' not in df.columns:
                        df['时间'] = df['Datetime'].dt.strftime('%H:%M:%S')
            else:
                # 无表头的原生 dat/txt 文件，按照物理列位置映射
                df = pd.read_csv(filepath, header=None, sep=sep_detected, engine='python', on_bad_lines='skip')
                num_cols = min(df.shape[1], len(COLUMNS))
                df = df.iloc[:, :num_cols]
                df.columns = COLUMNS[:num_cols]

            # 点名只保留第一列，将备份点名列及其他无用列丢弃
            if "点名_备份" in df.columns:
                df = df.drop(columns=["点名_备份"], errors='ignore')

            # 抛弃编码、里程、偏距、中桩里程、中桩高程、存储位置、存储类型列的数据
            drop_cols = ["编码", "里程", "偏距", "中桩里程", "中桩高程", "存储位置", "存储类型"]
            df = df.drop(columns=[col for col in drop_cols if col in df.columns], errors='ignore')

            # 解析日期与时间，生成 Datetime 列
            if 'Datetime' not in df.columns or df['Datetime'].isnull().all():
                if "日期" in df.columns and "时间" in df.columns:
                    df = df.dropna(subset=["日期", "时间"])
                    df['Datetime'] = pd.to_datetime(
                        df['日期'].astype(str).str.strip() + ' ' + df['时间'].astype(str).str.strip(),
                        errors='coerce')
                else:
                    raise ValueError("文件中缺失关键的日期或时间列，无法对齐时间轴。")

            df = df.dropna(subset=['Datetime'])

            # 统一转为数值类型
            numeric_cols = ["北坐标", "东坐标", "高程", "RMSH", "RMSV", "卫星数", "PDOP", "差分Age"]
            for col in numeric_cols:
                if col in df.columns:
                    df[col] = pd.to_numeric(df[col], errors='coerce')

            df = df.sort_values(by='Datetime')
            return df
        except Exception as e:
            raise ValueError(f"解析文件出错: {str(e)}")

    # --- 内存管理与双重重置辅助函数 ---
    def reset_single_plot(self):
        """仅清空南方.dat文件绘图区，关闭当前图表以释放缓存"""
        if self.single_fig is not None:
            plt.close(self.single_fig)
            self.single_fig = None

        for widget in self.plot_container_single.winfo_children():
            widget.destroy()

        self.btn_single_save_plot.config(state=tk.DISABLED)
        self.btn_single_save_sep.config(state=tk.DISABLED)
        gc.collect()

    def reset_single_all(self, show_msg=True):
        """清空数据并还原该页面状态（支持静默重置）"""
        self.single_df = None
        self.single_filepath = ""
        self.last_df_resampled = None

        self.lbl_single_path.config(text="未加载文件", foreground="gray")
        self.lbl_single_range.config(text="-")
        self.cmb_file_mode.set("移动点文件")  # 重置选项
        self.ent_single_start.delete(0, tk.END)
        self.ent_single_end.delete(0, tk.END)
        self.txt_single_output.delete("1.0", tk.END)
        self.ent_single_sub_w.delete(0, tk.END)
        self.ent_single_sub_w.insert(0, "16")
        self.ent_single_sub_h.delete(0, tk.END)
        self.ent_single_sub_h.insert(0, "4")

        self.btn_single_export_report.config(state=tk.DISABLED)
        self.btn_single_export_data.config(state=tk.DISABLED)
        self.reset_single_plot()
        if show_msg:
            messagebox.showinfo("重置成功", "南方.dat文件数据已被彻底清空，您可以加载新文件。")

    def reset_multi_plot(self):
        """仅清空多文件绘图区并释放内存"""
        if self.multi_fig is not None:
            plt.close(self.multi_fig)
            self.multi_fig = None

        for widget in self.plot_container_multi.winfo_children():
            widget.destroy()

        self.btn_multi_save_plot.config(state=tk.DISABLED)
        self.btn_multi_save_sep.config(state=tk.DISABLED)
        gc.collect()

    def reset_multi_all(self, show_msg=True):
        """完全清空对比页面的所有数据并还原状态（支持静默重置）"""
        self.ref_df = None
        self.ref_filepath = ""
        self.target_files.clear()
        self.last_dfs_dict = None

        self.lbl_ref_path.config(text="未导入参考文件", foreground="gray")
        self.lst_targets.delete(0, tk.END)
        self.lbl_multi_range.config(text="-")
        self.cmb_multi_file_mode.set("移动点文件")  # 重置多文件选项
        self.ent_multi_start.delete(0, tk.END)
        self.ent_multi_end.delete(0, tk.END)
        self.txt_multi_output.delete("1.0", tk.END)
        self.ent_multi_sub_w.delete(0, tk.END)
        self.ent_multi_sub_w.insert(0, "16")
        self.ent_multi_sub_h.delete(0, tk.END)
        self.ent_multi_sub_h.insert(0, "4")

        self.btn_multi_export_report.config(state=tk.DISABLED)
        self.btn_multi_export_data.config(state=tk.DISABLED)
        self.reset_multi_plot()
        if show_msg:
            messagebox.showinfo("重置成功", "多文件对比数据已彻底释放，可导入新任务。")

    # --- 南方.dat文件处理逻辑 ---
    def load_single_file(self):
        filepath = filedialog.askopenfilename(title="选择定位终端轨迹数据文件", filetypes=COMMON_FILETYPES)
        if filepath:
            try:
                self.reset_single_all(show_msg=False)
                self.lbl_single_path.config(text="正在导入中，请稍候...", foreground="#007acc")
                self.set_status(f"正在导入单数据文件: {os.path.basename(filepath)}")

                def load_task():
                    return self.parse_gnss_file(filepath)

                def on_loaded(df):
                    self.single_filepath = filepath
                    self.lbl_single_path.config(text=os.path.basename(filepath), foreground="black")
                    self.single_df = df
                    t_min = df['Datetime'].min()
                    t_max = df['Datetime'].max()

                    self.lbl_single_range.config(text=f"{t_min} 至 {t_max}")
                    self.ent_single_start.insert(0, t_min.strftime('%Y-%m-%d %H:%M:%S'))
                    self.ent_single_end.insert(0, t_max.strftime('%Y-%m-%d %H:%M:%S'))
                    self.set_status("单数据文件加载完成")

                self.run_async(load_task, callback=on_loaded)
            except Exception as e:
                messagebox.showerror("读取错误", f"无法正确解析该文件: {str(e)}")

    def process_single(self):
        if self.single_df is None:
            messagebox.showwarning("提示", "请先加载数据文件。")
            return

        try:
            start_str = self.ent_single_start.get().strip()
            end_str = self.ent_single_end.get().strip()
            res_val = int(self.ent_single_res.get().strip())
            file_mode = self.cmb_file_mode.get()  # 获取用户选择的模式

            start_dt = pd.to_datetime(start_str)
            end_dt = pd.to_datetime(end_str)
        except Exception:
            messagebox.showerror("格式错误", "时间格式不正确或分辨率不是有效的整数秒。")
            return

        self.set_status("正在执行南方.dat文件时段数据重采样及指标统计...")

        def process_task():
            df_filtered = self.single_df[
                (self.single_df['Datetime'] >= start_dt) & (self.single_df['Datetime'] <= end_dt)].copy()
            if df_filtered.empty:
                return None, None

            df_filtered.set_index('Datetime', inplace=True)
            resample_rule = f"{res_val}s"

            # 规避高版本 Pandas 文本列求平均崩溃报错
            df_resampled = df_filtered.resample(resample_rule).mean(numeric_only=True)

            # 修复：还原在 resample 中因为非数值而被过滤掉的“点名”与“解状态”
            if '点名' in df_filtered.columns and '点名' not in df_resampled.columns:
                df_resampled.insert(0, '点名', df_filtered['点名'].resample(resample_rule).first())
            if '解状态' in df_filtered.columns and '解状态' not in df_resampled.columns:
                df_resampled['解状态'] = df_filtered['解状态'].resample(resample_rule).first()

            full_idx = pd.date_range(start=start_dt, end=end_dt, freq=resample_rule)
            df_resampled = df_resampled.reindex(full_idx)

            self.last_df_resampled = df_resampled

            # 指标计算
            valid_epochs = df_resampled['北坐标'].notna().sum()
            total_epochs = len(df_resampled)
            fixed_rate = (valid_epochs / total_epochs) * 100 if total_epochs > 0 else 0.0

            mean_rmsh = df_filtered['RMSH'].mean() if 'RMSH' in df_filtered else np.nan
            mean_rmsv = df_filtered['RMSV'].mean() if 'RMSV' in df_filtered else np.nan
            mean_pdop = df_filtered['PDOP'].mean() if 'PDOP' in df_filtered else np.nan
            mean_sat = df_filtered['卫星数'].mean() if '卫星数' in df_filtered else np.nan
            mean_age = df_filtered['差分Age'].mean() if '差分Age' in df_filtered else np.nan

            report = f"================ 南方.dat单文件分析指标报告 ================\n"
            report += f"分析文件: {os.path.basename(self.single_filepath)}\n"
            report += f"文件类型: {file_mode}\n"
            report += f"所选时间窗口: {start_str} 至 {end_str}\n"
            report += f"重采样时间分辨率: {res_val} 秒\n"
            report += f"----------------------------------------------------\n"
            report += f"★ 固定率: {fixed_rate:.2f} % (有效格网点数: {valid_epochs} / 总区间点数: {total_epochs})\n"
            report += f"平均 RMSH: {mean_rmsh:.4f} m\n"
            report += f"平均 RMSV: {mean_rmsv:.4f} m\n"
            report += f"平均 PDOP: {mean_pdop:.2f}\n"
            report += f"平均卫星数: {mean_sat:.1f}\n"
            report += f"平均差分Age: {mean_age:.2f} s\n"

            # 如果选择固定点文件，则在指标统计中增加坐标平均值与标准差
            if file_mode == "固定点文件":
                mean_N = df_filtered['北坐标'].mean() if '北坐标' in df_filtered else np.nan
                mean_E = df_filtered['东坐标'].mean() if '东坐标' in df_filtered else np.nan
                mean_H = df_filtered['高程'].mean() if '高程' in df_filtered else np.nan
                std_N = df_filtered['北坐标'].std() if '北坐标' in df_filtered else np.nan
                std_E = df_filtered['东坐标'].std() if '东坐标' in df_filtered else np.nan
                std_H = df_filtered['高程'].std() if '高程' in df_filtered else np.nan

                report += f"------------------ 固定点观测精度指标 ------------------\n"
                report += f"平均北坐标: {mean_N:.4f} m\n"
                report += f"平均东坐标: {mean_E:.4f} m\n"
                report += f"平均高程: {mean_H:.4f} m\n"
                report += f"北坐标的标准差: {std_N:.4f} m\n"
                report += f"东坐标的标准差: {std_E:.4f} m\n"
                report += f"高程的标准差: {std_H:.4f} m\n"

            report += f"====================================================\n"

            return df_resampled, report

        def on_processed(result):
            df_resampled, report = result
            if df_resampled is None:
                messagebox.showwarning("无数据", "所选时间段内没有有效的定位记录。")
                self.set_status("南方.dat单文件处理失败：选定时段无数据")
                return

            self.last_df_resampled = df_resampled
            self.txt_single_output.delete("1.0", tk.END)
            self.txt_single_output.insert(tk.END, report)
            self.single_report_text = report

            # 主交互图渲染
            self.draw_single_plots(df_resampled)

            self.btn_single_export_report.config(state=tk.NORMAL)
            self.btn_single_export_data.config(state=tk.NORMAL)
            self.btn_single_save_plot.config(state=tk.NORMAL)
            self.btn_single_save_sep.config(state=tk.NORMAL)
            self.set_status("南方.dat单文件时段分析绘图完成")

        self.run_async(process_task, callback=on_processed)

    def draw_single_plots(self, df):
        if self.single_fig is not None:
            plt.close(self.single_fig)

        for widget in self.plot_container_single.winfo_children():
            widget.destroy()

        fig, axs = plt.subplots(5, 1, figsize=(8, 8.5), sharex=True, dpi=100)

        main_title = self.ent_single_title.get()
        x_label = self.ent_single_xlabel.get()
        y1_label = self.ent_single_y1.get()
        y2_label = self.ent_single_y2.get()
        y3_label = self.ent_single_y3.get()
        y4_label = self.ent_single_y4.get()
        y5_label = self.ent_single_y5.get()

        lw = float(self.ent_single_lw.get().strip() or 1.2)
        ls = self.cmb_single_ls.get()
        grid_visible = self.var_single_grid.get()
        leg_pos = self.cmb_single_leg.get()

        x_tick_sz = int(self.ent_single_xtick.get() or 9)
        y_tick_sz = int(self.ent_single_ytick.get() or 9)
        x_lbl_sz = int(self.ent_single_xtitle_sz.get() or 10)
        y_lbl_sz = int(self.ent_single_ytitle_sz.get() or 10)
        leg_sz = int(self.ent_single_leg_sz.get() or 8)

        axs[0].plot(df.index, df['RMSH'], color='#1f77b4', label=to_academic_font('RMSH'), lw=lw, linestyle=ls)
        axs[0].set_ylabel(to_academic_font(y1_label), fontsize=y_lbl_sz, fontname='SimSun')
        axs[0].legend(loc=leg_pos, frameon=True, fontsize=leg_sz, prop={'family': 'SimSun', 'size': leg_sz})

        axs[1].plot(df.index, df['RMSV'], color='#d62728', label=to_academic_font('RMSV'), lw=lw, linestyle=ls)
        axs[1].set_ylabel(to_academic_font(y2_label), fontsize=y_lbl_sz, fontname='SimSun')
        axs[1].legend(loc=leg_pos, frameon=True, fontsize=leg_sz, prop={'family': 'SimSun', 'size': leg_sz})

        axs[2].plot(df.index, df['PDOP'], color='#2ca02c', lw=lw, linestyle=ls)
        axs[2].set_ylabel(to_academic_font(y3_label), fontsize=y_lbl_sz, fontname='SimSun')

        axs[3].plot(df.index, df['卫星数'], color='#ff7f0e', lw=lw, linestyle=ls)
        axs[3].set_ylabel(to_academic_font(y4_label), fontsize=y_lbl_sz, fontname='SimSun')

        axs[4].plot(df.index, df['差分Age'], color='#9467bd', lw=lw, linestyle=ls)
        axs[4].set_ylabel(to_academic_font(y5_label), fontsize=y_lbl_sz, fontname='SimSun')

        for ax in axs:
            ax.tick_params(axis='x', labelsize=x_tick_sz)
            ax.tick_params(axis='y', labelsize=y_tick_sz)
            ax.margins(x=0)
            if grid_visible:
                ax.grid(True, linestyle=':', alpha=0.6)

        axs[4].xaxis.set_major_formatter(mdates.DateFormatter('%H:%M'))
        axs[4].set_xlabel(to_academic_font(x_label), fontsize=x_lbl_sz, fontname='SimSun')

        fig.suptitle(to_academic_font(main_title), fontsize=11, fontweight='bold', y=0.98, fontname='SimSun')
        fig.tight_layout()

        self.single_fig = fig
        canvas = FigureCanvasTkAgg(fig, master=self.plot_container_single)
        canvas.draw()
        canvas.get_tk_widget().pack(fill=tk.BOTH, expand=True)

        toolbar_frame = ttk.Frame(self.plot_container_single)
        toolbar_frame.pack(fill=tk.X, side=tk.BOTTOM)
        toolbar = NavigationToolbar2Tk(canvas, toolbar_frame)
        toolbar.update()

    def save_single_plot(self):
        if self.single_fig is None:
            return
        filepath = filedialog.asksaveasfilename(title="保存完整合成图表", defaultextension=".png",
                                                filetypes=[("PNG图片", "*.png"), ("PDF矢量图", "*.pdf"),
                                                           ("JPEG图片", "*.jpg")])
        if filepath:
            try:
                # 容错读取自定义DPI
                try:
                    dpi_val = int(self.ent_single_dpi.get().strip())
                except Exception:
                    dpi_val = 300
                self.single_fig.tight_layout()
                self.single_fig.savefig(filepath, dpi=dpi_val, bbox_inches='tight')
                messagebox.showinfo("成功", f"图表已成功保存至: {filepath}")
            except Exception as e:
                messagebox.showerror("保存错误", f"保存失败: {str(e)}")

    def save_single_subplots_separately(self):
        if self.single_df is None or self.last_df_resampled is None:
            messagebox.showwarning("提示", "请先开始分析并绘制生成图表。")
            return

        base_path = filedialog.asksaveasfilename(title="选择子图导出基础路径与文件名(系统将自动增加后缀)",
                                                 defaultextension=".png",
                                                 filetypes=[("PNG图片", "*.png"), ("PDF矢量图", "*.pdf"),
                                                            ("JPEG图片", "*.jpg")])
        if not base_path:
            return

        dir_name = os.path.dirname(base_path)
        base_name, ext = os.path.splitext(os.path.basename(base_path))

        # 读取自定义DPI与长宽尺寸参数
        try:
            dpi_val = int(self.ent_single_dpi.get().strip())
        except Exception:
            dpi_val = 300

        try:
            sub_w = float(self.ent_single_sub_w.get().strip())
        except Exception:
            sub_w = 16.0

        try:
            sub_h = float(self.ent_single_sub_h.get().strip())
        except Exception:
            sub_h = 4.0

        df = self.last_df_resampled

        lw = float(self.ent_single_lw.get().strip() or 1.2)
        ls = self.cmb_single_ls.get()
        grid_visible = self.var_single_grid.get()
        leg_pos = self.cmb_single_leg.get()
        x_tick_sz = int(self.ent_single_xtick.get() or 9)
        y_tick_sz = int(self.ent_single_ytick.get() or 9)
        x_lbl_sz = int(self.ent_single_xtitle_sz.get() or 10)
        y_lbl_sz = int(self.ent_single_ytitle_sz.get() or 10)
        leg_sz = int(self.ent_single_leg_sz.get() or 8)

        metrics = [
            ("1_RMSH", ["RMSH"], self.ent_single_y1.get()),
            ("2_RMSV", ["RMSV"], self.ent_single_y2.get()),
            ("3_PDOP", ["PDOP"], self.ent_single_y3.get()),
            ("4_Satellites", ["卫星数"], self.ent_single_y4.get()),
            ("5_DiffAge", ["差分Age"], self.ent_single_y5.get())
        ]

        for suffix, cols, ylabel in metrics:
            # 采用自定义的画布纵横比尺寸 figsize=(sub_w, sub_h)，DPI同步匹配
            fig, ax = plt.subplots(figsize=(sub_w, sub_h), dpi=dpi_val)

            col = cols[0]
            color_map = {"RMSH": '#1f77b4', "RMSV": '#d62728', "PDOP": '#2ca02c', "卫星数": '#ff7f0e', "差分Age": '#9467bd'}
            ax.plot(df.index, df[col], color=color_map.get(col, '#1f77b4'), lw=lw, linestyle=ls)

            if col in ["RMSH", "RMSV"]:
                ax.legend(loc=leg_pos, frameon=True, fontsize=leg_sz, prop={'family': 'SimSun', 'size': leg_sz})

            ax.set_ylabel(to_academic_font(ylabel), fontsize=y_lbl_sz, fontname='SimSun')
            ax.set_xlabel(to_academic_font(self.ent_single_xlabel.get()), fontsize=x_lbl_sz, fontname='SimSun')
            ax.tick_params(axis='x', labelsize=x_tick_sz)
            ax.tick_params(axis='y', labelsize=y_tick_sz)
            ax.margins(x=0)
            ax.xaxis.set_major_formatter(mdates.DateFormatter('%H:%M'))

            if grid_visible:
                ax.grid(True, linestyle=':', alpha=0.6)

            fig.tight_layout()
            out_file = os.path.join(dir_name, f"{base_name}_{suffix}{ext}")
            fig.savefig(out_file, dpi=dpi_val, bbox_inches='tight')  # 使用自定义DPI保存
            plt.close(fig)

        messagebox.showinfo("成功", f"五个独立子图（尺寸: {sub_w}x{sub_h} 英寸, DPI: {dpi_val}）已成功拆分保存。")

    def export_single_data(self):
        if self.last_df_resampled is None:
            messagebox.showwarning("提示", "请先分析并绘制图表后再导出数据。")
            return

        filepath = filedialog.asksaveasfilename(
            title="选择导出时段数据文件",
            defaultextension=".csv",
            filetypes=[("CSV 逗号分隔文件", "*.csv"), ("文本文件", "*.txt"), ("所有文件", "*.*")]
        )
        if filepath:
            try:
                self.set_status("正在导出单轨时段数据...")
                export_df = self.last_df_resampled.copy()
                export_df.index.name = 'Datetime'

                export_df['日期'] = export_df.index.strftime('%Y/%m/%d')
                export_df['时间'] = export_df.index.strftime('%H:%M:%S')

                export_df = export_df.reset_index()
                export_df.to_csv(filepath, index=False, encoding='utf-8-sig')
                self.set_status("时段数据导出成功")
                messagebox.showinfo("成功", f"该时段重采样数据已导出至: {filepath}")
            except Exception as e:
                self.set_status("数据导出失败")
                messagebox.showerror("导出错误", f"无法导出数据: {str(e)}")

    def export_single_report(self):
        if not hasattr(self, 'single_report_text'):
            return
        filepath = filedialog.asksaveasfilename(title="保存指标报告", defaultextension=".txt", filetypes=[("文本文件", "*.txt")])
        if filepath:
            with open(filepath, 'w', encoding='utf-8') as f:
                f.write(self.single_report_text)
            messagebox.showinfo("成功", "统计指标报告文件已成功导出。")

    # --- 多文件对比逻辑 ---
    def load_ref_file(self):
        filepath = filedialog.askopenfilename(title="选择参考/基准数据文件", filetypes=COMMON_FILETYPES)
        if filepath:
            try:
                self.reset_multi_all(show_msg=False)
                self.lbl_ref_path.config(text="正在导入中，请稍候...", foreground="#007acc")
                self.set_status(f"正在导入参考基准文件: {os.path.basename(filepath)}")

                def load_task():
                    return self.parse_gnss_file(filepath)

                def on_loaded(df):
                    self.ref_filepath = filepath
                    self.lbl_ref_path.config(text=os.path.basename(filepath), foreground="black")
                    self.ref_df = df
                    self.update_multi_time_range()
                    self.set_status("参考基准数据导入完成")

                self.run_async(load_task, callback=on_loaded)
            except Exception as e:
                messagebox.showerror("读取错误", f"无法正确解析该文件: {str(e)}")

    def load_target_files(self):
        filepaths = filedialog.askopenfilenames(title="添加一个或多个待处理文件", filetypes=COMMON_FILETYPES)
        if filepaths:
            self.set_status("正在批量导入对比终端数据...")

            def load_task():
                loaded_files = {}
                for path in filepaths:
                    if path not in self.target_files:
                        loaded_files[path] = self.parse_gnss_file(path)
                return loaded_files

            def on_loaded(loaded_files):
                for path, df in loaded_files.items():
                    self.target_files[path] = df
                    self.lst_targets.insert(tk.END, os.path.basename(path))
                self.update_multi_time_range()
                self.set_status("对比数据批量导入完成")

            self.run_async(load_task, callback=on_loaded)

    def clear_target_files(self):
        self.target_files.clear()
        self.lst_targets.delete(0, tk.END)
        self.lbl_multi_range.config(text="-")
        self.set_status("待对比多终端数据已清空")

    def update_multi_time_range(self):
        if self.ref_df is None:
            return
        all_dfs = [self.ref_df] + list(self.target_files.values())
        if len(all_dfs) == 0:
            return

        mins = [df['Datetime'].min() for df in all_dfs]
        maxs = [df['Datetime'].max() for df in all_dfs]

        overlap_min = max(mins)
        overlap_max = min(maxs)

        if overlap_min <= overlap_max:
            self.lbl_multi_range.config(text=f"{overlap_min} 至 {overlap_max} (重叠区间)")
            self.ent_multi_start.delete(0, tk.END)
            self.ent_multi_start.insert(0, overlap_min.strftime('%Y-%m-%d %H:%M:%S'))
            self.ent_multi_end.delete(0, tk.END)
            self.ent_multi_end.insert(0, overlap_max.strftime('%Y-%m-%d %H:%M:%S'))
        else:
            overall_min = min(mins)
            overall_max = max(maxs)
            self.lbl_multi_range.config(text=f"无交叉重合！总区间: {overall_min} 至 {overall_max}")
            self.ent_multi_start.delete(0, tk.END)
            self.ent_multi_start.insert(0, overall_min.strftime('%Y-%m-%d %H:%M:%S'))
            self.ent_multi_end.delete(0, tk.END)
            self.ent_multi_end.insert(0, overall_max.strftime('%Y-%m-%d %H:%M:%S'))

    def process_multi(self):
        if self.ref_df is None:
            messagebox.showwarning("提示", "请先导入参考/基准文件。")
            return
        if not self.target_files:
            messagebox.showwarning("提示", "请至少导入一个待处理对比文件。")
            return

        try:
            start_str = self.ent_multi_start.get().strip()
            end_str = self.ent_multi_end.get().strip()
            res_val = int(self.ent_multi_res.get().strip())
            multi_file_mode = self.cmb_multi_file_mode.get()  # 获取多文件对比下的移动点/固定点模式

            start_dt = pd.to_datetime(start_str)
            end_dt = pd.to_datetime(end_str)
        except Exception:
            messagebox.showerror("格式错误", "时间格式不正确或分辨率不是有效的整数秒。")
            return

        self.set_status("正在进行多终端对齐、重采样与对比分析...")

        def process_task():
            resample_rule = f"{res_val}s"
            full_idx = pd.date_range(start=start_dt, end=end_dt, freq=resample_rule)

            ref_filtered = self.ref_df[
                (self.ref_df['Datetime'] >= start_dt) & (self.ref_df['Datetime'] <= end_dt)].copy()
            if ref_filtered.empty:
                return None, None, None
            ref_filtered.set_index('Datetime', inplace=True)
            ref_res = ref_filtered.resample(resample_rule).mean(numeric_only=True)

            # 修复：还原在多文件基准重采样中被过滤掉的“点名”与“解状态”
            if '点名' in ref_filtered.columns and '点名' not in ref_res.columns:
                ref_res.insert(0, '点名', ref_filtered['点名'].resample(resample_rule).first())
            if '解状态' in ref_filtered.columns and '解状态' not in ref_res.columns:
                ref_res['解状态'] = ref_filtered['解状态'].resample(resample_rule).first()

            ref_res = ref_res.reindex(full_idx)

            all_resampled_dfs = {self.ref_filepath: ref_res}
            target_metrics_results = []

            ref_valid_epochs = ref_res['北坐标'].notna().sum()
            ref_fixed_rate = (ref_valid_epochs / len(full_idx)) * 100 if len(full_idx) > 0 else 0.0
            ref_base_stats = {
                "name": os.path.basename(self.ref_filepath),
                "is_ref": True,
                "fixed_rate": ref_fixed_rate,
                "mean_rmsh": ref_filtered['RMSH'].mean() if 'RMSH' in ref_filtered else np.nan,
                "mean_rmsv": ref_filtered['RMSV'].mean() if 'RMSV' in ref_filtered else np.nan,
                "mean_pdop": ref_filtered['PDOP'].mean() if 'PDOP' in ref_filtered else np.nan,
                "mean_sat": ref_filtered['卫星数'].mean() if '卫星数' in ref_filtered else np.nan,
                "mean_age": ref_filtered['差分Age'].mean() if '差分Age' in ref_filtered else np.nan,
            }

            # 如果为固定点文件，则对基准/参考文件计算平均坐标及标准差
            if multi_file_mode == "固定点文件":
                ref_base_stats.update({
                    "mean_N": ref_filtered['北坐标'].mean() if '北坐标' in ref_filtered else np.nan,
                    "mean_E": ref_filtered['东坐标'].mean() if '东坐标' in ref_filtered else np.nan,
                    "mean_H": ref_filtered['高程'].mean() if '高程' in ref_filtered else np.nan,
                    "std_N": ref_filtered['北坐标'].std() if '北坐标' in ref_filtered else np.nan,
                    "std_E": ref_filtered['东坐标'].std() if '东坐标' in ref_filtered else np.nan,
                    "std_H": ref_filtered['高程'].std() if '高程' in ref_filtered else np.nan,
                })

            target_metrics_results.append(ref_base_stats)

            for filepath, df in self.target_files.items():
                tgt_filtered = df[(df['Datetime'] >= start_dt) & (df['Datetime'] <= end_dt)].copy()
                if tgt_filtered.empty:
                    continue
                tgt_filtered.set_index('Datetime', inplace=True)
                tgt_res = tgt_filtered.resample(resample_rule).mean(numeric_only=True)

                # 修复：还原在多文件对比重采样中被过滤掉的“点名”与“解状态”
                if '点名' in tgt_filtered.columns and '点名' not in tgt_res.columns:
                    tgt_res.insert(0, '点名', tgt_filtered['点名'].resample(resample_rule).first())
                if '解状态' in tgt_filtered.columns and '解状态' not in tgt_res.columns:
                    tgt_res['解状态'] = tgt_filtered['解状态'].resample(resample_rule).first()

                tgt_res = tgt_res.reindex(full_idx)
                all_resampled_dfs[filepath] = tgt_res

                tgt_valid_epochs = tgt_res['北坐标'].notna().sum()
                tgt_fixed_rate = (tgt_valid_epochs / len(full_idx)) * 100 if len(full_idx) > 0 else 0.0

                aligned = pd.DataFrame(index=full_idx)
                aligned['ref_N'] = ref_res['北坐标']
                aligned['ref_E'] = ref_res['东坐标']
                aligned['ref_H'] = ref_res['高程']
                aligned['tgt_N'] = tgt_res['北坐标']
                aligned['tgt_E'] = tgt_res['东坐标']
                aligned['tgt_H'] = tgt_res['高程']

                aligned['dN'] = aligned['tgt_N'] - aligned['ref_N']
                aligned['dE'] = aligned['tgt_E'] - aligned['ref_E']
                aligned['dH'] = aligned['tgt_H'] - aligned['ref_H']

                diffs = aligned[['dN', 'dE', 'dH']].dropna()

                if len(diffs) > 0:
                    bias_N = diffs['dN'].mean()
                    bias_E = diffs['dE'].mean()
                    bias_H = diffs['dH'].mean()
                    rmse_N = np.sqrt((diffs['dN'] ** 2).mean())
                    rmse_E = np.sqrt((diffs['dE'] ** 2).mean())
                    rmse_H = np.sqrt((diffs['dH'] ** 2).mean())
                else:
                    bias_N = bias_E = bias_H = np.nan
                    rmse_N = rmse_E = rmse_H = np.nan

                tgt_stats = {
                    "name": os.path.basename(filepath),
                    "is_ref": False,
                    "fixed_rate": tgt_fixed_rate,
                    "mean_rmsh": tgt_filtered['RMSH'].mean() if 'RMSH' in tgt_filtered else np.nan,
                    "mean_rmsv": tgt_filtered['RMSV'].mean() if 'RMSV' in tgt_filtered else np.nan,
                    "mean_pdop": tgt_filtered['PDOP'].mean() if 'PDOP' in tgt_filtered else np.nan,
                    "mean_sat": tgt_filtered['卫星数'].mean() if '卫星数' in tgt_filtered else np.nan,
                    "mean_age": tgt_filtered['差分Age'].mean() if '差分Age' in tgt_filtered else np.nan,
                    "bias_N": bias_N, "bias_E": bias_E, "bias_H": bias_H,
                    "rmse_N": rmse_N, "rmse_E": rmse_E, "rmse_H": rmse_H,
                    "valid_diffs_count": len(diffs)
                }

                # 如果为固定点文件，则对各待比对文件计算平均坐标及标准差
                if multi_file_mode == "固定点文件":
                    tgt_stats.update({
                        "mean_N": tgt_filtered['北坐标'].mean() if '北坐标' in tgt_filtered else np.nan,
                        "mean_E": tgt_filtered['东坐标'].mean() if '东坐标' in tgt_filtered else np.nan,
                        "mean_H": tgt_filtered['高程'].mean() if '高程' in tgt_filtered else np.nan,
                        "std_N": tgt_filtered['北坐标'].std() if '北坐标' in tgt_filtered else np.nan,
                        "std_E": tgt_filtered['东坐标'].std() if '东坐标' in df else np.nan,
                        "std_H": tgt_filtered['高程'].std() if '高程' in df else np.nan,
                    })

                target_metrics_results.append(tgt_stats)

            # 生成对比报告
            report_text = f"====================================================\n"
            report_text += f"            GNSS 多文件对比与精度分析报告\n"
            report_text += f"====================================================\n"
            report_text += f"生成时间: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}\n"
            report_text += f"分析区间: {start_str} 至 {end_str}\n"
            report_text += f"文件类型: {multi_file_mode}\n"
            report_text += f"重采样频率: {res_val} 秒\n"
            report_text += f"参考/基准文件: {os.path.basename(self.ref_filepath)}\n\n"

            for item in target_metrics_results:
                if item["is_ref"]:
                    report_text += f"▶【基准】: {item['name']}\n"
                    report_text += f"   - 固定率: {item['fixed_rate']:.2f} %\n"
                    report_text += f"   - 平均 RMSH: {item['mean_rmsh']:.4f} m, RMSV: {item['mean_rmsv']:.4f} m\n"
                    report_text += f"   - 平均 PDOP: {item['mean_pdop']:.2f}, 卫星数: {item['mean_sat']:.1f}, 差分Age: {item['mean_age']:.2f} s\n"

                    # 固定点文件模式下输出基准的均值与标准差
                    if multi_file_mode == "固定点文件":
                        report_text += f"   * 各文件固定点观测精度指标:\n"
                        report_text += f"     - 平均北坐标: {item['mean_N']:.4f} m\n"
                        report_text += f"     - 平均东坐标: {item['mean_E']:.4f} m\n"
                        report_text += f"     - 平均高程: {item['mean_H']:.4f} m\n"
                        report_text += f"     - 北坐标的标准差: {item['std_N']:.4f} m\n"
                        report_text += f"     - 东坐标的标准差: {item['std_E']:.4f} m\n"
                        report_text += f"     - 高程的标准差: {item['std_H']:.4f} m\n"
                else:
                    report_text += f"▶【待比对】: {item['name']}\n"
                    report_text += f"   - 固定率: {item['fixed_rate']:.2f} %\n"
                    report_text += f"   - 平均 RMSH: {item['mean_rmsh']:.4f} m, RMSV: {item['mean_rmsv']:.4f} m\n"
                    report_text += f"   - 平均 PDOP: {item['mean_pdop']:.2f}, 卫星数: {item['mean_sat']:.1f}, 差分Age: {item['mean_age']:.2f} s\n"

                    # 固定点文件模式下输出各比对文件的均值与标准差
                    if multi_file_mode == "固定点文件":
                        report_text += f"   * 各文件固定点观测精度指标:\n"
                        report_text += f"     - 平均北坐标: {item['mean_N']:.4f} m\n"
                        report_text += f"     - 平均东坐标: {item['mean_E']:.4f} m\n"
                        report_text += f"     - 平均高程: {item['mean_H']:.4f} m\n"
                        report_text += f"     - 北坐标的标准差: {item['std_N']:.4f} m\n"
                        report_text += f"     - 东坐标的标准差: {item['std_E']:.4f} m\n"
                        report_text += f"     - 高程的标准差: {item['std_H']:.4f} m\n"

                    report_text += f"   * 坐标精度差值分析 (共用重采样点对数: {item['valid_diffs_count']} 个):\n"
                    if item['valid_diffs_count'] > 0:
                        report_text += f"     - 北坐标 (Delta N): 平均偏差 = {item['bias_N']:.4f} m, RMSE = {item['rmse_N']:.4f} m\n"
                        report_text += f"     - 东坐标 (Delta E): 平均偏差 = {item['bias_E']:.4f} m, RMSE = {item['rmse_E']:.4f} m\n"
                        report_text += f"     - 高  程 (Delta H): 平均偏差 = {item['bias_H']:.4f} m, RMSE = {item['rmse_H']:.4f} m\n"
                    else:
                        report_text += f"     - 暂无数据：双方在该区间无交集坐标对。\n"
                report_text += f"----------------------------------------------------\n"

            return all_resampled_dfs, report_text

        def on_processed(result):
            all_resampled_dfs, report = result
            if all_resampled_dfs is None:
                messagebox.showwarning("无数据", "参考基准文件在选定区间内无定位数据。")
                self.set_status("多终端对比分析失败")
                return

            self.last_dfs_dict = all_resampled_dfs
            self.txt_multi_output.delete("1.0", tk.END)
            self.txt_multi_output.insert(tk.END, report)
            self.multi_report_text = report

            self.draw_multi_plots(all_resampled_dfs)

            self.btn_multi_export_report.config(state=tk.NORMAL)
            self.btn_multi_export_data.config(state=tk.NORMAL)
            self.btn_multi_save_plot.config(state=tk.NORMAL)
            self.btn_multi_save_sep.config(state=tk.NORMAL)
            self.set_status("多文件对比分析与联合绘图完成")

        self.run_async(process_task, callback=on_processed)

    def draw_multi_plots(self, dfs_dict):
        if self.multi_fig is not None:
            plt.close(self.multi_fig)

        for widget in self.plot_container_multi.winfo_children():
            widget.destroy()

        fig, axs = plt.subplots(5, 1, figsize=(8, 8.5), sharex=True, dpi=100)

        main_title = self.ent_multi_title.get()
        x_label = self.ent_multi_xlabel.get()
        y1_label = self.ent_multi_y1.get()
        y2_label = self.ent_multi_y2.get()
        y3_label = self.ent_multi_y3.get()
        y4_label = self.ent_multi_y4.get()
        y5_label = self.ent_multi_y5.get()

        lw = float(self.ent_multi_lw.get().strip() or 1.2)
        ls = self.cmb_multi_ls.get()
        grid_visible = self.var_multi_grid.get()
        leg_pos = self.cmb_multi_leg.get()

        x_tick_sz = int(self.ent_multi_xtick.get() or 9)
        y_tick_sz = int(self.ent_multi_ytick.get() or 9)
        x_lbl_sz = int(self.ent_multi_xtitle_sz.get() or 10)
        y_lbl_sz = int(self.ent_multi_ytitle_sz.get() or 10)
        leg_sz = int(self.ent_multi_leg_sz.get() or 7)

        color_cycle = plt.rcParams['axes.prop_cycle'].by_key()['color']

        for idx, (filepath, df) in enumerate(dfs_dict.items()):
            label_name = os.path.basename(filepath)
            color = color_cycle[idx % len(color_cycle)]
            file_lw = lw + 0.3 if filepath == self.ref_filepath else lw

            lbl_h = to_academic_font(f"{label_name}")

            axs[0].plot(df.index, df['RMSH'], color=color, label=lbl_h, lw=file_lw, linestyle=ls)
            axs[1].plot(df.index, df['RMSV'], color=color, label=lbl_h, lw=file_lw, linestyle=ls)
            axs[2].plot(df.index, df['PDOP'], color=color, lw=file_lw, linestyle=ls)
            axs[3].plot(df.index, df['卫星数'], color=color, lw=file_lw, linestyle=ls)
            axs[4].plot(df.index, df['差分Age'], color=color, lw=file_lw, linestyle=ls)

        # === 核心优化：图例仅在最顶部的第一个子图 (RMSH) 显示，所有 5 个子图共用此图例 ===
        axs[0].set_ylabel(to_academic_font(y1_label), fontsize=y_lbl_sz, fontname='SimSun')
        axs[0].legend(loc=leg_pos, frameon=True, fontsize=leg_sz, ncol=max(1, len(dfs_dict)),
                      prop={'family': 'SimSun', 'size': leg_sz})

        axs[1].set_ylabel(to_academic_font(y2_label), fontsize=y_lbl_sz, fontname='SimSun')
        # 移除原有的 axs[1].legend(...) 调用以消除冗余

        axs[2].set_ylabel(to_academic_font(y3_label), fontsize=y_lbl_sz, fontname='SimSun')
        axs[3].set_ylabel(to_academic_font(y4_label), fontsize=y_lbl_sz, fontname='SimSun')
        axs[4].set_ylabel(to_academic_font(y5_label), fontsize=y_lbl_sz, fontname='SimSun')

        for ax in axs:
            ax.tick_params(axis='x', labelsize=x_tick_sz)
            ax.tick_params(axis='y', labelsize=y_tick_sz)
            ax.margins(x=0)
            if grid_visible:
                ax.grid(True, linestyle=':', alpha=0.5)

        axs[4].xaxis.set_major_formatter(mdates.DateFormatter('%H:%M'))
        axs[4].set_xlabel(to_academic_font(x_label), fontsize=x_lbl_sz, fontname='SimSun')

        fig.suptitle(to_academic_font(main_title), fontsize=11, fontweight='bold', y=0.98, fontname='SimSun')
        fig.tight_layout()

        self.multi_fig = fig
        canvas = FigureCanvasTkAgg(fig, master=self.plot_container_multi)
        canvas.draw()
        canvas.get_tk_widget().pack(fill=tk.BOTH, expand=True)

        toolbar_frame = ttk.Frame(self.plot_container_multi)
        toolbar_frame.pack(fill=tk.X, side=tk.BOTTOM)
        toolbar = NavigationToolbar2Tk(canvas, toolbar_frame)
        toolbar.update()

    def save_multi_plot(self):
        if self.multi_fig is None:
            return
        filepath = filedialog.asksaveasfilename(title="保存统一对比大图", defaultextension=".png",
                                                filetypes=[("PNG图片", "*.png"), ("PDF矢量图", "*.pdf")])
        if filepath:
            try:
                # 容错读取自定义DPI
                try:
                    dpi_val = int(self.ent_multi_dpi.get().strip())
                except Exception:
                    dpi_val = 300
                self.multi_fig.tight_layout()
                self.multi_fig.savefig(filepath, dpi=dpi_val, bbox_inches='tight')
                messagebox.showinfo("成功", f"多文件大图已成功导出至: {filepath}")
            except Exception as e:
                messagebox.showerror("保存错误", f"保存失败: {str(e)}")

    def save_multi_subplots_separately(self):
        if not hasattr(self, 'last_dfs_dict') or self.last_dfs_dict is None:
            messagebox.showwarning("提示", "请先分析并绘制生成对比图表。")
            return

        base_path = filedialog.asksaveasfilename(title="选择多文件子图导出基础路径", defaultextension=".png",
                                                 filetypes=[("PNG图片", "*.png"), ("PDF矢量图", "*.pdf")])
        if not base_path:
            return

        dir_name = os.path.dirname(base_path)
        base_name, ext = os.path.splitext(os.path.basename(base_path))

        # 读取自定义DPI与长宽尺寸参数
        try:
            dpi_val = int(self.ent_multi_dpi.get().strip())
        except Exception:
            dpi_val = 300

        try:
            sub_w = float(self.ent_multi_sub_w.get().strip())
        except Exception:
            sub_w = 16.0

        try:
            sub_h = float(self.ent_multi_sub_h.get().strip())
        except Exception:
            sub_h = 4.0

        dfs_dict = self.last_dfs_dict

        lw = float(self.ent_multi_lw.get().strip() or 1.2)
        ls = self.cmb_multi_ls.get()
        grid_visible = self.var_multi_grid.get()
        leg_pos = self.cmb_multi_leg.get()
        x_tick_sz = int(self.ent_multi_xtick.get() or 9)
        y_tick_sz = int(self.ent_multi_ytick.get() or 9)
        x_lbl_sz = int(self.ent_multi_xtitle_sz.get() or 10)
        y_lbl_sz = int(self.ent_multi_ytitle_sz.get() or 10)
        leg_sz = int(self.ent_multi_leg_sz.get() or 7)

        color_cycle = plt.rcParams['axes.prop_cycle'].by_key()['color']

        metrics = [
            ("1_RMSH", ["RMSH"], self.ent_multi_y1.get()),
            ("2_RMSV", ["RMSV"], self.ent_multi_y2.get()),
            ("3_PDOP", ["PDOP"], self.ent_multi_y3.get()),
            ("4_Satellites", ["卫星数"], self.ent_multi_y4.get()),
            ("5_DiffAge", ["差分Age"], self.ent_multi_y5.get())
        ]

        for suffix, cols, ylabel in metrics:
            # 采用自定义的画布纵横比尺寸 figsize=(sub_w, sub_h)，DPI同步匹配
            fig, ax = plt.subplots(figsize=(sub_w, sub_h), dpi=dpi_val)

            col = cols[0]
            for idx, (filepath, df) in enumerate(dfs_dict.items()):
                label_name = os.path.basename(filepath)
                color = color_cycle[idx % len(color_cycle)]
                file_lw = lw + 0.3 if filepath == self.ref_filepath else lw
                ax.plot(df.index, df[col], color=color, label=to_academic_font(label_name), lw=file_lw, linestyle=ls)

            ax.set_ylabel(to_academic_font(ylabel), fontsize=y_lbl_sz, fontname='SimSun')
            ax.set_xlabel(to_academic_font(self.ent_multi_xlabel.get()), fontsize=x_lbl_sz, fontname='SimSun')
            ax.tick_params(axis='x', labelsize=x_tick_sz)
            ax.tick_params(axis='y', labelsize=y_tick_sz)
            ax.margins(x=0)
            ax.xaxis.set_major_formatter(mdates.DateFormatter('%H:%M'))

            ax.legend(loc=leg_pos, frameon=True, fontsize=leg_sz, prop={'family': 'SimSun', 'size': leg_sz})

            if grid_visible:
                ax.grid(True, linestyle=':', alpha=0.6)

            fig.tight_layout()
            out_file = os.path.join(dir_name, f"{base_name}_{suffix}{ext}")
            fig.savefig(out_file, dpi=dpi_val, bbox_inches='tight')  # 使用自定义DPI保存
            plt.close(fig)

        messagebox.showinfo("成功", f"四个对比独立子图（尺寸: {sub_w}x{sub_h} 英寸, DPI: {dpi_val}）已成功拆分保存。")

    def export_multi_data(self):
        if self.last_dfs_dict is None:
            messagebox.showwarning("提示", "请先进行对比分析后再导出数据。")
            return

        filepath = filedialog.asksaveasfilename(
            title="选择导出合并时段数据文件",
            defaultextension=".csv",
            filetypes=[("CSV 逗号分隔文件", "*.csv"), ("文本文件", "*.txt"), ("所有文件", "*.*")]
        )
        if filepath:
            try:
                self.set_status("正在合并各路对比时段数据...")
                combined_df = None
                for fpath, df_res in self.last_dfs_dict.items():
                    name = os.path.splitext(os.path.basename(fpath))[0]
                    df_temp = df_res.copy()

                    df_temp.columns = [f"{name}_{col}" for col in df_temp.columns]

                    if combined_df is None:
                        combined_df = df_temp
                    else:
                        combined_df = combined_df.join(df_temp, how='outer')

                combined_df.index.name = 'Datetime'

                combined_df['日期'] = combined_df.index.strftime('%Y/%m/%d')
                combined_df['时间'] = combined_df.index.strftime('%H:%M:%S')

                combined_df = combined_df.reset_index()

                combined_df.to_csv(filepath, index=False, encoding='utf-8-sig')
                self.set_status("合并时段数据导出成功")
                messagebox.showinfo("成功", f"合并时段数据已成功导出至: {filepath}")
            except Exception as e:
                self.set_status("合并数据导出失败")
                messagebox.showerror("导出错误", f"无法导出合并数据: {str(e)}")

    def export_multi_report(self):
        if not hasattr(self, 'multi_report_text'):
            return
        filepath = filedialog.asksaveasfilename(title="保存对比分析指标报告", defaultextension=".txt",
                                                filetypes=[("文本文件", "*.txt")])
        if filepath:
            with open(filepath, 'w', encoding='utf-8') as f:
                f.write(self.multi_report_text)
            messagebox.showinfo("成功", "多文件对比分析统计报告文件已成功导出。")


# --- 程序启动 ---
if __name__ == "__main__":
    root = tk.Tk()
    app = GNSSProcessorApp(root)


    # 安全、干净的退出函数，防止任何后台残留进程
    def on_closing():
        try:
            plt.close('all')  # 关闭所有 Matplotlib 图表窗口，释放内存
        except Exception:
            pass
        try:
            root.destroy()  # 彻底销毁 Tkinter 主窗口事件循环
        except Exception:
            pass
        # 强制立即终止当前 Python 进程，清除任何挂起中的库、子线程或句柄
        os._exit(0)


    root.protocol("WM_DELETE_WINDOW", on_closing)  # 拦截右上角 "X" 关闭协议
    root.mainloop()