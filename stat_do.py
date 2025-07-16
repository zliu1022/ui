#!/usr/bin/env python3
# -*- coding: utf-8 -*-

from config import db_name

from pymongo import MongoClient
from collections import defaultdict
import re
from prettytable import PrettyTable
import sys

# 定义ver的排序规则（提取p后的数字）
def ver_key(ver_str):
    match = re.search(r'p(\d+)$', ver_str)
    return int(match.group(1)) if match else 0

def analyze_ret_pattern(ver_stats):
    # 4. 分析不同ver的ret规律
    print("\n不同ver的ret规律分析:")
    ver_ratio = {}
    for ver, stats in sorted(ver_stats.items(), key=lambda x: ver_key(x[0])):
        ratio = stats['true_count'] / stats['total'] if stats['total'] > 0 else 0
        ver_ratio[ver] = ratio
        print(f"- {ver:>8}: 总数={stats['total']:>4}, True={stats['true_count']:>4}, 比例={ratio:.2%}")

    # 检查总体是否满足"p值越大，True比例越高"
    versions = sorted(ver_ratio.keys(), key=ver_key)
    ratios = [ver_ratio[v] for v in versions]
    is_increasing = all(ratios[i] <= ratios[i+1] for i in range(len(ratios)-1))

    print("\n总体规律验证结果:")
    if is_increasing:
        print("✅ 总体符合规律: p值越大，ret=True的比例越高")
        for i in range(len(versions)-1):
            print(f"  {versions[i]} ({ratios[i]:.2%}) → {versions[i+1]} ({ratios[i+1]:.2%})")
    else:
        print("❌ 总体不符合规律: p值增大但比例未持续升高")

def print_non_conforming_ids(non_conforming_ids):
    # 5. 打印不符合规律的publicid
    if non_conforming_ids:
        print("\n4. 不符合规律的publicid详情:")
        non_conform_table = PrettyTable()
        non_conform_table.field_names = ["publicid", "ret值序列"]

        for publicid, ret_values in non_conforming_ids:
            # 将布尔值转换为更易读的字符串
            readable_values = ['T    ' if v is True else 'False' for v in ret_values]
            non_conform_table.add_row([publicid, " → ".join(readable_values)])

        print("以下publicid不符合'p值越大，ret=True比例越高'的规律:")
        print("（即当某个版本出现True后，后续版本又出现False）")
        print(non_conform_table)

        print(f"\n总计 {len(non_conforming_ids)} 个publicid不符合规律")
    else:
        print("\n4. 所有publicid都符合'p值越大，ret=True比例越高'的规律")

def stat_q_do(weight_name):
    client = MongoClient('mongodb://localhost:27017/')
    db = client[db_name]  # 替换为实际数据库名
    collection = db['q_do']

    # 1. 按publicid分组，收集不同ver的ret值
    publicid_data = defaultdict(dict)
    ver_stats = defaultdict(lambda: {'total': 0, 'true_count': 0})

    # 查询所有文档
    for doc in collection.find():
        publicid = doc['publicid']
        ver = doc.get('ver', '')
        ret = doc.get('ret')  # 使用get避免KeyError

        if ret is None:
            continue  # 跳过没有ret字段的文档

        if ver.find(weight_name)!=0:
            continue

        # 存储publicid对应的ver-ret数据
        publicid_data[publicid][ver] = ret

        # 统计每个ver的总数和ret=True的数量
        ver_stats[ver]['total'] += 1
        if ret:
            ver_stats[ver]['true_count'] += 1

    return publicid_data, ver_stats

def stat_do(weight_name):
    publicid_data, ver_stats = stat_q_do(weight_name)

    # 创建统计表格
    table = PrettyTable()
    ver_columns = sorted(set(ver for data in publicid_data.values() for ver in data), key=ver_key)
    table.field_names = ["publicid", *ver_columns, "ver_count"]

    # 输出每个publicid的不同ver数量
    print("\n每个publicid的不同ver数量:")
    for publicid, data in publicid_data.items():
        print(f"publicid {publicid}: {len(data)} 个不同版本")
        break

    non_conforming_ids = [] # 存储不符合规律的publicid
    for publicid, ver_ret in publicid_data.items():
        fail = False # 一个也没有失败过
        row = [publicid]
        ret_values = []

        if ver_ret.get('', 'N/A') != 'N/A':
            continue

        # 按顺序添加每个ver的ret值
        for ver in ver_columns:
            ret_val = ver_ret.get(ver, 'N/A')
            row.append(ret_val)
            if ret_val != 'N/A':
                ret_values.append(ret_val)
            if ret_val != 'N/A' and ret_val == False:
                fail = True

        # 添加不同ver的数量
        ver_count = len(ver_ret)
        row.append(ver_count)
        if not fail:
            table.add_row(row)

        # 检查是否符合规律
        if len(ret_values) < 2:
            continue  # 少于2个版本无法比较

        # 检查是否符合"p值越大，ret=True比例越高"的规律
        # 允许的情况: T,T,T / F,T,T / F,F,T / F,F,F
        # 不允许的情况: T,F,* / F,T,F / T,T,F / F,F,T,F 等
        has_true = False
        non_conforming = False

        for i, ret_val in enumerate(ret_values):
            if ret_val is True:
                has_true = True
            elif ret_val is False and has_true:
                # 如果之前出现过True，但现在出现False，则不符合规律
                non_conforming = True
                break

        if non_conforming:
            non_conforming_ids.append((publicid, ret_values))

    print("每个publicid的不同ver统计:")
    print(table)
    quit()

    analyze_ret_pattern(ver_stats)
    #print_non_conforming_ids(non_conforming_ids)

if __name__ == "__main__":
    weight_name = 'b28'
    if len(sys.argv)==2:
        weight_name = sys.argv[1]
    stat_do(weight_name)
