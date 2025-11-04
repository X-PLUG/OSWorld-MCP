import os
import json
import argparse
from typing import List


def get_png_minus_one(task_dir: str, sub_result) -> int:
    png_cnt = 0
    for root, _, files in os.walk(task_dir):
        png_cnt += sum(1 for f in files if f.lower().endswith(".png"))

    result = png_cnt - 1 if png_cnt > 0 else 0
    if sub_result:
        result = min(15, result)

    return result


def average_png_minus_one(base_path: str, has_tools_json_path: str, sub_result) -> float:
    with open(has_tools_json_path, 'r', encoding='utf-8') as f:
        has_tools_dict = json.load(f)

    values: List[int] = []
    for app_name, task_list in has_tools_dict.items():
        app_dir_path = os.path.join(base_path, app_name)
        if not os.path.isdir(app_dir_path):
            continue

        for task_name in task_list:
            task_dir_path = os.path.join(app_dir_path, task_name)
            if not os.path.isdir(task_dir_path):
                continue

            values.append(get_png_minus_one(task_dir_path, sub_result))

    if not values:      
        return 0.0
    return sum(values) / len(values)


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="只统计 has_tools.json 中列出的任务 (png 数量 - 1) 平均值"
    )
    parser.add_argument(
        "--base_path", "-b", required=True,
        help="根目录路径（base_path）"
    )
    parser.add_argument(
        "--has_tools_json", "-j", required=True,
        help="has_tools.json 文件路径"
    )
    parser.add_argument('--sub_result', action='store_true')
    return parser.parse_args()


if __name__ == "__main__":
    args = parse_args()
    avg_val = average_png_minus_one(args.base_path, args.has_tools_json, args.sub_result)
    print(f"任务的平均完成步数值: {avg_val:.4f}")
