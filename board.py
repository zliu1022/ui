#!/usr/bin/env python3
# -*- coding: utf-8 -*-

#棋盘类（GoBoard） ：
#负责绘制棋盘，管理棋盘状态（例如，哪些位置有棋子，棋子的颜色等）。
#处理棋盘相关的操作，如落子、提子、检查棋组、判断气等。
#处理棋盘上的事件（如鼠标点击）。
#
#题目类（Problem） ：
#表示一个围棋题目，包含题目的所有信息，如初始位置、先手、难度、答案等。
#负责从数据库加载题目数据。

from pymongo import MongoClient
from config import db_name

class GoBoard:
    def __init__(self, canvas, size=19, canvas_size=600, margin=50):
        self.canvas = canvas
        self.size = size
        self.canvas_size = canvas_size
        self.margin = margin
        self.cell_size = (canvas_size - 2 * margin) / (size - 1)
        self.board = [[None for _ in range(size)] for _ in range(size)]

    def draw_board(self):
        for i in range(self.size):
            # Vertical lines
            x = self.margin + i * self.cell_size
            self.canvas.create_line(x, self.margin, x, self.canvas_size - self.margin)
            # Horizontal lines
            y = self.margin + i * self.cell_size
            self.canvas.create_line(self.margin, y, self.canvas_size - self.margin, y)

        self._draw_coordinates()

    def _draw_coordinates(self):
        """ 绘制棋盘坐标 """
        columns = 'ABCDEFGHJKLMNOPQRST'
        for i in range(self.size):
            # 左侧坐标
            x_left = self.margin / 2
            y = self.margin + i * self.cell_size
            self.canvas.create_text(x_left, y, text=str(19 - i))
            
            # 右侧坐标
            x_right = self.canvas_size - self.margin / 2
            self.canvas.create_text(x_right, y, text=str(19 - i))
            
            # 顶部坐标
            x = self.margin + i * self.cell_size
            y_top = self.margin / 2
            self.canvas.create_text(x, y_top, text=columns[i])
            
            # 底部坐标
            y_bottom = self.canvas_size - self.margin / 2
            self.canvas.create_text(x, y_bottom, text=columns[i])

    def coord_to_position(self, coord):
        columns = 'abcdefghijklmnopqrst'
        col_letter, row_letter = coord[1], coord[0]
        col = columns.index(col_letter)
        row = columns.index(row_letter)
        row = self.size - row - 1  # Adjust row index to match the display
        return row, col

    def position_to_coord(self, row, col):
        columns = 'abcdefghijklmnopqrst'
        row_letter = columns[self.size - row - 1]
        col_letter = columns[col]
        return col_letter + row_letter

    def draw_stone(self, row, col, color):
        x = self.margin + col * self.cell_size
        y = self.margin + row * self.cell_size
        r = self.cell_size / 2 - 2
        stone = self.canvas.create_oval(x - r, y - r, x + r, y + r, fill=color)
        return stone

    def draw_hint(self, coord):
        row, col = self.coord_to_position(coord)
        x = self.margin + col * self.cell_size
        y = self.margin + row * self.cell_size
        r = self.cell_size / 2 - 2
        hint = self.canvas.create_oval(x - r, y - r, x + r, y + r, outline='red', width=2)
        return hint

    def clear_board(self):
        for row in range(self.size):
            for col in range(self.size):
                if self.board[row][col] is not None:
                    self.canvas.delete(self.board[row][col]['stone'])
                    if self.board[row][col]['label'] is not None:
                        self.canvas.delete(self.board[row][col]['label'])
                    self.board[row][col] = None

    def place_preset_stones(self, prepos):
        for color, positions in prepos.items():
            for coord in positions:
                row, col = self.coord_to_position(coord)
                x = self.margin + col * self.cell_size
                y = self.margin + row * self.cell_size
                r = self.cell_size / 2 - 2
                stone_color = 'black' if color == 'b' else 'white'
                stone = self.canvas.create_oval(x - r, y - r, x + r, y + r, fill=stone_color, tags='preset_stone')
                self.board[row][col] = {'color': stone_color, 'stone': stone, 'label': None}

    def get_actual_height(self):
        """返回包含坐标标签的实际高度"""
        return self.canvas_size + self.margin  # 棋盘高度 + 坐标标签空间

class GoProblem:
    def __init__(self, problem_data=None):
        self.problem_data = problem_data or {}
        self.prepos = self.problem_data.get('prepos', {})
        self.blackfirst = self.problem_data.get('blackfirst', True)
        self.level = self.problem_data.get('level', 'N/A')
        self.answers = self.problem_data.get('answers', [])
        self.publicid = self.problem_data.get('publicid', 'N/A')
        self.ty = self.problem_data.get('qtype', 'N/A')

    @staticmethod
    def load_problems_from_db(criteria):
        client = MongoClient('mongodb://localhost:27017/')
        db = client[db_name]
        collection = db['q']
        problems_cursor = collection.find(criteria)
        problems_data = list(problems_cursor)
        problems = [GoProblem(problem_data) for problem_data in problems_data]
        return problems
