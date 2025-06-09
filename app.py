#!/usr/bin/env python3
# -*- coding: utf-8 -*-

import tkinter as tk
from tkinter import ttk
import datetime
import time
from pymongo import MongoClient
from pprint import pprint
import random
from config import db_name, full_board_size
from board import GoBoard
from game import GoGame
from tkinter import messagebox
from matchq import canonicalize_positions
import json

#主应用类（App） ：
#负责初始化Tkinter主窗口，管理主要的GUI组件和事件循环。
#处理按钮的创建和事件绑定。
class GoApp:
    def __init__(self, root):
        client = MongoClient()
        self.db = client[db_name]

        self.root = root
        self.root.title("Go Problem Viewer")

        # 创建主容器
        self.main_frame = tk.Frame(root)
        self.main_frame.pack(fill=tk.BOTH, expand=True)

        # Create canvas
        self.canvas_size = 350
        self.canvas = tk.Canvas(self.main_frame, width=self.canvas_size, height=self.canvas_size)
        self.canvas.grid(row=0, column=0, padx=10, pady=10)

        # 创建默认 game board，根据具体的题目再进行绘制
        self.board = GoBoard(self.canvas, size=full_board_size, canvas_size=self.canvas_size, margin=30)

        # Create game instance
        self.game = GoGame(self.board)
        self.game.load_problems({"status": 2, "qtype": "死活题", "level": "9K"})

        # 创建一个容器 Frame，用于放置 info_label 和 result_label
        self.info_frame = tk.Frame(root)
        self.info_frame.pack(pady=2)

        # Info label：显示题目的级别、编号、谁先
        self.info_label = tk.Label(self.info_frame, text="", fg='black', font=('Arial', 18))
        self.info_label.pack(side='left')

        # Result label：显示做题结果
        self.result_label = tk.Label(self.info_frame, text="", font=('Arial', 20, 'bold'))
        self.result_label.pack(side='left')

        # 按钮框架
        self.button_frame = tk.Frame(root)
        self.button_frame.pack(pady=2)

        # 创建“搜索”按钮
        self.search_button = tk.Button(self.button_frame, text="搜索", command=self.on_search_click)
        self.search_button.pack(side='left')

        # Bind the click event
        self.canvas.bind("<Button-1>", self.on_board_click)

        # 横幅
        self.banner = None
        self.banner_text = None
        self.pending_action_after_banner = None

        # Load the initial problem
        self.next_problem(self.board)

    def show_message_on_board(self, message):
        # 创建上方横幅的矩形，高度为棋盘的1/4
        banner_lr_margin = 50
        x0, y0 = banner_lr_margin, self.canvas_size / 4
        x1, y1 = self.canvas_size-banner_lr_margin, self.canvas_size / 8
        self.banner = self.canvas.create_rectangle(
            x0, y0, x1, y1, fill='lightblue'  # 选择温和的颜色
        )
        # 在横幅中心显示消息
        self.banner_text = self.canvas.create_text(
            x1 / 2, y0/2+y1 / 2,
            text=message, font=('Arial', 36), fill='black'  # 调整字体大小和颜色
        )
        # 3秒后移除横幅
        self.root.after(3000, self.remove_banner)

    def remove_banner(self):
        if self.banner:
            self.canvas.delete(self.banner)
            self.canvas.delete(self.banner_text)
            self.banner = None
            self.banner_text = None
        # 根据需要执行后续操作
        if self.pending_action_after_banner == 'next_problem':
            self.next_problem(self.board)
            self.result_label.config(text='')
        elif self.pending_action_after_banner == 'reset_problem':
            self.reset_problem()
            self.result_label.config(text='')
        self.pending_action_after_banner = None

    def show_correct_message(self):
        result_info_text = "正确"
        self.show_message_on_board(result_info_text)
        self.pending_action_after_banner = 'next_problem'  # 横幅消失后进入下一题

        self.result_label.config(text=result_info_text, fg='green')

    def show_incorrect_message(self):
        result_info_text = "错误"
        self.show_message_on_board(result_info_text)
        self.pending_action_after_banner = 'reset_problem'  # 横幅消失后重置题目

        self.result_label.config(text=result_info_text, fg='red')

    def reset_problem(self):
        # 重新加载当前题目
        self.game.load_problem(self.board, index=self.game.current_problem_index)
        self.update_problem_info()

    def update_problem_info(self):
        """更新题目信息显示"""
        problem_info = {
            'level': self.game.current_problem.level,
            'color': '黑' if self.game.current_problem.blackfirst else '白',
            'problem_no': self.game.current_problem.publicid,
            'type': self.game.current_problem.qtype
        }
        self.root.title(
            f"{problem_info['level']} - {problem_info['type']} - "
            f"{problem_info['color']}先 - No.{problem_info['problem_no']}"
        )
        self.info_label.config(
            text=f"{problem_info['level']}  |  "
            f"{problem_info['color']}先  |  No.{problem_info['problem_no']}"
        )

    def on_board_click(self, event):
        x_click = event.x - self.board.margin
        y_click = event.y - self.board.margin
        if (x_click < -self.board.cell_size / 2 or y_click < -self.board.cell_size / 2 or
            x_click > self.canvas_size - self.board.margin or y_click > self.canvas_size - self.board.margin):
            # Click outside the board area
            return

        # Calculate approximate grid position from click
        col_click = x_click / self.board.cell_size
        row_click = y_click / self.board.cell_size
        col = int(round(col_click)) + self.board.min_col
        row = int(round(row_click)) + self.board.min_row

        if not (0 <= row < self.board.size and 0 <= col < self.board.size):
            # Click is outside the board grid
            return

        # Try to make the move
        result = self.game.make_move(row, col)
        if result == 'invalid_move':
            # 可以选择提示无效操作，这里省略
            pass
        elif result == 'incorrect':
            self.show_incorrect_message()
        elif result == 'correct':
            self.show_correct_message()
        elif result == 'continue':
            # 游戏继续
            # 获取全部正解
            next_expected_coords = list(self.game.get_expected_next_coords(self.game.user_moves))

            # 从正解中，随机选择一个最强应对
            random_answer_index = random.randint(0, len(next_expected_coords) - 1)
            coord = next_expected_coords[random_answer_index]
            next_row, next_col = self.board.coord_to_position(coord)

            # 下出对手的最强应对
            result = self.game.make_move(next_row, next_col)
            # 也可能是对手走完后，题目结束
            if result == 'correct':
                self.show_correct_message()
            pass

    def next_problem(self, board):
        ret = self.game.load_problem(board) # 随机加载下一道题目
        self.update_problem_info()
        return
        if self.game.current_problem_index < len(self.game.problems) - 1:
            # 按照顺序加载下一题
            self.game.load_problem(board, index=self.game.current_problem_index + 1) # 顺序加载下一道题目
            self.update_problem_info()

    def on_search_click(self):
        # 创建一个新的顶级窗口
        self.search_window = tk.Toplevel(self.root)
        self.search_window.title("搜索题目")

        # 设置窗口大小
        self.search_window.geometry("400x450")

        # 创建搜索棋盘的画布
        canvas_size = 350
        self.search_canvas = tk.Canvas(self.search_window, width=canvas_size, height=canvas_size)
        self.search_canvas.pack()

        # 创建一个新的GoBoard实例用于搜索棋盘
        self.search_board = GoBoard(self.search_canvas, size=19, canvas_size=canvas_size, margin=30)
        self.search_board.draw_board()

        # 绑定左键和右键点击事件
        self.search_canvas.bind("<Button-1>", self.on_search_board_left_click)
        self.search_canvas.bind("<Button-3>", self.on_search_board_right_click)

        # 创建提示标签
        self.prompt_label = tk.Label(self.search_window, text="左键黑子，右键白子")
        self.prompt_label.pack()

        # 创建匹配数量的标签
        self.match_count_label = tk.Label(self.search_window, text="当前匹配的棋形数：0")
        self.match_count_label.pack()

        # 创建“搜索”和“取消”按钮
        button_frame = tk.Frame(self.search_window)
        button_frame.pack(pady=2)

        search_button = tk.Button(button_frame, text="搜索", command=self.on_search_board_search)
        search_button.pack(side='left', padx=5)

        cancel_button = tk.Button(button_frame, text="取消", command=self.on_search_board_cancel)
        cancel_button.pack(side='left', padx=5)

    # 左键点击事件
    def on_search_board_left_click(self, event):
        self.on_search_board_click(event, left_click=True)

    # 右键点击事件
    def on_search_board_right_click(self, event):
        self.on_search_board_click(event, left_click=False)

    def on_search_board_click(self, event, left_click=True):
        x_click = event.x - self.search_board.margin
        y_click = event.y - self.search_board.margin
        if (x_click < -self.search_board.cell_size / 2 or y_click < -self.search_board.cell_size / 2 or
            x_click > self.search_board.canvas_size - self.search_board.margin or y_click > self.search_board.canvas_size - self.search_board.margin):
            # Click outside the board area
            return

        # Calculate approximate grid position from click
        col_click = x_click / self.search_board.cell_size
        row_click = y_click / self.search_board.cell_size
        col = int(round(col_click))
        row = int(round(row_click))

        if not (0 <= row < self.search_board.size and 0 <= col < self.search_board.size):
            # Click is outside the board grid
            return

        stone = self.search_board.stones[row][col]
        if left_click:
            if stone is None or stone['color'] == 'white':
                # Place black stone
                if stone:
                    # Remove the existing white stone
                    self.search_board.canvas.delete(stone['stone'])
                    self.search_board.stones[row][col] = None
                # Draw black stone
                stone_obj = self.search_board.draw_stone(row, col, 'black')
                self.search_board.stones[row][col] = {'color': 'black', 'stone': stone_obj, 'label': None}
            elif stone['color'] == 'black':
                # Remove black stone
                self.search_board.canvas.delete(stone['stone'])
                self.search_board.stones[row][col] = None
        else:  # Right-click
            if stone is None or stone['color'] == 'black':
                # Place white stone
                if stone:
                    # Remove the existing black stone
                    self.search_board.canvas.delete(stone['stone'])
                    self.search_board.stones[row][col] = None
                # Draw white stone
                stone_obj = self.search_board.draw_stone(row, col, 'white')
                self.search_board.stones[row][col] = {'color': 'white', 'stone': stone_obj, 'label': None}
            elif stone['color'] == 'white':
                # Remove white stone
                self.search_board.canvas.delete(stone['stone'])
                self.search_board.stones[row][col] = None

        # 更新匹配数量
        self.update_matching_count()

    def calc_search_board_min_pp_list(self):
        prepos = {'b': [], 'w': []}
        for row in range(self.search_board.size):
            for col in range(self.search_board.size):
                stone = self.search_board.stones[row][col]
                if stone:
                    coord = self.search_board.position_to_coord(row, col)
                    if stone['color'] == 'black':
                        prepos['b'].append(coord)
                    else:  # 'white'
                        prepos['w'].append(coord)

        # 将坐标列表排序，以便与数据库中的数据进行比较
        prepos['b'].sort()
        prepos['w'].sort()

        stones_key = canonicalize_positions(prepos)
        stones_key_list = [list(item) for item in stones_key]
        return stones_key_list

    def update_matching_count(self):
        collection = self.db['q_search']

        min_pp_list = self.calc_search_board_min_pp_list()
        if len(min_pp_list) == 0:
            return

        stones_list = []
        stones_bw_list = [] #黑白交换
        for entry in min_pp_list:
            stones_list.append(f"{entry[0]}-{entry[1]}-{entry[2]}")
            stones_bw_list.append(f"{'w' if entry[0] == 'b' else 'b'}-{entry[1]}-{entry[2]}")

        query = {'min_pp_list': {'$all': stones_list}}
        count = collection.count_documents(query)
        query_bw = {'min_pp_list': {'$all': stones_bw_list}}
        count_bw = collection.count_documents(query_bw)

        # Update the label
        message = f"当前匹配的棋形数：黑白正常{count} 黑白交换{count_bw}"
        self.match_count_label.config(text=message)

        print(message)
        if count<=5 and count>0:
            print('黑白正常')
            self.print_q_min_pp_list(query)
        if count_bw<=5 and count_bw>0:
            print('黑白交换')
            self.print_q_min_pp_list(query_bw)
        if count>0 or count_bw>0:
            print('--------')

    def print_q_min_pp_list(self, query):
        collection = self.db['q_search']
        col_q = self.db['q']

        docs = collection.find(query)
        for doc in docs:
            ret = col_q.find_one({'min_pp': doc.get('min_pp')})
            print(ret.get('publicid'), ret.get('status'), ret.get('level'), ret.get('qtype'), ret.get('title'), ret.get('_id'), ret.get('min_pp'))

    def on_search_board_search(self):
        min_pp_list = self.calc_search_board_min_pp_list()
        min_pp = json.dumps(min_pp_list, sort_keys=True)

        collection = self.db['q']

        # 执行查询
        doc = collection.find_one({'min_pp': min_pp})
        if doc:
            message = "找到"
            message = message + str(doc.get('_id')) + ' '
            print(doc.get('publicid'), doc.get('status'), doc.get('level'), doc.get('qtype'), doc.get('title'), doc.get('version'))
            self.game.load_problems(criteria={'_id': doc.get('_id')})
            self.next_problem(self.board)
        else:
            message = "找不到"

        # 显示提示信息
        tk.messagebox.showinfo("搜索结果", message, parent=self.search_window)

    def on_search_board_cancel(self):
        self.search_window.destroy()

# 测试程序，快速显示下一题
def timer_callback(app):
    global show_interval;
    app.next_problem(app.board)
    root.after(show_interval, timer_callback, app)

if __name__ == "__main__":
    global show_interval;
    show_interval = 300;
    root = tk.Tk()
    app = GoApp(root)
    #root.after(show_interval, timer_callback, app) # 测试程序，快速显示题目
    root.mainloop()
