"""生成《新疆风资源图集》DOCX：每页一张图 + 下方注释说明。

用法（VS Code）：Ctrl+F5 运行本文件，或在终端
    conda run -n met python 图集/生成图集.py

输出：图集/新疆风资源图集.docx
"""
from __future__ import annotations

from pathlib import Path

import docx
from docx.enum.text import WD_ALIGN_PARAGRAPH, WD_BREAK
from docx.oxml.ns import qn
from docx.shared import Cm, Pt, RGBColor

BASE = Path(__file__).resolve().parent.parent
FIG = BASE / "3_成果图"
OUT = BASE / "图集" / "新疆风资源图集.docx"

# (标题, 图片文件名, 画的是什么, 数据, 怎么读, 结论, 局限)
ENTRIES = [
    ("2015 年平均风速（全要素）", "图集_2015年平均风速_全要素.png",
     "2015 年全年平均的 10 米风速，叠加河流、14 个地州名、400 km 比例尺与指北针。",
     "ERA5 单层，0.25°（61×121），6 小时，1460 个时次。",
     "颜色为风速（0–8 m/s）：深紫是静风区，黄绿是强风区。投影为兰勃特——新疆跨 30 个经度，等经纬度会把东西向拉长。",
     "深紫（2–3 m/s）沿天山中段与塔里木盆地南缘；青绿（4–5 m/s）在准噶尔西部与哈密一带。河流基本沿天山南北两侧走，说明地形控制风速。",
     "单年结果，不能代表 10 年平均；10 米高度不是轮毂高度。"),

    ("2020 年代表月风速四联图", "ERA5风速_2020_四季四联图.png",
     "2020 年 1/4/7/10 月的平均风速，2×2 排列。",
     "四个月共 492 个时次，同一网格。",
     "四张子图共用一套色标（0–7.5 m/s），颜色可直接横向比较。若各自归一化，10 月的 5.98 m/s 会被画得和 1 月 7.16 m/s 一样深，结论就错了。",
     "全区均值：1 月 2.34、4 月 2.78、7 月 2.85、10 月 2.62 m/s；最大值 1 月 7.16。7 月略强，但四个月差不到 0.5 m/s。",
     "只有四个月，不能代表全年；四个月的“平均”也不等于年均。"),

    ("2020 代表月平均（不是年均）", "ERA5风速_2020年平均.png",
     "把四联图的四个场再平均一次，得到一张图。",
     "同上，492 个时次。",
     "全区 2.65 m/s、最大 5.13 m/s。图名与脚本注释都注明“代表月平均”。",
     "这只是四个代表月的合成，缺 8 个月，不能当 2020 年年均使用。",
     "真年均要 12 个月或按天数加权；本图仅用于季节对比。"),

    ("2020 年 1 月月平均", "ERA5风速_2020-01_月平均.png",
     "单月（2020-01）平均风速，最基础的填色图。",
     "ERA5 单层 0.25°，6 小时，124 个时次。",
     "看空间格局：西部（伊犁、塔城）与东部（哈密）偏强，中部天山一带偏弱。",
     "单月也能看出“两强一弱”，与多年平均形态一致。",
     "单月代表性有限；10 米高度。"),

    ("乌鲁木齐单点风速时间序列", "ERA5风速_2020-01_时间序列.png",
     "43.8°N/87.6°E 附近 2020 年 1 月的 6 小时风速，叠加区域平均作参照。",
     "单点序列 124 个时次；区域平均由同一网格算出。",
     "红实线为单点，灰虚线为区域平均；纵轴 m/s，横轴 UTC。",
     "单点均值约 2.3 m/s，峰值接近 8 m/s；区域平均平稳得多——单点波动远大于区域平均。",
     "6 小时分辨率不能谈日变化；时间为 UTC，北京时间 +8。"),

    ("CMFD 1 月 / 7 月 / 差值三联图", "CMFD风速_季节对比_带行政区.png",
     "1979—2018 年 CMFD 的 1 月平均、7 月平均，以及“7 月 − 1 月”的差值，附地州边界。",
     "CMFD 0.1°，40 年月平均。",
     "差值图用发散色标、0 居中：红 = 夏季更大，蓝 = 冬季更大。",
     "大部分区域 7 月高于 1 月，但天山与部分盆地出现蓝区——季节差异存在区域反转。",
     "只比两个月；12 个月排开后结论需修正（见下一张）。"),

    ("CMFD 12 个月气候态（春峰冬谷）", "CMFD风速_季节循环.png",
     "全区与“百里风区热点”的 12 个月气候态曲线。",
     "CMFD 0.1°，1979—2018 年月平均，480 个时次。",
     "横轴月份、纵轴风速；两条线分别是全区平均与热点。",
     "全区峰值在 4 月 3.22 m/s、谷值在 12 月 2.01；热点峰值在 6 月 8.93、谷值 1 月 3.42。两者峰值相差两个月。",
     "最初只比 1 月与 7 月得出“夏峰冬谷”，是样本偏差；本图是修正后的结果。"),

    ("CMFD 40 年年平均序列", "CMFD风速_1979-2018_年均序列.png",
     "1979—2018 年新疆区域平均风速的年平均序列。",
     "CMFD 0.1°，480 个月 → 40 个年均值。",
     "点线为逐年值；纵轴 m/s。",
     "1979 年 2.85 → 1998 年 2.30（最低）→ 2018 年 2.67；40 年先降后升，降幅 0.55、回升 0.37。",
     "区域平均掩盖空间差异；未做趋势显著性检验。"),

    ("极端阈值（p95，逐格点）", "极端_阈值_p95.png",
     "基准期 2009—2014 年，每个格点自己 95 分位上的风速阈值。",
     "ERA5 10 年（2009–2018），基准期约 2.1 万个时次。",
     "阈值空间差 0.49–12.82 m/s（20 倍）：山区高、盆地低。",
     "不能用单一数字卡全疆：3.58 m/s 对哈密太低、对塔里木太高。阈值必须逐格点算。",
     "基准期只有 6 年；更稳的做法是 20–30 年。"),

    ("极端超阈天数（研究期）", "极端_超阈天数_p95.png",
     "研究期 2015—2018 年各格点超过自己阈值的累计天数。",
     "同上，研究期约 1.4 万个时次。",
     "这是 4 年累计，不是每年：区域均值 71.1 天、最大 129.8 天（折合每年约 18 天）。",
     "阈值是逐格点 p95，超阈率天然接近 5%——本图只回答“哪里更异常”，不回答“哪里风最大”。",
     "方法属性决定，不是数据巧合；想看绝对强度要用固定阈值。"),

    ("极端平均强度", "极端_强度_p95.png",
     "超阈时刻的平均超出量（只对超阈时刻求平均）。",
     "同上。",
     "单位 m/s；不超阈的时刻不参与平均，否则会被稀释。",
     "平均 1.09 m/s、最大 3.02 m/s；高值区在天山与东部——一旦超阈，超得更多。",
     "只有强度、不含频次，需与上一张一起看。"),

    ("极端最长持续", "极端_持续_p95.png",
     "连续超阈的最长时次（每个时次 6 小时）。",
     "同上。",
     "单位为“连续时次”，乘以 6 即小时数。",
     "区域最长 5 个时次 = 30 小时；新疆极端风过程多为 1–2 天，与冷空气过境的物理图像一致。",
     "6 小时分辨率会低估短过程，逐小时数据下最大值可能更高。"),

    ("极端逐年趋势", "极端_趋势_p95.png",
     "用同一套阈值回算每一年，得到区域平均超阈天数的年际序列与线性拟合。",
     "2009—2018 年，每年约 1460 个时次。",
     "纵轴为每年超阈天数（约 17–21 天）；虚线为线性趋势。",
     "趋势 −0.15 天/年，p = 0.33，不显著：10 年看不出风极端在变多或变少。",
     "p 不显著 ≠ 没有变化；10 年对气候趋势太短，20–30 年才有统计意义。"),
]


def set_cn_font(run, size=10.5, bold=False, color=None):
    run.font.name = "Microsoft YaHei"
    run._element.rPr.rFonts.set(qn("w:eastAsia"), "Microsoft YaHei")
    run.font.size = Pt(size)
    run.bold = bold
    if color:
        run.font.color.rgb = RGBColor(*color)


def add_caption(doc, label: str, text: str) -> None:
    """一条注释：加粗标签 + 正文，左对齐、首行不缩进。"""
    p = doc.add_paragraph()
    p.paragraph_format.space_after = Pt(3)
    p.paragraph_format.line_spacing = 1.25
    r1 = p.add_run(f"{label}：")
    set_cn_font(r1, 9.5, bold=True, color=(0x1F, 0x3B, 0x57))
    r2 = p.add_run(text)
    set_cn_font(r2, 9.5)


def main() -> int:
    doc = docx.Document()

    # 页面：A4、2 cm 边距
    sec = doc.sections[0]
    sec.page_width, sec.page_height = Cm(21), Cm(29.7)
    sec.left_margin = sec.right_margin = Cm(2.0)
    sec.top_margin = sec.bottom_margin = Cm(2.0)

    normal = doc.styles["Normal"]
    normal.font.name = "Microsoft YaHei"
    normal.element.rPr.rFonts.set(qn("w:eastAsia"), "Microsoft YaHei")

    # ---------- 封面 ----------
    t = doc.add_paragraph()
    t.alignment = WD_ALIGN_PARAGRAPH.CENTER
    set_cn_font(t.add_run("新疆风资源与极端风速"), 24, bold=True, color=(0x1F, 0x3B, 0x57))
    s = doc.add_paragraph()
    s.alignment = WD_ALIGN_PARAGRAPH.CENTER
    set_cn_font(s.add_run("图 集"), 18, bold=False, color=(0x1F, 0x3B, 0x57))

    doc.add_paragraph()
    info = doc.add_paragraph()
    info.alignment = WD_ALIGN_PARAGRAPH.CENTER
    set_cn_font(info.add_run("ERA5（2009–2018，0.25°，6 小时） · CMFD（1979–2018，0.1°，月平均）"), 10)
    d = doc.add_paragraph()
    d.alignment = WD_ALIGN_PARAGRAPH.CENTER
    set_cn_font(d.add_run("13 张图 · 每张图下方附注释"), 9, color=(0x66, 0x66, 0x66))

    doc.add_paragraph().add_run().add_break(WD_BREAK.PAGE)

    # ---------- 数据说明 ----------
    doc.add_heading("数据与读图说明", level=1)
    for txt in [
        "ERA5 再分析：欧洲中期天气预报中心产品，本文用 0.25°、6 小时分辨率。2009–2018 共 10 年、14,608 个时次用于极端指数；2020 年 1/4/7/10 四个月（492 个时次）用于季节对比。",
        "CMFD：中国区域地面气象要素驱动数据集，0.1°、月平均，1979–2018 共 480 个时次，用于长期气候态。",
        "统一处理：所有数据经 src/era5x 的 io 层统一坐标（valid_time→time、删 expver、纬度升序），compute 层算风速 √(u²+v²)，plot 层出图。",
        "关于“极端”：阈值取基准期逐格点 95 分位，研究期统计超阈频次、强度与持续。基准期与统计期分离，避免循环论证。",
        "关于颜色：同一组图共用一套 levels，所以颜色可以横向比较；单独一张图看时，注意色标范围。",
    ]:
        p = doc.add_paragraph(txt)
        p.paragraph_format.space_after = Pt(6)
        p.paragraph_format.line_spacing = 1.3
        for r in p.runs:
            set_cn_font(r, 10)

    # ---------- 13 张图 ----------
    for i, (title, fname, what, data, how, concl, limit) in enumerate(ENTRIES, start=1):
        doc.add_paragraph().add_run().add_break(WD_BREAK.PAGE)

        h = doc.add_heading(level=1)
        set_cn_font(h.add_run(f"图 {i}　{title}"), 13, bold=True, color=(0x1F, 0x3B, 0x57))

        img = FIG / fname
        p = doc.add_paragraph()
        p.alignment = WD_ALIGN_PARAGRAPH.CENTER
        p.paragraph_format.space_before = Pt(2)
        p.paragraph_format.space_after = Pt(4)
        p.add_run().add_picture(str(img), width=Cm(16.4))

        cap = doc.add_paragraph()
        cap.alignment = WD_ALIGN_PARAGRAPH.CENTER
        set_cn_font(cap.add_run(f"图 {i}　{title}"), 9, color=(0x66, 0x66, 0x66))

        add_caption(doc, "画的是什么", what)
        add_caption(doc, "数据", data)
        add_caption(doc, "怎么读", how)
        add_caption(doc, "结论", concl)
        add_caption(doc, "局限", limit)

    # ---------- 附录：其余 18 张 ----------
    doc.add_paragraph().add_run().add_break(WD_BREAK.PAGE)
    doc.add_heading("附录：其余 18 张过程图", level=1)
    p = doc.add_paragraph("以下图不进入主图集，但都能在 3_成果图/ 找到，用途见表。")
    for r in p.runs:
        set_cn_font(r, 10)

    rows = [
        ("cli_plot.png", "CLI 默认参数出的 2015 年平均风场（旧样式）", "验证 CLI 跑通"),
        ("cli_2015-07.png", "CLI --month 2015-07", "验证按月切片"),
        ("cli_check.png", "又一次默认出图", "纯功能验证"),
        ("cli_lambert.png", "CLI --projection lambert（旧样式）", "验证投影参数"),
        ("cli_series.png", "CLI series 2015 全年单点序列", "验证点吸附 43.75N/87.50E"),
        ("cli_thr.png", "CLI index 单年 p95 阈值", "与 6 年基准期对比样本量影响"),
        ("CMFD风速_1979-2018.png", "40 年平均风速", "最早国产数据成果"),
        ("CMFD风速_1979-2018-01月.png", "1 月气候态", "冬季偏弱"),
        ("CMFD风速_1979-2018-07月.png", "7 月气候态", "夏季偏强，但峰值月在 4 月"),
        ("wind_demo.png", "演示数据占位图", "只为验证环境能出图"),
        ("试验_极端阈值_p95.png", "4 个月算的 p95 阈值", "样本不足的方法演示"),
        ("试验_极端超阈次数对比.png", "逐格点 vs 区域统一阈值", "说明超阈率 5% 是定义属性"),
        ("投影_等经纬度.png", "PlateCarree 投影", "高纬东西向拉长"),
        ("投影_兰勃特等角圆锥.png", "Lambert 投影", "形状最准，现为默认"),
        ("投影_墨卡托.png", "Mercator 投影", "保角但面积放大"),
        ("投影_三合一对比.png", "三投影并排、共用色标", "教学用对比"),
        ("要素_全要素_plate.png", "同数据等经纬度投影", "对照投影对形状的影响"),
        ("要素_全要素_lambert.png", "同数据兰勃特投影", "第 1 张的前一版"),
    ]
    table = doc.add_table(rows=1, cols=3)
    table.style = "Light Grid Accent 1"
    for c, name in enumerate(["文件", "是什么", "用途 / 结论"]):
        cell = table.rows[0].cells[c]
        cell.text = ""
        set_cn_font(cell.paragraphs[0].add_run(name), 9, bold=True)
    for f, what, use in rows:
        cells = table.add_row().cells
        for c, text in enumerate([f, what, use]):
            cells[c].text = ""
            set_cn_font(cells[c].paragraphs[0].add_run(text), 8.5)

    doc.save(OUT)
    print(f"已保存: {OUT}")
    print(f"  图 {len(ENTRIES)} 张 + 附录 {len(rows)} 条")
    print(f"  大小 {OUT.stat().st_size / 1024:.0f} KB")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
