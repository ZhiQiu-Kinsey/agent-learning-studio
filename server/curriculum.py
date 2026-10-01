"""完整课程规划的唯一数据源；目录登记不代表已实现可执行课程。"""
import json
from pathlib import Path

CATALOG_PATH = Path(__file__).resolve().parents[1] / "curriculum" / "catalog.json"


def load_curriculum():
    return json.loads(CATALOG_PATH.read_text(encoding="utf-8"))


def public_curriculum():
    catalog = load_curriculum()
    for source in catalog["sources"]:
        source.pop("local_path", None)
    return catalog


def roadmap():
    catalog = load_curriculum()
    planned_categories = {lesson["category_id"] for lesson in catalog["lessons"]
                          if lesson["status"] == "planned"}
    return [{"id": category["id"], "title": category["title"],
             "description": category["description"], "available": False}
            for category in catalog["categories"] if category["id"] in planned_categories]
