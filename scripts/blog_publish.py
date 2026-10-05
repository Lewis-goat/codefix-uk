#!/usr/bin/env python3
"""Per-locale nightly blog publisher. Config in blog-config.json next to this file.
Renders bank/*.md (strict md subset) to /blog/ pages inside a static GitHub-Pages
repo (the locale site), updates the blog index, RSS and the site sitemap."""
import os, re, html, glob, json, datetime, urllib.request

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
CFG = json.load(open(os.path.join(ROOT, "blog-config.json")))
LANG, HOST = CFG["lang"], CFG["host"]
EN_BLOG = "https://blog.codefixcoffee.com"
LOCALES = ["fr","de","es","it","pl","nl","pt","hu","cs","ro","sv","tr"]
UI = CFG["ui"]  # {home_title, home_desc, back, footer}

def esc(s): return html.escape(s, quote=False)

def inline(s):
    s = esc(s)
    s = re.sub(r"\[([^\]]+)\]\((https?://[^)\s]+)\)", r'<a href="\2">\1</a>', s)
    s = re.sub(r"\*\*([^*]+)\*\*", r"<strong>\1</strong>", s)
    s = re.sub(r"(?<!\*)\*([^*]+)\*(?!\*)", r"<em>\1</em>", s)
    s = re.sub(r"`([^`]+)`", r"<code>\1</code>", s)
    return s

def render(md):
    out, in_ul, in_ol = [], False, False
    for line in md.splitlines():
        l = line.strip()
        if not l:
            if in_ul: out.append("</ul>"); in_ul = False
            if in_ol: out.append("</ol>"); in_ol = False
            continue
        if l.startswith("### "): out.append(f"<h3>{inline(l[4:])}</h3>"); continue
        if l.startswith("## "): out.append(f"<h2>{inline(l[3:])}</h2>"); continue
        if l.startswith("- "):
            if in_ol: out.append("</ol>"); in_ol = False
            if not in_ul: out.append("<ul>"); in_ul = True
            out.append(f"<li>{inline(l[2:])}</li>"); continue
        m = re.match(r"^(\d+)\.\s+(.*)$", l)
        if m:
            if in_ul: out.append("</ul>"); in_ul = False
            if not in_ol: out.append("<ol>"); in_ol = True
            out.append(f"<li>{inline(m.group(2))}</li>"); continue
        out.append(f"<p>{inline(l)}</p>")
    if in_ul: out.append("</ul>")
    if in_ol: out.append("</ol>")
    return "\n".join(out)

def alt_tags(slug):
    if CFG.get("canonical_to_en"):
        return f'<link rel="canonical" href="{EN_BLOG}/post/{slug}/">', ""
    tags = [f'<link rel="alternate" hreflang="en" href="{EN_BLOG}/post/{slug}/" />']
    for l in LOCALES:
        tags.append(f'<link rel="alternate" hreflang="{l}" href="https://{l}.codefixcoffee.com/blog/{slug}/" />')
    return f'<link rel="canonical" href="{HOST}/blog/{slug}/">', "\n  ".join(tags)

def page(title, body, desc, canonical, alts="", extra_head=""):
    return f"""<!doctype html>
<html lang="{LANG}">
<head>
<meta charset="utf-8"><meta name="viewport" content="width=device-width, initial-scale=1">
<title>{esc(title)}</title>
<meta name="description" content="{esc(desc)}">
{canonical}
{alts}
<link rel="stylesheet" href="/blog/blog.css">
<link rel="alternate" type="application/rss+xml" title="CodeFix Blog" href="/blog/rss.xml">
{extra_head}</head>
<body>
<header class="site"><div class="in"><a class="brand" href="/blog/">☕ CodeFix Blog</a><span><a href="/">{UI['back']}</a></span></div></header>
<main>
{body}
</main>
<footer>{UI['footer']}</footer>
</body></html>"""

def post_meta(src):
    m = re.match(r"^---\ntitle: (.+)\ndescription: (.+)\n---\n(.*)$", src, re.S)
    if not m: raise SystemExit("bad frontmatter")
    return m.group(1).strip(), m.group(2).strip(), m.group(3)

def main():
    bank = sorted(glob.glob(os.path.join(ROOT, "bank", "*.md")))
    if bank:
        src_path = bank[0]
        slug = re.sub(r"^\d+-", "", os.path.splitext(os.path.basename(src_path))[0])
        date = datetime.date.today().isoformat()
        title, desc, body = post_meta(open(src_path).read())
        d = os.path.join(ROOT, "blog", slug)
        os.makedirs(d, exist_ok=True)
        canon, alts = alt_tags(slug)
        open(os.path.join(d, "index.html"), "w").write(
            page(title, f'<h1>{esc(title)}</h1>\n<p class="meta">{date}</p>\n{render(body)}', desc, canon, alts))
        open(os.path.join(d, "date.txt"), "w").write(date)
        os.remove(src_path)
        print(f"published {slug}")
        print(f"::set-output name=title::{title}")
        print(f"::set-output name=url::{HOST}/blog/{slug}/")
    else:
        print("::notice::bank empty"); print("::set-output name=url::"); print("::set-output name=empty::true")
        slug = None
    entries = []
    for p in sorted(glob.glob(os.path.join(ROOT, "blog", "*", "index.html"))):
        s = os.path.dirname(p); sl = os.path.basename(s)
        doc = open(p).read()
        t = re.search(r"<title>(.*?)</title>", doc).group(1)
        de = re.search(r'<meta name="description" content="([^"]*)"', doc).group(1)
        dt = open(os.path.join(s, "date.txt")).read().strip() if os.path.exists(os.path.join(s, "date.txt")) else "2026-10-05"
        entries.append((dt, sl, t, de))
    entries.sort(reverse=True)
    lst = "\n".join(f'<li><a href="/blog/{sl}/">{esc(t)}</a><small>{dt} — {esc(de)}</small></li>' for dt, sl, t, de in entries)
    open(os.path.join(ROOT, "blog", "index.html"), "w").write(
        page(UI["home_title"], f"<h1>{esc(UI['home_title'])}</h1>\n<p class=\"meta\">{esc(UI['home_desc'])}</p>\n<ul class=\"postlist\">\n{lst}\n</ul>",
             UI["home_desc"], f"{HOST}/blog/"))
    items = "\n".join(f"<item><title>{esc(t)}</title><link>{HOST}/blog/{sl}/</link><guid>{HOST}/blog/{sl}/</guid><pubDate>{dt}</pubDate><description>{esc(de)}</description></item>" for dt, sl, t, de in entries[:20])
    open(os.path.join(ROOT, "blog", "rss.xml"), "w").write(
        f'<?xml version="1.0" encoding="UTF-8"?>\n<rss version="2.0"><channel><title>CodeFix Blog</title><link>{HOST}/blog/</link><description>{esc(UI["home_desc"])}</description>\n{items}\n</channel></rss>')
    # merge blog urls into the site sitemap
    sm = os.path.join(ROOT, "sitemap-0.xml")
    add = "".join(f"<url><loc>{HOST}/blog/{sl}/</loc><lastmod>{dt}</lastmod></url>" for dt, sl, t, de in entries)
    add = f"<url><loc>{HOST}/blog/</loc><lastmod>{datetime.date.today()}</lastmod></url>" + add
    if os.path.exists(sm):
        cur = open(sm).read()
        cur = re.sub(r"<url><loc>[^<]*/blog/[^<]*</loc>.*?</url>", "", cur)
        open(sm, "w").write(cur.replace("</urlset>", add + "</urlset>"))
    else:
        open(sm, "w").write(f'<?xml version="1.0" encoding="UTF-8"?>\n<urlset xmlns="http://www.sitemaps.org/schemas/sitemap/0.9">\n{add}\n</urlset>')

if __name__ == "__main__":
    main()
