---
name: patagonia-scraper
version: 1.1.0
description: |
  爬取 Patagonia 官网商品页面数据（产品信息 + 全部颜色的高清图片），生成中文 Word 文档。
  基于实战验证的 Demandware CDN 反爬绕过方案：Playwright 有头浏览器统一提取文本和高清图片。
  无需任何付费 MCP 工具，仅依赖 Playwright + python-docx。
  自动发现并抓取页面上的所有颜色变体图片。
  触发词：patagonia、爬取 patagonia、patagonia 商品、patagonia 图片、爬巴塔哥尼亚。
  当用户提供 Patagonia 产品链接并要求抓取数据/图片/生成文档时使用此 skill。
---

# Patagonia 商品数据抓取

抓取 patagonia.com 商品页面，提取完整产品信息并下载全部颜色的高清图片，生成中文 Word 文档。

## 为什么需要专门的 skill

Patagonia 使用 Salesforce Commerce Cloud (Demandware) 平台，具有三层反爬保护：
1. **浏览器指纹检测** — 直接请求返回 "Hang Tight" 挡板页
2. **CDN 防盗链** — 图片 URL 直接 HTTP 请求返回 404
3. **懒加载图片** — 页面使用 1x1 占位符，真实图片由 JS 动态加载

通用爬虫方案全部失败，必须组合使用多种技术。

## 环境依赖

- `playwright`（Python 版，需 `playwright install chromium`）
- `python-docx`
- `Pillow`
- Windows 环境需 `verify=False` + `urllib3.disable_warnings()` 解决 SSL 证书问题

**不需要任何付费 MCP 工具。** 文本和图片数据全部通过 Playwright 有头浏览器一次完成。

## 本地文件存储规范

所有数据按款式编号（style number）组织到独立文件夹中，一个型号一个文件夹：

```
scraped_data/
├── {style_number}/
│   ├── images/                          # 该型号全部颜色的高清图片
│   │   ├── {style}_{color}.jpg          # 主图
│   │   ├── {style}_{color}_GNL1.jpg     # 模特展示 1
│   │   ├── {style}_{color}_GNL2.jpg     # 模特展示 2
│   │   ├── {style}_{color2}.jpg         # 第二个颜色的主图
│   │   ├── {style}_{color2}_CDD1.jpg    # 第二个颜色的细节图
│   │   └── {style}_000_LIFESTYLE1.jpg   # 共用生活场景图
│   ├── product.json                     # 原始产品数据（JSON）
│   └── Patagonia_{style}_商品信息.docx   # 中文 Word 文档
```

示例：
```
scraped_data/
├── 38504/
│   ├── images/
│   │   └── 38504_TNGO.jpg
│   ├── product.json
│   └── Patagonia_38504_商品信息.docx
├── 44937/
│   ├── images/
│   │   ├── 44937_CGBX.jpg              # 颜色1 主图
│   │   ├── 44937_CGBX_GNL1.jpg         # 颜色1 模特展示
│   │   ├── 44937_CGBX_ALTFRONT.jpg     # 颜色1 正面展示
│   │   ├── 44937_CGSX.jpg              # 颜色2 主图
│   │   ├── 44937_CGSX_CDD1.jpg         # 颜色2 细节图
│   │   ├── 44937_000_LIFESTYLE1.jpg    # 共用生活场景图
│   │   └── ...
│   ├── product.json
│   └── Patagonia_44937_商品信息.docx
```

关键规则：
- 每个型号一个顶级文件夹，以款式编号命名（如 `44937`）
- 图片统一放在该文件夹下的 `images/` 子目录中
- JSON 数据和 Word 文档放在型号根目录下
- **不要**将图片散落在 `scraped_data/` 根目录

## 完整抓取流程

整个流程只使用一个 Playwright 浏览器会话，分两步提取文本和图片。

### 第一步：用 Playwright 提取产品文本数据

在加载页面后、抓图片的同时，用 `page.evaluate()` 直接从 DOM 提取产品信息：

```python
async def extract_product_data(page, style_number):
    """从已加载的页面 DOM 中提取产品数据"""
    return await page.evaluate('''(styleNumber) => {
        const data = {};

        // 产品名称
        const titleEl = document.querySelector('h1, [class*="product-name"], [class*="product-title"]');
        data.name = titleEl ? titleEl.innerText.trim() : '';

        // 从页面全文提取关键信息
        const text = document.body.innerText;

        // 款式编号 + 颜色代码：格式 "XXXX | Style No. XXXXX"
        const styleMatch = text.match(/([A-Z0-9]{4})\\s*\\|\\s*Style No\\.\\s*(\\d+)/);
        data.color_code = styleMatch ? styleMatch[1] : '';
        data.style_number = styleMatch ? styleMatch[2] : styleNumber;

        // 价格
        const priceMatch = text.match(/\\$([\\d.]+)/);
        data.price = priceMatch ? '$' + priceMatch[1] : '';

        // 版型
        const fitMatch = text.match(/(Regular fit|Slim fit|Relaxed fit|Slim fit)/i);
        data.fit = fitMatch ? fitMatch[1] : '';

        // 重量
        const weightMatch = text.match(/(\\d+)\\s*g\\s*\\(([\\d.]+\\s*oz)\\)/);
        data.weight = weightMatch ? weightMatch[0] : '';

        // 产地
        const originMatch = text.match(/Made in ([^.]+)/);
        data.origin = originMatch ? 'Made in ' + originMatch[1] : '';

        // 材质：在 "Materials & Care Instructions" 附近
        const matMatch = text.match(/(\\d+\\.\\d+-oz[^\\n]+)/);
        data.materials = matMatch ? matMatch[1].trim() : '';

        // 特性：在 "Specs & Features" 下的各个子标题
        const features = [];
        const featureHeadings = document.querySelectorAll('[class*="specs"] h3, [class*="feature"] h3');
        featureHeadings.forEach(h => {
            const text = h.innerText.trim();
            if (text && !text.includes('Country of Origin') && !text.includes('Weight')) {
                features.push(text);
            }
        });
        data.features = features;

        // 认证
        const certs = [];
        if (text.includes('Fair Trade Certified')) certs.push('Fair Trade Certified');
        if (text.includes('bluesign')) certs.push('bluesign approved');
        data.certifications = certs;

        // 洗涤说明
        const careMatch = text.match(/Care Instructions\\s*([^#]+)/);
        if (careMatch) {
            data.care_instructions = careMatch[1]
                .split(',')
                .map(s => s.trim())
                .filter(s => s.length > 0 && s.length < 50);
        } else {
            data.care_instructions = [];
        }

        // 产品描述
        const descEl = document.querySelector('[class*="product-description"], [class*="product-details"]');
        data.description = descEl ? descEl.innerText.trim() : '';

        return data;
    }''', style_number)
```

如果 `page.evaluate()` 提取不完整（Patagonia 页面结构可能变化），可以用 `page.content()` 获取完整 HTML 作为备选，然后用正则/文本解析提取。

### 第二步：用同一 Playwright 会话抓取全部颜色的高清图片

在第一步加载页面后，复用同一个浏览器会话抓取图片。核心是三个技术的组合：

#### 技术 A：有头浏览器 + 反检测

```python
from playwright.async_api import async_playwright
import asyncio, os, re

async def launch_browser():
    p = await async_playwright().start()
    browser = await p.chromium.launch(
        headless=False,  # 必须有头，headless 会被检测
        args=['--disable-blink-features=AutomationControlled']
    )
    context = await browser.new_context(
        user_agent='Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/125.0.0.0 Safari/537.36',
        viewport={'width': 1920, 'height': 1080}
    )
    page = await context.new_page()
    await page.add_init_script('Object.defineProperty(navigator, "webdriver", {get: () => undefined});')
    return p, browser, context, page
```

#### 技术 B：route 拦截升级图片分辨率

图片默认以 `sw=512` 缩略图加载，通过路由拦截替换为 `sw=1400`：

```python
async def upgrade_image(route):
    url = route.request.url
    if 'BDJB_PRD' in url and 'sw=' in url:
        new_url = re.sub(r'sw=\d+', 'sw=1400', url)
        new_url = re.sub(r'sh=\d+', 'sh=1400', new_url)
        await route.continue_(url=new_url)
    else:
        await route.continue_()

await page.route('**/dw/image/v2/BDJB_PRD/**', upgrade_image)
```

#### 技术 C：response 事件捕获真实图片数据

直接下载图片 URL 返回 404，必须在浏览器加载时拦截响应体：

```python
captured = {}

async def handle_response(response):
    url = response.url
    if 'BDJB_PRD' in url and 'hi-res' in url:
        try:
            body = await response.body()
            if len(body) > 5000:  # 过滤掉挡板页（通常 ~14KB）
                match = re.search(r'/([^/]+)\.jpg', url)
                if match:
                    fname = match.group(1)
                    # 同名文件保留更大的版本（更高分辨率）
                    if fname not in captured or len(body) > len(captured[fname]):
                        captured[fname] = body
        except:
            pass

page.on('response', lambda r: asyncio.ensure_future(handle_response(r)))
```

#### 完整图片抓取脚本（支持多颜色）

Patagonia 产品通常有多个颜色变体，每个颜色有独立的图片集。必须遍历所有颜色才能拿到完整图片。

```python
async def capture_all_images(product_url, style_number):
    """
    product_url: 产品页面 URL（任意颜色变体即可）
    style_number: 款式编号，如 "44937"，用作存储目录名
    """
    output_dir = f'scraped_data/{style_number}/images'
    os.makedirs(output_dir, exist_ok=True)

    # --- 第一阶段：加载原始页面，捕获第一个颜色的图片 + 发现所有颜色 ---
    p, browser, context, page = await launch_browser()

    # 注册 response handler（必须在 goto 之前）
    all_captured = {}
    async def on_response(response):
        url = response.url
        if 'BDJB_PRD' in url and 'hi-res' in url and style_number in url:
            try:
                body = await response.body()
                if len(body) > 5000:
                    match = re.search(r'/([^/]+)\.jpg', url)
                    if match:
                        fname = match.group(1)
                        if fname not in all_captured or len(body) > len(all_captured[fname]):
                            all_captured[fname] = body
            except:
                pass
    page.on('response', lambda r: asyncio.ensure_future(on_response(r)))

    # 注册 route 拦截（必须在 goto 之前）
    async def upgrade(route):
        url = route.request.url
        if 'BDJB_PRD' in url and 'sw=' in url:
            new_url = re.sub(r'sw=\d+', 'sw=1400', url)
            new_url = re.sub(r'sh=\d+', 'sh=1400', new_url)
            await route.continue_(url=new_url)
        else:
            await route.continue_()
    await page.route('**/dw/image/v2/BDJB_PRD/**', upgrade)

    # 加载原始页面，捕获第一个颜色的图片
    await page.goto(product_url, wait_until='domcontentloaded', timeout=90000)
    await page.wait_for_timeout(12000)

    # --- 提取所有颜色变体代码 ---
    color_codes = await page.evaluate('''() => {
        const codes = new Set();

        // 方法1: 从颜色选择器/色块中提取
        const swatches = document.querySelectorAll(
            '[class*="color-swatch"], [class*="color-attribute"], [data-color], [aria-label*="color"]'
        );
        swatches.forEach(el => {
            const code = el.getAttribute('data-color') ||
                         el.getAttribute('data-attr-value') ||
                         el.getAttribute('href')?.match(/color=([A-Z0-9]+)/)?.[1];
            if (code && code.length <= 10) codes.add(code);
        });

        // 方法2: 从 URL 参数中提取当前颜色
        try {
            const pid = document.querySelector('[data-pid]');
            if (pid) {
                const urlColor = new URL(window.location.href).searchParams.get(
                    'dwvar_' + pid.getAttribute('data-pid') + '_color'
                );
                if (urlColor) codes.add(urlColor);
            }
        } catch(e) {}

        // 方法3: 从页面文本中匹配颜色代码（XXXX | Style No. 格式）
        const bodyText = document.body.innerText;
        const colorMatches = bodyText.matchAll(/\\b([A-Z0-9]{4})\\s*\\|\\s*Style No\\./g);
        for (const m of colorMatches) codes.add(m[1]);

        return [...codes];
    }''') or []

    # 确保当前 URL 中的颜色在列表首位（已抓过了）
    current_color_match = re.search(r'color=([A-Z0-9]+)', product_url)
    if current_color_match:
        cc = current_color_match.group(1)
        color_codes = [cc] + [c for c in color_codes if c != cc]

    print(f'Found {len(color_codes)} color variants: {color_codes}')

    # --- 第二阶段：逐个加载其他颜色的页面 ---
    # 构造干净的 base_url，去掉尾部残留的 ? 或 &
    base_url = re.sub(r'[?&]dwvar_\w+_color=[A-Z0-9]+', '', product_url)
    base_url = base_url.rstrip('?&')

    for color_code in color_codes[1:]:  # 跳过第一个（已经抓过了）
        variant_url = f'{base_url}?dwvar_{style_number}_color={color_code}'
        print(f'Loading color variant: {color_code}')

        try:
            await page.goto(variant_url, wait_until='domcontentloaded', timeout=60000)
            await page.wait_for_timeout(10000)

            new_count = sum(1 for f in all_captured if f'_{color_code}_' in f or f == f'{style_number}_{color_code}')
            print(f'  {color_code}: captured {new_count} images')
        except Exception as e:
            print(f'  Error loading {color_code}: {e}')

    # --- 第三阶段：保存所有图片 ---
    saved = 0
    for fname, body in all_captured.items():
        path = os.path.join(output_dir, f'{fname}.jpg')
        if os.path.exists(path) and os.path.getsize(path) >= len(body):
            continue
        with open(path, 'wb') as f:
            f.write(body)
        saved += 1

    print(f'Total: {len(all_captured)} images ({saved} new), {len(color_codes)} colors')

    await browser.close()
    await p.stop()
    return list(all_captured.keys()), color_codes
```

### 第三步：保存产品 JSON 数据

将第一步提取的产品信息保存为 JSON：

```python
import json

def save_product_json(product_data, style_number):
    """保存产品数据为 JSON"""
    output_path = f'scraped_data/{style_number}/product.json'
    os.makedirs(f'scraped_data/{style_number}', exist_ok=True)
    with open(output_path, 'w', encoding='utf-8') as f:
        json.dump(product_data, f, ensure_ascii=False, indent=2)
```

### 第四步：生成中文 Word 文档

```python
from docx import Document
from docx.shared import Inches, Pt
from docx.oxml.ns import qn
from docx.enum.text import WD_ALIGN_PARAGRAPH
import os

def set_cn_font(run, font_name='微软雅黑'):
    """统一设置中文字体"""
    run.font.name = font_name
    run.element.rPr.rFonts.set(qn('w:eastAsia'), font_name)

def generate_docx(product_data, style_number):
    """
    product_data: 包含以下字段的字典
        - cn_title: 中文标题
        - basic_info: [(标签, 值), ...] 基本信息列表
        - description: 商品描述（中文）
        - features: [str, ...] 产品特性列表
        - materials: 材质信息（中文）
        - certifications: [str, ...] 认证列表
        - care_instructions: [str, ...] 洗涤说明列表
        - images: [(文件名, 中文描述), ...] 图片列表
        - source_url: 原始链接
    style_number: 款式编号，如 "44937"
    """
    image_dir = f'scraped_data/{style_number}/images'
    output_path = f'scraped_data/{style_number}/Patagonia_{style_number}_商品信息.docx'

    doc = Document()

    # 设置默认字体
    style = doc.styles['Normal']
    style.font.name = '微软雅黑'
    style.font.size = Pt(11)
    style.element.rPr.rFonts.set(qn('w:eastAsia'), '微软雅黑')

    # 标题
    title = doc.add_heading('', level=1)
    run = title.add_run(product_data['cn_title'])
    set_cn_font(run)
    run.font.size = Pt(18)
    title.alignment = WD_ALIGN_PARAGRAPH.CENTER

    # 基本信息
    doc.add_heading('基本信息', level=2)
    for label, value in product_data['basic_info']:
        p = doc.add_paragraph()
        run_label = p.add_run(f'{label}：')
        run_label.bold = True
        set_cn_font(run_label)
        run_val = p.add_run(value)
        set_cn_font(run_val)

    # 产品图片（多颜色时按颜色分组显示）
    images = product_data.get('images', [])
    if images:
        # 按颜色分组
        color_groups = {}
        for fname, desc in images:
            # 从文件名提取颜色代码：{style}_{COLOR}_{suffix} 或 {style}_{COLOR}
            parts = fname.replace(f'{style_number}_', '').split('_')
            color = parts[0] if parts else 'OTHER'
            if color == '000':
                color = 'LIFESTYLE'  # 生活场景图归为一组
            if color not in color_groups:
                color_groups[color] = []
            color_groups[color].append((fname, desc))

        total = sum(len(imgs) for imgs in color_groups.values())
        doc.add_heading(f'产品图片（共{total}张）', level=2)

        for color, imgs in color_groups.items():
            if len(color_groups) > 1:
                p = doc.add_paragraph()
                run = p.add_run(f'— 颜色：{color} —')
                set_cn_font(run)
                run.bold = True
                p.alignment = WD_ALIGN_PARAGRAPH.CENTER

            for fname, desc in imgs:
                img_path = os.path.join(image_dir, f'{fname}.jpg')
                if os.path.exists(img_path):
                    p = doc.add_paragraph()
                    p.alignment = WD_ALIGN_PARAGRAPH.CENTER
                    run = p.add_run(f'【{desc}】')
                    set_cn_font(run)
                    run.font.size = Pt(9)

                    p = doc.add_paragraph()
                    p.alignment = WD_ALIGN_PARAGRAPH.CENTER
                    run = p.add_run()
                    # 多图时缩小尺寸，避免文档过大
                    run.add_picture(img_path, width=Inches(2.8))

    # 商品描述
    if product_data.get('description'):
        doc.add_heading('商品描述', level=2)
        p = doc.add_paragraph(product_data['description'])
        set_cn_font(p.runs[0] if p.runs else p.add_run())

    # 产品特性
    if product_data.get('features'):
        doc.add_heading('产品特性', level=2)
        for f in product_data['features']:
            p = doc.add_paragraph(f, style='List Bullet')
            for run in p.runs:
                set_cn_font(run)

    # 材质信息
    if product_data.get('materials'):
        doc.add_heading('材质信息', level=2)
        p = doc.add_paragraph(product_data['materials'])
        set_cn_font(p.runs[0] if p.runs else p.add_run())

    # 认证信息
    if product_data.get('certifications'):
        doc.add_heading('认证信息', level=2)
        for c in product_data['certifications']:
            p = doc.add_paragraph(c, style='List Bullet')
            for run in p.runs:
                set_cn_font(run)

    # 洗涤说明
    if product_data.get('care_instructions'):
        doc.add_heading('洗涤说明', level=2)
        for c in product_data['care_instructions']:
            p = doc.add_paragraph(c, style='List Bullet')
            for run in p.runs:
                set_cn_font(run)

    # 数据来源
    if product_data.get('source_url'):
        doc.add_heading('数据来源', level=2)
        p = doc.add_paragraph(product_data['source_url'])
        set_cn_font(p.runs[0] if p.runs else p.add_run())

    doc.save(output_path)
    print(f'Word document saved: {output_path} ({os.path.getsize(output_path)//1024}KB)')
```

## 图片文件名含义对照

Patagonia 图片命名规则（`{style}_{color}_{type}.jpg`）：

| 文件名后缀 | 含义 |
|------------|------|
| （无后缀） | 主图 - 产品平铺 |
| `_GNL1` ~ `_GNL4` | 模特展示图（General） |
| `_CDD1` ~ `_CDD2` | 颜色细节/对比图（Color Detail） |
| `_ALTFRONT` | 正面展示 |
| `_ALTGNLHOOD` | 帽子细节 |
| `_ALTGNLBUTTON` | 纽扣细节 |
| `_ALTGNLPKT` | 口袋细节 |
| `_ALTGNLLOOP` | 挂环细节 |
| `_000_LIFESTYLE1` ~ `4` | 生活场景图（跨颜色共用） |

**多颜色说明：**
- 同一产品的不同颜色各自有独立的产品图和细节图
- 生活场景图（`_000_LIFESTYLE`）通常是跨颜色共用的
- 不同颜色的图片数量可能不同（主力色图片多，次色可能只有 2-3 张）
- 抓取时必须遍历页面上的所有颜色变体

## 已知限制

1. **Playwright 超时** — `networkidle` 经常超时，用 `domcontentloaded` + 显式等待替代
2. **SSL 证书** — Windows 环境下 requests 需 `verify=False`
3. **图片尺寸** — `sw=1400` 是实测可获取的最大稳定分辨率，`sw=1920` 有时不返回
4. **页面结构变化** — Patagonia 定期更新前端，选择器可能失效
5. **视频** — 最后一张通常是产品视频缩略图（`i.ytimg.com`），不是图片
6. **颜色发现** — 依赖页面 DOM 结构提取颜色代码，Patagonia 改版可能导致提取失败

## 失败方案记录（不要用）

| 方案 | 结果 | 原因 |
|------|------|------|
| 直接 requests.get 页面 | 返回挡板页 | 浏览器指纹检测 |
| Playwright headless | 返回挡板页 | headless 被识别 |
| 直接 requests.get 图片 URL | 404 | CDN 防盗链 |
| fetch() API 下载图片 | 404 | CDN 防盗链 |
| context.request.get 下载图片 | 返回挡板页 | 非浏览器发起请求 |
| 点击轮播图触发懒加载 | 失败 | 图片 URL 在 HTML 中但被 1x1 占位 |
