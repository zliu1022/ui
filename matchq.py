#!/usr/bin/env python3
# -*- coding: utf-8 -*-

from pymongo import MongoClient
from config import db_name

'''
读取mongodb，x库，q表，里面存放的是围棋死活题
每个document的格式如下，其中 no字段是题目编号，
其中的 prepos字段就是死活题里黑子、白子的初始摆放位置
里面的具体数值，就是a映射成1，b映射成2，而且不必跳过 i

编程，读取指定 no的document，获取初始位置，
功能函数1：对初始位置进行生成旋转对称，生成8种结果，可以采用方便的内部数据结构进行存储
功能函数2：输入8种旋转对称位置，找到最靠近棋盘左上角（x横轴19，y纵轴1）的初始位置，称为“左上角初始位置”，返回这个初始位置，可以是方便的内部数据结构，或者方便进行“功能函数4”比较的结构
功能函数3：把最靠近棋盘左上角的，方便的内部数据结构，转换成 prepos字段的json格式，这是个独立的功能
功能函数4：对于指定 no的document，得到“左上角初始位置”，和其他document的左上角初始位置，进行比较：如果所有棋子的颜色和位置都相同，表示完全一样
功能函数5：对于全部document，每一个no，都调用功能函数4，得到全部文档的匹配结果，如果已经出现一样，则跳过，同时需要考虑有多个题目完全一样的情况，打印结果

每个document的格式如下：
{
    "no": "1",
    "prepos": {
        "b": [
            "rb",
            "rc",
            "qd",
            "pd",
            "oc",
            "nc",
            "lc",
            "ra"
        ],
        "w": [
            "sc",
            "rd",
            "re",
            "qf",
            "qc",
            "pc",
            "qb",
            "qa",
            "ob"
        ]
    },
}
'''

# Function to map letters to numbers and vice versa
def letter_to_number(letter):
    return ord(letter) - ord('a') + 1

def number_to_letter(number):
    return chr(ord('a') + number - 1)

# Transformation functions
N = 19

def identity(x, y):
    return x, y

def rotate90(x, y):
    return N + 1 - y, x

def rotate180(x, y):
    return N + 1 - x, N + 1 - y

def rotate270(x, y):
    return y, N + 1 - x

def reflect_x(x, y):
    return x, N + 1 - y

def reflect_y(x, y):
    return N + 1 - x, y

def reflect_main_diagonal(x, y):
    return y, x

def reflect_anti_diagonal(x, y):
    return N + 1 - y, N + 1 - x

transformations = [identity, rotate90, rotate180, rotate270,
                   reflect_x, reflect_y, reflect_main_diagonal, reflect_anti_diagonal]

# Function to parse prepos into list of stones
def parse_prepos(prepos):
    stones = []
    for color in prepos:
        for pos_str in prepos[color]:
            x = letter_to_number(pos_str[0])
            y = letter_to_number(pos_str[1])
            stones.append((color, x, y))
    return stones

# Function to apply a transformation to a list of stones
def apply_transformation(stones, transformation):
    return [(color, *transformation(x, y)) for color, x, y in stones]

'''
元组 (s[0], s[1], s[2]): 棋子颜色，'b' 或 'w', x, y
使用 sorted() 函数对棋子列表进行排序,找到最小的那个,假设第一个列表被认为是最小的
“左上”位置并不一定是真正地在棋盘的左上角，而是指在比较规则下，排序后最小的那个棋子排列

列表比较规则： Python中，列表可以直接比较。规则：
1. 首先比较第一个元素，如果相等，继续比较下一个元素，以此类推。
2. 对于元素是元组的情况，也是按元组的比较规则逐级比较
确保对任意一个棋局，得到一个唯一的标准形式
'''
# Function to select the left-top initial position among all transformations
def select_left_top_position(stones_list):
    # Sort stones within each transformation
    sorted_stones_list = []
    for stones in stones_list:
        sorted_stones = sorted(stones, key=lambda s: (s[0], s[1], s[2]))
        sorted_stones_list.append(sorted_stones)
    # Select the minimal one
    min_stones = min(sorted_stones_list)
    return min_stones

# Function to convert stones to prepos format
def stones_to_prepos(stones):
    prepos = {'b': [], 'w': []}
    for color, x, y in stones:
        pos_str = number_to_letter(x) + number_to_letter(y)
        prepos[color].append(pos_str)
    return prepos

'''
唯一性说明，快速检索说明：
哈希化处理： 将排序后的 min_stones 转换为一个元组，作为字典的键，便于快速查找和比较
当棋局具有对称性时，经过某些变换（旋转和反射），棋局可能映射到自身。这意味着对于一些变换，变换后的棋子布局与原始布局相同
即使有多个变换后的棋子列表相同（因为棋局的对称性导致某些变换后布局相同），使用 min() 函数时，这些相同的列表实际上视为一个
因此在一组列表中，无论有多少个相同的列表，min() 函数的结果都是唯一的

为什么不采用更短的字符串
避免了字符串转换的开销，直接利用 Python 内置的序列比较功能
对于大规模数据，可能在性能上与字符串比较相近
直接比较列表或元组可能会比字符串比较稍快，因为避免了字符串的创建和内存分配
字符串表示更简洁，尤其在需要将棋局状态保存为文件或进行网络传输时

tuple(left_top_stones)
把列表("[]"包裹)，转换为3元组的元组("()"包裹)
元组可以作为字典的键，因为元组是可哈希的
'''
def canonicalize_positions(prepos):
    # 这里实现了对棋局的标准化处理，返回 stones_key
    # 您之前提供的代码或逻辑应该放在这里
    # 返回值应该是一个元组的元组，形式类似于：
    # (('B', 0, 0), ('W', 1, 2), ('B', 2, 1))
    stones = parse_prepos(prepos)

    transformed_stones_list = []
    for transformation in transformations:
        transformed_stones = apply_transformation(stones, transformation)
        transformed_stones_list.append(transformed_stones)

    left_top_stones = select_left_top_position(transformed_stones_list)

    # Convert stones to a hashable key
    stones_key = tuple(left_top_stones)
    return stones_key

def process_all_documents():
    client = MongoClient('mongodb://localhost:27017/')
    db = client[db_name]  # Replace with your database name
    collection = db['q']  # Replace with your collection name

    documents = list(collection.find({}))

    duplicates = {}  # Key: tuple of stones, Value: list of 'no's
    unique_nos = set()

    for doc in documents:
        no = doc['_id']
        url_no = doc['url_no']
        prepos = doc.get('prepos')
        if not prepos:
            continue
        stones = parse_prepos(prepos)

        stones_key = canonicalize_positions(prepos)

        if stones_key in duplicates:
            duplicates[stones_key].append(no)
        else:
            duplicates[stones_key] = [no]
            unique_nos.add(no)

    # Output the results
    for stones_key, nos in duplicates.items():
        if len(nos) > 1:
            print(f"Positions for nos {nos} are identical.")

if __name__ == "__main__":
    process_all_documents()
