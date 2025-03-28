#!/usr/bin/env python3
# -*- coding: utf-8 -*-

#主应用类（App） ：
#负责初始化Tkinter主窗口，管理主要的GUI组件和事件循环。
#处理按钮的创建和事件绑定。

import tkinter as tk
from tkinter import ttk

import datetime
import time
from pymongo import MongoClient

from config import db_name
from board import GoBoard
from game import GoGame

class GoApp:
    def __init__(self, root):
        # 替换为您的MongoDB连接字符串
        client = MongoClient()
        db = client[db_name]
        self.ex_collection = db['ex']

        self.root = root
        self.root.title("Go Problem Viewer")

        # 创建主容器
        self.main_frame = tk.Frame(root)
        self.main_frame.pack(fill=tk.BOTH, expand=True)

        # Create canvas
        self.canvas_size = 600
        self.canvas = tk.Canvas(self.main_frame, width=self.canvas_size, height=self.canvas_size)
        self.canvas.grid(row=0, column=0, padx=10, pady=10)

        # Create game board
        self.board = GoBoard(self.canvas, size=19, canvas_size=self.canvas_size, margin=50)
        self.board.draw_board()

        # Create game instance
        self.game = GoGame(self.board)
        self.game.load_problems()

        # 题目列表区域 (右侧)
        self.problem_list_frame = tk.Frame(self.main_frame, width=200)
        self.problem_list_frame.grid(row=0, column=1, sticky=tk.NSEW, padx=10, pady=10)

        # 滚动条
        self.scrollbar = tk.Scrollbar(self.problem_list_frame)
        self.listbox = tk.Listbox(
            self.problem_list_frame,
            yscrollcommand=self.scrollbar.set,
            width=25,
            font=('Arial', 12)
        )
        self.scrollbar.config(command=self.listbox.yview)

        self.scrollbar.pack(side=tk.RIGHT, fill=tk.Y)
        self.listbox.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)
        self.listbox.bind('<<ListboxSelect>>', self.on_problem_selected)

        # 新增：做题情况区域 (最右侧)
        self.status_frame = tk.Frame(self.main_frame, width=200)
        self.status_frame.grid(row=0, column=2, sticky=tk.NSEW, padx=10, pady=10)

        # 初始化统计数据结构
        self.stats = {}

        # 在 status_frame 中添加控件

        # 今日统计
        self.today_label = tk.Label(self.status_frame, text="今日统计", font=('Arial', 14, 'bold'))
        self.today_label.pack(anchor='w')
        self.today_stats_text = tk.Text(self.status_frame, width=30, height=5)
        self.today_stats_text.pack()

        # 昨日统计
        self.yesterday_label = tk.Label(self.status_frame, text="昨日统计", font=('Arial', 14, 'bold'))
        self.yesterday_label.pack(anchor='w')
        self.yesterday_stats_text = tk.Text(self.status_frame, width=30, height=5)
        self.yesterday_stats_text.pack()

        # 历史统计
        self.history_label = tk.Label(self.status_frame, text="历史统计", font=('Arial', 14, 'bold'))
        self.history_label.pack(anchor='w')
        self.history_stats_text = tk.Text(self.status_frame, width=30, height=5)
        self.history_stats_text.pack()

        # 创建一个用于放置Treeview的框架-----
        detail_frame = ttk.Frame(self.status_frame)
        detail_frame.pack(fill='both', expand=True)

        # 定义列
        columns = ('date', 'level', 'status', 'quantity', 'duration', 'score')
        self.tree = ttk.Treeview(detail_frame, columns=columns, show='headings')

        # 设置表头
        self.tree.heading('date', text='日期')
        self.tree.heading('level', text='难度')
        self.tree.heading('status', text='状态')
        self.tree.heading('quantity', text='数量')
        self.tree.heading('duration', text='用时')
        self.tree.heading('score', text='得分')

        # 可选：设置列宽
        for col in columns:
            self.tree.column(col, width=10)

        # 添加垂直滚动条
        scrollbar = ttk.Scrollbar(detail_frame, orient='vertical', command=self.tree.yview)
        self.tree.configure(yscroll=scrollbar.set)
        scrollbar.pack(side='right', fill='y')
        self.tree.pack(side='left', fill='both', expand=True)

        # 初始化时更新统计显示-----
        self.update_stats_display()

        # 创建一个容器 Frame，用于放置 info_label 和 result_label
        self.info_frame = tk.Frame(root)
        self.info_frame.pack(pady=5)

        # Info label
        self.info_label = tk.Label(self.info_frame, text="", fg='black', font=('Arial', 12))
        self.info_label.pack(side='left')

        # Result label
        self.result_label = tk.Label(self.info_frame, text="", font=('Arial', 14, 'bold'))
        self.result_label.pack(side='left')


        # 加载题目列表
        self.populate_problem_list()

        # 创建按钮容器 Frame，使按钮并排放置
        self.button_frame = tk.Frame(root)
        self.button_frame.pack(pady=5)

        # Previous problem button
        self.prev_button = tk.Button(self.button_frame, text="上一题 (Previous Problem)", command=self.prev_problem)
        self.prev_button.pack(side=tk.LEFT, padx=5)

        # Next problem button
        self.next_button = tk.Button(self.button_frame, text="下一题 (Next Problem)", command=self.next_problem)
        self.next_button.pack(side=tk.LEFT, padx=5)

        # Bind the click event
        self.canvas.bind("<Button-1>", self.on_board_click)

        # Load the initial problem
        self.next_problem()

        # 横幅
        self.banner = None
        self.banner_text = None
        self.pending_action_after_banner = None

        # 更新按钮状态
        self.update_buttons_state()

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
        #if self.pending_action_after_banner == 'next_problem':
        #    self.next_problem()
        #elif self.pending_action_after_banner == 'reset_problem':
        #    self.reset_problem()
        self.pending_action_after_banner = None

    def update_lable_text(self, new_result):
        # 替换上次的追加（假设上次追加的内容在最后一个空格之后）
        text = self.info_label.cget("text")
        if text.endswith(" 正确") or text.endswith(" 错误"):
            text = text.rsplit(' ', 1)[0]
        new_text = text + ' ' + new_result
        return new_text

    def show_correct_message(self):
        result_info_text = "正确"
        self.show_message_on_board(result_info_text)
        # 在 info_label 中追加显示“正确”
        #self.info_label.config(text=self.info_label.cget("text") + " 正确")
        #self.pending_action_after_banner = 'next_problem'  # 横幅消失后进入下一题

        self.result_label.config(text=result_info_text, fg='green')

    def show_incorrect_message(self):
        result_info_text = "错误"
        self.show_message_on_board(result_info_text)
        # 在 info_label 中追加显示“错误”
        #self.info_label.config(text=self.info_label.cget("text") + " 错误")
        #self.pending_action_after_banner = 'reset_problem'  # 横幅消失后重置题目

        self.result_label.config(text=result_info_text, fg='red')

    def reset_problem(self):
        # 重新加载当前题目
        self.game.load_problem(index=self.game.current_problem_index)
        self.update_problem_info()
        self.board.clear_board()
        self.board.place_preset_stones(self.game.current_problem.prepos)

    def populate_problem_list(self):
        """填充题目列表"""
        self.listbox.delete(0, tk.END)  # 清空旧列表
        for idx, problem in enumerate(self.game.problems):
            problem_no = problem.publicid
            difficulty = problem.level
            self.listbox.insert(tk.END, f"[{difficulty}] {problem_no}")

    def on_problem_selected(self, event):
        """处理题目选择事件"""
        selection = event.widget.curselection()
        if selection:
            index = selection[0]
            self.game.load_problem(index)
            self.update_problem_info()
            self.board.clear_board()
            self.board.place_preset_stones(self.game.current_problem.prepos)

            # 记录开始时间
            self.problem_start_time = time.time()

            # 更新按钮状态
            self.update_buttons_state()

    def update_problem_info(self):
        """更新题目信息显示"""
        problem_info = {
            'level': self.game.current_problem.level,
            'color': 'Black' if self.game.current_problem.blackfirst else 'White',
            'problem_no': self.game.current_problem.publicid,
            'type': self.game.current_problem.ty
        }
        self.root.title(
            f"Level {problem_info['level']} - {problem_info['type']} - "
            f"{problem_info['color']} first - No.{problem_info['problem_no']}"
        )
        self.info_label.config(
            text=f"Level: {problem_info['level']} | "
            f"{problem_info['color']} plays first | No.{problem_info['problem_no']}"
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
        col = int(round(col_click))
        row = int(round(row_click))

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
            time_taken = time.time() - self.problem_start_time
            self.record_attempt(self.game.current_problem.publicid, correct=False, time_taken=time_taken)
        elif result == 'correct':
            self.show_correct_message()
            time_taken = time.time() - self.problem_start_time
            self.record_attempt(self.game.current_problem.publicid, correct=True, time_taken=time_taken)
        elif result == 'continue':
            # 游戏继续，不需要额外操作
            pass

        # 在记录之后，更新统计显示
        self.update_stats_display()

    def record_attempt(self, problem_id, correct, time_taken):
        # 获取今天的日期字符串
        today = time.strftime("%Y-%m-%d")
        attempt = {
            'problem_id': problem_id,
            'correct': correct,
            'time_taken': time_taken,
        }
        if today not in self.stats:
            self.stats[today] = []
        self.stats[today].append(attempt)

    def update_stats_display(self):
        # 清空文本控件内容
        self.today_stats_text.delete('1.0', tk.END)
        self.yesterday_stats_text.delete('1.0', tk.END)
        self.history_stats_text.delete('1.0', tk.END)

        # 获取今天和昨天的日期
        today = time.strftime("%Y-%m-%d")
        yesterday = (datetime.date.today() - datetime.timedelta(days=1)).strftime("%Y-%m-%d")

        today_attempts = self.stats.get(today, [])
        yesterday_attempts = self.stats.get(yesterday, [])

        # 统计今日数据
        today_total = len(today_attempts)
        today_correct = sum(1 for a in today_attempts if a['correct'])
        today_incorrect = today_total - today_correct
        today_time = sum(a['time_taken'] for a in today_attempts)

        # 显示今日统计
        self.today_stats_text.insert(tk.END, f"做题数量: {today_total}\n")
        self.today_stats_text.insert(tk.END, f"总耗时: {today_time:.1f} 秒\n")
        self.today_stats_text.insert(tk.END, f"正确: {today_correct}\n")
        self.today_stats_text.insert(tk.END, f"错误: {today_incorrect}\n")
        for a in today_attempts:
            correctness = '正确' if a['correct'] else '错误'
            self.today_stats_text.insert(tk.END, f"题目 {a['problem_id']}: {correctness}, 用时: {a['time_taken']:.1f}秒\n")

        # 统计昨日数据
        yesterday_total = len(yesterday_attempts)
        yesterday_correct = sum(1 for a in yesterday_attempts if a['correct'])
        yesterday_incorrect = yesterday_total - yesterday_correct
        yesterday_time = sum(a['time_taken'] for a in yesterday_attempts)

        # 显示昨日统计
        self.yesterday_stats_text.insert(tk.END, f"做题数量: {yesterday_total}\n")
        self.yesterday_stats_text.insert(tk.END, f"总耗时: {yesterday_time:.1f} 秒\n")
        self.yesterday_stats_text.insert(tk.END, f"正确: {yesterday_correct}\n")
        self.yesterday_stats_text.insert(tk.END, f"错误: {yesterday_incorrect}\n")
        for a in yesterday_attempts:
            correctness = '正确' if a['correct'] else '错误'
            self.yesterday_stats_text.insert(tk.END, f"题目 {a['problem_id']}: {correctness}, 用时: {a['time_taken']:.1f}秒\n")

        # 统计历史数据
        total_attempts = sum(len(attempts) for attempts in self.stats.values())
        total_correct = sum(1 for attempts in self.stats.values() for a in attempts if a['correct'])
        total_incorrect = total_attempts - total_correct
        total_time = sum(a['time_taken'] for attempts in self.stats.values() for a in attempts)

        # 显示历史统计
        self.history_stats_text.insert(tk.END, f"总做题数量: {total_attempts}\n")
        self.history_stats_text.insert(tk.END, f"总耗时: {total_time:.1f} 秒\n")
        self.history_stats_text.insert(tk.END, f"正确: {total_correct}\n")
        self.history_stats_text.insert(tk.END, f"错误: {total_incorrect}\n")

        records = self.get_user_records(1)
        self.update_treeview_with_records(records)

    def update_treeview_with_records(self, records):
        # 清空当前数据
        for item in self.tree.get_children():
            self.tree.delete(item)

        # 插入新的数据
        for record in records:
            date = record['begin_time'].split(' ')[0]
            level = record['level']
            quantity = len(record['q'])
            completed = sum(1 for q in record['q'] if q['ret'] in (1, 2))
            correct = sum(1 for q in record['q'] if q['ret'] == 2)
            status = f"{completed}/{quantity}"
            duration = self.calculate_duration(record['begin_time'], record['end_time'])
            score = f"{correct}/{quantity}"

            self.tree.insert('', 'end', values=(date, level, status, quantity, duration, score))

    def calculate_duration(self, start_time_str, end_time_str):
        fmt = '%Y-%m-%d %H:%M:%S'
        start_time = datetime.datetime.strptime(start_time_str, fmt)
        end_time = datetime.datetime.strptime(end_time_str, fmt)
        duration = end_time - start_time
        return str(duration)

    def store_user_data(self, userid, begin_time, end_time, level, q_list):
        document = {
            'userid': userid,
            'begin_time': begin_time,
            'end_time': end_time,
            'level': level,
            'q': q_list  # q_list是题目列表，格式为 [{'min_pp': 'xxx', 'ret': 0}, ...]
        }
        self.ex_collection.insert_one(document)

    def get_user_records(self, userid):
        records = list(self.ex_collection.find({'userid': userid}))
        return records

    def show_error_message(self):
        error_window = tk.Toplevel(self.root)
        error_window.title("Result")
        tk.Label(error_window, text="错误！(Incorrect!)", font=('Arial', 16)).pack(padx=20, pady=20)
        error_window.after(2000, error_window.destroy)

    def next_problem(self):
        if self.game.current_problem_index < len(self.game.problems) - 1:
            # 加载下一题
            self.game.load_problem(index=self.game.current_problem_index + 1)
            self.update_problem_info()
            self.board.clear_board()
            self.board.place_preset_stones(self.game.current_problem.prepos)

            # 记录开始时间
            self.problem_start_time = time.time()

            # 更新列表选择
            self.listbox.selection_clear(0, tk.END)
            self.listbox.selection_set(self.game.current_problem_index)
            self.listbox.activate(self.game.current_problem_index)
            self.listbox.see(self.game.current_problem_index)

            # 更新按钮状态
            self.update_buttons_state()

    def prev_problem(self):
        if self.game.current_problem_index > 0:
            # 加载前一题
            self.game.load_problem(index=self.game.current_problem_index - 1)
            self.update_problem_info()
            self.board.clear_board()
            self.board.place_preset_stones(self.game.current_problem.prepos)

            # 记录开始时间
            self.problem_start_time = time.time()

            # 更新列表选择
            self.listbox.selection_clear(0, tk.END)
            self.listbox.selection_set(self.game.current_problem_index)
            self.listbox.activate(self.game.current_problem_index)
            self.listbox.see(self.game.current_problem_index)

            # 更新按钮状态
            self.update_buttons_state()

    def update_buttons_state(self):
        if self.game.current_problem_index <= 0:
            self.prev_button.config(state=tk.DISABLED)
        else:
            self.prev_button.config(state=tk.NORMAL)

        if self.game.current_problem_index >= len(self.game.problems) - 1:
            self.next_button.config(state=tk.DISABLED)
        else:
            self.next_button.config(state=tk.NORMAL)

if __name__ == "__main__":
    root = tk.Tk()
    app = GoApp(root)
    root.mainloop()
