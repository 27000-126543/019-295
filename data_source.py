import random
import datetime
from typing import List, Dict, Tuple

PLATFORMS = ["微博", "小红书", "抖音", "B站", "知乎", "微信公众号", "快手"]

SAMPLE_CONTENTS_POSITIVE = [
    "这款产品真的太好用了，强烈推荐给大家！",
    "用了一个月，效果非常明显，会继续回购。",
    "包装很精致，送人也很有面子。",
    "性价比超高，比同价位的其他品牌好太多。",
    "客服态度很好，有问题都能及时解决。",
    "颜值在线，功能也很强大，爱了爱了。",
]

SAMPLE_CONTENTS_NEUTRAL = [
    "刚刚入手，等用过一段时间再来评价。",
    "有人用过这个牌子吗？想听听大家的意见。",
    "今天在专柜试了一下，感觉还可以。",
    "新款和旧款对比，大家觉得哪个更好？",
    "分享一下我做的功课，供参考。",
]

SAMPLE_CONTENTS_NEGATIVE = [
    "踩雷了，完全不是宣传的那样，大家别买。",
    "用了两次就过敏了，联系客服也没人理。",
    "质量太差了，用了一周就坏了，退货也麻烦。",
    "虚假宣传，实际效果和广告差太远。",
    "物流慢得离谱，包装也破了。",
    "价格虚高，完全不值这个价。",
]

TOPIC_KEYWORDS_POOL = [
    "性价比", "颜值", "包装", "物流", "客服", "质量", "效果", "使用体验",
    "回购", "推荐", "对比", "新款", "活动价", "赠品", "成分", "过敏",
    "假货", "售后", "升级", "联名", "代言人", "开箱", "测评", "平替"
]


def _seed_from_project(project_name: str) -> int:
    return hash(project_name) % (2**31)


def generate_brand_volume(project_name: str, brand_words: List[str], competitor_words: List[str]) -> List[Dict]:
    random.seed(_seed_from_project(project_name) + datetime.datetime.now().hour)
    all_brands = brand_words + competitor_words
    result = []
    for brand in all_brands:
        base = random.randint(80, 800)
        change_pct = round(random.uniform(-30, 85), 1)
        yesterday = max(20, int(base / (1 + change_pct / 100)))
        today = base
        negative = random.randint(0, int(base * 0.15))
        platform_counts = {p: random.randint(0, int(base / 3)) for p in PLATFORMS}
        most_active = max(platform_counts, key=platform_counts.get)
        is_competitor = brand in competitor_words
        result.append({
            "name": brand,
            "is_competitor": is_competitor,
            "today_vol": today,
            "yesterday_vol": yesterday,
            "change_pct": change_pct,
            "negative_count": negative,
            "most_active_platform": most_active,
            "platform_counts": platform_counts,
        })
    result.sort(key=lambda x: x["today_vol"], reverse=True)
    return result


def detect_anomalies(volume_data: List[Dict]) -> List[Dict]:
    anomalies = []
    for item in volume_data:
        if item["change_pct"] >= 40:
            reasons = [
                "新品发布/活动上线", "KOL集中投放", "热搜话题带动",
                "促销活动刺激", "竞品事件溢出"
            ]
            random.seed(hash(item["name"]) % (2**31))
            anomalies.append({
                "name": item["name"],
                "change_pct": item["change_pct"],
                "today_vol": item["today_vol"],
                "likely_reason": random.choice(reasons),
                "needs_review": item["change_pct"] >= 65,
            })
    anomalies.sort(key=lambda x: x["change_pct"], reverse=True)
    return anomalies


def generate_topics(project_name: str, brand_name: str, count: int = 10) -> List[Dict]:
    seed = _seed_from_project(project_name) + hash(brand_name)
    random.seed(seed % (2**31))
    topics = random.sample(TOPIC_KEYWORDS_POOL, min(count, len(TOPIC_KEYWORDS_POOL)))
    result = []
    for topic in topics:
        mention_count = random.randint(15, 200)
        sentiment = random.choice(["positive", "neutral", "negative"])
        if sentiment == "positive":
            samples = random.sample(SAMPLE_CONTENTS_POSITIVE, min(2, len(SAMPLE_CONTENTS_POSITIVE)))
        elif sentiment == "negative":
            samples = random.sample(SAMPLE_CONTENTS_NEGATIVE, min(2, len(SAMPLE_CONTENTS_NEGATIVE)))
        else:
            samples = random.sample(SAMPLE_CONTENTS_NEUTRAL, min(2, len(SAMPLE_CONTENTS_NEUTRAL)))
        platform = random.choice(PLATFORMS)
        result.append({
            "topic": topic,
            "mention_count": mention_count,
            "sentiment": sentiment,
            "samples": samples,
            "platform": platform,
        })
    result.sort(key=lambda x: x["mention_count"], reverse=True)
    return result


def generate_daily_brief(project_name: str, brand_words: List[str], volume_data: List[Dict], anomalies: List[Dict]) -> str:
    if not volume_data:
        return "暂无数据"
    own_brands = [v for v in volume_data if not v["is_competitor"]]
    comp_brands = [v for v in volume_data if v["is_competitor"]]
    own_total = sum(v["today_vol"] for v in own_brands)
    comp_total = sum(v["today_vol"] for v in comp_brands)
    top_own = max(own_brands, key=lambda x: x["today_vol"]) if own_brands else None
    top_comp = max(comp_brands, key=lambda x: x["today_vol"]) if comp_brands else None
    lines = []
    lines.append(f"【{project_name}声量日报】")
    lines.append(f"近24h总声量：自有品牌 {own_total} | 竞品 {comp_total}")
    if top_own and top_comp:
        if top_own["today_vol"] >= top_comp["today_vol"]:
            lines.append(f"领先：{top_own['name']}（{top_own['today_vol']}）领先 {top_comp['name']}（{top_comp['today_vol']}）")
        else:
            lines.append(f"注意：{top_comp['name']}（{top_comp['today_vol']}）超过自有 {top_own['name']}（{top_own['today_vol']}）")
    if anomalies:
        lines.append(f"异常增幅品牌：")
        for a in anomalies:
            tag = "⚠需人工复核" if a["needs_review"] else ""
            lines.append(f"  • {a['name']} +{a['change_pct']}%（{a['today_vol']}条）— 疑似{a['likely_reason']} {tag}")
    else:
        lines.append("异常增幅品牌：无")
    neg_total = sum(v["negative_count"] for v in volume_data)
    lines.append(f"负面内容：{neg_total} 条")
    if neg_total > 20:
        lines.append("  ⚠ 负面内容较多，建议人工复核")
    review_flags = [a["name"] for a in anomalies if a["needs_review"]]
    if neg_total > 20:
        review_flags.append("高负面量")
    if review_flags:
        lines.append(f"需人工复核项：{', '.join(review_flags)}")
    else:
        lines.append("需人工复核项：无")
    return "\n".join(lines)
