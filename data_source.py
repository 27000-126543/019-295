import random
import datetime
import json
import os
import csv
from typing import List, Dict, Tuple, Optional

PLATFORMS = ["微博", "小红书", "抖音", "B站", "知乎", "微信公众号", "快手"]

SAMPLE_CONTENTS_POSITIVE = [
    "这款产品真的太好用了，强烈推荐给大家！身边好几个朋友都被我种草了。",
    "用了一个月，效果非常明显，皮肤状态好了很多，会继续回购。",
    "包装很精致，送人也很有面子，收到的朋友都很喜欢。",
    "性价比超高，比同价位的其他品牌好太多，真心建议试试。",
    "客服态度很好，有问题都能及时解决，售后非常安心。",
    "颜值在线，功能也很强大，爱了爱了，必须五星好评。",
    "终于等到新品了！第一时间下单，用了几天果然没让我失望。",
    "已经是第三次购买了，老顾客了，品质一直在线。",
    "出差带着很方便，小小一支不占地方，效果也满意。",
    "被博主种草的，抱着试试的心态，结果超出预期！",
]

SAMPLE_CONTENTS_NEUTRAL = [
    "刚刚入手，等用过一段时间再来评价，先给个四星观望。",
    "有人用过这个牌子吗？想听听大家的真实使用感受。",
    "今天在专柜试了一下，感觉还可以，再对比对比。",
    "新款和旧款对比，大家觉得哪个更好？求建议。",
    "分享一下我做的功课，仅供参考，每个人肤质不一样。",
    "618凑单买的，价格还可以，效果待定。",
    "有姐妹知道这个和XX比哪个更好用吗？纠结中。",
    "看了好多测评，褒贬不一，有点犹豫要不要入。",
    "生产日期是最近的，保质期还有挺久，先囤着。",
    "直播间抢到的，不知道是不是好价，懂的来说说。",
]

SAMPLE_CONTENTS_NEGATIVE = [
    "踩雷了，完全不是宣传的那样，大家别买，浪费钱。",
    "用了两次就过敏了，脸上起了好多小红疹，联系客服也没人理。",
    "质量太差了，用了一周就坏了，退货流程也特别麻烦。",
    "虚假宣传，实际效果和广告差太远，感觉交了智商税。",
    "物流慢得离谱，包装也破了，里面东西都露出来了。",
    "价格虚高，完全不值这个价，同价位有更好的选择。",
    "用完之后爆痘，以为是自己的问题，结果查了好多人都这样。",
    "味道太难闻了，一股刺鼻的香精味，根本用不下去。",
    "买的时候说有赠品，收到货什么都没有，客服扯皮。",
    "用了一周肤色反而暗沉了，不敢再用了，已闲置。",
]

TOPIC_KEYWORDS_POOL = [
    "性价比", "颜值", "包装", "物流", "客服", "质量", "效果", "使用体验",
    "回购", "推荐", "对比", "新款", "活动价", "赠品", "成分", "过敏",
    "假货", "售后", "升级", "联名", "代言人", "开箱", "测评", "平替",
    "爆痘", "暗沉", "香精味", "赠品缺失", "直播间", "凑单", "囤货",
    "生产日期", "专柜试色", "博主种草", "老顾客"
]


def _seed_from_project(project_name: str, extra: int = 0) -> int:
    return (hash(project_name) + extra) % (2**31)


def _split_sentiment_counts(total: int, seed: int) -> Tuple[int, int, int]:
    rng = random.Random(seed)
    pos_ratio = rng.uniform(0.35, 0.70)
    neg_ratio = rng.uniform(0.05, 0.25)
    neu_ratio = max(0.0, 1.0 - pos_ratio - neg_ratio)
    s = pos_ratio + neg_ratio + neu_ratio
    pos = int(total * pos_ratio / s)
    neg = int(total * neg_ratio / s)
    neu = total - pos - neg
    return max(0, pos), max(0, neu), max(0, neg)


def generate_brand_volume(project_name: str, brand_words: List[str], competitor_words: List[str]) -> List[Dict]:
    random.seed(_seed_from_project(project_name) + datetime.datetime.now().hour)
    all_brands = brand_words + competitor_words
    result = []
    for brand in all_brands:
        base = random.randint(80, 800)
        change_pct = round(random.uniform(-30, 85), 1)
        yesterday = max(20, int(base / (1 + change_pct / 100)))
        today = base
        platform_counts = {}
        for p in PLATFORMS:
            platform_counts[p] = random.randint(0, max(1, int(base / 2.5)))
        most_active = max(platform_counts, key=platform_counts.get)
        is_competitor = brand in competitor_words
        pos, neu, neg = _split_sentiment_counts(today, hash(brand) % (2**31))
        hourly = []
        running = 0
        for h in range(24):
            hour_vol = max(0, int(today / 24 * random.uniform(0.3, 2.0)))
            running += hour_vol
            hourly.append(hour_vol)
        total_h = sum(hourly) or 1
        scale = today / total_h
        hourly = [int(h * scale) for h in hourly]
        last8 = sum(hourly[-8:])
        prev8 = sum(hourly[-16:-8])
        if prev8 > 0:
            trend_pct = round((last8 - prev8) / prev8 * 100, 1)
        else:
            trend_pct = 0.0
        result.append({
            "name": brand,
            "is_competitor": is_competitor,
            "today_vol": today,
            "yesterday_vol": yesterday,
            "change_pct": change_pct,
            "negative_count": neg,
            "positive_count": pos,
            "neutral_count": neu,
            "most_active_platform": most_active,
            "platform_counts": platform_counts,
            "hourly_volume": hourly,
            "recent_trend_pct": trend_pct,
        })
    result.sort(key=lambda x: x["today_vol"], reverse=True)
    return result


def detect_anomalies(volume_data: List[Dict]) -> List[Dict]:
    anomalies = []
    reasons = [
        "新品发布/活动上线", "KOL集中投放", "热搜话题带动",
        "促销活动刺激", "竞品事件溢出", "明星代言官宣",
        "负面舆情发酵", "直播专场带货"
    ]
    for item in volume_data:
        if item["change_pct"] >= 40:
            rng = random.Random(hash(item["name"]) % (2**31))
            anomalies.append({
                "name": item["name"],
                "change_pct": item["change_pct"],
                "today_vol": item["today_vol"],
                "likely_reason": rng.choice(reasons),
                "needs_review": item["change_pct"] >= 65,
            })
    anomalies.sort(key=lambda x: x["change_pct"], reverse=True)
    return anomalies


def generate_topics(project_name: str, brand_name: str, count: int = 10) -> List[Dict]:
    seed = _seed_from_project(project_name) + hash(brand_name)
    rng = random.Random(seed % (2**31))
    topics = rng.sample(TOPIC_KEYWORDS_POOL, min(count, len(TOPIC_KEYWORDS_POOL)))
    result = []
    for topic in topics:
        mention_count = rng.randint(15, 220)
        pos, neu, neg = _split_sentiment_counts(mention_count, hash(topic) + seed)
        platform_counts = {}
        for p in PLATFORMS:
            platform_counts[p] = rng.randint(0, max(1, int(mention_count / 3)))
        total_p = sum(platform_counts.values()) or 1
        platform_pct = {p: round(v / total_p * 100, 1) for p, v in platform_counts.items()}
        top_platforms = sorted(platform_pct.items(), key=lambda x: x[1], reverse=True)[:3]
        trend_val = round(rng.uniform(-25, 60), 1)
        if trend_val >= 20:
            trend_label = "🔥升温"
        elif trend_val <= -10:
            trend_label = "📉降温"
        else:
            trend_label = "➡️平稳"
        dominant_sentiment = "positive" if pos >= neu and pos >= neg else ("negative" if neg >= neu else "neutral")
        if dominant_sentiment == "positive":
            pool = SAMPLE_CONTENTS_POSITIVE
        elif dominant_sentiment == "negative":
            pool = SAMPLE_CONTENTS_NEGATIVE
        else:
            pool = SAMPLE_CONTENTS_NEUTRAL
        samples = rng.sample(pool, min(2, len(pool)))
        result.append({
            "topic": topic,
            "mention_count": mention_count,
            "positive": pos,
            "neutral": neu,
            "negative": neg,
            "sentiment": dominant_sentiment,
            "platform_pct": platform_pct,
            "top_platforms": top_platforms,
            "trend_pct": trend_val,
            "trend_label": trend_label,
            "samples": samples,
        })
    result.sort(key=lambda x: x["mention_count"], reverse=True)
    return result


def generate_topic_examples(project_name: str, brand_name: str, topic: str, count: int = 10) -> List[Dict]:
    seed = _seed_from_project(project_name) + hash(brand_name) + hash(topic)
    rng = random.Random(seed % (2**31))
    sentiment_weights = [
        (SAMPLE_CONTENTS_POSITIVE, 0.45, "positive", "green"),
        (SAMPLE_CONTENTS_NEUTRAL, 0.35, "neutral", "yellow"),
        (SAMPLE_CONTENTS_NEGATIVE, 0.20, "negative", "red"),
    ]
    examples = []
    for i in range(count):
        r = rng.random()
        acc = 0
        chosen_pool = None
        chosen_sent = None
        chosen_tag = None
        for pool, w, sent, tag in sentiment_weights:
            acc += w
            if r <= acc:
                chosen_pool = pool
                chosen_sent = sent
                chosen_tag = tag
                break
        if chosen_pool is None:
            chosen_pool, chosen_sent, chosen_tag = sentiment_weights[0][:3]
        text = rng.choice(chosen_pool)
        platform = rng.choice(PLATFORMS)
        likes = rng.randint(2, 5000)
        comments = rng.randint(0, int(likes / 3))
        hours_ago = rng.randint(0, 23)
        author_id = "@" + "".join(rng.choices("abcdefghijklmnopqrstuvwxyz0123456789", k=8))
        examples.append({
            "text": text,
            "sentiment": chosen_sent,
            "tag": chosen_tag,
            "platform": platform,
            "likes": likes,
            "comments": comments,
            "author": author_id,
            "hours_ago": hours_ago,
        })
    examples.sort(key=lambda x: x["likes"] + x["comments"] * 2, reverse=True)
    return examples


def generate_daily_brief(project_name: str, brand_words: List[str], volume_data: List[Dict], anomalies: List[Dict]) -> str:
    if not brand_words or not volume_data:
        return ""
    own_brands = [v for v in volume_data if not v["is_competitor"]]
    comp_brands = [v for v in volume_data if v["is_competitor"]]
    if not own_brands or not comp_brands:
        return ""
    own_total = sum(v["today_vol"] for v in own_brands)
    comp_total = sum(v["today_vol"] for v in comp_brands)
    top_own = max(own_brands, key=lambda x: x["today_vol"]) if own_brands else None
    top_comp = max(comp_brands, key=lambda x: x["today_vol"]) if comp_brands else None
    lines = []
    lines.append(f"【{project_name}声量日报】")
    date_str = datetime.datetime.now().strftime("%m月%d日")
    lines.append(f"巡检日期：{date_str}")
    lines.append(f"近24h总声量：自有品牌 {own_total} | 竞品 {comp_total}")
    if top_own and top_comp:
        diff = top_own["today_vol"] - top_comp["today_vol"]
        if diff >= 0:
            lines.append(f"领先：自有 {top_own['name']}（{top_own['today_vol']}）领先 {top_comp['name']}（{top_comp['today_vol']}）{diff}条")
        else:
            lines.append(f"注意：竞品 {top_comp['name']}（{top_comp['today_vol']}）超过自有 {top_own['name']}（{top_own['today_vol']}）{-diff}条，主要活跃平台：{top_comp['most_active_platform']}")
    elif top_own and not comp_brands:
        lines.append(f"自有声量TOP：{top_own['name']}（{top_own['today_vol']}）")
    elif top_comp and not own_brands:
        lines.append(f"竞品声量TOP：{top_comp['name']}（{top_comp['today_vol']}）")
    if anomalies:
        lines.append("异常增幅品牌：")
        for a in anomalies:
            tag = "⚠需人工复核" if a["needs_review"] else ""
            lines.append(f"  • {a['name']} +{a['change_pct']}%（{a['today_vol']}条）— 疑似{a['likely_reason']} {tag}")
    else:
        lines.append("异常增幅品牌：无")
    neg_total = sum(v["negative_count"] for v in volume_data)
    neg_ratio = round(neg_total / sum(v["today_vol"] for v in volume_data) * 100, 1) if volume_data else 0
    lines.append(f"负面内容：{neg_total} 条（占比 {neg_ratio}%）")
    high_neg = [v["name"] for v in volume_data if v["negative_count"] > 0 and v["negative_count"] / max(1, v["today_vol"]) > 0.2]
    if high_neg:
        lines.append(f"  ⚠ 高负面占比品牌：{', '.join(high_neg)}，建议人工复核具体原文")
    elif neg_total > 30:
        lines.append("  ⚠ 负面内容绝对值较多，建议人工复核")
    review_flags = [a["name"] for a in anomalies if a["needs_review"]]
    if high_neg or neg_total > 30:
        review_flags.append("高负面风险")
    if review_flags:
        lines.append(f"需人工复核项：{', '.join(review_flags)}")
    else:
        lines.append("需人工复核项：无")
    return "\n".join(lines)


def generate_summary_brief(all_results: List[Dict]) -> str:
    if not all_results:
        return ""
    date_str = datetime.datetime.now().strftime("%m月%d日")
    lines = []
    lines.append(f"【{date_str} 全客户声量总览日报】")
    total_own = 0
    total_comp = 0
    total_neg = 0
    all_anomalies = []
    overtakes = []
    for res in all_results:
        if res.get("error"):
            continue
        vol = res["volume_data"]
        anom = res["anomalies"]
        own = sum(v["today_vol"] for v in vol if not v["is_competitor"])
        comp = sum(v["today_vol"] for v in vol if v["is_competitor"])
        total_own += own
        total_comp += comp
        total_neg += sum(v["negative_count"] for v in vol)
        all_anomalies.extend([{**a, "project": res["project_name"]} for a in anom])
        own_brands = [v for v in vol if not v["is_competitor"]]
        comp_brands = [v for v in vol if v["is_competitor"]]
        if own_brands and comp_brands:
            top_own = max(own_brands, key=lambda x: x["today_vol"])
            top_comp = max(comp_brands, key=lambda x: x["today_vol"])
            if top_comp["today_vol"] > top_own["today_vol"]:
                overtakes.append((res["project_name"], top_comp["name"], top_own["name"], top_comp["today_vol"] - top_own["today_vol"]))
    lines.append(f"客户数：{len(all_results)} 个")
    lines.append(f"全量总声量：自有 {total_own} | 竞品 {total_comp}")
    lines.append(f"全量负面：{total_neg} 条")
    if overtakes:
        lines.append(f"⚠ 竞品超过自有（{len(overtakes)}个项目）：")
        for pname, cname, oname, diff in overtakes:
            lines.append(f"  • [{pname}] {cname} 超过 {oname} {diff}条")
    else:
        lines.append("✓ 所有项目自有品牌声量均领先")
    if all_anomalies:
        lines.append(f"异常增幅品牌（{len(all_anomalies)}个）：")
        all_anomalies.sort(key=lambda x: x["change_pct"], reverse=True)
        for a in all_anomalies[:10]:
            tag = "⚠需复核" if a["needs_review"] else ""
            lines.append(f"  • [{a['project']}] {a['name']} +{a['change_pct']}% — {a['likely_reason']} {tag}")
    review_count = len([a for a in all_anomalies if a["needs_review"]])
    risk_projects = set()
    for res in all_results:
        vol = res.get("volume_data", [])
        neg_total = sum(v["negative_count"] for v in vol)
        if neg_total > 30:
            risk_projects.add(res["project_name"])
    if risk_projects:
        lines.append(f"高负面风险项目：{', '.join(sorted(risk_projects))}")
    lines.append(f"需人工复核项：异常品牌 {review_count} 个" + (f"，高负面 {len(risk_projects)} 个项目" if risk_projects else ""))
    return "\n".join(lines)


def load_projects_file(path: str) -> List[Dict]:
    if not os.path.exists(path):
        return []
    with open(path, "r", encoding="utf-8") as f:
        if path.endswith(".json"):
            data = json.load(f)
        else:
            data = json.load(f)
    projects = []
    if isinstance(data, list):
        for item in data:
            if isinstance(item, dict) and "name" in item:
                projects.append({
                    "name": str(item["name"]).strip(),
                    "brands": [str(b).strip() for b in (item.get("brands") or item.get("own_brands") or []) if str(b).strip()],
                    "competitors": [str(c).strip() for c in (item.get("competitors") or []) if str(c).strip()],
                })
    elif isinstance(data, dict):
        for key, item in data.items():
            if isinstance(item, dict):
                projects.append({
                    "name": str(item.get("name", key)).strip(),
                    "brands": [str(b).strip() for b in (item.get("brands") or item.get("own_brands") or []) if str(b).strip()],
                    "competitors": [str(c).strip() for c in (item.get("competitors") or []) if str(c).strip()],
                })
    return projects


HISTORY_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)), "history")
EXPORT_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)), "exports")


def _ensure_dirs():
    os.makedirs(HISTORY_DIR, exist_ok=True)
    os.makedirs(EXPORT_DIR, exist_ok=True)


def save_inspection_record(batch_id: str, results: List[Dict]):
    _ensure_dirs()
    timestamp = datetime.datetime.now().strftime("%Y%m%d_%H%M%S")
    record = {
        "batch_id": batch_id,
        "timestamp": timestamp,
        "datetime": datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
        "results": results,
    }
    fname = f"inspection_{timestamp}.json"
    fpath = os.path.join(HISTORY_DIR, fname)
    with open(fpath, "w", encoding="utf-8") as f:
        json.dump(record, f, ensure_ascii=False, indent=2)
    return fpath


def list_history(limit: int = 20) -> List[Dict]:
    _ensure_dirs()
    files = sorted(
        [f for f in os.listdir(HISTORY_DIR) if f.startswith("inspection_") and f.endswith(".json")],
        reverse=True
    )
    out = []
    for fname in files[:limit]:
        fpath = os.path.join(HISTORY_DIR, fname)
        try:
            with open(fpath, "r", encoding="utf-8") as f:
                rec = json.load(f)
            out.append({
                "file": fname,
                "path": fpath,
                "timestamp": rec.get("timestamp"),
                "datetime": rec.get("datetime"),
                "batch_id": rec.get("batch_id"),
                "project_count": len(rec.get("results", [])),
            })
        except Exception:
            continue
    return out


def load_history_record(file_name: str) -> Optional[Dict]:
    _ensure_dirs()
    if not os.path.isabs(file_name):
        fpath = os.path.join(HISTORY_DIR, file_name)
    else:
        fpath = file_name
    if not os.path.exists(fpath):
        return None
    with open(fpath, "r", encoding="utf-8") as f:
        return json.load(f)


def export_csv(results: List[Dict], output_path: Optional[str] = None) -> str:
    _ensure_dirs()
    timestamp = datetime.datetime.now().strftime("%Y%m%d_%H%M%S")
    if output_path is None:
        output_path = os.path.join(EXPORT_DIR, f"volume_report_{timestamp}.csv")
    os.makedirs(os.path.dirname(os.path.abspath(output_path)), exist_ok=True)
    with open(output_path, "w", encoding="utf-8-sig", newline="") as f:
        writer = csv.writer(f)
        writer.writerow(["项目", "品牌", "类型", "今日声量", "昨日声量", "环比%", "正面", "中性", "负面", "负面占比%", "最活跃平台", "近8h趋势%"])
        for res in results:
            if res.get("error"):
                continue
            pname = res["project_name"]
            for v in res["volume_data"]:
                total = max(1, v["today_vol"])
                neg_ratio = round(v["negative_count"] / total * 100, 1)
                writer.writerow([
                    pname,
                    v["name"],
                    "竞品" if v["is_competitor"] else "自有",
                    v["today_vol"],
                    v["yesterday_vol"],
                    v["change_pct"],
                    v["positive_count"],
                    v["neutral_count"],
                    v["negative_count"],
                    neg_ratio,
                    v["most_active_platform"],
                    v["recent_trend_pct"],
                ])
    return output_path


def export_topics_csv(project_name: str, brand_name: str, topics: List[Dict], output_path: Optional[str] = None) -> str:
    _ensure_dirs()
    timestamp = datetime.datetime.now().strftime("%Y%m%d_%H%M%S")
    if output_path is None:
        safe_p = "".join(c if c.isalnum() or c in ("-", "_") else "_" for c in project_name)
        safe_b = "".join(c if c.isalnum() or c in ("-", "_") else "_" for c in brand_name)
        output_path = os.path.join(EXPORT_DIR, f"topics_{safe_p}_{safe_b}_{timestamp}.csv")
    os.makedirs(os.path.dirname(os.path.abspath(output_path)), exist_ok=True)
    with open(output_path, "w", encoding="utf-8-sig", newline="") as f:
        writer = csv.writer(f)
        writer.writerow(["话题", "提及量", "正面", "中性", "负面", "情绪主导", "TOP1平台", "TOP1占比%", "TOP2平台", "TOP2占比%", "趋势%", "趋势标签", "样例1", "样例2"])
        for t in topics:
            tp = t["top_platforms"]
            tp1_name, tp1_pct = tp[0] if len(tp) > 0 else ("", 0)
            tp2_name, tp2_pct = tp[1] if len(tp) > 1 else ("", 0)
            sent_label = {"positive": "正面", "neutral": "中性", "negative": "负面"}.get(t["sentiment"], t["sentiment"])
            s1 = t["samples"][0] if len(t["samples"]) > 0 else ""
            s2 = t["samples"][1] if len(t["samples"]) > 1 else ""
            writer.writerow([
                t["topic"], t["mention_count"], t["positive"], t["neutral"], t["negative"],
                sent_label, tp1_name, tp1_pct, tp2_name, tp2_pct,
                t["trend_pct"], t["trend_label"], s1, s2,
            ])
    return output_path


def export_brief_text(brief_text: str, label: str = "brief") -> str:
    _ensure_dirs()
    timestamp = datetime.datetime.now().strftime("%Y%m%d_%H%M%S")
    safe_label = "".join(c if c.isalnum() or c in ("-", "_") else "_" for c in label)
    output_path = os.path.join(EXPORT_DIR, f"{safe_label}_{timestamp}.txt")
    with open(output_path, "w", encoding="utf-8") as f:
        f.write(brief_text)
    return output_path
