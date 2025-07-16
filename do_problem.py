#!/usr/bin/env python3
# -*- coding: utf-8 -*-

import subprocess
import threading
import time
from pymongo import MongoClient, UpdateOne

from detect_surrounding import detect_one
from read_katago_info import read_katago_config
from get_temperature import get_temperature
from gtp_engine import GTPEngine
from solver import GoProblemSolver
from config import db_name

def log_diff(publicid, existing_doc, new_values):
    if existing_doc is None:
        print(f"{publicid:>6} 新增")
    else:
        for field in new_values:
            old_value = existing_doc.get(field)
            new_value = new_values[field]
            if old_value != new_value:
                print(f"{publicid:>6} {field:>6} 从 {old_value} 修改为 {new_value}")

def process_batch(q_do_col, publicid_list, new_values_list, katago_ver):
    if not publicid_list:
        return
    # 批量获取已有的文档
    existing_docs = q_do_col.find({'publicid': {'$in': publicid_list}})
    existing_docs_dict = {doc['publicid']: doc for doc in existing_docs}

    bulk_operations = []

    # 处理批次中的每个记录
    for idx, pid in enumerate(publicid_list):
        new_values = new_values_list[idx]
        new_ret = new_values.get('ret')
        existing_doc = existing_docs_dict.get(pid)

        #log_diff(pid, existing_doc, new_values)

        # 准备批量更新操作
        bulk_operations.append(
            UpdateOne(
                {'publicid': pid, 'ver': katago_ver},
                {'$set': new_values},
                upsert=True
            )
        )

    # 执行批量更新
    if bulk_operations:
        q_do_col.bulk_write(bulk_operations)

def already_done(q_do_col, publicid, katago_ver):
    comment_lists = [
        {'publicid':1895, 'comment':'更像对杀题，外面一定能活得黑子和白子'},
        {'publicid':3416, 'comment':'9x8范围更像边上的死活，ratio 4.46, dist 4.4'},
        {'publicid':3620, 'comment':'内部还有2x3一小块 dist 4.2'},
        {'publicid':5073, 'comment':'被包围子有2个子穿过了空挡 ratio 4.2'},
        {'publicid':5531, 'comment':'半个棋盘，边上的对杀'},
        {'publicid':10902, 'comment':'角上对杀'},
        {'publicid':43156, 'comment':'角上对杀'},
        {'publicid':59954, 'comment':'角上死活，有3个空，被包围黑可达所有边界，白虽然ratio有3个达标[0.22, 0.09, 4.75, 0.15]，但是左右dist2个不够[11.7, 0.9, 2.0, 1.2], 原因左右方向白子一条直线的太多，而且中间有空挡'},

        {'publicid':4728, 'comment':'正解是双活。死活权重，会导向开劫，而后万劫不应。普通权重也是先开劫，如果增加2块有2口外气的白盘角曲四作为劫材，komi299，可以得到正解'},
        {'publicid':12683, 'comment':'应该是黑白正常'},
        {'publicid':44390, 'comment':'应该是黑白正常，且对杀'},
        {'publicid':53703, 'comment':'应该是黑白交换'},
        {'publicid':55796, 'comment':'外面包裹的黑子太多影响了关键死活的判断，题目要求先从外面延气，然后进行对杀'},
        {'publicid':65325, 'comment':'正解净杀，内部黑子走中间，使得黑子两边黑白都不入气，只能由黑从外部收起杀白。而死活权重，会导向开劫杀，依赖于对于任何劫材都不回应'},
        {'publicid':74824, 'comment':'死活权重，po高于10可以做对'},
        {'publicid':80989, 'comment':'构造黑棋盘角曲四，即b_threat，强迫黑不开劫，死活权重，可以得到正解，黑净杀白。b_threat：内部黑曲四，白包围在外，且有3口以上外气'},
        {'publicid':84444, 'comment':'白先双活，需构造2个白盘角曲四，如果白劫活需要损失1个盘角曲四'},
        {'publicid':143592, 'comment':'黑净杀，构造1个黑盘角曲四，如果黑劫杀需要损失1个盘角曲四,komi357'},
        {'publicid':178295, 'comment':'同4728'},
        {'publicid':233194, 'comment':'死活权重，对称，50po；普通权重，正常，50po'},
        {'publicid':242451, 'comment':'黑先，增加黑有损失的劫材（白的劫材），迫使黑不导向劫'},
        {'publicid':391513, 'comment':'死活权重，高po可以做对'},
        {'publicid':1, 'comment':''},

    ]
    comment_set = set()
    for i in comment_lists:
        comment_set.add(i.get('publicid'))

    # 跳过记录的题目
    if publicid in comment_set:
        return True

    # 跳过已经做过的题目，ver格式 b28-p10, 死活权重28b，10 playouts
    existing = q_do_col.find_one({'publicid':publicid, 'ver':katago_ver})
    #existing = False # 解除注释，重做全部题目
    if existing:
        #return True # 只要做过就不再做
        if existing.get('ret'):
            #print('已做  ')
            return True
        if existing.get('comment'):
            #print('已备注')
            return True
    return False

def print_bw_info(bw):
    match bw:
        case 10:
            print("黑白正常", end=' ')
        case 11:
            print("黑白劫财", end=' ')
        case 20:
            print("黑白交换", end=' ')
        case 21:
            print("交换劫财", end=' ')
        case _:
            print("未知值")

def attempt_do_one_problem(gtp_engine, solver, bw):
    print_bw_info(bw)
    ret, ans = solver.solve_problem(gtp_engine)
    if not ret:
        bw += 1
        print_bw_info(bw)
        solver.symmetry_fill_black_in_empty_board()
        ret, ans = solver.solve_problem(gtp_engine)
    return ret, ans

def do_one_problem(gtp_engine, q, sleep_ratio):
    b_surrounding = detect_one(q)
    start_time = time.time()

    ret = False
    answer = ''
    bw = 3
    solver = GoProblemSolver(q, keepsize=True)
    if b_surrounding == 1: #黑包围白
        bw = 10
        ret, ans = attempt_do_one_problem(gtp_engine, solver, bw)
    elif b_surrounding == 2:
        solver.swap_black_white()

        bw = 20
        ret, ans = attempt_do_one_problem(gtp_engine, solver, bw)
    else:
        bw = 10
        ret, ans = attempt_do_one_problem(gtp_engine, solver, bw)
        if not ret:
            solver.swap_black_white()
            bw = 20
            ret, ans = attempt_do_one_problem(gtp_engine, solver, bw)

    end_time = time.time()
    duration = end_time-start_time
    print(f'{duration:>5.2f}s')
    time.sleep(sleep_ratio * duration)

    return bw, ret, ans

def do_all_problem():
    # Start GTP engine
    # 普通权重
    katago_cfg_filename = '/Users/zliu/go/katago/gtp_normal_v500.cfg'
    weight_name = 'n28'
    katago_po = read_katago_config(katago_cfg_filename).get('maxPlayouts')
    katago_ver = weight_name + '-p' + katago_po
    engine_command = [
        "/Users/zliu/go/katago/katago-metal-1move", "gtp", 
        "-config", katago_cfg_filename,
        "-model", "/Users/zliu/go/katago/b28.bin.gz",
    ]
    gtp_engine1 = GTPEngine(engine_command)

    # 死活权重
    katago_cfg_filename = '/Users/zliu/go/katago/gtp_killall_do_problem.cfg'
    weight_name = 'b18'
    katago_po = read_katago_config(katago_cfg_filename).get('maxPlayouts')
    katago_ver = weight_name + '-p' + katago_po
    engine_command = [
        "/Users/zliu/go/katago/katago-metal-1move", "gtp", 
        "-config", katago_cfg_filename,
        "-model", "/Users/zliu/go/katago/lifego_" + weight_name + ".bin.gz",
    ]
    gtp_engine = GTPEngine(engine_command)

    # Read problem from MongoDB
    client = MongoClient()
    db = client[db_name]
    q_col = db['q']
    q_do_col = db['q_do']

    batch_size = 10  # 批处理大小
    publicid_list = []
    new_values_list = []
    count = 0
    batch_count = 0

    # 设置题目范围
    docs = q_col.find({'status': 2, 'qtype':'死活题', 'level':'8K+', 'size':19}).sort('publicid', 1)
    #docs = q_col.find({'publicid': {'$in':[3707]}})
    data_list = [
            {
                'publicid': doc.get('publicid'), 
                'level': doc.get('level'), 
                'prepos':doc.get('prepos'), 
                'answers':doc.get('answers'), 
                'blackfirst':doc.get('blackfirst'),
                'size':doc.get('size'),
            } for doc in docs
        ]
    for q in data_list:
        publicid = q.get('publicid')
        level = q.get('level')

        # 跳过一些题目
        if already_done(q_do_col, publicid, katago_ver):
            continue

        print(f"{publicid:>6}", end=' ')
        bw, ret, answer = do_one_problem(gtp_engine1, q, sleep_ratio=0)
        cooling_gpu()
        continue

        bw, ret, answer = do_one_problem(gtp_engine, q, sleep_ratio=0)

        new_values = {
            'bw': bw,
            'ret': ret,
            'level': level, 
            'answer': answer
        }
        publicid_list.append(publicid)
        new_values_list.append(new_values)
        count += 1

        if count % batch_size == 0:
            process_batch(q_do_col, publicid_list, new_values_list, katago_ver)

            # 清空批次数据
            publicid_list = []
            new_values_list = []
            count = 0
            batch_count += 1

            cooling_gpu()

    # 处理剩余不足一个批次的记录
    if publicid_list:
        process_batch(q_do_col, publicid_list, new_values_list, katago_ver)

    # Close GTP engine
    gtp_engine.close()
    gtp_engine1.close()

def cooling_gpu(temp_threshold=60):
    s_time = time.time()
    cpu, gpu, other, cpu_data, gpu_data, other_data = get_temperature()
    first = 1
    while cpu>temp_threshold or gpu>temp_threshold or other>temp_threshold:
        if first:
            print(f'cooling', end=' ', flush=True)
            first = 0
        '''
        if cpu>temp_threshold and cpu_data:
            print(cpu_data, end=' ', flush=True)
        if gpu>temp_threshold and gpu_data:
            print(gpu_data, end=' ', flush=True)
        '''

        sleep_time = 5*max(cpu-temp_threshold, gpu-temp_threshold, other-temp_threshold)
        time.sleep(sleep_time)
        cpu, gpu, other, cpu_data, gpu_data, other_data = get_temperature()
    e_time = time.time()
    duration = e_time - s_time
    print(f'{duration:>5.2f}s')

if __name__ == "__main__":
    do_all_problem()
