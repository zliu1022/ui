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
from board import GoProblem, GoBoard
from game import GoGame
from tkinter import messagebox, ttk
import json
from matchq import transformations, apply_transformation, parse_prepos

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
        
        # 搜索功能：动态匹配到的Top题目
        self.matching_problems = []

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
        # 创建一个新的顶级窗口:搜索输入
        self.search_window = tk.Toplevel(self.root)
        self.search_window.title("搜索题目")

        # 在设置完搜索窗口的内容后，更新其布局以获取正确的尺寸
        self.search_window.update_idletasks()

        # 获取搜索窗口的位置和尺寸
        x = self.search_window.winfo_x()
        y = self.search_window.winfo_y()
        width = self.search_window.winfo_width()
        height = self.search_window.winfo_height()

        # 设置窗口大小
        self.search_window.geometry("400x450+0+100")

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

        # 创建“取消”按钮
        button_frame = tk.Frame(self.search_window)
        button_frame.pack(pady=2)

        cancel_button = tk.Button(button_frame, text="取消", command=self.on_search_board_cancel)
        cancel_button.pack(side='left', padx=5)

        # 创建一个新的顶级窗口:搜索结果
        self.search_result_window = tk.Toplevel(self.search_window)
        self.search_result_window.title("搜索结果")

        # Set the search result window as transient to search_window
        self.search_result_window.transient(self.search_window)

        # 设置搜索结果窗口的位置，使其紧贴在搜索窗口的右边
        # 设置每行显示的列数
        self.search_result_columns = 4
        result_width = self.search_result_columns * 230
        self.search_result_window.geometry(f"{result_width}x1000+{int(x+1.9*width)}+{y}")

        # 创建显示匹配题目的框架，包含滚动条
        self.matches_frame = tk.Frame(self.search_result_window)
        self.matches_frame.pack(side='right', fill=tk.BOTH, expand=True)

        # 创建滚动条
        self.matches_canvas = tk.Canvas(self.matches_frame)
        scrollbar = tk.Scrollbar(self.matches_frame, orient="vertical", command=self.matches_canvas.yview)
        self.scrollable_frame = tk.Frame(self.matches_canvas, bg='white')

        self.scrollable_frame.bind("<Configure>", lambda e: self.matches_canvas.configure(scrollregion=self.matches_canvas.bbox("all")))

        self.matches_canvas.create_window((0, 0), window=self.scrollable_frame, anchor="nw")
        self.matches_canvas.configure(yscrollcommand=scrollbar.set)

        self.matches_canvas.pack(side="left", fill="both", expand=True)
        scrollbar.pack(side="right", fill="y")

        # Force focus back to search_window after both windows have been created
        self.search_window.lift()
        self.search_window.focus_force()

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

        # 动态匹配，打印当前min_pp
        stones = parse_prepos(prepos)
        stones_key_list = [list(item) for item in tuple(stones)]
        print(json.dumps(stones_key_list, sort_keys=True))

        configurations = []

        for transform in transformations:
            # 原始颜色
            transformed_stones = apply_transformation(stones, transform)
            stones_list = [f"{color}-{x}-{y}" for color, x, y in transformed_stones]
            configurations.append(stones_list)

            # 黑白交换
            transformed_stones_bw = [('w' if color == 'b' else 'b', x, y) for color, x, y in transformed_stones]
            stones_list_bw = [f"{color}-{x}-{y}" for color, x, y in transformed_stones_bw]
            configurations.append(stones_list_bw)

        return configurations

    def update_matching_count(self):
        collection = self.db['q_search']
        col_q = self.db['q']

        configurations = self.calc_search_board_min_pp_list()
        if not configurations:
            return 

        #匹配数量
        start_time = time.time()
        # 构建 $or 查询条件
        or_clauses = []
        for stones_list in configurations:
            clause = {'min_pp_list': {'$all': stones_list}}
            or_clauses.append(clause)
        query = {'$or': or_clauses}

        # 执行查询，获取匹配的文档, 按照 min_pp 字符串长度排序，最短的在前, 保留前30个匹配结果
        cursor = collection.find(query)

        # 存储已匹配的 min_pp，避免重复
        matched_min_pp = set()
        matching_docs = []

        for doc in cursor:
            min_pp = doc.get('min_pp')
            if min_pp not in matched_min_pp:
                matched_min_pp.add(min_pp)
                matching_docs.append(doc)

        # Update the label
        total_matches = len(matching_docs)
        message = f"当前匹配的棋形数：{total_matches}"
        self.match_count_label.config(text=message)

        matching_docs.sort(key=lambda doc: len(doc.get('min_pp', '')))
        top_matches = matching_docs[:30]
        end_time = time.time()
        print(f'$all {end_time-start_time:>5.2f}s {total_matches:>6}', end=' ')

        # 匹配Top
        start_time = time.time()
        # 存储匹配题目的详细信息，供显示使用
        self.matching_problems = []
        for doc in top_matches:
            problem = col_q.find_one({'status':2, 'min_pp': doc.get('min_pp')})
            if problem:
                self.matching_problems.append(problem)
        end_time = time.time()
        print(f'$match {end_time-start_time:>5.2f}s {len(self.matching_problems):>6}')

        # 匹配到的数量小于3个，打印min_pp
        if len(self.matching_problems)>0 and len(self.matching_problems)<=3:
            for p in self.matching_problems:
                print(p.get('publicid'), p.get('min_pp'))

        # Update the matching problems display
        self.update_matching_display()

    def on_search_board_cancel(self):
        self.search_window.destroy()

    def update_matching_display(self):
        # 清空之前的显示内容
        for widget in self.scrollable_frame.winfo_children():
            widget.destroy()

        canvas_size = int(self.search_board.canvas_size / 2)  # 图形尺寸为搜索棋盘的一半

        for index, problem in enumerate(self.matching_problems):
            row = index // self.search_result_columns
            col = index % self.search_result_columns

            # 创建一个容器 Frame，包含棋盘和信息
            problem_frame = tk.Frame(self.scrollable_frame, bg='white')
            problem_frame.grid(row=row, column=col, padx=5, pady=5)

            # 创建棋盘画布
            problem_canvas = tk.Canvas(problem_frame, width=canvas_size, height=canvas_size, bg='white')
            problem_canvas.pack()

            # 创建小尺寸的 GoBoard 和 GoGame 实例
            mini_board = GoBoard(problem_canvas, size=problem.get('size', 19), canvas_size=canvas_size, margin=15)
            mini_game = GoGame(mini_board)

            # 加载题目到棋盘中
            mini_game.current_problem = GoProblem(problem)
            mini_game.reset_game()
            mini_game.current_color = 'black' if mini_game.current_problem.blackfirst else 'white'

            # 调整棋盘尺寸，显示局部棋盘
            if mini_game.current_problem.size == full_board_size:
                min_row, max_row, min_col, max_col = mini_game.current_problem.get_board_extent()
                view_distance = 2
                min_row = max(0, min_row - view_distance)
                min_col = max(0, min_col - view_distance)
                max_row = min(mini_board.size - 1, max_row + view_distance)
                max_col = min(mini_board.size - 1, max_col + view_distance)
                mini_board.draw_board(min_row=min_row, max_row=max_row, min_col=min_col, max_col=max_col)
            else:
                mini_board.draw_board()

            # 摆放棋子
            mini_board.place_preset_stones(mini_game.current_problem.prepos)

            # 显示题目信息
            self.display_problem_info(mini_game, problem_frame)

            # 绑定点击事件，点击后在主棋盘中加载该题目
            problem_canvas.bind("<Button-1>", lambda e, idx=index: self.load_problem_from_match(idx))

    def display_problem_info(self, mini_problem, problem_frame):
        status_dict = { 0: "审核", 1: "取消", 2: "入库" }
        status_str = status_dict.get(mini_problem.current_problem.status, "未知")
        info_text_before_status = f"Q-{mini_problem.current_problem.publicid}\n{mini_problem.current_problem.qtype} {mini_problem.current_problem.level} "

        # Create a Text widget
        info_text_widget = tk.Text(problem_frame, height=2, width=30, bd=0, relief='flat')
        info_text_widget.pack()

        # Insert the text before status_str
        info_text_widget.insert('1.0', info_text_before_status)

        # Record the starting index of status_str
        start_index = info_text_widget.index('insert')

        # Insert status_str
        info_text_widget.insert('insert', status_str)

        # Record the ending index of status_str
        end_index = info_text_widget.index('insert')

        # Apply styles based on status_str
        if status_str == "取消":
            # Apply red color
            info_text_widget.tag_add('status', start_index, end_index)
            info_text_widget.tag_config('status', foreground='red')
        elif status_str == "入库":
            # Apply green color and bold font
            info_text_widget.tag_add('status', start_index, end_index)
            info_text_widget.tag_config('status', foreground='green', font=('TkDefaultFont', 9, 'bold'))
        else:  # "审核" or other
            # Apply black color
            info_text_widget.tag_add('status', start_index, end_index)
            info_text_widget.tag_config('status', foreground='black')

        # Disable editing
        info_text_widget.config(state='disabled')

    def load_problem_from_match(self, index):
        selected_problem = self.matching_problems[index]
        # 加载选中的题目
        self.game.load_problems(criteria={'_id': selected_problem.get('_id')})
        self.next_problem(self.board)
        # 关闭搜索窗口
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
