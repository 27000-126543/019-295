import sys
import os
import argparse
import datetime
from rich.console import Console
from rich.table import Table
from rich.panel import Panel
from rich.text import Text
from rich.prompt import Prompt
from data_source import (
    generate_brand_volume,
    detect_anomalies,
    generate_topics,
    generate_topic_examples,
    generate_daily_brief,
    generate_summary_brief,
    load_projects_file,
    save_inspection_record,
    list_history,
    load_history_record,
    export_csv,
    export_topics_csv,
    export_brief_text,
    PLATFORMS,
)

console = Console()


def _sentiment_color(sentiment: str) -> str:
    return {"positive": "green", "negative": "red", "neutral": "yellow"}.get(sentiment, "white")


def _sentiment_label(sentiment: str) -> str:
    return {"positive": "正面", "negative": "负面", "neutral": "中性"}.get(sentiment, sentiment)


def _trend_color(trend_label: str) -> str:
    if "升温" in trend_label:
        return "bold red"
    if "降温" in trend_label:
        return "bold blue"
    return "white"


def run_single_inspection(project_name: str, brand_words, competitor_words, save: bool = True):
    if not brand_words and not competitor_words:
        console.print(f"[red]✗ 项目「{project_name}」缺少品牌词包和竞品词包，已跳过[/red]")
        return {"project_name": project_name, "error": "缺少词包", "volume_data": [], "anomalies": [], "brief": ""}
    if not brand_words:
        console.print(f"[yellow]⚠ 项目「{project_name}」未设置自有品牌词，仅展示竞品[/yellow]")
    elif not competitor_words:
        console.print(f"[yellow]⚠ 项目「{project_name}」未设置竞品词，仅展示自有品牌[/yellow]")
    console.print(Panel.fit(f"[bold cyan]{project_name}[/bold cyan] — 近24小时声量巡检", border_style="cyan"))
    data = generate_brand_volume(project_name, brand_words, competitor_words)
    anomalies = detect_anomalies(data)

    table = Table(show_header=True, header_style="bold magenta")
    table.add_column("品牌", style="bold")
    table.add_column("类型", justify="center")
    table.add_column("今日声量", justify="right")
    table.add_column("昨日声量", justify="right")
    table.add_column("环比", justify="right")
    table.add_column("情绪(正/中/负)", justify="center")
    table.add_column("负面占比", justify="right")
    table.add_column("最活跃平台", justify="center")
    table.add_column("近8h趋势", justify="right")

    for item in data:
        change_color = "green" if item["change_pct"] >= 0 else "red"
        sign = "+" if item["change_pct"] >= 0 else ""
        type_label = "[yellow]竞品[/yellow]" if item["is_competitor"] else "[cyan]自有[/cyan]"
        total = max(1, item["today_vol"])
        neg_ratio = round(item["negative_count"] / total * 100, 1)
        neg_color = "red" if neg_ratio >= 20 else ("yellow" if neg_ratio >= 10 else "green")
        sent_text = (
            f"[green]{item['positive_count']}[/green]/"
            f"[yellow]{item['neutral_count']}[/yellow]/"
            f"[red]{item['negative_count']}[/red]"
        )
        trend_sign = "+" if item["recent_trend_pct"] >= 0 else ""
        trend_color = "green" if item["recent_trend_pct"] >= 0 else "red"
        table.add_row(
            item["name"],
            type_label,
            str(item["today_vol"]),
            str(item["yesterday_vol"]),
            f"[{change_color}]{sign}{item['change_pct']}%[/{change_color}]",
            sent_text,
            f"[{neg_color}]{neg_ratio}%[/{neg_color}]",
            item["most_active_platform"],
            f"[{trend_color}]{trend_sign}{item['recent_trend_pct']}%[/{trend_color}]",
        )
    console.print(table)

    if anomalies:
        console.print()
        a_table = Table(title="⚠ 异常增幅品牌", show_header=True, header_style="bold red")
        a_table.add_column("品牌", style="bold")
        a_table.add_column("增幅", justify="right")
        a_table.add_column("今日声量", justify="right")
        a_table.add_column("疑似原因")
        a_table.add_column("复核", justify="center")
        for a in anomalies:
            review = "[bold red]是[/bold red]" if a["needs_review"] else "[green]否[/green]"
            a_table.add_row(a["name"], f"[red]+{a['change_pct']}%[/red]", str(a["today_vol"]), a["likely_reason"], review)
        console.print(a_table)
    else:
        console.print("\n[green]✓ 无异常增幅品牌[/green]")

    brief = generate_daily_brief(project_name, brand_words, data, anomalies)
    return {
        "project_name": project_name,
        "brand_words": list(brand_words),
        "competitor_words": list(competitor_words),
        "volume_data": data,
        "anomalies": anomalies,
        "brief": brief,
        "saved_at": datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
    }


def print_overview(all_results):
    valid = [r for r in all_results if not r.get("error")]
    if not valid:
        return
    console.print()
    console.print(Panel.fit("[bold green]多项目巡检总览[/bold green]", border_style="green"))
    t = Table(show_header=True, header_style="bold magenta")
    t.add_column("项目名", style="bold")
    t.add_column("自有声量", justify="right")
    t.add_column("竞品声量", justify="right")
    t.add_column("总声量", justify="right")
    t.add_column("异常数", justify="right")
    t.add_column("负面数", justify="right", style="red")
    t.add_column("需复核", justify="center")
    t.add_column("领先状态", justify="center")
    total_own = 0
    total_comp = 0
    total_neg = 0
    need_review_count = 0
    for r in valid:
        vol = r["volume_data"]
        own = sum(v["today_vol"] for v in vol if not v["is_competitor"])
        comp = sum(v["today_vol"] for v in vol if v["is_competitor"])
        neg = sum(v["negative_count"] for v in vol)
        anom_count = len(r["anomalies"])
        review_flag = any(a["needs_review"] for a in r["anomalies"]) or neg > 30
        if review_flag:
            need_review_count += 1
        total_own += own
        total_comp += comp
        total_neg += neg
        own_top = max([v for v in vol if not v["is_competitor"]], key=lambda x: x["today_vol"], default=None)
        comp_top = max([v for v in vol if v["is_competitor"]], key=lambda x: x["today_vol"], default=None)
        if own_top and comp_top:
            if own_top["today_vol"] >= comp_top["today_vol"]:
                lead = "[green]自有领先[/green]"
            else:
                lead = f"[red]{comp_top['name']}超[/red]"
        elif own_top:
            lead = "[green]仅自有[/green]"
        elif comp_top:
            lead = "[yellow]仅竞品[/yellow]"
        else:
            lead = "-"
        t.add_row(
            r["project_name"],
            str(own),
            str(comp),
            str(own + comp),
            str(anom_count),
            str(neg),
            "[bold red]是[/bold red]" if review_flag else "[green]否[/green]",
            lead,
        )
    total_row = Text.assemble(("[bold]合计[/bold]", "bold white"))
    t.add_row(
        "[bold]合计[/bold]",
        f"[bold]{total_own}[/bold]",
        f"[bold]{total_comp}[/bold]",
        f"[bold]{total_own + total_comp}[/bold]",
        str(sum(len(r["anomalies"]) for r in valid)),
        f"[bold red]{total_neg}[/bold red]",
        str(need_review_count),
        "",
    )
    console.print(t)


def print_topics(project_name: str, brand_name: str):
    topics = generate_topics(project_name, brand_name)
    if not topics:
        console.print(f"[yellow]未找到 {brand_name} 的话题数据[/yellow]")
        return [], None

    console.print(Panel.fit(f"[bold cyan]{brand_name}[/bold cyan] — 热门话题 TOP 10（输入序号或话题词查看详情 / 返回退出）", border_style="cyan"))
    t = Table(show_header=True, header_style="bold magenta")
    t.add_column("#", justify="right", style="bold")
    t.add_column("话题", style="bold")
    t.add_column("提及量", justify="right")
    t.add_column("情绪占比(正/中/负)", justify="center")
    t.add_column("TOP3平台", justify="left")
    t.add_column("趋势", justify="center")

    for idx, topic in enumerate(topics, 1):
        total = max(1, topic["mention_count"])
        pos_pct = round(topic["positive"] / total * 100)
        neu_pct = round(topic["neutral"] / total * 100)
        neg_pct = 100 - pos_pct - neu_pct
        sent_bar = f"[green]{pos_pct}%[/green]/[yellow]{neu_pct}%[/yellow]/[red]{neg_pct}%[/red]"
        platforms_str = "  ".join(
            f"{name} {pct}%" for name, pct in topic["top_platforms"]
        )
        t.add_row(
            str(idx),
            f"[bold]#{topic['topic']}[/bold]",
            str(topic["mention_count"]),
            sent_bar,
            platforms_str,
            f"[{_trend_color(topic['trend_label'])}]{topic['trend_label']} {topic['trend_pct']:+g}%[/{_trend_color(topic['trend_label'])}]",
        )
    console.print(t)
    console.print()
    for idx, topic in enumerate(topics, 1):
        color = _sentiment_color(topic["sentiment"])
        label = _sentiment_label(topic["sentiment"])
        header = Text.assemble(
            (f"{idx:>2}. ", "bold white"),
            (f"#{topic['topic']} ", f"bold {color}"),
            (f"({topic['mention_count']}条 · {label})", "white"),
        )
        console.print(header)
        for s in topic["samples"]:
            console.print(f"    └─ {s}")
        console.print()
    return topics, brand_name


def print_topic_detail(project_name: str, brand_name: str, topic_name: str, topics_cache):
    target = None
    if topics_cache:
        for tp in topics_cache:
            if tp["topic"] == topic_name:
                target = tp
                break
    if target is None:
        all_topics = generate_topics(project_name, brand_name)
        for tp in all_topics:
            if tp["topic"] == topic_name:
                target = tp
                break
    if target is None:
        console.print(f"[yellow]未找到话题「{topic_name}」，请先追问对应品牌[/yellow]")
        return
    total = max(1, target["mention_count"])
    pos_pct = round(target["positive"] / total * 100)
    neu_pct = round(target["neutral"] / total * 100)
    neg_pct = 100 - pos_pct - neu_pct
    console.print(Panel.fit(
        f"[bold]#{target['topic']}[/bold] · {brand_name} · {target['mention_count']}条\n"
        f"情绪: [green]正面{pos_pct}%[/green] / [yellow]中性{neu_pct}%[/yellow] / [red]负面{neg_pct}%[/red]  |  "
        f"趋势: [{_trend_color(target['trend_label'])}]{target['trend_label']} {target['trend_pct']:+g}%[/{_trend_color(target['trend_label'])}]",
        border_style="magenta",
    ))
    platforms_str = "  ".join(f"{name} {pct}%" for name, pct in target["top_platforms"])
    console.print(f"主要平台：{platforms_str}\n")
    examples = generate_topic_examples(project_name, brand_name, target["topic"], 10)
    t = Table(show_header=True, header_style="bold magenta")
    t.add_column("#", justify="right")
    t.add_column("情绪", justify="center")
    t.add_column("平台", justify="center")
    t.add_column("用户", justify="left")
    t.add_column("原文", overflow="fold")
    t.add_column("赞/评", justify="right")
    t.add_column("发布", justify="right")
    for idx, ex in enumerate(examples, 1):
        label = _sentiment_label(ex["sentiment"])
        color = _sentiment_color(ex["sentiment"])
        t.add_row(
            str(idx),
            f"[{color}]{label}[/{color}]",
            ex["platform"],
            f"[dim]{ex['author']}[/dim]",
            ex["text"],
            f"👍{ex['likes']} 💬{ex['comments']}",
            f"{ex['hours_ago']}h前",
        )
    console.print(t)


def print_brief_panel(brief_text: str, label: str = "日报简报（可复制到工作群）"):
    console.print()
    if not brief_text:
        console.print(Panel("[yellow]⚠ 词包不完整，未生成简报（需同时设置自有品牌词和竞品词）[/yellow]", title=label, border_style="yellow", expand=False))
        return
    console.print(Panel(brief_text, title=f"📋 {label}", border_style="green", expand=False))
    console.print("[dim]（以上内容已可直接复制粘贴）[/dim]")


HELP_TEXT = """
[bold]可用命令：[/bold]
[cyan]━━ 基础设置 ━━[/cyan]
  项目 <名称> <自有品牌词...>   设置客户项目名和自有品牌（空格/逗号分隔）
  品牌 <词1 词2 ...>            补充/修改自有品牌词
  竞品 <词1 词2 ...>            设置竞品词包
  状态                          查看当前项目配置
[cyan]━━ 巡检执行 ━━[/cyan]
  巡检                          执行当前项目的声量巡检
  批量 <清单文件.json>          从JSON文件批量读取多个项目并巡检
[cyan]━━ 舆情分析 ━━[/cyan]
  追问 <品牌名>                 查看某品牌 TOP10 话题（情绪、平台、趋势）
  详情 <序号|话题词>            在追问后下钻查看该话题 10 条原文详情
  返回                          退出话题详情视图
[cyan]━━ 日报与导出 ━━[/cyan]
  生成日报                      当前项目日报（要求品牌词和竞品词齐全）
  汇总日报                      最近一次批量巡检的汇总日报
  导出 csv                      导出最近一次巡检的声量数据为 CSV
  导出 日报 <标签>              导出最近生成的简报文本为 TXT
  导出 话题 <项目> <品牌>       导出话题分析 CSV
[cyan]━━ 历史记录 ━━[/cyan]
  历史                          查看最近 20 次巡检记录
  历史 <序号>                   打开第 N 条历史记录并重播
  保存                          手动保存当前巡检到历史
[cyan]━━ 系统 ━━[/cyan]
  help                          查看本帮助
  quit/exit/q                   退出
"""


def interactive_mode():
    console.print(Panel.fit(
        "[bold cyan]品牌声量巡检工具 v2[/bold cyan]\n"
        "早会批量巡检 · 舆情追问下钻 · 日报生成导出 · 历史记录归档\n"
        "输入 help 查看全部命令，或直接开始",
        border_style="cyan",
    ))
    project_name = ""
    brand_words = []
    competitor_words = []
    last_results = []
    last_single = None
    last_topics = None
    last_topics_brand = None
    last_brief_text = ""
    last_summary_brief = ""

    while True:
        try:
            raw = Prompt.ask("\n[bold]>[/bold]")
        except (EOFError, KeyboardInterrupt):
            console.print("\n[dim]再见[/dim]")
            break
        cmd = raw.strip()
        if not cmd:
            continue
        lower = cmd.lower()
        if lower in ("quit", "exit", "q"):
            console.print("[dim]再见[/dim]")
            break
        if lower == "help":
            console.print(HELP_TEXT)
            continue
        if lower == "状态":
            console.print(f"项目名：{project_name or '[yellow]未设置[/yellow]'}")
            console.print(f"自有品牌：{', '.join(brand_words) if brand_words else '[yellow]未设置[/yellow]'}")
            console.print(f"竞品：{', '.join(competitor_words) if competitor_words else '[yellow]未设置[/yellow]'}")
            console.print(f"上次巡检：{'已缓存 ' + str(len(last_results)) + ' 个项目' if last_results else '[dim]无[/dim]'}")
            continue

        if cmd.startswith("项目") or cmd.startswith("project"):
            parts = cmd.split(None, 1)
            if len(parts) < 2:
                console.print("[red]用法：项目 <名称> <自有品牌词1 品牌词2...>[/red]")
                continue
            tokens = [t for t in parts[1].replace(",", " ").replace("，", " ").split() if t]
            if not tokens:
                console.print("[red]请提供项目名和品牌词[/red]")
                continue
            project_name = tokens[0]
            brand_words = tokens[1:] if len(tokens) > 1 else []
            console.print(f"[green]✓ 已设置项目：{project_name}[/green]")
            if brand_words:
                console.print(f"[green]✓ 自有品牌：{', '.join(brand_words)}[/green]")
            else:
                console.print("[yellow]⚠ 未设置自有品牌词，可用 '品牌 <词1 词2>' 补充[/yellow]")
            continue

        if cmd.startswith("品牌") and not cmd.startswith("品牌声量"):
            parts = cmd.split(None, 1)
            if len(parts) < 2:
                console.print("[red]用法：品牌 <词1 词2 ...>[/red]")
                continue
            brand_words = [t for t in parts[1].replace(",", " ").replace("，", " ").split() if t]
            console.print(f"[green]✓ 自有品牌：{', '.join(brand_words)}[/green]")
            continue

        if cmd.startswith("竞品"):
            parts = cmd.split(None, 1)
            if len(parts) < 2:
                console.print("[red]用法：竞品 <词1 词2 ...>[/red]")
                continue
            competitor_words = [t for t in parts[1].replace(",", " ").replace("，", " ").split() if t]
            console.print(f"[green]✓ 竞品：{', '.join(competitor_words)}[/green]")
            continue

        if cmd == "巡检" or cmd == "check":
            if not project_name:
                console.print("[red]请先设置项目：项目 <名称> <自有品牌词>[/red]")
                continue
            if not brand_words and not competitor_words:
                console.print("[red]请至少设置自有品牌或竞品词[/red]")
                continue
            res = run_single_inspection(project_name, brand_words, competitor_words, save=False)
            last_single = res
            last_results = [res]
            try:
                saved = save_inspection_record(f"single_{project_name}", last_results)
                console.print(f"[dim]✓ 已保存至历史记录：{os.path.basename(saved)}[/dim]")
            except Exception as e:
                console.print(f"[yellow]保存历史失败：{e}[/yellow]")
            continue

        if cmd.startswith("批量") or lower.startswith("batch"):
            parts = cmd.split(None, 1)
            path = ""
            if len(parts) >= 2:
                path = parts[1].strip().strip('"').strip("'")
            if not path:
                path = "projects_sample.json"
                console.print(f"[yellow]未指定清单路径，默认使用示例：{path}[/yellow]")
            projects = load_projects_file(path)
            if not projects:
                console.print(f"[red]未从 {path} 读取到任何项目，请检查文件格式[/red]")
                console.print("[dim]格式示例：[{\"name\": \"项目A\", \"brands\": [\"品牌1\"], \"competitors\": [\"竞品1\"]}][/dim]")
                continue
            console.print(f"[green]✓ 读取到 {len(projects)} 个项目，开始巡检...[/green]")
            results = []
            error_count = 0
            for idx, p in enumerate(projects, 1):
                console.print(f"\n[dim]━━ [{idx}/{len(projects)}] {p['name']} ━━[/dim]")
                r = run_single_inspection(p["name"], p["brands"], p["competitors"], save=False)
                results.append(r)
                if r.get("error"):
                    error_count += 1
            print_overview(results)
            last_results = results
            last_single = None
            if error_count > 0:
                console.print(f"[yellow]⚠ {error_count} 个项目因词包缺失被跳过，请补齐后再生成对应日报[/yellow]")
            try:
                saved = save_inspection_record("batch", results)
                console.print(f"[dim]✓ 已保存至历史记录：{os.path.basename(saved)}[/dim]")
            except Exception as e:
                console.print(f"[yellow]保存历史失败：{e}[/yellow]")
            continue

        if cmd.startswith("追问") or cmd.startswith("topic"):
            parts = cmd.split(None, 1)
            if len(parts) < 2:
                console.print("[red]用法：追问 <品牌名>[/red]")
                continue
            target = parts[1].strip()
            if not project_name:
                console.print("[yellow]⚠ 未设置当前项目名，可先用 '项目 <名称> ...' 设置[/yellow]")
                pname_guess = target
            else:
                pname_guess = project_name
            topics, bname = print_topics(pname_guess, target)
            last_topics = topics
            last_topics_brand = bname
            last_topics_project = pname_guess
            continue

        if cmd.startswith("详情") or cmd.startswith("查看"):
            if last_topics is None:
                console.print("[yellow]请先执行「追问 <品牌名>」获取话题列表[/yellow]")
                continue
            parts = cmd.split(None, 1)
            if len(parts) < 2:
                console.print("[red]用法：详情 <序号> 或 详情 <话题词>[/red]")
                continue
            arg = parts[1].strip()
            project_for_detail = locals().get("last_topics_project", project_name or "")
            if arg.isdigit():
                idx = int(arg)
                if 1 <= idx <= len(last_topics):
                    topic_name = last_topics[idx - 1]["topic"]
                else:
                    console.print(f"[red]序号超出范围（1-{len(last_topics)}）[/red]")
                    continue
            else:
                topic_name = arg.lstrip("#")
            print_topic_detail(project_for_detail, last_topics_brand, topic_name, last_topics)
            continue

        if cmd == "返回":
            last_topics = None
            last_topics_brand = None
            console.print("[dim]已退出话题详情视图[/dim]")
            continue

        if cmd == "生成日报" or cmd == "日报" or cmd == "brief":
            if not last_results:
                if not project_name or (not brand_words and not competitor_words):
                    console.print("[red]请先设置项目并执行巡检[/red]")
                    continue
                console.print("[yellow]未找到巡检数据，自动执行一次...[/yellow]")
                res = run_single_inspection(project_name, brand_words, competitor_words, save=False)
                last_results = [res]
                last_single = res
            if len(last_results) == 1:
                r = last_results[0]
                if not r.get("error"):
                    if not r["brand_words"] or not r["competitor_words"]:
                        console.print("[yellow]⚠ 无法生成完整日报：需同时设置自有品牌和竞品词包[/yellow]")
                        console.print("[dim]提示：使用「品牌 <词...>」或「竞品 <词...>」补齐后再巡检[/dim]")
                        last_brief_text = ""
                        continue
                    brief = r.get("brief", "") or generate_daily_brief(r["project_name"], r["brand_words"], r["volume_data"], r["anomalies"])
                    print_brief_panel(brief, f"{r['project_name']} 声量日报")
                    last_brief_text = brief
            else:
                console.print("[yellow]检测到批量巡检结果，默认输出汇总日报；如需单项目请输入「生成日报 <项目名>」[/yellow]")
                sb = generate_summary_brief(last_results)
                print_brief_panel(sb, "全客户汇总日报")
                last_summary_brief = sb
                last_brief_text = sb
            continue

        if cmd.startswith("生成日报") and " " in cmd:
            parts = cmd.split(None, 1)
            target_name = parts[1].strip()
            matched = None
            for r in last_results:
                if r["project_name"] == target_name:
                    matched = r
                    break
            if not matched:
                console.print(f"[red]未找到项目「{target_name}」的巡检记录[/red]")
                continue
            if matched.get("error"):
                console.print(f"[yellow]项目「{target_name}」存在问题：{matched['error']}，无法生成日报[/yellow]")
                continue
            if not matched["brand_words"] or not matched["competitor_words"]:
                console.print(f"[yellow]项目「{target_name}」缺少品牌词或竞品词，无法生成完整日报，请补齐[/yellow]")
                continue
            brief = matched.get("brief", "") or generate_daily_brief(matched["project_name"], matched["brand_words"], matched["volume_data"], matched["anomalies"])
            print_brief_panel(brief, f"{matched['project_name']} 声量日报")
            last_brief_text = brief
            continue

        if cmd == "汇总日报" or cmd == "总日报":
            if not last_results or len(last_results) < 2:
                console.print("[yellow]需要先执行批量巡检（至少2个项目）才能生成汇总日报[/yellow]")
                continue
            sb = generate_summary_brief(last_results)
            print_brief_panel(sb, "全客户声量汇总日报")
            last_summary_brief = sb
            last_brief_text = sb
            continue

        if cmd.startswith("导出"):
            parts = cmd.split(None, 2)
            sub = parts[1].lower() if len(parts) >= 2 else ""
            if sub == "csv":
                if not last_results:
                    console.print("[red]请先执行巡检[/red]")
                    continue
                path = export_csv(last_results)
                console.print(f"[green]✓ CSV 已导出：{path}[/green]")
                continue
            if sub == "日报" or sub == "brief":
                if not last_brief_text and last_results:
                    last_brief_text = generate_summary_brief(last_results) if len(last_results) > 1 else (last_results[0].get("brief", "") if not last_results[0].get("error") else "")
                if not last_brief_text:
                    console.print("[yellow]没有可导出的简报，请先生成日报[/yellow]")
                    continue
                label = parts[2] if len(parts) >= 3 else ("summary_brief" if len(last_results) > 1 else "project_brief")
                path = export_brief_text(last_brief_text, label)
                console.print(f"[green]✓ 简报文本已导出：{path}[/green]")
                continue
            if sub == "话题" or sub == "topic":
                if len(parts) < 3:
                    console.print("[red]用法：导出 话题 <项目名> <品牌名>[/red]")
                    continue
                rest = parts[2].strip()
                rest_tokens = [t for t in rest.replace(",", " ").split() if t]
                if len(rest_tokens) < 2:
                    console.print("[red]用法：导出 话题 <项目名> <品牌名>[/red]")
                    continue
                pname, bname = rest_tokens[0], " ".join(rest_tokens[1:])
                topics = generate_topics(pname, bname)
                path = export_topics_csv(pname, bname, topics)
                console.print(f"[green]✓ 话题分析 CSV 已导出：{path}[/green]")
                continue
            console.print("[yellow]用法：导出 csv | 导出 日报 <标签> | 导出 话题 <项目> <品牌>[/yellow]")
            continue

        if cmd.startswith("历史"):
            parts = cmd.split(None, 1)
            if len(parts) >= 2 and parts[1].strip().isdigit():
                idx = int(parts[1].strip())
                history = list_history(limit=20)
                if idx < 1 or idx > len(history):
                    console.print(f"[red]序号超出范围（1-{len(history)}）[/red]")
                    continue
                item = history[idx - 1]
                record = load_history_record(item["file"])
                if not record:
                    console.print("[red]读取历史记录失败[/red]")
                    continue
                console.print(f"[green]✓ 回放历史记录：{item['datetime']}  {item['batch_id']} ({item['project_count']}个项目)[/green]")
                results = record.get("results", [])
                for r in results:
                    if not r.get("error"):
                        console.print(Panel.fit(f"[bold cyan]{r['project_name']}[/bold cyan] — 历史回放", border_style="cyan"))
                        _render_volume_table_only(r["volume_data"], r["anomalies"])
                print_overview(results)
                last_results = results
                continue
            history = list_history(limit=20)
            if not history:
                console.print("[yellow]暂无历史记录[/yellow]")
                continue
            t = Table(show_header=True, header_style="bold magenta")
            t.add_column("#", justify="right")
            t.add_column("时间")
            t.add_column("批次")
            t.add_column("项目数", justify="right")
            t.add_column("文件名", style="dim")
            for idx, h in enumerate(history, 1):
                t.add_row(str(idx), h["datetime"], h["batch_id"] or "-", str(h["project_count"]), h["file"])
            console.print(t)
            console.print("[dim]使用「历史 <序号>」打开对应记录[/dim]")
            continue

        if cmd == "保存":
            if not last_results:
                console.print("[red]没有可保存的巡检数据[/red]")
                continue
            batch_id = "batch" if len(last_results) > 1 else f"manual_{project_name or 'single'}"
            saved = save_inspection_record(batch_id, last_results)
            console.print(f"[green]✓ 已保存：{os.path.basename(saved)}[/green]")
            continue

        console.print(f"[yellow]未知命令：{cmd}，输入 help 查看命令列表[/yellow]")


def _render_volume_table_only(volume_data, anomalies):
    table = Table(show_header=True, header_style="bold magenta")
    table.add_column("品牌", style="bold")
    table.add_column("类型", justify="center")
    table.add_column("今日", justify="right")
    table.add_column("昨日", justify="right")
    table.add_column("环比", justify="right")
    table.add_column("正/中/负", justify="center")
    table.add_column("负面占比", justify="right")
    table.add_column("TOP平台", justify="center")
    for item in volume_data:
        change_color = "green" if item["change_pct"] >= 0 else "red"
        sign = "+" if item["change_pct"] >= 0 else ""
        type_label = "[yellow]竞品[/yellow]" if item["is_competitor"] else "[cyan]自有[/cyan]"
        total = max(1, item["today_vol"])
        neg_ratio = round(item["negative_count"] / total * 100, 1)
        neg_color = "red" if neg_ratio >= 20 else ("yellow" if neg_ratio >= 10 else "green")
        sent_text = (
            f"[green]{item['positive_count']}[/green]/[yellow]{item['neutral_count']}[/yellow]/[red]{item['negative_count']}[/red]"
        )
        table.add_row(
            item["name"], type_label,
            str(item["today_vol"]), str(item["yesterday_vol"]),
            f"[{change_color}]{sign}{item['change_pct']}%[/{change_color}]",
            sent_text,
            f"[{neg_color}]{neg_ratio}%[/{neg_color}]",
            item["most_active_platform"],
        )
    console.print(table)
    if anomalies:
        a_table = Table(title="⚠ 异常增幅品牌", show_header=True, header_style="bold red")
        a_table.add_column("品牌", style="bold")
        a_table.add_column("增幅", justify="right")
        a_table.add_column("今日", justify="right")
        a_table.add_column("疑似原因")
        a_table.add_column("复核", justify="center")
        for a in anomalies:
            review = "[bold red]是[/bold red]" if a["needs_review"] else "[green]否[/green]"
            a_table.add_row(a["name"], f"[red]+{a['change_pct']}%[/red]", str(a["today_vol"]), a["likely_reason"], review)
        console.print(a_table)


def main():
    parser = argparse.ArgumentParser(description="品牌声量巡检 CLI 工具 v2")
    parser.add_argument("--project", "-p", help="客户项目名")
    parser.add_argument("--brands", "-b", nargs="+", help="自有品牌词包（空格分隔）")
    parser.add_argument("--competitors", "-c", nargs="+", help="竞品词包（空格分隔）")
    parser.add_argument("--batch", metavar="FILE", help="批量巡检：从 JSON 文件读取项目清单")
    parser.add_argument("--topic", "-t", help="追问某品牌的热门话题")
    parser.add_argument("--brief", action="store_true", help="生成日报简报")
    parser.add_argument("--summary-brief", action="store_true", help="批量巡检后输出汇总日报")
    parser.add_argument("--export-csv", metavar="PATH", help="导出 CSV 到指定路径")
    parser.add_argument("--interactive", "-i", action="store_true", help="进入交互模式")
    args = parser.parse_args()

    if args.interactive or (len(sys.argv) == 1 and not args.batch):
        interactive_mode()
        return

    if args.batch:
        projects = load_projects_file(args.batch)
        if not projects:
            console.print(f"[red]无法从 {args.batch} 读取项目清单[/red]")
            sys.exit(1)
        console.print(f"[green]读取到 {len(projects)} 个项目，开始批量巡检...[/green]")
        results = []
        for idx, p in enumerate(projects, 1):
            console.print(f"\n[dim]━━ [{idx}/{len(projects)}] {p['name']} ━━[/dim]")
            r = run_single_inspection(p["name"], p["brands"], p["competitors"])
            results.append(r)
        print_overview(results)
        try:
            saved = save_inspection_record("batch_cli", results)
            console.print(f"[dim]✓ 已保存历史：{os.path.basename(saved)}[/dim]")
        except Exception:
            pass
        if args.export_csv:
            path = export_csv(results, args.export_csv)
            console.print(f"[green]✓ CSV 已导出：{path}[/green]")
        elif True:
            path = export_csv(results)
            console.print(f"[dim]✓ CSV 自动导出：{path}[/dim]")
        if args.brief or args.summary_brief:
            sb = generate_summary_brief(results)
            print_brief_panel(sb, "全客户声量汇总日报")
            bp = export_brief_text(sb, "summary_brief_cli")
            console.print(f"[dim]✓ 汇总日报已导出：{bp}[/dim]")
        return

    if not args.project:
        console.print("[red]缺少 --project 参数，或使用 --batch 批量模式[/red]")
        parser.print_help()
        sys.exit(1)

    brand_words = args.brands or []
    competitor_words = args.competitors or []
    res = run_single_inspection(args.project, brand_words, competitor_words)
    results = [res]

    if args.topic:
        console.print()
        print_topics(args.project, args.topic)

    if args.brief:
        if not brand_words or not competitor_words:
            console.print("[yellow]⚠ 无法生成日报：请同时设置 --brands 和 --competitors[/yellow]")
        else:
            brief = res.get("brief", "") or generate_daily_brief(args.project, brand_words, res["volume_data"], res["anomalies"])
            print_brief_panel(brief, f"{args.project} 声量日报")
            bp = export_brief_text(brief, f"project_{args.project}")
            console.print(f"[dim]✓ 日报已导出：{bp}[/dim]")

    try:
        saved = save_inspection_record(f"cli_{args.project}", results)
        console.print(f"[dim]✓ 已保存历史：{os.path.basename(saved)}[/dim]")
        path = export_csv(results)
        console.print(f"[dim]✓ CSV 导出：{path}[/dim]")
    except Exception:
        pass


if __name__ == "__main__":
    main()
