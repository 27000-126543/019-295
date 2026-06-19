import sys
import argparse
from rich.console import Console
from rich.table import Table
from rich.panel import Panel
from rich.text import Text
from rich.prompt import Prompt
from data_source import (
    generate_brand_volume,
    detect_anomalies,
    generate_topics,
    generate_daily_brief,
)

console = Console()


def _sentiment_color(sentiment: str) -> str:
    return {"positive": "green", "negative": "red", "neutral": "yellow"}.get(sentiment, "white")


def _sentiment_label(sentiment: str) -> str:
    return {"positive": "正面", "negative": "负面", "neutral": "中性"}.get(sentiment, sentiment)


def print_volume_report(project_name: str, brand_words, competitor_words):
    console.print(Panel.fit(f"[bold cyan]{project_name}[/bold cyan] — 近24小时声量巡检", border_style="cyan"))
    data = generate_brand_volume(project_name, brand_words, competitor_words)
    anomalies = detect_anomalies(data)

    table = Table(show_header=True, header_style="bold magenta")
    table.add_column("品牌", style="bold")
    table.add_column("类型", justify="center")
    table.add_column("今日声量", justify="right")
    table.add_column("昨日声量", justify="right")
    table.add_column("环比", justify="right")
    table.add_column("负面", justify="right", style="red")
    table.add_column("最活跃平台", justify="center")

    for item in data:
        change_color = "green" if item["change_pct"] >= 0 else "red"
        sign = "+" if item["change_pct"] >= 0 else ""
        type_label = "[yellow]竞品[/yellow]" if item["is_competitor"] else "[cyan]自有[/cyan]"
        table.add_row(
            item["name"],
            type_label,
            str(item["today_vol"]),
            str(item["yesterday_vol"]),
            f"[{change_color}]{sign}{item['change_pct']}%[/{change_color}]",
            str(item["negative_count"]),
            item["most_active_platform"],
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

    return data, anomalies


def print_topics(project_name: str, brand_name: str):
    topics = generate_topics(project_name, brand_name)
    if not topics:
        console.print(f"[yellow]未找到 {brand_name} 的话题数据[/yellow]")
        return

    console.print(Panel.fit(f"[bold cyan]{brand_name}[/bold cyan] — 热门话题 TOP 10", border_style="cyan"))
    for idx, t in enumerate(topics, 1):
        color = _sentiment_color(t["sentiment"])
        label = _sentiment_label(t["sentiment"])
        header = Text.assemble(
            (f"{idx:>2}. ", "bold white"),
            (f"#{t['topic']} ", f"bold {color}"),
            (f"({t['mention_count']}条", "white"),
            (f" · {label}", color),
            (f" · {t['platform']})", "white"),
        )
        console.print(header)
        for s in t["samples"]:
            console.print(f"    └─ {s}")
        console.print()


def print_daily_brief(project_name: str, brand_words, volume_data, anomalies):
    brief = generate_daily_brief(project_name, brand_words, volume_data, anomalies)
    console.print()
    console.print(Panel(brief, title="📋 日报简报（可复制到工作群）", border_style="green", expand=False))
    console.print("[dim]（以上内容已可直接复制粘贴）[/dim]")
    return brief


def interactive_mode():
    console.print(Panel.fit("[bold cyan]品牌声量巡检工具[/bold cyan]\n输入项目信息开始巡检，或输入 help 查看命令", border_style="cyan"))
    project_name = ""
    brand_words = []
    competitor_words = []
    last_volume = None
    last_anomalies = None

    while True:
        try:
            cmd = Prompt.ask("\n[bold]>[/bold]").strip()
        except (EOFError, KeyboardInterrupt):
            console.print("\n[dim]再见[/dim]")
            break

        if not cmd:
            continue
        if cmd.lower() in ("quit", "exit", "q"):
            console.print("[dim]再见[/dim]")
            break
        if cmd.lower() == "help":
            console.print("""
[bold]可用命令：[/bold]
  [cyan]项目 <名称> <自有品牌词>[/cyan]   设置客户项目名和自有品牌（空格/逗号分隔）
  [cyan]竞品 <竞品词列表>[/cyan]          设置竞品词（空格/逗号分隔）
  [cyan]巡检[/cyan]                      执行声量巡检（需先设置项目和竞品）
  [cyan]追问 <品牌名>[/cyan]             查看某品牌的 TOP10 话题
  [cyan]生成日报[/cyan]                  生成可复制的日报简报
  [cyan]状态[/cyan]                      查看当前项目配置
  [cyan]quit/exit[/cyan]                 退出
""")
            continue
        if cmd.lower() == "状态":
            console.print(f"项目名：{project_name or '[yellow]未设置[/yellow]'}")
            console.print(f"自有品牌：{', '.join(brand_words) if brand_words else '[yellow]未设置[/yellow]'}")
            console.print(f"竞品：{', '.join(competitor_words) if competitor_words else '[yellow]未设置[/yellow]'}")
            continue

        if cmd.startswith("项目") or cmd.startswith("project"):
            parts = cmd.split(None, 1)
            if len(parts) < 2:
                console.print("[red]用法：项目 <名称> <自有品牌词1,品牌词2...>[/red]")
                continue
            rest = parts[1].strip()
            tokens = [t for t in rest.replace(",", " ").replace("，", " ").split() if t]
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

        if cmd.startswith("品牌"):
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
            last_volume, last_anomalies = print_volume_report(project_name, brand_words, competitor_words)
            continue

        if cmd.startswith("追问") or cmd.startswith("topic"):
            parts = cmd.split(None, 1)
            if len(parts) < 2:
                console.print("[red]用法：追问 <品牌名>[/red]")
                continue
            target = parts[1].strip()
            if not project_name:
                console.print("[red]请先设置项目名[/red]")
                continue
            print_topics(project_name, target)
            continue

        if cmd == "生成日报" or cmd == "日报" or cmd == "brief":
            if not project_name:
                console.print("[red]请先设置项目并执行巡检[/red]")
                continue
            if last_volume is None:
                console.print("[yellow]未找到上次巡检数据，将自动执行一次巡检...[/yellow]")
                last_volume, last_anomalies = print_volume_report(project_name, brand_words, competitor_words)
            print_daily_brief(project_name, brand_words, last_volume, last_anomalies)
            continue

        console.print(f"[yellow]未知命令：{cmd}，输入 help 查看命令列表[/yellow]")


def main():
    parser = argparse.ArgumentParser(description="品牌声量巡检 CLI 工具")
    parser.add_argument("--project", "-p", help="客户项目名")
    parser.add_argument("--brands", "-b", nargs="+", help="自有品牌词包（空格分隔）")
    parser.add_argument("--competitors", "-c", nargs="+", help="竞品词包（空格分隔）")
    parser.add_argument("--topic", "-t", help="追问某品牌的热门话题")
    parser.add_argument("--brief", action="store_true", help="生成日报简报")
    parser.add_argument("--interactive", "-i", action="store_true", help="进入交互模式")
    args = parser.parse_args()

    if args.interactive or len(sys.argv) == 1:
        interactive_mode()
        return

    if not args.project:
        console.print("[red]缺少 --project 参数[/red]")
        parser.print_help()
        sys.exit(1)

    brand_words = args.brands or []
    competitor_words = args.competitors or []

    volume_data, anomalies = print_volume_report(args.project, brand_words, competitor_words)

    if args.topic:
        console.print()
        print_topics(args.project, args.topic)

    if args.brief:
        print_daily_brief(args.project, brand_words, volume_data, anomalies)


if __name__ == "__main__":
    main()
